import asyncio
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
from trio.storage.database import Database
from trio.storage.sessions import SessionRepository


class Config:
    def __init__(self, name="Ada", energy=5):
        self.name, self.energy = name, energy

    def model_dump(self, mode="json"):
        return {"name": self.name, "role": "pragmatist",
                "stats": {"energy": self.energy}, "alignment": "neutral"}


def snapshot():
    return {
        "mode": "A", "model_digests": {"pragmatist": "sha256:a"},
        "profile": "Base",
        "language_lock": {"language": "en", "script": "Latn"},
        "ablations": {"stage1": True},
        "personas": [Config()],
    }


def test_snapshot_is_immutable_when_live_stats_change(tmp_path):
    async def run():
        async with Database.open(tmp_path / "db.sqlite") as database:
            repository = SessionRepository(database)
            original = snapshot()
            session_id = await repository.create_session(original)
            original["profile"] = "changed-after-save"
            await repository.update_live_stats(session_id, Config(energy=9))
            stored = await repository.get_session(session_id)
            event = await database.fetchone(
                "SELECT kind,payload_json FROM events WHERE session_id=?",
                (session_id,),
            )
            return stored, event
    stored, event = asyncio.run(run())
    assert stored == json_ready(snapshot() | {"profile": "Base"})
    assert event[0] == "live_stats_changed" and '"energy": 9' in event[1]


def json_ready(value):
    import json
    return json.loads(json.dumps(
        value, default=lambda item: item.model_dump(mode="json")
    ))


def test_missing_snapshot_field_and_unknown_session(tmp_path):
    async def run():
        async with Database.open(tmp_path / "db.sqlite") as database:
            repository = SessionRepository(database)
            with pytest.raises(ValueError, match="model_digests"):
                await repository.create_session({"mode": "A"})
            return await repository.get_session("missing")
    assert asyncio.run(run()) is None


def test_presets_are_versioned(tmp_path):
    async def run():
        async with Database.open(tmp_path / "db.sqlite") as database:
            repository = SessionRepository(database)
            versions = [await repository.save_preset(Config()) for _ in range(2)]
            rows = await database.fetchall(
                "SELECT version FROM presets ORDER BY version"
            )
            return versions, rows
    assert asyncio.run(run()) == ([1, 2], [(1,), (2,)])
