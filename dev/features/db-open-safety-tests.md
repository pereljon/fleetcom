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
| Startup, not a database | `server.main` with `--db` naming a file that is not SQLite (added for review finding R1) | `SystemExit` whose message says it cannot open the database |
| Lock in a tool call | Another connection holds `BEGIN IMMEDIATE`; call `task_create` | `is_error` is true; the text contains `locked` and `retry` |
| Lock at startup | Another connection holds `BEGIN IMMEDIATE`; `migrate` on a current database | Returns without error |
| Concurrent creation | Six processes open one new file with `create=True` at once, 20 rounds | All succeed, and the file is in WAL mode (existing test, now passing `create=True`) |

The new tests must fail on the current code before the fix lands.

Every existing `db.connect` on a new file passes `create=True`, including the shared fixture in `tests/conftest.py` and `_open_at_barrier` in `tests/test_db.py`. The second open in `test_rejected_write_releases_the_write_lock` (`tests/test_tasks.py`) reaches a file that exists by then, so it does not pass the flag.

## Live checks

After the promote and client restarts (plan, Task E3):

1. Run the installed `fleetcom-mcp --db <scratch folder>/does-not-exist.db`. Expect exit status 1, the `--create-db` message, and no file created.
2. Confirm every client still reaches the live database with one `task_list` each from Hermes, Claude Code, and Codex.

## Results

2026-11-14, on branch `db-open-safety`:

- `uv run pytest -q`: 120 passed. `ruff check` and `ruff format --check`: clean.
- On the old code, every test errored, because the shared fixture passes `create=True`. Each new test was instead checked against a targeted mutation of the new code, and each mutation failed at least one test (review below).
- The README's `--create-db` example, run on a scratch path with stdin closed, created the folder with mode 700 and the file with mode 600, and exited 0. A missing path exited 1 with the `--create-db` message and created nothing.

Live, 2026-11-15, after release 0.2.0 (`3b693f3`):

- The installed `fleetcom-mcp` on a missing scratch database exited 1 with the `--create-db` message and created no file.
- Claude Code, Hermes, and Codex each reached the live database with one `task_list`.

## Review findings

A subagent reviewed `e932aaa` before the merge on 2026-11-14 (Opus, high effort), limited to findings with a clear execution path. It found no blocker.

| ID | Finding | Evidence | Resolution |
|----|---------|----------|------------|
| R1 | A file that is not a database, or `--create-db` in a read-only folder, printed a traceback instead of the one-line message | Subprocess runs of `main` | `main` catches `OSError` and `sqlite3.DatabaseError`; test added for a file that is not a database |
| R2 | No test covers `?mode=rw`; removing it passes every test | Mutation | Not changed: it matters only if the file disappears between the existence check and the open |
| R3 | Under a regression, the home-folder test leaves a `~` folder in the working folder, and its second assertion cannot fail | Mutation left `./~/fleetcom.db` | The test changes to the temp folder first |

The reviewer also confirmed by experiment:

- Symlinked folders and files reach the same rows, `-wal` file, and write lock.
- `create=True` keeps the mode of an existing file or folder.
- With another connection holding the write lock, startup on a current database took no measurable time.
- The lock mapping covers `task_accept`, `task_reject`, `task_update`, `contact_create`, and `event_delete`, and leaves no transaction open.
