import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "src"))

from trio.inference.cancellation import CancellationRegistry
from trio.inference.protocol import ChunkKind, TokenChunk
from trio.orchestrator.events import UtteranceLifecycle, UtteranceState
from trio.orchestrator.user_input import (
    ActiveTurn,
    UserEvent,
    handle_user_event,
)


async def streaming(started, closed):
    try:
        yield TokenChunk("request-1", ChunkKind.CONTENT, "first ")
        yield TokenChunk("request-1", ChunkKind.CONTENT, "second")
        started.set()
        await asyncio.Event().wait()
    finally:
        closed.set()


async def consume(stream):
    async for _ in stream:
        pass


def active_lifecycle():
    return UtteranceLifecycle(
        "session-1", "utterance-1", UtteranceState.STREAMING, 3
    )


def test_user_event_atomically_preserves_partial_and_rebuilds_queue() -> None:
    async def run():
        registry = CancellationRegistry()
        started, closed = asyncio.Event(), asyncio.Event()
        tracked = registry.stream(
            "request-1", streaming(started, closed)
        )
        task = asyncio.create_task(consume(tracked))
        await started.wait()
        active = ActiveTurn(
            "request-1", active_lifecycle(), registry, task
        )
        actions = await handle_user_event(
            UserEvent("user-4", "session-1", 4, "Stop and answer this."), active
        )
        return actions, closed
    actions, closed = asyncio.run(run())
    user, interrupted = actions.append_events
    assert user.text == "Stop and answer this."
    assert interrupted.text == "first second"
    assert interrupted.state is UtteranceState.INTERRUPTED
    assert interrupted.reason == "user_interrupt"
    assert actions.lifecycle.state is UtteranceState.INTERRUPTED
    assert actions.cancel_requested and actions.rebuild_queue
    assert closed.is_set()


def test_user_event_without_active_turn_still_rebuilds_queue() -> None:
    event = UserEvent("user-1", "session-1", 1, "New input")
    actions = asyncio.run(handle_user_event(event, None))
    assert actions.append_events == (event,)
    assert not actions.cancel_requested and actions.rebuild_queue
