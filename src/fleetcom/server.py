"""fleetcom MCP server: task/event/contact tools over stdio."""

from __future__ import annotations

import argparse
import functools
import sqlite3
import sys
import threading
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from . import agenda, contacts, db, events, tasks, util

# The SDK runs sync tools in worker threads, and all of them share one connection.
# Transactions are per connection, so calls must not interleave on it.
_call_lock = threading.Lock()


def _updated_fields(**fields: Any) -> dict[str, Any]:
    return {k: v for k, v in fields.items() if v is not None}


def _anticipated(fn):
    """Turn a storage-layer rejection (bad enum/date-range CHECK, unknown update
    field) into a `ToolError`, so the calling agent sees the actual reason instead
    of the generic 'Error executing tool X' every other exception produces."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with _call_lock:
            try:
                return fn(*args, **kwargs)
            except (ValueError, sqlite3.IntegrityError) as exc:
                raise ToolError(str(exc)) from exc
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc):
                    raise
                raise ToolError(
                    "database is locked: another fleetcom server held the write "
                    "lock past the busy timeout; retry the call"
                ) from exc

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
        limit: int = util.DEFAULT_LIMIT,
    ) -> dict[str, Any]:
        """List tasks, optionally filtered by status (open/in-progress/blocked/completed)
        or owner. due_now=True returns not-yet-completed tasks whose remind_at or
        due has passed (a pull-only "what needs attention" check, not a push notification).
        truncated=true means rows were cut: try a narrower filter first, then a larger
        limit (default 50).
        Without due_now, rows sort active, then unreviewed, then reviewed. If the last
        row is completed with reviewed=1, only accepted history was cut, so no retry is needed."""
        rows, truncated = util.capped(
            lambda n: tasks.list(
                conn, status=status, owner=owner, due_now=due_now, limit=n
            ),
            limit,
        )
        return {"truncated": truncated, "tasks": rows}

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
        blocked_reason (in this call or already stored on the row). ok=false means no
        argument changed anything. An unknown id is an error that names the id."""
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
        """Delete a task. An unknown id is an error that names the id."""
        return {"ok": tasks.delete(conn, task_id)}

    @mcp.tool()
    @_anticipated
    def task_accept(task_id: str, actor: str) -> dict[str, Any]:
        """CoS accepts a completed task's result (sets reviewed=1, records actor in
        description). ok=false means the task is not completed; an unknown id is an
        error that names the id. actor is not an enforced permission -- fleetcom has
        no agent-identity layer."""
        return {"ok": tasks.accept(conn, task_id, actor=actor)}

    @mcp.tool()
    @_anticipated
    def task_reject(task_id: str, actor: str, note: str) -> dict[str, Any]:
        """CoS bounces a completed task back to in-progress with a note (appended to
        description) and clears reviewed. ok=false means the task is not completed; an
        unknown id is an error that names the id."""
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
    def event_list(
        start: str, end: str, limit: int = util.DEFAULT_LIMIT
    ) -> dict[str, Any]:
        """List events whose start falls within [start, end] (ISO-8601).
        truncated=true means rows were cut: try a narrower range first, then a larger
        limit (default 50)."""
        rows, truncated = util.capped(
            lambda n: events.list_in_range(conn, start=start, end=end, limit=n), limit
        )
        return {"truncated": truncated, "events": rows}

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
        """Update an event. Only non-null arguments are changed. ok=false means no
        argument changed anything. An unknown id is an error that names the id."""
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
        """Delete an event. An unknown id is an error that names the id."""
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
    def contact_search(query: str, limit: int = util.DEFAULT_LIMIT) -> dict[str, Any]:
        """Search contacts by a substring match on name or tags.
        truncated=true means rows were cut: try a narrower query first, then a larger
        limit (default 50)."""
        rows, truncated = util.capped(
            lambda n: contacts.search(conn, query=query, limit=n), limit
        )
        return {"truncated": truncated, "contacts": rows}

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
        """Update a contact. Only non-null arguments are changed. ok=false means no
        argument changed anything. An unknown id is an error that names the id."""
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
        """Delete a contact. An unknown id is an error that names the id."""
        return {"ok": contacts.delete(conn, contact_id)}

    # -- agenda ---------------------------------------------------------------

    @mcp.tool()
    @_anticipated
    def agenda_today() -> dict[str, Any]:
        """Aggregate: tasks due right now (due_now) plus events happening today (UTC),
        up to 50 of each. If tasks_truncated is true, call task_list(due_now=True, limit=N).
        If events_truncated is true, call event_list from T00:00:00Z to T23:59:59Z
        on the current UTC date, with limit=N."""
        return agenda.today(conn)

    return mcp


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="fleetcom-mcp")
    parser.add_argument(
        "--db",
        default=None,
        help="Path to the fleetcom SQLite database (overrides FLEETCOM_DB_PATH)",
    )
    parser.add_argument(
        "--create-db",
        action="store_true",
        help="Create the database, or set up an existing empty file",
    )
    args = parser.parse_args(argv)
    args.db = args.db or db.default_db_path()
    return args


def main() -> None:
    args = _parse_args()
    try:
        conn = db.connect(args.db, create=args.create_db)
    except FileNotFoundError as error:
        sys.exit(f"fleetcom-mcp: {error}")
    except (OSError, sqlite3.DatabaseError) as error:
        sys.exit(f"fleetcom-mcp: cannot open database {args.db}: {error}")
    db.migrate(conn)
    server = build_server(conn)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
