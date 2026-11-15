"""Event CRUD: scheduled dates, meetings, and milestones."""

from __future__ import annotations

from . import crud, util

TABLE = "events"
FIELDS = {"summary", "description", "start", "end", "location"}
TIME_FIELDS = ("start", "end")


def create(
    conn, *, created_by, summary, start, description=None, end=None, location=None
) -> str:
    return crud.create(
        conn,
        TABLE,
        FIELDS,
        created_by=created_by,
        summary=summary,
        description=description,
        **util.normalize_times({"start": start, "end": end}, TIME_FIELDS),
        location=location,
    )


def get(conn, id_: str) -> dict | None:
    return crud.get(conn, TABLE, id_)


def list_in_range(
    conn, *, start: str, end: str, limit: int = util.DEFAULT_LIMIT
) -> list[dict]:
    start, end = util.to_utc(start), util.to_utc(end)
    rows = conn.execute(
        "SELECT * FROM events WHERE start >= ? AND start <= ? ORDER BY start LIMIT ?",
        (start, end, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def update(conn, id_: str, **fields) -> bool:
    fields = util.normalize_times(fields, TIME_FIELDS)
    return crud.update(conn, TABLE, FIELDS, id_, **fields)


def delete(conn, id_: str) -> bool:
    return crud.delete(conn, TABLE, id_)
