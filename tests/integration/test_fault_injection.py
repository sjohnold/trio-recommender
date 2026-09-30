import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
from trio.contracts import Mode
from trio.inference.protocol import ChunkKind
from trio.inference.resilience import ResilienceRequest, TimeoutLimits, run_with_limits
from trio.orchestrator.coordinator import Coordinator, RoundCandidate, RoundEvent
from trio.orchestrator.events import UtteranceState
from trio.state.validation import StateValidationError, fallback_state, validate_state
import trio.orchestrator.coordinator as coordinator_module


def collect(iterator):
    async def run():
        return [item async for item in iterator]
    return asyncio.run(run())


def test_invalid_state_json_uses_explicit_unknown_safe_fallback():
    with pytest.raises(StateValidationError):
        validate_state("{invalid")
    previous = fallback_state([], None)
    result = fallback_state([{"speaker": "user", "stance": "disagree"}], previous)
    assert result.source == "fallback"
    assert result.tension == previous.tension
    assert result.user_signal["stance"] == "disagree"
    assert result.confidence <= .4


def test_ollama_503_and_disconnect_preserve_partial_with_one_start():
    calls = 0
    async def start_503():
        nonlocal calls
        calls += 1
        async def stream():
            yield NS(kind=ChunkKind.CONTENT, text="saved ")
            yield NS(kind=ChunkKind.ERROR, text="HTTP 503", error_code="http_error")
        return stream()
    result = asyncio.run(run_with_limits(
        ResilienceRequest("r503", start_503), TimeoutLimits(.1, .1, .2)
    ))
    assert (result.error_code, result.text, calls) == (
        "ollama_overloaded", "saved ", 1)

    async def disconnect():
        async def stream():
            yield NS(kind=ChunkKind.CONTENT, text="partial")
        return stream()
    result = asyncio.run(run_with_limits(
        ResilienceRequest("disconnect", disconnect), TimeoutLimits(.1, .1, .2)
    ))
    assert (result.error_code, result.text) == ("incomplete_stream", "partial")


class Router:
    def resolve(self, mode, role):
        return NS(name="local-model")


class Backend:
    def __init__(self, code=None, delay=0):
        self.code, self.delay, self.starts, self.unloads = code, delay, 0, 0
    async def stream(self, request):
        self.starts += 1
        yield NS(kind=ChunkKind.CONTENT, text="durable ")
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.code:
            yield NS(kind=ChunkKind.ERROR, text="", error_code=self.code)
        else:
            yield NS(kind=ChunkKind.DONE, text="", error_code=None)


def round_events(backend, timeout=.1):
    role = NS(value="pragmatist")
    original_score = coordinator_module.score_candidate
    original_context = coordinator_module.build_context
    try:
        coordinator_module.score_candidate = lambda *_: NS(
            total=1, role=role, should_speak=True)
        coordinator_module.build_context = lambda *_: NS(
            parts=(NS(kind="unconditional", text="local rules"),))
        candidate = RoundCandidate(
            None, None, None, NS(event="local event"), NS())
        event = RoundEvent("session", 0, Mode.A, (candidate,), 100)
        return collect(Coordinator(Router(), backend, timeout).handle(event))
    finally:
        coordinator_module.score_candidate = original_score
        coordinator_module.build_context = original_context


@pytest.mark.parametrize(
    ("code", "state"),
    [
        ("user_interrupt", UtteranceState.INTERRUPTED),
        ("orchestrator_interrupt", UtteranceState.INTERRUPTED),
        ("missing_model", UtteranceState.FAILED),
    ],
)
def test_interrupts_and_missing_model_are_terminal_and_preserve_text(code, state):
    backend = Backend(code)
    terminal = round_events(backend)[-1]
    assert (terminal.state, terminal.reason, terminal.text) == (
        state, code, "durable ")
    assert (backend.starts, backend.unloads) == (1, 0)


def test_hard_timeout_is_terminal_without_hang_or_fallback():
    backend = Backend(delay=.05)
    terminal = round_events(backend, timeout=.005)[-1]
    assert (terminal.state, terminal.reason, terminal.text) == (
        UtteranceState.TIMED_OUT, "hard_timeout", "durable ")
    assert (backend.starts, backend.unloads) == (1, 0)
