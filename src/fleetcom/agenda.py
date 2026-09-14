"""Cross-entity "what needs attention today" aggregation."""

from __future__ import annotations

from . import events, tasks, util


def today(conn) -> dict:
    """Tasks due/reminder-due right now, plus events happening today (UTC)."""
    today_date = util.now_iso()[:10]
    return {
        "tasks_due": tasks.list(conn, due_now=True),
        "events_today": events.list_in_range(
            conn, start=f"{today_date}T00:00:00Z", end=f"{today_date}T23:59:59Z"
        ),
    }
