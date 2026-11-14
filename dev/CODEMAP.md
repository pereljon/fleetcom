# CODEMAP - where things live

Owns: a one-line purpose for each function or module, for locating code. Does NOT hold logic flow (dev/SKELETON.md) or architecture (dev/IMPLEMENTATION-SPEC.md).
Maintain: add a row when code lands; keep each purpose to one line.

| function/module | one-line purpose |
|-----------------|------------------|
| `src/fleetcom/db.py` | schema DDL for tasks/events/contacts; `connect(path, *, create=False)` (expands `~`, refuses a missing file, and an existing file with no `schema_version`, unless `create`; opens with `mode=rw`), `_enable_wal` (bounded retry of the WAL switch), `_stored_version` (reads `schema_version`, or `None` on a new file), `migrate` (skips its write when the version is current), `default_db_path` |
| `src/fleetcom/util.py` | `new_id` (uuid4), `now_iso` (UTC RFC3339-ish timestamp), `capped` (fetches `limit + 1` rows to report truncation and validates `limit`) |
| `src/fleetcom/crud.py` | generic, injection-safe CRUD engine (`create`/`get`/`update`/`delete`) shared by all entities; `update` and `delete` raise `NotFoundError` (a `ValueError`) when no row has the id; field names are validated against a fixed allow-list before being interpolated into SQL identifier positions |
| `src/fleetcom/tasks.py` | task CRUD (absorbs former reminders via `remind_at`); `list(due_now=True)` bespoke query; `accept`/`reject` bespoke status-gated transitions |
| `src/fleetcom/events.py` | event CRUD + `list_in_range` (start between two ISO timestamps) |
| `src/fleetcom/contacts.py` | contact CRUD + `search` (substring match on name/tags, with LIKE-wildcard escaping) |
| `src/fleetcom/agenda.py` | `today(conn)`: cross-entity aggregator combining `tasks.list(due_now=True)` and `events.list_in_range` for the current day |
| `src/fleetcom/server.py` | `build_server(conn)` registers all 15 MCP tools as closures over one connection; `_anticipated` decorator converts anticipated storage errors (bad enum, CHECK violation, unknown field) into `ToolError` so callers see the real reason, and maps `database is locked` to a `ToolError` with a retry hint; `_parse_args` parses `--db`/`FLEETCOM_DB_PATH` precedence and `--create-db`; `main()` is the `fleetcom-mcp` entry point and exits with status 1 when the database cannot be opened |
| `src/skills/fleetcom/SKILL.md` | fleet-facing skill doc: fleetcom vs. memory/chat routing rule, task conventions (handles, owner="user" meaning, accept/reject), wiring notes |
| `src/skills/fleetcom/references/tools.md` | one-line usage example per registered MCP tool, grepped from `server.py` rather than hand-counted |
