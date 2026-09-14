import sqlite3

import pytest

from fleetcom import tasks


def test_create_and_get(conn):
    task_id = tasks.create(conn, created_by="agent-1", summary="write tests")
    got = tasks.get(conn, task_id)
    assert got["summary"] == "write tests"
    assert got["status"] == "open"
    assert got["created_by"] == "agent-1"


def test_list_filters_by_status_and_owner(conn):
    tasks.create(conn, created_by="agent-1", summary="a", owner="agent-1")
    t2 = tasks.create(conn, created_by="agent-1", summary="b", owner="agent-2")
    tasks.update(conn, t2, status="completed")

    open_tasks = tasks.list(conn, status="open")
    assert [t["summary"] for t in open_tasks] == ["a"]

    agent2_tasks = tasks.list(conn, owner="agent-2")
    assert [t["summary"] for t in agent2_tasks] == ["b"]


def test_update_changes_fields_and_updated_at(conn):
    task_id = tasks.create(conn, created_by="agent-1", summary="a")
    before = tasks.get(conn, task_id)["updated_at"]

    ok = tasks.update(conn, task_id, status="completed", owner="agent-2")
    assert ok is True

    got = tasks.get(conn, task_id)
    assert got["status"] == "completed"
    assert got["owner"] == "agent-2"
    assert got["updated_at"] >= before


def test_update_unknown_field_rejected(conn):
    task_id = tasks.create(conn, created_by="agent-1", summary="a")
    with pytest.raises(ValueError):
        tasks.update(conn, task_id, created_by="agent-evil")


def test_update_nonexistent_id_returns_false(conn):
    assert tasks.update(conn, "no-such-id", status="completed") is False


def test_delete_removes_row(conn):
    task_id = tasks.create(conn, created_by="agent-1", summary="a")
    assert tasks.delete(conn, task_id) is True
    assert tasks.get(conn, task_id) is None
    assert tasks.delete(conn, task_id) is False


def test_create_with_remind_at_and_due(conn):
    task_id = tasks.create(
        conn,
        created_by="a",
        summary="renew lease",
        due="2026-12-01T00:00:00Z",
        remind_at="2026-11-01T00:00:00Z",
    )
    got = tasks.get(conn, task_id)
    assert got["due"] == "2026-12-01T00:00:00Z"
    assert got["remind_at"] == "2026-11-01T00:00:00Z"


def test_update_can_set_blocked_with_reason(conn):
    task_id = tasks.create(conn, created_by="a", summary="x")
    ok = tasks.update(
        conn, task_id, status="blocked", blocked_reason="waiting on vendor"
    )
    assert ok is True
    got = tasks.get(conn, task_id)
    assert got["status"] == "blocked"
    assert got["blocked_reason"] == "waiting on vendor"


def test_update_blocked_without_reason_raises(conn):
    task_id = tasks.create(conn, created_by="a", summary="x")
    with pytest.raises(sqlite3.IntegrityError):
        tasks.update(conn, task_id, status="blocked")


def test_list_due_now_returns_unmet_reminders_and_deadlines(conn):
    due = tasks.create(
        conn, created_by="a", summary="renew now", remind_at="2020-01-01T00:00:00Z"
    )
    tasks.create(
        conn, created_by="a", summary="future", remind_at="2099-01-01T00:00:00Z"
    )
    no_remind = tasks.create(conn, created_by="a", summary="no reminder set")
    tasks.update(conn, due, status="completed")

    results = tasks.list(conn, due_now=True)
    assert results == []  # `due` is now completed, so due_now correctly excludes it

    still_due = tasks.create(
        conn, created_by="a", summary="still due", remind_at="2020-01-01T00:00:00Z"
    )
    results = tasks.list(conn, due_now=True)
    assert [t["id"] for t in results] == [still_due]
    assert no_remind not in [t["id"] for t in results]


def test_accept_sets_reviewed_only_when_completed(conn):
    task_id = tasks.create(conn, created_by="a", summary="x")
    assert tasks.accept(conn, task_id, actor="cos") is False

    tasks.update(conn, task_id, status="completed", result_summary="done")
    assert tasks.accept(conn, task_id, actor="cos") is True
    assert tasks.get(conn, task_id)["reviewed"] == 1


def test_accept_records_actor(conn):
    task_id = tasks.create(conn, created_by="a", summary="x")
    tasks.update(conn, task_id, status="completed", result_summary="done")
    tasks.accept(conn, task_id, actor="cos-agent")
    assert "cos-agent" in tasks.get(conn, task_id)["description"]


def test_reject_bounces_completed_back_to_in_progress(conn):
    task_id = tasks.create(conn, created_by="a", summary="x")
    tasks.update(conn, task_id, status="completed", result_summary="done")
    tasks.accept(conn, task_id, actor="cos")

    ok = tasks.reject(conn, task_id, actor="cos-agent", note="needs more detail")
    assert ok is True
    got = tasks.get(conn, task_id)
    assert got["status"] == "in-progress"
    assert got["reviewed"] == 0
    assert "needs more detail" in got["description"]
    assert "cos-agent" in got["description"]
    assert "needs more detail" in got["description"]
