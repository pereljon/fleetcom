"""fleetcom MCP server: task/event/contact tools over stdio."""

from __future__ import annotations

import functools
import sqlite3
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from . import agenda, contacts, db, events, tasks


def _updated_fields(**fields: Any) -> dict[str, Any]:
    return {k: v for k, v in fields.items() if v is not None}


def _anticipated(fn):
    """Turn a storage-layer rejection (bad enum/date-range CHECK, unknown update
    field) into a `ToolError`, so the calling agent sees the actual reason instead
    of the generic 'Error executing tool X' every other exception produces."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (ValueError, sqlite3.IntegrityError) as exc:
            raise ToolError(str(exc)) from exc

    return wrapper


def build_server(conn: sqlite3.Connection) -> MCPServer:
    mcp = MCPServer("fleetcom")

    # -- tasks --------------------------------------------------------------

    @mcp.tool()
    @_anticipated
    def task_create(
        summary: str,
        created_by: str,
        description: str | None = None,
        owner: str | None = None,
        due: str | None = None,
        remind_at: str | None = None,
    ) -> dict[str, Any]:
        """Create a new task. Set remind_at alone for a pure reminder, due alone for
        a plain deadline, or both for a deadline with advance warning."""
        task_id = tasks.create(
            conn,
            created_by=created_by,
            summary=summary,
            description=description,
            owner=owner,
            due=due,
            remind_at=remind_at,
        )
        return {"id": task_id}

    @mcp.tool()
    @_anticipated
    def task_list(
        status: str | None = None,
        owner: str | None = None,
        due_now: bool = False,
        limit: int = 50,
    ) -> dict[str, Any]:
        """List tasks, optionally filtered by status (open/in-progress/blocked/completed)
        or owner. due_now=True returns not-yet-completed tasks whose remind_at has
        passed (a pull-only "what needs attention" check, not a push notification)."""
        return {
            "tasks": tasks.list(
                conn, status=status, owner=owner, due_now=due_now, limit=limit
            )
        }

    @mcp.tool()
    @_anticipated
    def task_update(
        task_id: str,
        summary: str | None = None,
        description: str | None = None,
        status: str | None = None,
        blocked_reason: str | None = None,
        owner: str | None = None,
        due: str | None = None,
        remind_at: str | None = None,
        result_summary: str | None = None,
    ) -> dict[str, Any]:
        """Update a task. Only non-null arguments are changed. status='blocked' requires
        blocked_reason (in this call or already stored on the row)."""
        fields = _updated_fields(
            summary=summary,
            description=description,
            status=status,
            blocked_reason=blocked_reason,
            owner=owner,
            due=due,
            remind_at=remind_at,
            result_summary=result_summary,
        )
        return {"ok": tasks.update(conn, task_id, **fields)}

    @mcp.tool()
    @_anticipated
    def task_delete(task_id: str) -> dict[str, Any]:
        """Delete a task."""
        return {"ok": tasks.delete(conn, task_id)}

    @mcp.tool()
    @_anticipated
    def task_accept(task_id: str, actor: str) -> dict[str, Any]:
        """CoS accepts a completed task's result (sets reviewed=1, records actor in
        description). No-op (ok=False) unless the task is currently completed.
        actor is not an enforced permission -- fleetcom has no agent-identity layer."""
        return {"ok": tasks.accept(conn, task_id, actor=actor)}

    @mcp.tool()
    @_anticipated
    def task_reject(task_id: str, actor: str, note: str) -> dict[str, Any]:
        """CoS bounces a completed task back to in-progress with a note (appended to
        description) and clears reviewed. No-op (ok=False) unless currently completed."""
        return {"ok": tasks.reject(conn, task_id, actor=actor, note=note)}

    # -- events -----------------------------------------------------------

    @mcp.tool()
    @_anticipated
    def event_create(
        summary: str,
        start: str,
        created_by: str,
        description: str | None = None,
        end: str | None = None,
        location: str | None = None,
    ) -> dict[str, Any]:
        """Create a calendar event."""
        event_id = events.create(
            conn,
            created_by=created_by,
            summary=summary,
            start=start,
            description=description,
            end=end,
            location=location,
        )
        return {"id": event_id}

    @mcp.tool()
    @_anticipated
    def event_list(start: str, end: str, limit: int = 50) -> dict[str, Any]:
        """List events whose start falls within [start, end] (ISO-8601)."""
        return {"events": events.list_in_range(conn, start=start, end=end, limit=limit)}

    @mcp.tool()
    @_anticipated
    def event_update(
        event_id: str,
        summary: str | None = None,
        description: str | None = None,
        start: str | None = None,
        end: str | None = None,
        location: str | None = None,
    ) -> dict[str, Any]:
        """Update an event. Only non-null arguments are changed."""
        fields = _updated_fields(
            summary=summary,
            description=description,
            start=start,
            end=end,
            location=location,
        )
        return {"ok": events.update(conn, event_id, **fields)}

    @mcp.tool()
    @_anticipated
    def event_delete(event_id: str) -> dict[str, Any]:
        """Delete an event."""
        return {"ok": events.delete(conn, event_id)}

    # -- contacts -----------------------------------------------------------

    @mcp.tool()
    @_anticipated
    def contact_create(
        name: str,
        created_by: str,
        kind: str = "other",
        email: str | None = None,
        phone: str | None = None,
        org: str | None = None,
        notes: str | None = None,
        tags: str | None = None,
    ) -> dict[str, Any]:
        """Add a contact (vendor/client/team/other) to the shared address book."""
        contact_id = contacts.create(
            conn,
            created_by=created_by,
            name=name,
            kind=kind,
            email=email,
            phone=phone,
            org=org,
            notes=notes,
            tags=tags,
        )
        return {"id": contact_id}

    @mcp.tool()
    @_anticipated
    def contact_search(query: str, limit: int = 50) -> dict[str, Any]:
        """Search contacts by a substring match on name or tags."""
        return {"contacts": contacts.search(conn, query=query, limit=limit)}

    @mcp.tool()
    @_anticipated
    def contact_update(
        contact_id: str,
        name: str | None = None,
        kind: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        org: str | None = None,
        notes: str | None = None,
        tags: str | None = None,
    ) -> dict[str, Any]:
        """Update a contact. Only non-null arguments are changed."""
        fields = _updated_fields(
            name=name,
            kind=kind,
            email=email,
            phone=phone,
            org=org,
            notes=notes,
            tags=tags,
        )
        return {"ok": contacts.update(conn, contact_id, **fields)}

    @mcp.tool()
    @_anticipated
    def contact_delete(contact_id: str) -> dict[str, Any]:
        """Delete a contact."""
        return {"ok": contacts.delete(conn, contact_id)}

    # -- agenda ---------------------------------------------------------------

    @mcp.tool()
    @_anticipated
    def agenda_today() -> dict[str, Any]:
        """Aggregate: tasks due right now (due_now) plus events happening today (UTC)."""
        return agenda.today(conn)

    return mcp


def main() -> None:
    conn = db.connect(db.default_db_path())
    db.migrate(conn)
    server = build_server(conn)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
