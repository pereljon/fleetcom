# Changelog

All notable changes to this project will be documented in this file.

## Unreleased

Nothing in this project has been released yet; the entries below reflect the current unreleased state, not a chronological log (an earlier Go implementation with atomic task-claiming, an agent directory, and an RFC-2119 policy engine was fully replaced before ever shipping — see `docs/ISSUES.md` (Decisions), 2026-09-13 restart).

- Add `src/fleetcom`: Python package with SQLite storage (WAL) for three tables (`tasks`, `events`, `contacts`) via a shared generic CRUD engine. `tasks` absorbs what a standalone `reminders` table did in an earlier iteration (`remind_at`), plus `blocked`/`blocked_reason` and a `completed`/`reviewed` two-axis completion model — see `docs/ISSUES.md` (Decisions) for the design review behind both.
- Add `fleetcom-mcp`: stdio MCP server (official `mcp` SDK) exposing 15 tools — plain create/list/update/delete over tasks/events/contacts, `task_accept`/`task_reject` for the review gate, and `agenda_today` aggregating tasks due now with today's events.
- Add `--db` CLI flag (`FLEETCOM_DB_PATH` env var still works; the flag takes precedence).
- Change a missing database from a silent new empty database to a startup error (exit status 1). Add `--create-db` to create one on purpose.
- Refuse an existing file that is not a fleetcom database (an empty file, or another application's SQLite file) without `--create-db`, and leave it unchanged. `--create-db` sets up an existing empty file.
- Expand `~` in `--db` and `FLEETCOM_DB_PATH`. It was taken literally before.
- Create a new database file with mode 600 in a mode 700 folder (with `--create-db`).
- Return `database is locked` from a tool call as a tool error with a retry hint.
- Stop writing `schema_version` at startup when it is already current, so a held write lock no longer crashes startup.
- Change the default database path to `~/.fleetcom/fleetcom.db`.
- Fix list tools cutting rows silently: add `truncated` to `task_list`, `event_list`, and `contact_search`, and `tasks_truncated` and `events_truncated` to `agenda_today`.
- Change the default `task_list` order to active, then unreviewed, then reviewed, newest first in each group.
- Reject `limit` outside 1 to 1,000,000. `limit=-1` no longer returns every row.
- Fix servers crashing with `database is locked` when they start together on a new database file.
- Fix a rejected write leaving its transaction open, which blocked writes from every other server.
- Fix concurrent tool calls interleaving on the shared connection, which lost writes already reported as successful.
- Fix `task_accept` and `task_reject` overwriting a concurrent `description` edit.
- Fix `due_now` and `agenda_today` misjudging times with a UTC offset. Times are stored in UTC, and existing rows are repaired at every startup. Rows that cannot be repaired are named by table and id on stderr.
- Reject a `due`, `remind_at`, `start`, or `end` that is not ISO-8601. It was stored and never came due.
- Let `""` clear `due`, `remind_at`, and `end`. `due=""` used to count as overdue forever.
- Make `event_list` name a bad bound in its error and refuse an empty one.
- Fix `reviewed` surviving when a task leaves `completed`.
- Fix update, delete, accept, and reject tools returning `ok=false` for an unknown id: they now return an error that names the id (`crud.NotFoundError`), so `ok=false` means only that nothing changed or the task is not completed.
- Include overdue `due` dates in `due_now` and `agenda_today`.
- Pin `mcp` to `>=2.2,<2.3`.
- Fix `scripts/promote.sh`: pin Python 3.11, and stop `ln` writing a link inside the deployed skill.
- Add `src/skills/fleetcom/`: fleet-facing skill doc and per-tool usage reference.
- Deployment: install via `uv tool install --from . fleetcom` for a stable, absolute-path launcher, rather than running from the development checkout.
- Add `fleetcom-mcp --version`.
- Fix `scripts/promote.sh`: it requires a clean `main`, a current `uv.lock`, and passing tests and linters, and refuses unknown arguments. It installs with `uv.lock` constraints and checks the installed version before swapping the skill. The skill swap leaves the old skill if the copy fails. It stamps `mcp.promoted-sha` only after an install.
