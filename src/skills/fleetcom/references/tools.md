# fleetcom tool reference

One usage example per tool. All 15 tools, grepped from `src/fleetcom/server.py`'s actual `@mcp.tool()` registrations — this list is not maintained by hand elsewhere, so if it drifts from the running server, trust `tools/list`, not this file.

## Tasks

- `task_create(summary="renew SSL cert", created_by="hermes:builder", due="2026-10-01T00:00:00Z")` — a plain deadline.
- `task_create(summary="check domain renewal", created_by="hermes:secretary", remind_at="2026-09-20T09:00:00Z")` — a pure reminder (no `due`).
- `task_list(owner="hermes:builder", status="open")` — what's on your open list.
- `task_list(due_now=True)` — everything not yet completed whose `remind_at` has passed.
- `task_update(task_id="...", status="in-progress")` — claim/advance a task.
- `task_update(task_id="...", status="blocked", blocked_reason="waiting on vendor callback")` — blocked requires a reason.
- `task_update(task_id="...", status="completed", result_summary="cert renewed, expires 2027-10-01")` — mark done with evidence.
- `task_delete(task_id="...")` — remove a task.
- `task_accept(task_id="...", actor="hermes:cos")` — CoS confirms a completed task's result.
- `task_reject(task_id="...", actor="hermes:cos", note="result_summary doesn't show verification")` — CoS bounces it back to `in-progress`.

## Events

- `event_create(summary="fleet standup", start="2026-09-15T09:00:00Z", end="2026-09-15T09:30:00Z", created_by="hermes:cos")` — a scheduled meeting.
- `event_list(start="2026-09-01T00:00:00Z", end="2026-09-30T00:00:00Z")` — everything this month.
- `event_update(event_id="...", location="conference room B")` — change a field.
- `event_delete(event_id="...")` — remove an event.

## Contacts

- `contact_create(name="Acme Plumbing", created_by="hermes:secretary", kind="vendor", phone="555-1234", tags="plumbing,emergency")` — add to the address book.
- `contact_search(query="acme")` — substring match on name or tags.
- `contact_update(contact_id="...", phone="555-0000")` — change a field.
- `contact_delete(contact_id="...")` — remove a contact.

## Agenda

- `agenda_today()` — tasks due right now plus events happening today, in one call. Equivalent to calling `task_list(due_now=True)` and `event_list` for today's date range yourself, combined.
