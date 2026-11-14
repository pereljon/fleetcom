import multiprocessing
import sqlite3
import stat
import time
from pathlib import Path
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
    conn = db.connect(str(tmp_path / "f.db"), create=True)
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
        db.connect(str(tmp_path / "f.db"), create=True)
    assert 10 <= fake_clock["now"] < 10.1
    assert factory.attempts > 100


def test_connect_does_not_retry_other_errors(monkeypatch, tmp_path, fake_clock):
    factory = _connection_failing_wal("disk I/O error", failures=10**6)
    _connect_with_factory(monkeypatch, factory)
    with pytest.raises(sqlite3.OperationalError, match="disk I/O"):
        db.connect(str(tmp_path / "f.db"), create=True)
    assert factory.attempts == 1


def _open_at_barrier(path, barrier):
    barrier.wait(timeout=20)
    db.migrate(db.connect(path, create=True))


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


def test_connect_refuses_a_missing_file(tmp_path):
    path = tmp_path / "missing" / "fleetcom.db"
    with pytest.raises(FileNotFoundError, match="--create-db"):
        db.connect(str(path))
    assert not path.parent.exists()


def test_connect_creates_a_private_file_when_asked(tmp_path):
    path = tmp_path / "new" / "fleetcom.db"
    conn = db.connect(str(path), create=True)
    db.migrate(conn)
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(Path(f"{path}-wal").stat().st_mode) == 0o600
    conn.close()


def test_connect_opens_an_existing_file_without_create(tmp_path):
    path = tmp_path / "fleetcom.db"
    db.migrate(db.connect(str(path), create=True))
    conn = db.connect(str(path))
    assert conn.execute("SELECT version FROM schema_version").fetchone()[0] == 1
    conn.close()


def test_connect_expands_home(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    conn = db.connect("~/fleetcom.db", create=True)
    conn.close()
    assert (tmp_path / "fleetcom.db").exists()
    assert not (tmp_path / "~").exists()


def test_migrate_does_not_write_when_the_schema_is_current(tmp_path):
    path = str(tmp_path / "fleetcom.db")
    db.migrate(db.connect(path, create=True))
    conn = db.connect(path)
    conn.execute("PRAGMA busy_timeout = 0")
    holder = sqlite3.connect(path)
    holder.execute("BEGIN IMMEDIATE")
    try:
        db.migrate(conn)
    finally:
        holder.rollback()
        holder.close()
        conn.close()


def test_connect_refuses_an_empty_file(tmp_path):
    path = tmp_path / "fleetcom.db"
    path.touch()
    with pytest.raises(sqlite3.DatabaseError, match="--create-db"):
        db.connect(str(path))
    assert path.stat().st_size == 0


def test_connect_refuses_another_applications_database(tmp_path):
    path = tmp_path / "other.db"
    other = sqlite3.connect(path)
    other.execute("CREATE TABLE notes (x)")
    other.commit()
    other.close()
    with pytest.raises(sqlite3.DatabaseError, match="not a fleetcom database"):
        db.connect(str(path))
    check = sqlite3.connect(path)
    assert check.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
    tables = check.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    assert [row[0] for row in tables] == ["notes"]
    check.close()


def test_connect_sets_up_an_empty_file_when_asked(tmp_path):
    path = tmp_path / "fleetcom.db"
    path.touch()
    conn = db.connect(str(path), create=True)
    db.migrate(conn)
    assert conn.execute("SELECT version FROM schema_version").fetchone()[0] == 1
    conn.close()


def test_connect_opens_while_another_server_holds_the_write_lock(tmp_path):
    path = str(tmp_path / "fleetcom.db")
    db.migrate(db.connect(path, create=True))
    holder = sqlite3.connect(path)
    holder.execute("BEGIN IMMEDIATE")
    try:
        started = time.monotonic()
        conn = db.connect(path)
        assert time.monotonic() - started < 1
        conn.close()
    finally:
        holder.rollback()
        holder.close()


def test_connect_opens_a_database_with_an_older_schema_version(tmp_path):
    path = str(tmp_path / "fleetcom.db")
    db.migrate(db.connect(path, create=True))
    old = sqlite3.connect(path)
    old.execute("UPDATE schema_version SET version = 0")
    old.commit()
    old.close()
    db.connect(path).close()
