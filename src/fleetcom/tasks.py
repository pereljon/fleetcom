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

# Appends in SQL so a concurrent edit from another server process isn't overwritten.
_APPEND_DESCRIPTION = (
    "description = CASE WHEN COALESCE(description, '') = '' THEN ? "
    "ELSE description || char(10, 10) || ? END"
)


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

    now = util.now_iso()
    query = "SELECT * FROM tasks WHERE status != 'completed' AND (remind_at <= ? OR due <= ?)"
    args: list = [now, now]
    if status is not None:
        query += " AND status = ?"
        args.append(status)
    if owner is not None:
        query += " AND owner = ?"
        args.append(owner)
    query += " ORDER BY MIN(COALESCE(remind_at, due), COALESCE(due, remind_at)) LIMIT ?"
    args.append(limit)
    return [dict(row) for row in conn.execute(query, args).fetchall()]


def update(conn, id_: str, **fields) -> bool:
    status = fields.get("status")
    if status is None or status == "completed":
        return crud.update(conn, TABLE, FIELDS, id_, **fields)
    # Reopened work has not been reviewed. Same UPDATE, so the two can't diverge.
    fields["reviewed"] = 0
    return crud.update(conn, TABLE, FIELDS | {"reviewed"}, id_, **fields)


def delete(conn, id_: str) -> bool:
    return crud.delete(conn, TABLE, id_)


def accept(conn, task_id: str, actor: str) -> bool:
    """CoS accepts a completed task's result, setting reviewed=1 and recording
    who accepted it (appended to description -- there's no dedicated column
    or activity log in this schema, same approach as `reject`).

    `actor` is not an enforced permission -- fleetcom has no agent-identity
    layer, so this can't verify the caller really is CoS.
    """
    note = f"[Accepted by {actor}]"
    with conn:
        cur = conn.execute(
            f"UPDATE tasks SET reviewed = 1, {_APPEND_DESCRIPTION}, updated_at = ? "
            "WHERE id = ? AND status = 'completed'",
            (note, note, util.now_iso(), task_id),
        )
    return cur.rowcount > 0


def reject(conn, task_id: str, actor: str, note: str) -> bool:
    """CoS bounces a completed task back to in-progress with a note.

    The note is appended to `description` -- there's no dedicated column for
    it in the approved schema. `actor` is audit-trail data, not enforcement
    (see `accept`).
    """
    annotation = f"[Rejected by {actor}]: {note}"
    with conn:
        cur = conn.execute(
            f"UPDATE tasks SET status = 'in-progress', reviewed = 0, {_APPEND_DESCRIPTION}, "
            "updated_at = ? WHERE id = ? AND status = 'completed'",
            (annotation, annotation, util.now_iso(), task_id),
        )
    return cur.rowcount > 0
