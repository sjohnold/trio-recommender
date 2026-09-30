"""Ordered event journal and persisted utterance aggregates."""
import json
from dataclasses import asdict

from trio.orchestrator.events import SessionEvent, TERMINAL_STATES, UtteranceState
from trio.storage.database import Database


class SequenceError(ValueError):
    pass


class UtteranceRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def append_event(self, event: SessionEvent) -> None:
        async with self.database.transaction() as transaction:
            row = await transaction.fetchone(
                "SELECT COALESCE(MAX(sequence),0) FROM events WHERE session_id=?",
                (event.session_id,),
            )
            if event.sequence != row[0] + 1:
                raise SequenceError(
                    f"expected sequence {row[0] + 1}, got {event.sequence}"
                )
            await transaction.execute(
                "INSERT INTO events(id,session_id,sequence,kind,payload_json) "
                "VALUES(?,?,?,?,?)",
                (event.event_id, event.session_id, event.sequence,
                 event.state.value, json.dumps(asdict(event), default=str)),
            )

    async def start_utterance(
        self, session_id: str, utterance_id: str, role: str, generation: dict
    ) -> None:
        role = getattr(role, "value", role)
        await self.database.execute(
            "INSERT INTO utterances"
            "(id,session_id,role,state,generation_json,latency_json) "
            "VALUES(?,?,?,?,?,?)",
            (utterance_id, session_id, role, UtteranceState.PLANNED.value,
             json.dumps(generation), "{}"),
        )

    async def append_chunk(self, utterance_id: str, text: str) -> None:
        row = await self.database.fetchone(
            "SELECT state FROM utterances WHERE id=?", (utterance_id,)
        )
        if not row:
            raise KeyError(utterance_id)
        if UtteranceState(row[0]) in TERMINAL_STATES:
            raise ValueError("cannot append to terminal utterance")
        await self.database.execute(
            "UPDATE utterances SET text=text||?,state=? WHERE id=?",
            (text, UtteranceState.STREAMING.value, utterance_id),
        )

    async def finish_utterance(
        self, utterance_id: str, state: UtteranceState, reason: str | None,
        latency: dict, terminal_event_id: str | None = None,
    ) -> None:
        if state not in TERMINAL_STATES:
            raise ValueError("finish state must be terminal")
        if state is not UtteranceState.COMPLETED and not reason:
            raise ValueError("non-success terminal state requires reason")
        row = await self.database.fetchone(
            "SELECT state FROM utterances WHERE id=?", (utterance_id,)
        )
        if not row:
            raise KeyError(utterance_id)
        if UtteranceState(row[0]) in TERMINAL_STATES:
            raise ValueError("utterance is already terminal")
        await self.database.execute(
            "UPDATE utterances SET state=?,reason=?,latency_json=?,"
            "terminal_event_id=? WHERE id=?",
            (state.value, reason, json.dumps(latency), terminal_event_id, utterance_id),
        )
