"""Immutable session snapshots and versioned persona presets."""
import json
from uuid import uuid4

from trio.persona.models import PersonaConfig
from trio.storage.database import Database

REQUIRED = frozenset(
    {"mode", "model_digests", "profile", "language_lock", "ablations", "personas"}
)


def _json(value) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True,
        default=lambda item: item.model_dump(mode="json"),
    )


class SessionRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def create_session(self, snapshot) -> str:
        normalized = json.loads(_json(snapshot))
        missing = REQUIRED - normalized.keys()
        if missing:
            raise ValueError(f"session snapshot missing: {', '.join(sorted(missing))}")
        lock = normalized["language_lock"]
        session_id = str(uuid4())
        values = (
            session_id, normalized["mode"], lock["language"], lock["script"],
            lock.get("variant"), normalized["profile"], _json(normalized),
        )
        async with self.database.transaction() as transaction:
            await transaction.execute(
                "INSERT INTO sessions"
                "(id,mode,language,script,variant,profile,snapshot_json) "
                "VALUES(?,?,?,?,?,?,?)", values,
            )
        return session_id

    async def get_session(self, session_id: str):
        row = await self.database.fetchone(
            "SELECT snapshot_json FROM sessions WHERE id=?", (session_id,)
        )
        return json.loads(row[0]) if row else None

    async def save_preset(self, config: PersonaConfig) -> int:
        async with self.database.transaction() as transaction:
            row = await transaction.fetchone(
                "SELECT COALESCE(MAX(version),0)+1 FROM presets WHERE id=?",
                (config.name,),
            )
            version = row[0]
            await transaction.execute(
                "INSERT INTO presets(id,version,persona_json) VALUES(?,?,?)",
                (config.name, version, _json(config)),
            )
        return version

    async def update_live_stats(
        self, session_id: str, config: PersonaConfig
    ) -> str:
        event_id = str(uuid4())
        async with self.database.transaction() as transaction:
            row = await transaction.fetchone(
                "SELECT COALESCE(MAX(sequence),0)+1 FROM events WHERE session_id=?",
                (session_id,),
            )
            await transaction.execute(
                "INSERT INTO events(id,session_id,sequence,kind,payload_json) "
                "VALUES(?,?,?,?,?)",
                (event_id, session_id, row[0], "live_stats_changed", _json(config)),
            )
        return event_id
