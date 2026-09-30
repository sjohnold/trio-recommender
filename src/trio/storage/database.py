"""Async SQLite lifecycle, migrations, and serialized transactions."""
import asyncio
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

try:
    import aiosqlite
except ImportError:  # pragma: no cover - permits source-tree tests before install
    aiosqlite = None

_MIGRATION = Path(__file__).parents[3] / "migrations/001_initial.sql"


class Database:
    def __init__(self, connection: Any, asynchronous: bool) -> None:
        self.connection, self.asynchronous = connection, asynchronous
        self._lock = asyncio.Lock()

    @classmethod
    @asynccontextmanager
    async def open(cls, path: str | Path):
        if aiosqlite:
            connection = await aiosqlite.connect(path, isolation_level=None)
        else:
            connection = sqlite3.connect(path, isolation_level=None)
        database = cls(connection, aiosqlite is not None)
        try:
            for pragma in (
                "PRAGMA foreign_keys=ON",
                "PRAGMA journal_mode=WAL",
                "PRAGMA busy_timeout=5000",
            ):
                await database.execute(pragma)
            if not await database._migration_applied():
                await database._script(_MIGRATION.read_text())
            yield database
        finally:
            await database._call("close")

    async def _call(self, method: str, *args):
        function = getattr(self.connection, method)
        if self.asynchronous:
            return await function(*args)
        return function(*args)

    async def execute(self, sql: str, parameters=()) -> None:
        await self._call("execute", sql, parameters)

    async def fetchone(self, sql: str, parameters=()):
        cursor = await self._call("execute", sql, parameters)
        if self.asynchronous:
            return await cursor.fetchone()
        return cursor.fetchone()

    async def fetchall(self, sql: str, parameters=()):
        cursor = await self._call("execute", sql, parameters)
        if self.asynchronous:
            return await cursor.fetchall()
        return cursor.fetchall()

    async def _script(self, sql: str) -> None:
        await self._call("executescript", sql)

    async def _migration_applied(self):
        exists = await self.fetchone(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='schema_migrations'"
        )
        return exists and await self.fetchone(
            "SELECT 1 FROM schema_migrations WHERE version=1"
        )

    @asynccontextmanager
    async def transaction(self):
        async with self._lock:
            await self.execute("BEGIN IMMEDIATE")
            try:
                yield self
            except BaseException:
                await self._call("rollback")
                raise
            else:
                await self._call("commit")
