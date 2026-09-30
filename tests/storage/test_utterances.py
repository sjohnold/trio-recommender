import asyncio
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
from trio.orchestrator.events import SessionEvent, UtteranceState
from trio.storage.database import Database
from trio.storage.utterances import SequenceError, UtteranceRepository

SESSION = ("s", "A", "en", "Latn", "Base", "{}")


async def setup(database):
    await database.execute(
        "INSERT INTO sessions(id,mode,language,script,profile,snapshot_json) "
        "VALUES(?,?,?,?,?,?)", SESSION,
    )


def event(event_id, sequence):
    return SessionEvent(
        event_id=event_id, session_id="s", sequence=sequence,
        utterance_id="u", state=UtteranceState.PLANNED,
    )


def test_events_require_next_sequence(tmp_path):
    async def run():
        async with Database.open(tmp_path / "db") as database:
            await setup(database)
            repository = UtteranceRepository(database)
            await repository.append_event(event("e1", 1))
            with pytest.raises(SequenceError, match="expected sequence 2"):
                await repository.append_event(event("e2", 1))
            return await database.fetchall("SELECT sequence FROM events")
    assert asyncio.run(run()) == [(1,)]


@pytest.mark.parametrize("terminal", [
    UtteranceState.INTERRUPTED, UtteranceState.TIMED_OUT,
])
def test_terminal_utterances_keep_partial_text(tmp_path, terminal):
    async def run():
        async with Database.open(tmp_path / "db") as database:
            await setup(database)
            repository = UtteranceRepository(database)
            await repository.start_utterance(
                "s", "u", "pragmatist", {"temperature": 0.7}
            )
            await repository.append_chunk("u", "partial ")
            await repository.append_chunk("u", "answer")
            await repository.finish_utterance(
                "u", terminal, "user_interrupt", {"total_ms": 10}
            )
            with pytest.raises(ValueError, match="terminal"):
                await repository.append_chunk("u", "lost")
            return await database.fetchone(
                "SELECT state,text,reason,generation_json,latency_json "
                "FROM utterances WHERE id='u'"
            )
    row = asyncio.run(run())
    assert row[:3] == (terminal.value, "partial answer", "user_interrupt")
    assert '"temperature": 0.7' in row[3] and '"total_ms": 10' in row[4]
