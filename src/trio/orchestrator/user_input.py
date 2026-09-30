"""Atomic orchestration actions for user input during an active turn."""
import asyncio
from dataclasses import dataclass
from trio.inference.cancellation import (
    CancellationRegistry,
    InterruptReason,
)
from trio.orchestrator.events import (
    SessionEvent,
    UtteranceLifecycle,
    UtteranceState,
)
@dataclass(frozen=True, slots=True)
class UserEvent:
    event_id: str
    session_id: str
    sequence: int
    text: str

    def __post_init__(self) -> None:
        if not self.event_id or not self.session_id or not self.text:
            raise ValueError("user event ids and text are required")
        if self.sequence < 1:
            raise ValueError("user event sequence must be positive")


@dataclass(frozen=True, slots=True)
class ActiveTurn:
    request_id: str
    lifecycle: UtteranceLifecycle
    registry: CancellationRegistry
    consumer_task: asyncio.Task


@dataclass(frozen=True, slots=True)
class OrchestratorActions:
    append_events: tuple[UserEvent | SessionEvent, ...]
    lifecycle: UtteranceLifecycle | None
    cancel_requested: bool
    rebuild_queue: bool


async def handle_user_event(
    event: UserEvent,
    active_turn: ActiveTurn | None,
) -> OrchestratorActions:
    if active_turn is None:
        return OrchestratorActions((event,), None, False, True)
    lifecycle = active_turn.lifecycle
    if event.session_id != lifecycle.session_id:
        raise ValueError("user event belongs to another session")
    if event.sequence <= lifecycle.last_sequence:
        raise ValueError("user event sequence is not monotonic")
    cancelled = active_turn.registry.cancel(
        active_turn.request_id, InterruptReason.USER
    )
    if not cancelled:
        raise RuntimeError("active turn could not be cancelled")
    await active_turn.consumer_task
    result = active_turn.registry.result(active_turn.request_id)
    if result is None:
        raise RuntimeError("cancellation result is unavailable")
    interrupted = SessionEvent(
        f"{event.event_id}-interrupted",
        event.session_id,
        event.sequence + 1,
        lifecycle.utterance_id,
        UtteranceState.INTERRUPTED,
        text=result.text,
        reason=result.reason.value,
    )
    next_lifecycle = lifecycle.transition(interrupted)
    return OrchestratorActions(
        (event, interrupted), next_lifecycle, True, True
    )
