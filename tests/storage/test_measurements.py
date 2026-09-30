import asyncio
import json
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
from trio.state.validation import DialogueState
from trio.storage.database import Database
from trio.storage.measurements import MeasurementRepository


async def setup(database):
    await database.execute(
        "INSERT INTO sessions(id,mode,language,script,profile,snapshot_json) "
        "VALUES('s','A','en','Latn','Base','{}')"
    )
    await database.execute(
        "INSERT INTO events(id,session_id,sequence,kind,payload_json) "
        "VALUES('e','s',1,'state','{}')"
    )


def state():
    return DialogueState(
        0.4, "rising", (), {"detected": False, "confidence": 0.8},
        {"valence": 0.1, "arousal": 0.2, "stance": "neutral",
         "confidence": 0.7},
        "logician", "model", 0.7,
    )


def test_raw_and_validated_state_are_distinct(tmp_path):
    async def run():
        async with Database.open(tmp_path / "db") as database:
            await setup(database)
            repository = MeasurementRepository(database)
            await repository.append_state("s", "e", '{"untrusted":true}', state())
            return await database.fetchone(
                "SELECT raw_json,validated_json,source,confidence FROM states"
            )
    raw, validated, source, confidence = asyncio.run(run())
    assert json.loads(raw) == '{"untrusted":true}'
    assert json.loads(validated)["trend"] == "rising"
    assert (source, confidence) == ("model", 0.7)


def test_metrics_are_turn_linked_typed_and_filtered(tmp_path):
    async def run():
        async with Database.open(tmp_path / "db") as database:
            await setup(database)
            repository = MeasurementRepository(database)
            with pytest.raises(ValueError, match="event_id"):
                await repository.append_metric("s", "drift", 0.25)
            await repository.append_metric(
                "s", "drift", {"score": 0.25}, event_id="e"
            )
            matched = await repository.query_metrics("s", "en", "A")
            wrong_language = await repository.query_metrics("s", "sr", "A")
            return matched, wrong_language
    matched, wrong_language = asyncio.run(run())
    assert matched[0].name == "drift"
    assert matched[0].value == {"score": 0.25}
    assert matched[0].event_id == "e"
    assert wrong_language == ()
