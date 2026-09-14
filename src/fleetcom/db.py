"""SQLite storage: schema and connection for the fleetcom office primitives."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

SCHEMA_VERSION = 1

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
    return str(Path.home() / "Claude" / "-hermes" / "fleetcom.db")


def connect(path: str) -> sqlite3.Connection:
    """Open (creating if needed) the SQLite DB at path with the required PRAGMAs."""
    parent = Path(path).parent
    if str(parent):
        parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    """Create all tables (idempotent) and record the schema version."""
    conn.executescript(SCHEMA_DDL)
    conn.execute(
        "INSERT INTO schema_version (id, version) VALUES (1, ?) "
        "ON CONFLICT(id) DO UPDATE SET version = excluded.version",
        (SCHEMA_VERSION,),
    )
    conn.commit()
