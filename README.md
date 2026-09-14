# Fleetcom

Shared office primitives for a fleet of AI agents.

When you run multiple AI agents across projects, they have no shared office data: a phone number one agent finds is invisible to the others, tasks get relayed through chat, nobody has a place to check what's due, and there's no shared address book for vendors and clients.

Fleetcom is that shared office notebook, exposed over the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/): three primitives, a single Python process talking stdio, backed by one SQLite file. No daemons, no queues, no policy engine.

---

## What It Does

- **Tasks:** Shared work items with an owner, a status (`open` / `in-progress` / `blocked` / `completed`), and optional `due`/`remind_at` timestamps. There is no separate reminders primitive — a task with only `remind_at` set *is* a reminder (`task_list(due_now=True)` surfaces it); a task with only `due` is a deadline; a task with both gets an advance-warning nudge before the deadline. See "The Reminder Merge" below for why.
- **Events:** Calendar entries with a start/end and a location. No completion concept — an event just happens or it doesn't.
- **Contacts:** A shared address book (vendors, clients, team, other), searchable by name or tag.
- **Agenda:** `agenda_today()` aggregates tasks due right now with events happening today, for a single "what needs my attention" check.

There is no atomic task-claiming, no lease/expiry machinery, and no agent registry. Ownership is a plain, nullable string field any agent can set; if two agents write the same task at once, last write wins. That's a deliberate simplification — this is a shared notebook, not a work-queue.

### The Reminder Merge

Reminders started as their own table and were folded into `tasks` after a design review (see `context/decisions.md`). The short version: a "completion" bit only means something in three ways — the creator did it, a specific person (jP) did it, or an automated system stamped a delivery time. None of those require a fourth, standalone primitive; every genuine reminder resolves to a small task (`remind_at` set, `owner` often null) or a plain event. `owner` being nullable on tasks matters here: an *unowned* task marked `completed` means "acknowledged / seen," not "verified work" — there's no work-product behind a dismissed FYI. An *owned* task marked `completed` means the owner is claiming the work is done, which is a distinct thing from `reviewed` (see below).

**Fleet guidance on where things go:** a fact with no deadline (a phone number, a preference) belongs in memory, not fleetcom — nothing here expires or reminds. A pure broadcast nobody needs to look up later belongs in chat. Fleetcom is for anything with a *time* or a *status* worth querying later.

### Status Lifecycle

`open → in-progress → completed` is the common path. `blocked` is reachable from either `open` or `in-progress`, and requires a `blocked_reason` (enforced by a CHECK constraint — the write is rejected without one). Completion has two independent axes:

- `status = 'completed'` + `result_summary` — set by whoever did the work, claiming it's done.
- `reviewed = 1` — set only via `task_accept`, by whoever is confirming that claim (e.g. CoS). `task_reject` bounces a completed task back to `in-progress` with a note (appended to `description`) and clears `reviewed`.

`actor` on `task_accept`/`task_reject` is audit-trail data, not an enforced permission — fleetcom has no agent-identity layer, so nothing verifies the caller really is who they claim.

---

## Quick Start

### 1. Install

Requires Python 3.11+.

```bash
git clone git@github.com-pereljon:pereljon/fleetcom.git
cd fleetcom
uv sync
```

### 2. Connect Your Agents

Fleetcom communicates over standard input/output (`stdio`).

#### Claude Code (`~/.claude.json`)

```json
{
  "mcpServers": {
    "fleetcom": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/fleetcom", "fleetcom-mcp"],
      "env": { "FLEETCOM_DB_PATH": "/path/to/fleetcom.db" }
    }
  }
}
```

#### Hermes Agent (`~/.hermes/config.yaml`)

```yaml
mcp_servers:
  fleetcom:
    command: uv
    args: ["run", "--directory", "/path/to/fleetcom", "fleetcom-mcp"]
    env:
      FLEETCOM_DB_PATH: /path/to/fleetcom.db
```

`FLEETCOM_DB_PATH` defaults to `~/Claude/-hermes/fleetcom.db` if unset.

---

## Tools Reference

| Tool | Purpose |
|------|---------|
| `task_create` | Add a task (summary, owner, due, remind_at, status) |
| `task_list` | List tasks, filtered by status/owner, or `due_now=True` for what's due |
| `task_update` | Change a task's fields; `status='blocked'` requires `blocked_reason` |
| `task_delete` | Remove a task |
| `task_accept` | CoS accepts a completed task's result (sets `reviewed=1`) |
| `task_reject` | CoS bounces a completed task back to `in-progress` with a note |
| `event_create` | Add a calendar event |
| `event_list` | List events whose start falls in a date range |
| `event_update` | Change an event's summary/time/location |
| `event_delete` | Remove an event |
| `contact_create` | Add a contact to the shared address book |
| `contact_search` | Search contacts by name or tag |
| `contact_update` | Change a contact's fields |
| `contact_delete` | Remove a contact |
| `agenda_today` | Tasks due now + events happening today, in one call |

---

## Architecture

- **Python + stdlib `sqlite3`**, official `mcp` SDK (`MCPServer`), stdio transport.
- **Two content tables**, `tasks` and `events`, plus `contacts` — no unified schema, no shared claim/lease columns.
- **WAL mode** for safe concurrent access from multiple agent processes.
- **Zero daemons:** the process starts when an agent connects and exits when it disconnects.

---

## License

[MIT](LICENSE) © 2026 Jonathan Perel
