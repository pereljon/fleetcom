"""SQLite storage: schema and connection for the fleetcom office primitives."""

from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

SCHEMA_VERSION = 1
WAL_RETRY_SECONDS = 10
WAL_RETRY_DELAY_SECONDS = 0.02

SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS tasks (
  id             TEXT PRIMARY KEY,
  summary        TEXT NOT NULL,
  description    TEXT,
  status         TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'in-progress', 'blocked', 'completed')),
  blocked_reason TEXT,
  owner          TEXT,
  created_by     TEXT NOT NULL,
  due            TEXT,
  remind_at      TEXT,
  result_summary TEXT,
  reviewed       INTEGER NOT NULL DEFAULT 0 CHECK (reviewed IN (0, 1)),
  created_at     TEXT NOT NULL,
  updated_at     TEXT NOT NULL,
  CHECK (status != 'blocked' OR blocked_reason IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_owner ON tasks(owner);
CREATE INDEX IF NOT EXISTS idx_tasks_remind_at ON tasks(remind_at);

CREATE TABLE IF NOT EXISTS events (
  id          TEXT PRIMARY KEY,
  summary     TEXT NOT NULL,
  description TEXT,
  start       TEXT NOT NULL,
  end         TEXT,
  location    TEXT,
  created_by  TEXT NOT NULL,
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL,
  CHECK (end IS NULL OR end >= start)
);
CREATE INDEX IF NOT EXISTS idx_events_start ON events(start);

CREATE TABLE IF NOT EXISTS contacts (
  id          TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  kind        TEXT NOT NULL DEFAULT 'other' CHECK (kind IN ('vendor', 'client', 'team', 'other')),
  email       TEXT,
  phone       TEXT,
  org         TEXT,
  notes       TEXT,
  tags        TEXT,
  created_by  TEXT NOT NULL,
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_contacts_name ON contacts(name);

CREATE TABLE IF NOT EXISTS schema_version (
  id      INTEGER PRIMARY KEY CHECK (id = 1),
  version INTEGER NOT NULL
);
"""


def default_db_path() -> str:
    """Return the fleetcom DB path, honoring FLEETCOM_DB_PATH."""
    override = os.environ.get("FLEETCOM_DB_PATH")
    if override:
        return override
    return str(Path.home() / ".fleetcom" / "fleetcom.db")


def _enable_wal(conn: sqlite3.Connection) -> None:
    # Switching a new file to WAL fails at once when another process is doing
    # the same; the busy timeout does not cover this error.
    deadline = time.monotonic() + WAL_RETRY_SECONDS
    while True:
        try:
            conn.execute("PRAGMA journal_mode = WAL")
            return
        except sqlite3.OperationalError as error:
            if "locked" not in str(error) or time.monotonic() >= deadline:
                raise
            time.sleep(WAL_RETRY_DELAY_SECONDS)


def connect(path: str, *, create: bool = False) -> sqlite3.Connection:
    """Open the SQLite DB at path with the required PRAGMAs.

    Only create=True makes a new file, so a mistyped path fails instead of
    starting an empty database.
    """
    file = Path(path).expanduser()
    if create:
        file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        file.touch(mode=0o600, exist_ok=True)
    elif not file.exists():
        raise FileNotFoundError(
            f"database not found: {file} (pass --create-db to create it)"
        )
    uri = f"{file.resolve().as_uri()}?mode=rw"
    conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 5000")
    # Check before the WAL switch, which would itself change a refused file.
    if not create and _stored_version(conn) is None:
        conn.close()
        raise sqlite3.DatabaseError(
            "not a fleetcom database (no schema_version); check the path, "
            "and pass --create-db only to set up a new database"
        )
    _enable_wal(conn)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _stored_version(conn: sqlite3.Connection) -> int | None:
    try:
        row = conn.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()
    except sqlite3.OperationalError as error:
        if "no such table" not in str(error):
            raise
        return None
    return row[0] if row else None


def migrate(conn: sqlite3.Connection) -> None:
    """Create all tables and record the schema version, unless already current.

    Writing on every startup would crash startup whenever another server holds
    the write lock past the busy timeout.
    """
    if _stored_version(conn) == SCHEMA_VERSION:
        return
    conn.executescript(SCHEMA_DDL)
    conn.execute(
        "INSERT INTO schema_version (id, version) VALUES (1, ?) "
        "ON CONFLICT(id) DO UPDATE SET version = excluded.version",
        (SCHEMA_VERSION,),
    )
    conn.commit()
