import sqlite3
from pathlib import Path
import pytest
SQL = (Path(__file__).parents[2] / "migrations/001_initial.sql").read_text()
TABLES = {
    "schema_migrations", "sessions", "events", "utterances",
    "states", "presets", "voice_bible", "metrics",
}
def apply(connection: sqlite3.Connection) -> bool:
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
    ).fetchone()
    if exists and connection.execute(
        "SELECT 1 FROM schema_migrations WHERE version=1"
    ).fetchone():
        return False
    connection.executescript(SQL)
    return True
def session(connection):
    connection.execute(
        "INSERT INTO sessions(id,mode,language,script,profile,snapshot_json) "
        "VALUES ('s','A','ru','Cyrl','Base','{}')"
    )
def test_initial_migration_applies_once_with_fk_and_utc() -> None:
    connection = sqlite3.connect(":memory:")
    assert apply(connection) is True
    assert apply(connection) is False
    names = {
        row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    assert TABLES <= names
    assert connection.execute("PRAGMA foreign_keys").fetchone() == (1,)
    assert connection.execute(
        "SELECT count(*) FROM schema_migrations"
    ).fetchone() == (1,)
    session(connection)
    assert connection.execute(
        "SELECT created_at FROM sessions WHERE id='s'"
    ).fetchone()[0].endswith("Z")
def test_json_fk_and_session_sequence_constraints() -> None:
    connection = sqlite3.connect(":memory:")
    apply(connection)
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO sessions VALUES('bad','A','ru','Cyrl',NULL,'Base','x',"
            "strftime('%Y-%m-%dT%H:%M:%fZ','now'))"
        )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO events(id,session_id,sequence,kind,payload_json) "
            "VALUES('e','missing',1,'user','{}')"
        )
    session(connection)
    connection.execute(
        "INSERT INTO events(id,session_id,sequence,kind,payload_json) "
        "VALUES('e1','s',1,'user','{}')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO events(id,session_id,sequence,kind,payload_json) "
            "VALUES('e2','s',1,'user','{}')"
        )
