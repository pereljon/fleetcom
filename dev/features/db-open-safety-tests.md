# Database open safety tests

Owns: the test plan and review findings for database open safety. Does NOT hold the design (`db-open-safety.md`).

Tests use temp databases and no sleeps. A test that holds a write lock sets `busy_timeout = 0` on the connection under test, so a wait fails at once instead of blocking. Each in-memory MCP call runs under `asyncio.wait_for` with a 10-second timeout.

## Baseline

On `main` at `a177129`, 2026-11-14: `uv run pytest -q` gave 110 passed, and `ruff check` and `ruff format --check` were clean.

## Automated tests

| Area | Case | Expected result |
|------|------|-----------------|
| Missing file | `db.connect` on a path in a missing folder, without `create` | `FileNotFoundError` naming `--create-db`; no folder or file created |
| New file | `db.connect(create=True)` in a new folder, then `migrate` | Folder mode 700; file and `-wal` file mode 600 |
| Existing file | `db.connect` without `create` on a file made earlier | Opens, and reads `schema_version` |
| Home folder | `db.connect("~/fleetcom.db", create=True)` with `HOME` set to a temp folder | The file is in the temp folder; no folder named `~` exists |
| Flag precedence | `_parse_args` with `--db` and `FLEETCOM_DB_PATH` both set, then only the variable | `--db` wins, then the variable (existing tests, renamed) |
| Flag default | `_parse_args([])` and `_parse_args(["--create-db"])` | `create_db` is false, then true |
| Startup, missing file | `server.main` with `--db` naming a missing file | `SystemExit` whose message names `--create-db`; no file created |
| Startup, folder | `server.main` with `--db` naming a folder | `SystemExit` whose message says it cannot open the database |
| Lock in a tool call | Another connection holds `BEGIN IMMEDIATE`; call `task_create` | `is_error` is true; the text contains `locked` and `retry` |
| Lock at startup | Another connection holds `BEGIN IMMEDIATE`; `migrate` on a current database | Returns without error |
| Concurrent creation | Six processes open one new file with `create=True` at once, 20 rounds | All succeed, and the file is in WAL mode (existing test, now passing `create=True`) |

The new tests must fail on the current code before the fix lands.

Every existing `db.connect` on a new file passes `create=True`: `tests/conftest.py:8`, `tests/test_server.py:12` and `:253`, `tests/test_db.py:101`, `:114`, `:123`, and `:129`, and `tests/test_tasks.py:167`. `tests/test_tasks.py:169` opens a file that exists by then, so it stays as is.

## Live checks

After the promote and client restarts (plan, Task E3):

1. Run the installed `fleetcom-mcp --db <scratch folder>/does-not-exist.db`. Expect exit status 1, the `--create-db` message, and no file created.
2. Confirm every client still reaches the live database with one `task_list` each from Hermes, Claude Code, and Codex.

## Review findings

None yet.
