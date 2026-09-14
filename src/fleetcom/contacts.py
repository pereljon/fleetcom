"""Contact CRUD: shared address book (vendors, clients, team, other)."""

from __future__ import annotations

from . import crud

TABLE = "contacts"
FIELDS = {"name", "kind", "email", "phone", "org", "notes", "tags"}


def create(
    conn,
    *,
    created_by,
    name,
    kind="other",
    email=None,
    phone=None,
    org=None,
    notes=None,
    tags=None,
) -> str:
    return crud.create(
        conn,
        TABLE,
        FIELDS,
        created_by=created_by,
        name=name,
        kind=kind,
        email=email,
        phone=phone,
        org=org,
        notes=notes,
        tags=tags,
    )


def get(conn, id_: str) -> dict | None:
    return crud.get(conn, TABLE, id_)


def search(conn, *, query: str, limit: int = 50) -> list[dict]:
    """Case-insensitive substring match on name or tags."""
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = f"%{escaped}%"
    rows = conn.execute(
        "SELECT * FROM contacts WHERE name LIKE ? ESCAPE '\\' OR tags LIKE ? ESCAPE '\\' "
        "ORDER BY name LIMIT ?",
        (pattern, pattern, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def update(conn, id_: str, **fields) -> bool:
    return crud.update(conn, TABLE, FIELDS, id_, **fields)


def delete(conn, id_: str) -> bool:
    return crud.delete(conn, TABLE, id_)
