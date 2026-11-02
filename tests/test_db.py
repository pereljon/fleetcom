import multiprocessing
import sqlite3
import time
from typing import ClassVar

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


def test_default_db_path_is_the_fleetcom_home_folder(monkeypatch, tmp_path):
    monkeypatch.delenv("FLEETCOM_DB_PATH", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert db.default_db_path() == str(tmp_path / ".fleetcom" / "fleetcom.db")


def _connection_failing_wal(message, failures):
    class FailingWal(sqlite3.Connection):
        attempts = 0
        statements: ClassVar[list[str]] = []

        def execute(self, sql, *args):
            FailingWal.statements.append(sql)
            if sql == "PRAGMA journal_mode = WAL":
                FailingWal.attempts += 1
                if FailingWal.attempts <= failures:
                    raise sqlite3.OperationalError(message)
            return super().execute(sql, *args)

    return FailingWal


@pytest.fixture
def fake_clock(monkeypatch):
    clock = {"now": 0.0}

    def sleep(seconds):
        clock["now"] += seconds

    monkeypatch.setattr(db.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(db.time, "sleep", sleep)
    return clock


def _connect_with_factory(monkeypatch, factory):
    real_connect = sqlite3.connect
    monkeypatch.setattr(
        db.sqlite3,
        "connect",
        lambda path, **kwargs: real_connect(path, factory=factory, **kwargs),
    )


def test_connect_retries_a_locked_wal_pragma(monkeypatch, tmp_path, fake_clock):
    factory = _connection_failing_wal("database is locked", failures=2)
    _connect_with_factory(monkeypatch, factory)
    conn = db.connect(str(tmp_path / "f.db"))
    assert factory.attempts == 3
    assert "PRAGMA busy_timeout = 5000" in factory.statements
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_connect_gives_up_on_a_lock_after_ten_seconds(
    monkeypatch, tmp_path, fake_clock
):
    factory = _connection_failing_wal("database is locked", failures=10**6)
    _connect_with_factory(monkeypatch, factory)
    with pytest.raises(sqlite3.OperationalError, match="locked"):
        db.connect(str(tmp_path / "f.db"))
    assert 10 <= fake_clock["now"] < 10.1
    assert factory.attempts > 100


def test_connect_does_not_retry_other_errors(monkeypatch, tmp_path, fake_clock):
    factory = _connection_failing_wal("disk I/O error", failures=10**6)
    _connect_with_factory(monkeypatch, factory)
    with pytest.raises(sqlite3.OperationalError, match="disk I/O"):
        db.connect(str(tmp_path / "f.db"))
    assert factory.attempts == 1


def _open_at_barrier(path, barrier):
    barrier.wait(timeout=20)
    db.migrate(db.connect(path))


def test_servers_starting_together_on_a_new_file_all_succeed(tmp_path):
    mp = multiprocessing.get_context("fork")
    for round_number in range(20):
        path = str(tmp_path / f"{round_number}.db")
        barrier = mp.Barrier(6)
        processes = [
            mp.Process(target=_open_at_barrier, args=(path, barrier), daemon=True)
            for _ in range(6)
        ]
        for process in processes:
            process.start()
        deadline = time.monotonic() + 30
        try:
            for process in processes:
                process.join(timeout=max(0, deadline - time.monotonic()))
            assert [process.exitcode for process in processes] == [0] * 6
        finally:
            for process in processes:
                process.kill()
        check = sqlite3.connect(path)
        assert check.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        check.close()
