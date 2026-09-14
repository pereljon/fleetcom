# Implementation Spec

Owns: architecture, configuration reference, design decisions, and deprecation policy. The authoritative "why it is built this way" document.
Maintain: update when architecture, settings, or behavior changes.

## Architecture

Fleetcom is a single Python process, run on demand by an MCP client (Claude Code, a Hermes profile), speaking stdio JSON-RPC via the official `mcp` SDK's `MCPServer`. It has no daemon, no network port, and no background task.

Storage is one SQLite file, opened once per process with `PRAGMA journal_mode=WAL`, `busy_timeout=5000`, `foreign_keys=ON`. Three independent tables hold the primitives (`tasks`, `events`, `contacts`); there is no unified "item" table and no cross-entity foreign keys — each row is self-contained aside from plain-string, nullable `owner`/`created_by` fields.

`src/fleetcom/crud.py` is a small generic engine (`create`/`get`/`list_rows`/`update`/`delete`) parameterized by table name and an allow-listed field set, used by all three entity modules (`tasks.py`, `events.py`, `contacts.py`). Each entity module adds its own bespoke queries where plain equality filtering isn't enough (`tasks.list(due_now=True)`, `events.list_in_range`, `contacts.search`), and `tasks.accept`/`tasks.reject` bypass the generic engine entirely for status-gated transitions the engine has no concept of.

`src/fleetcom/agenda.py` aggregates across `tasks` and `events` for a single "what needs attention today" query.

`src/fleetcom/server.py` wires the entity modules into 15 MCP tools, each a thin adapter with no business logic of its own, wrapped in `_anticipated` so anticipated storage-layer rejections reach the caller with a real message.

## Config Reference

| Setting | Source | Default |
|---|---|---|
| Database path | `FLEETCOM_DB_PATH` env var | `~/Claude/-hermes/fleetcom.db` |
| Python version | `pyproject.toml` `requires-python` | `>=3.11` |
| MCP SDK | `mcp` dependency | latest (currently 2.x, `MCPServer` API) |

No other configuration exists. There is no policy engine, no agent registry, and no lease/claim tuning (lease minutes, TTLs) because none of those concepts exist in this design.

## Design Decisions

See `context/decisions.md` for the dated log, including the 2026-09-13 restart. Summary of what's different from the original (Go, Mission-Control-style) design this replaced:

- **No atomic task claiming.** Ownership is a plain mutable string column. This is a shared office notebook for a small, trusted fleet, not a race-safe work queue for a large pool of untrusted, concurrently-competing workers.
- **No RFC-2119 fleet policy engine.** Fleet-wide conventions stay in `CLAUDE.md`; Fleetcom doesn't distribute or enforce them.
- **No agent directory / heartbeat table.** Nothing here tracks who's online or what capabilities an agent has.
- **Separate tables per distinct concept, not one unified `office_items` table.** Simpler DDL per entity, no shared CHECK-constraint matrix.
- **Reminders are not their own table.** Merged into `tasks` (2026-09-13, four-round design review in `context/decisions.md`) after concluding a "completion" bit only ever means creator-ownership, jP-ownership, or system delivery metadata — none of which need a fourth primitive. `task_list(due_now=True)` ports the old `reminder_list_due` query exactly. Still pull-only: no push notifications, no background polling loop.
- **Completion and review are separate axes.** `status='completed'` (anyone can set, via generic `task_update`) and `reviewed=1` (only via the bespoke `tasks.accept`, gated on current status) model "the owner claims it's done" and "someone else confirmed it" as independent facts, not sequential enum values — see `dev/SKELETON.md` for why this couldn't be done as a plain CHECK-constraint enum extension.

## Deprecation Policy

Pre-1.0, no backward-compatibility guarantees are made across tool signatures or the database schema. The prior Go implementation (atomic claiming, `office_items`, `policies`, `activity_log`, agent directory) was fully removed rather than deprecated in place — see the 2026-09-13 restart entry in `context/decisions.md` for why.
