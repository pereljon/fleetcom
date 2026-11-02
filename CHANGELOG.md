# Changelog

All notable changes to this project will be documented in this file.

## Unreleased

Nothing in this project has been released yet; the entries below reflect the current unreleased state, not a chronological log (an earlier Go implementation with atomic task-claiming, an agent directory, and an RFC-2119 policy engine was fully replaced before ever shipping — see `docs/ISSUES.md` (Decisions), 2026-09-13 restart).

- Add `src/fleetcom`: Python package with SQLite storage (WAL) for three tables (`tasks`, `events`, `contacts`) via a shared generic CRUD engine. `tasks` absorbs what a standalone `reminders` table did in an earlier iteration (`remind_at`), plus `blocked`/`blocked_reason` and a `completed`/`reviewed` two-axis completion model — see `docs/ISSUES.md` (Decisions) for the design review behind both.
- Add `fleetcom-mcp`: stdio MCP server (official `mcp` SDK) exposing 15 tools — plain create/list/update/delete over tasks/events/contacts, `task_accept`/`task_reject` for the review gate, and `agenda_today` aggregating tasks due now with today's events.
- Add `--db` CLI flag (`FLEETCOM_DB_PATH` env var still works; the flag takes precedence).
- Change the default database path to `~/Claude/-hermes/db/fleetcom.db`, the live database.
- Fix a rejected write leaving its transaction open, which blocked writes from every other server.
- Fix `reviewed` surviving when a task leaves `completed`.
- Include overdue `due` dates in `due_now` and `agenda_today`.
- Pin `mcp` to `>=2.2,<2.3`.
- Fix `scripts/promote.sh`: pin Python 3.11, and stop `ln` writing a link inside the deployed skill.
- Add `src/skills/fleetcom/`: fleet-facing skill doc and per-tool usage reference.
- Deployment: install via `uv tool install --from . fleetcom` for a stable, absolute-path launcher, rather than running from the development checkout.
