# Changelog

All notable changes to this project will be documented in this file.

## Unreleased

Nothing in this project has been released yet; the entries below reflect the current unreleased state, not a chronological log (an earlier Go implementation with atomic task-claiming, an agent directory, and an RFC-2119 policy engine was fully replaced before ever shipping — see `context/decisions.md`, 2026-09-13 restart).

- Add `src/fleetcom`: Python package with SQLite storage (WAL) for three tables (`tasks`, `events`, `contacts`) via a shared generic CRUD engine. `tasks` absorbs what a standalone `reminders` table did in an earlier iteration (`remind_at`), plus `blocked`/`blocked_reason` and a `completed`/`reviewed` two-axis completion model — see `context/decisions.md` for the design review behind both.
- Add `fleetcom-mcp`: stdio MCP server (official `mcp` SDK) exposing 15 tools — plain create/list/update/delete over tasks/events/contacts, `task_accept`/`task_reject` for the review gate, and `agenda_today` aggregating tasks due now with today's events.
- Add `--db` CLI flag (`FLEETCOM_DB_PATH` env var still works; the flag takes precedence).
- Add `skills/fleetcom/`: fleet-facing skill doc and per-tool usage reference.
- Deployment: install via `uv tool install --from . fleetcom` for a stable, absolute-path launcher, rather than running from the development checkout.
