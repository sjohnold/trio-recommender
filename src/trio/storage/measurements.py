"""Turn-linked State snapshots and typed metric observations."""
import json
from dataclasses import asdict, dataclass
from typing import Any

from trio.state.validation import DialogueState
from trio.storage.database import Database

JsonValue = str | int | float | bool | None | list[Any] | dict[str, Any]


@dataclass(frozen=True, slots=True)
class MetricObservation:
    name: str
    value: JsonValue
    event_id: str | None
    utterance_id: str | None


class MeasurementRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def append_state(
        self, session_id: str, event_id: str, raw: object,
        validated: DialogueState,
    ) -> None:
        raw = getattr(raw, "raw_json", raw)
        await self.database.execute(
            "INSERT INTO states(session_id,event_id,raw_json,validated_json,"
            "source,confidence) VALUES(?,?,?,?,?,?)",
            (session_id, event_id, json.dumps(raw, ensure_ascii=False),
             json.dumps(asdict(validated), ensure_ascii=False),
             validated.source, validated.confidence),
        )

    async def append_metric(
        self, session_id: str, name: str, value: JsonValue, *,
        event_id: str | None = None, utterance_id: str | None = None,
    ) -> None:
        if not name:
            raise ValueError("metric name is required")
        if event_id is None and utterance_id is None:
            raise ValueError("metric requires event_id or utterance_id")
        await self.database.execute(
            "INSERT INTO metrics"
            "(session_id,event_id,utterance_id,name,value_json) VALUES(?,?,?,?,?)",
            (session_id, event_id, utterance_id, name,
             json.dumps(value, ensure_ascii=False, allow_nan=False)),
        )

    async def query_metrics(
        self, session: str, language: str, mode: str
    ) -> tuple[MetricObservation, ...]:
        rows = await self.database.fetchall(
            "SELECT m.name,m.value_json,m.event_id,m.utterance_id "
            "FROM metrics m JOIN sessions s ON s.id=m.session_id "
            "WHERE m.session_id=? AND s.language=? AND s.mode=? ORDER BY m.id",
            (session, language, mode),
        )
        return tuple(
            MetricObservation(name, json.loads(value), event_id, utterance_id)
            for name, value, event_id, utterance_id in rows
        )
