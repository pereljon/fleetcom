"""Event CRUD: scheduled dates, meetings, and milestones."""

from __future__ import annotations

from . import crud

TABLE = "events"
FIELDS = {"summary", "description", "start", "end", "location"}


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
        start=start,
        end=end,
        location=location,
    )


def get(conn, id_: str) -> dict | None:
    return crud.get(conn, TABLE, id_)


def list_in_range(conn, *, start: str, end: str, limit: int = 50) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM events WHERE start >= ? AND start <= ? ORDER BY start LIMIT ?",
        (start, end, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def update(conn, id_: str, **fields) -> bool:
    return crud.update(conn, TABLE, FIELDS, id_, **fields)


def delete(conn, id_: str) -> bool:
    return crud.delete(conn, TABLE, id_)
