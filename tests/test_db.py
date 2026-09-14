import sqlite3

import pytest

from fleetcom import db


def test_migrate_creates_all_tables(conn):
    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {"tasks", "events", "contacts", "schema_version"} <= tables
    assert "reminders" not in tables


def test_migrate_is_idempotent(conn):
    db.migrate(conn)
    version = conn.execute(
        "SELECT version FROM schema_version WHERE id = 1"
    ).fetchone()[0]
    assert version == db.SCHEMA_VERSION


def test_connect_sets_wal_and_foreign_keys(conn):
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_events_check_rejects_end_before_start(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO events (id, summary, start, end, created_by, created_at, updated_at) "
            "VALUES ('e1', 'x', '2026-01-02T00:00:00Z', '2026-01-01T00:00:00Z', 'a', 't', 't')"
        )


def test_tasks_check_rejects_blocked_without_reason(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO tasks (id, summary, status, created_by, created_at, updated_at) "
            "VALUES ('t1', 'x', 'blocked', 'a', 't', 't')"
        )


def test_default_db_path_honors_env_override(monkeypatch, tmp_path):
    override = str(tmp_path / "custom.db")
    monkeypatch.setenv("FLEETCOM_DB_PATH", override)
    assert db.default_db_path() == override
