"""Immutable session events and utterance lifecycle transitions."""
from dataclasses import dataclass, replace
from enum import StrEnum
from trio.contracts import EventId, SessionId, UtteranceId
class UtteranceState(StrEnum):
    PLANNED = "PLANNED"
    CLAIMED = "CLAIMED"
    STREAMING = "STREAMING"
    COMPLETED = "COMPLETED"
    INTERRUPTED = "INTERRUPTED"
    TIMED_OUT = "TIMED_OUT"
    FAILED = "FAILED"
TERMINAL_STATES = frozenset({
    UtteranceState.COMPLETED,
    UtteranceState.INTERRUPTED,
    UtteranceState.TIMED_OUT,
    UtteranceState.FAILED,
})
_TRANSITIONS = {
    None: {UtteranceState.PLANNED},
    UtteranceState.PLANNED: {UtteranceState.CLAIMED},
    UtteranceState.CLAIMED: {UtteranceState.STREAMING},
    UtteranceState.STREAMING: TERMINAL_STATES,
}


class IllegalTransitionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class SessionEvent:
    event_id: EventId
    session_id: SessionId
    sequence: int
    utterance_id: UtteranceId
    state: UtteranceState
    text: str = ""
    reason: str | None = None

    def __post_init__(self) -> None:
        if not self.event_id or not self.session_id or not self.utterance_id:
            raise ValueError("event, session, and utterance ids are required")
        if self.sequence < 1:
            raise ValueError("event sequence must be positive")
        if self.state in {
            UtteranceState.INTERRUPTED,
            UtteranceState.TIMED_OUT,
            UtteranceState.FAILED,
        } and not self.reason:
            raise ValueError("non-success terminal events require a reason")


@dataclass(frozen=True, slots=True)
class UtteranceLifecycle:
    session_id: SessionId
    utterance_id: UtteranceId
    state: UtteranceState | None = None
    last_sequence: int = 0

    def transition(self, event: SessionEvent) -> "UtteranceLifecycle":
        if event.session_id != self.session_id:
            raise IllegalTransitionError("event belongs to another session")
        if event.utterance_id != self.utterance_id:
            raise IllegalTransitionError("event belongs to another utterance")
        if event.sequence <= self.last_sequence:
            raise IllegalTransitionError("event sequence is not monotonic")
        if event.state not in _TRANSITIONS.get(self.state, set()):
            raise IllegalTransitionError(
                f"illegal transition {self.state!s} -> {event.state}"
            )
        return replace(
            self, state=event.state, last_sequence=event.sequence
        )
