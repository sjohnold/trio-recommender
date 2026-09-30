import asyncio
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
from trio.storage.database import Database

INSERT = ("INSERT INTO sessions(id,mode,language,script,profile,snapshot_json) "
          "VALUES(?,?,?,?,?,?)")


def values(index):
    return f"s{index}", "A", "en", "Latn", "Base", "{}"


def test_open_configures_pragmas_and_migrations(tmp_path):
    async def run():
        async with Database.open(tmp_path / "trio.db") as database:
            return [await database.fetchone(f"PRAGMA {name}") for name in
                    ("journal_mode", "foreign_keys", "busy_timeout")], (
                await database.fetchone("SELECT count(*) FROM schema_migrations")
            )
    pragmas, migrations = asyncio.run(run())
    assert [row[0] for row in pragmas] == ["wal", 1, 5000]
    assert migrations == (1,)


def test_concurrent_writes_and_rollback(tmp_path):
    async def run():
        async with Database.open(tmp_path / "trio.db") as database:
            async def write(index):
                async with database.transaction() as transaction:
                    await transaction.execute(INSERT, values(index))
                    await asyncio.sleep(0)
            await asyncio.gather(write(1), write(2))
            with pytest.raises(RuntimeError):
                async with database.transaction() as transaction:
                    await transaction.execute(INSERT, values(3))
                    raise RuntimeError("rollback")
            return await database.fetchall("SELECT id FROM sessions ORDER BY id")
    assert asyncio.run(run()) == [("s1",), ("s2",)]


def test_transaction_propagates_error(tmp_path):
    async def run():
        async with Database.open(tmp_path / "trio.db") as database:
            async with database.transaction():
                raise ValueError("boom")
    with pytest.raises(ValueError, match="boom"):
        asyncio.run(run())
