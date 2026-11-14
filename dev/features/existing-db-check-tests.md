# Existing database check tests

Owns: the test plan and review findings for the existing database check. Does NOT hold the design (`existing-db-check.md`).

Tests use temp databases and no sleeps. Each test runs under the suite's timeout rules.

## Baseline

On `main` at `104283d`, 2026-11-14: `uv run pytest -q` gave 120 passed, and `ruff check` and `ruff format --check` were clean.

## Automated tests

| Area | Case | Expected result |
|------|------|-----------------|
| Zero-byte file | `db.connect` without `create` on a zero-byte file | `sqlite3.DatabaseError` naming `--create-db`; the file stays at 0 bytes |
| Foreign file | `db.connect` without `create` on an SQLite file holding only a `notes` table | `sqlite3.DatabaseError`; the file keeps journal mode `delete`, and still has only `notes` |
| Create on a zero-byte file | `db.connect(create=True)` on a zero-byte file, then `migrate` | Opens; `schema_version` reads 1 |
| Existing fleetcom file | `db.connect` without `create` on a migrated file | Opens (existing test `test_connect_opens_an_existing_file_without_create`) |
| Write lock held | Another connection takes `BEGIN IMMEDIATE` on a migrated WAL file before `db.connect` without `create` runs | Opens without waiting for the lock |
| Startup, zero-byte file | `server.main` with `--db` naming a zero-byte file | `SystemExit` whose message says `cannot open database` and `not a fleetcom database`; the file stays at 0 bytes |

The zero-byte, foreign-file, and startup tests must fail on the current code before the fix lands. The create and write-lock tests pass on the current code, and guard against the fix refusing too much.

## Live checks

After the promote and client restarts (plan, Task E3): run the installed `fleetcom-mcp --db <scratch folder>/empty.db < /dev/null` on a zero-byte file. Expect exit status 1, the `not a fleetcom database` message, and a file still at 0 bytes.

## Results

2026-11-14, on branch `existing-db-check`:

- On the old code, the zero-byte, foreign-file, and startup tests failed, and the create and write-lock tests passed.
- With the fix, `uv run pytest -q` gave 125 passed. `ruff check` and `ruff format --check` were clean.
- `uv run fleetcom-mcp --db <scratch>/empty.db < /dev/null` on a zero-byte file exited 1 with the `not a fleetcom database` message, and the file stayed at 0 bytes.

## Review findings

A subagent reviewed the design and this plan on 2026-11-14 (Opus, high effort). It applied the design to a scratch copy, where the full suite passed, and found no correctness defect.

| ID | Finding | Resolution |
|----|---------|------------|
| D1 | Design step 1 named an order the code does not have: `busy_timeout` is set after `_enable_wal` | Step 1 now moves the pragma first |
| D2 | The existing lock test takes the lock after `connect`, so it does not cover the check | New write-lock row takes the lock before `connect` |
| D3 | The create row passes on the current code, so "must fail first" was wrong for it | The plan names which tests must fail first |

The reviewer also found by experiment that a truncated or corrupt file is refused through the existing `sqlite3.DatabaseError` handler, and a second server during another's creation is refused cleanly (recorded under Interface change in the design).
