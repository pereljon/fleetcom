import sqlite3

import pytest

from fleetcom import events


def test_create_and_get(conn):
    eid = events.create(
        conn,
        created_by="a",
        summary="standup",
        start="2026-09-15T09:00:00Z",
        end="2026-09-15T09:30:00Z",
    )
    got = events.get(conn, eid)
    assert got["summary"] == "standup"
    assert got["end"] == "2026-09-15T09:30:00Z"


def test_create_rejects_end_before_start(conn):
    with pytest.raises(sqlite3.IntegrityError):
        events.create(
            conn,
            created_by="a",
            summary="bad",
            start="2026-09-15T09:00:00Z",
            end="2026-09-14T09:00:00Z",
        )


def test_list_in_range_filters_by_start(conn):
    in_range = events.create(
        conn, created_by="a", summary="in", start="2026-09-15T09:00:00Z"
    )
    events.create(conn, created_by="a", summary="out", start="2026-10-15T09:00:00Z")

    found = events.list_in_range(
        conn, start="2026-09-01T00:00:00Z", end="2026-09-30T00:00:00Z"
    )
    assert [e["id"] for e in found] == [in_range]


def test_delete_removes_row(conn):
    eid = events.create(conn, created_by="a", summary="x", start="2026-09-15T09:00:00Z")
    assert events.delete(conn, eid) is True
    assert events.get(conn, eid) is None
