# CODEMAP - where things live

Owns: a one-line purpose for each function or module, for locating code. Does NOT hold logic flow (dev/SKELETON.md) or architecture (dev/IMPLEMENTATION-SPEC.md).
Maintain: add a row when code lands; keep each purpose to one line.

| function/module | one-line purpose |
|-----------------|------------------|
| `src/fleetcom/db.py` | schema DDL for tasks/events/contacts; `connect`, `migrate`, `default_db_path` |
| `src/fleetcom/util.py` | `new_id` (uuid4), `now_iso` (UTC RFC3339-ish timestamp) |
| `src/fleetcom/crud.py` | generic, injection-safe CRUD engine (`create`/`get`/`list_rows`/`update`/`delete`) shared by all entities; field/filter names are validated against a fixed allow-list before being interpolated into SQL identifier positions |
| `src/fleetcom/tasks.py` | task CRUD (absorbs former reminders via `remind_at`); `list(due_now=True)` bespoke query; `accept`/`reject` bespoke status-gated transitions |
| `src/fleetcom/events.py` | event CRUD + `list_in_range` (start between two ISO timestamps) |
| `src/fleetcom/contacts.py` | contact CRUD + `search` (substring match on name/tags, with LIKE-wildcard escaping) |
| `src/fleetcom/agenda.py` | `today(conn)`: cross-entity aggregator combining `tasks.list(due_now=True)` and `events.list_in_range` for the current day |
| `src/fleetcom/server.py` | `build_server(conn)` registers all 15 MCP tools as closures over one connection; `_anticipated` decorator converts anticipated storage errors (bad enum, CHECK violation, unknown field) into `ToolError` so callers see the real reason; `_resolve_db_path` handles `--db`/`FLEETCOM_DB_PATH` precedence; `main()` is the `fleetcom-mcp` entry point |
| `skills/fleetcom/SKILL.md` | fleet-facing skill doc: fleetcom vs. memory/chat routing rule, task conventions (handles, owner="user" meaning, accept/reject), wiring notes |
| `skills/fleetcom/references/tools.md` | one-line usage example per registered MCP tool, grepped from `server.py` rather than hand-counted |
