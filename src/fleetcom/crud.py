"""Generic CRUD engine shared by the tasks/events/contacts tables.

Table names are always literals supplied by the calling module, never
caller-controlled. `allowed` sets are fixed per entity and gate every field
or filter name before it is interpolated into a SQL identifier position,
closing off column-name injection even though values are parameterized.

Writes run inside `with conn:` so a rejected statement rolls back. An open
transaction would hold the write lock against every other server process.
This does not isolate threads sharing a connection; `server._call_lock` does.
"""

from __future__ import annotations

import sqlite3

from . import util


def create(
    conn: sqlite3.Connection,
    table: str,
    allowed: set[str],
    *,
    created_by: str,
    **fields,
) -> str:
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"unknown field(s) for {table}: {sorted(unknown)}")
    id_ = util.new_id()
    now = util.now_iso()
    columns = ["id", "created_by", "created_at", "updated_at", *fields.keys()]
    values = [id_, created_by, now, now, *fields.values()]
    placeholders = ", ".join("?" for _ in columns)
    with conn:
        conn.execute(
            f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
            values,
        )
    return id_


def get(conn: sqlite3.Connection, table: str, id_: str) -> dict | None:
    row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (id_,)).fetchone()
    return dict(row) if row else None


def list_rows(
    conn: sqlite3.Connection,
    table: str,
    allowed: set[str],
    *,
    limit: int = 50,
    **filters,
) -> list[dict]:
    unknown = set(filters) - allowed
    if unknown:
        raise ValueError(f"unknown filter(s) for {table}: {sorted(unknown)}")
    query = f"SELECT * FROM {table} WHERE 1=1"
    args: list = []
    for key, value in filters.items():
        if value is None:
            continue
        query += f" AND {key} = ?"
        args.append(value)
    query += " ORDER BY created_at LIMIT ?"
    args.append(limit)
    return [dict(row) for row in conn.execute(query, args).fetchall()]


def update(
    conn: sqlite3.Connection, table: str, allowed: set[str], id_: str, **fields
) -> bool:
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"unknown field(s) for {table}: {sorted(unknown)}")
    if not fields:
        return False
    fields["updated_at"] = util.now_iso()
    set_clause = ", ".join(f"{key} = ?" for key in fields)
    args = [*fields.values(), id_]
    with conn:
        cur = conn.execute(f"UPDATE {table} SET {set_clause} WHERE id = ?", args)
    return cur.rowcount > 0


def delete(conn: sqlite3.Connection, table: str, id_: str) -> bool:
    with conn:
        cur = conn.execute(f"DELETE FROM {table} WHERE id = ?", (id_,))
    return cur.rowcount > 0
