"""Task CRUD: shared work items, absorbing what used to be the reminders table.

`remind_at` is set alone for a pure reminder, `due` alone for a plain deadline,
and both together for a deadline with advance warning.

`owner` is nullable. An unowned task marked `completed` means "acknowledged /
read" (nobody was assigned, someone just noted they'd seen it) -- there is no
work-product to speak of. An owned task marked `completed` means the owner
did and is claiming credit for the work; `reviewed` (set only via `accept`)
is the separate, later gate for someone else confirming that claim.
"""

from __future__ import annotations

from . import crud, util

TABLE = "tasks"
FIELDS = {
    "summary",
    "description",
    "status",
    "blocked_reason",
    "owner",
    "due",
    "remind_at",
    "result_summary",
}
FILTERS = {"status", "owner"}


def create(
    conn,
    *,
    created_by,
    summary,
    description=None,
    owner=None,
    due=None,
    remind_at=None,
    status="open",
) -> str:
    return crud.create(
        conn,
        TABLE,
        FIELDS,
        created_by=created_by,
        summary=summary,
        description=description,
        owner=owner,
        due=due,
        remind_at=remind_at,
        status=status,
    )


def get(conn, id_: str) -> dict | None:
    return crud.get(conn, TABLE, id_)


def list(
    conn, *, status=None, owner=None, due_now: bool = False, limit: int = 50
) -> list[dict]:
    if not due_now:
        return crud.list_rows(
            conn, TABLE, FILTERS, limit=limit, status=status, owner=owner
        )

    query = "SELECT * FROM tasks WHERE status != 'completed' AND remind_at IS NOT NULL AND remind_at <= ?"
    args: list = [util.now_iso()]
    if status is not None:
        query += " AND status = ?"
        args.append(status)
    if owner is not None:
        query += " AND owner = ?"
        args.append(owner)
    query += " ORDER BY remind_at LIMIT ?"
    args.append(limit)
    return [dict(row) for row in conn.execute(query, args).fetchall()]


def update(conn, id_: str, **fields) -> bool:
    return crud.update(conn, TABLE, FIELDS, id_, **fields)


def delete(conn, id_: str) -> bool:
    return crud.delete(conn, TABLE, id_)


def accept(conn, task_id: str, actor: str) -> bool:
    """CoS accepts a completed task's result, setting reviewed=1 and recording
    who accepted it (appended to description -- there's no dedicated column
    or activity log in this schema, same approach as `reject`).

    `actor` is not an enforced permission -- fleetcom has no agent-identity
    layer, so this can't verify the caller really is CoS.
    """
    row = get(conn, task_id)
    if row is None or row["status"] != "completed":
        return False
    existing = row.get("description") or ""
    annotated = f"{existing}\n\n[Accepted by {actor}]".strip()
    now = util.now_iso()
    cur = conn.execute(
        "UPDATE tasks SET reviewed = 1, description = ?, updated_at = ? "
        "WHERE id = ? AND status = 'completed'",
        (annotated, now, task_id),
    )
    conn.commit()
    return cur.rowcount > 0


def reject(conn, task_id: str, actor: str, note: str) -> bool:
    """CoS bounces a completed task back to in-progress with a note.

    The note is appended to `description` -- there's no dedicated column for
    it in the approved schema. `actor` is audit-trail data, not enforcement
    (see `accept`).
    """
    row = get(conn, task_id)
    if row is None or row["status"] != "completed":
        return False
    existing = row.get("description") or ""
    annotated = f"{existing}\n\n[Rejected by {actor}]: {note}".strip()
    now = util.now_iso()
    cur = conn.execute(
        "UPDATE tasks SET status = 'in-progress', reviewed = 0, description = ?, updated_at = ? "
        "WHERE id = ? AND status = 'completed'",
        (annotated, now, task_id),
    )
    conn.commit()
    return cur.rowcount > 0
