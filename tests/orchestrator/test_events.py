import sys
from dataclasses import FrozenInstanceError
from pathlib import Path
import pytest
ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "src"))

from trio.orchestrator.events import (
    IllegalTransitionError,
    SessionEvent,
    UtteranceLifecycle,
    UtteranceState,
)


def event(sequence, state, reason=None):
    return SessionEvent(
        f"event-{sequence}", "session-1", sequence, "utterance-1",
        state, reason=reason,
    )


def test_happy_path_is_immutable_and_monotonic() -> None:
    lifecycle = UtteranceLifecycle("session-1", "utterance-1")
    original = lifecycle
    for sequence, state in enumerate((
        UtteranceState.PLANNED,
        UtteranceState.CLAIMED,
        UtteranceState.STREAMING,
        UtteranceState.COMPLETED,
    ), 1):
        lifecycle = lifecycle.transition(event(sequence, state))
    assert original.state is None
    assert lifecycle.state is UtteranceState.COMPLETED
    assert lifecycle.last_sequence == 4
    with pytest.raises(FrozenInstanceError):
        lifecycle.state = UtteranceState.STREAMING


@pytest.mark.parametrize(
    ("terminal", "reason"),
    [
        (UtteranceState.INTERRUPTED, "user_interrupt"),
        (UtteranceState.TIMED_OUT, "total_timeout"),
        (UtteranceState.FAILED, "ollama_overloaded"),
    ],
)
def test_terminal_states_cannot_resume(terminal, reason) -> None:
    lifecycle = UtteranceLifecycle("session-1", "utterance-1")
    for sequence, state in enumerate((
        UtteranceState.PLANNED,
        UtteranceState.CLAIMED,
        UtteranceState.STREAMING,
    ), 1):
        lifecycle = lifecycle.transition(event(sequence, state))
    lifecycle = lifecycle.transition(event(4, terminal, reason))
    with pytest.raises(IllegalTransitionError):
        lifecycle.transition(event(5, UtteranceState.STREAMING))


def test_rejects_nonmonotonic_or_cross_session_event() -> None:
    lifecycle = UtteranceLifecycle("session-1", "utterance-1")
    lifecycle = lifecycle.transition(event(2, UtteranceState.PLANNED))
    with pytest.raises(IllegalTransitionError, match="monotonic"):
        lifecycle.transition(event(2, UtteranceState.CLAIMED))
    foreign = SessionEvent(
        "event-x", "session-2", 3, "utterance-1", UtteranceState.CLAIMED
    )
    with pytest.raises(IllegalTransitionError, match="another session"):
        lifecycle.transition(foreign)
