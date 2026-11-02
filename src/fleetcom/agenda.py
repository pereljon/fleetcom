"""Cross-entity "what needs attention today" aggregation."""

from __future__ import annotations

from . import events, tasks, util


def today(conn) -> dict:
    """Tasks due/reminder-due right now, plus events happening today (UTC)."""
    today_date = util.now_iso()[:10]
    tasks_due, tasks_truncated = util.capped(
        lambda limit: tasks.list(conn, due_now=True, limit=limit)
    )
    events_today, events_truncated = util.capped(
        lambda limit: events.list_in_range(
            conn,
            start=f"{today_date}T00:00:00Z",
            end=f"{today_date}T23:59:59Z",
            limit=limit,
        )
    )
    # Flags come first: Hermes keeps only the head of a large result.
    return {
        "tasks_truncated": tasks_truncated,
        "events_truncated": events_truncated,
        "tasks_due": tasks_due,
        "events_today": events_today,
    }
