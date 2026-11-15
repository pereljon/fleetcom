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
| Older schema version | `db.connect` without `create` on a fleetcom file whose `schema_version` holds 0 | Opens, so `migrate` can upgrade it (added for review finding R2) |
| Write lock held | Another connection takes `BEGIN IMMEDIATE` on a migrated WAL file before `db.connect` without `create` runs | Opens without waiting for the lock |
| Startup, zero-byte file | `server.main` with `--db` naming a zero-byte file | `SystemExit` whose message says `cannot open database` and `not a fleetcom database`; the file stays at 0 bytes |

The zero-byte, foreign-file, and startup tests must fail on the current code before the fix lands. The create and write-lock tests pass on the current code, and guard against the fix refusing too much.

## Live checks

After the promote and client restarts (plan, Task E3): run the installed `fleetcom-mcp --db <scratch folder>/empty.db < /dev/null` on a zero-byte file. Expect exit status 1, the `not a fleetcom database` message, and a file still at 0 bytes.

## Results

2026-11-14, on branch `existing-db-check`:

- On the old code, the zero-byte, foreign-file, and startup tests failed, and the create and write-lock tests passed.
- With the fix, `uv run pytest -q` gave 125 passed, and 126 after the R2 test. `ruff check` and `ruff format --check` were clean.
- `uv run fleetcom-mcp --db <scratch>/empty.db < /dev/null` on a zero-byte file exited 1 with the `not a fleetcom database` message, and the file stayed at 0 bytes.

Live, 2026-11-15, after release 0.2.0 (`3b693f3`): the installed binary on a zero-byte scratch file exited 1 with "not a fleetcom database" and left the file at 0 bytes.

## Review findings

A subagent reviewed the design and this plan on 2026-11-14 (Opus, high effort). It applied the design to a scratch copy, where the full suite passed, and found no correctness defect.

| ID | Finding | Resolution |
|----|---------|------------|
| D1 | Design step 1 named an order the code does not have: `busy_timeout` is set after `_enable_wal` | Step 1 now moves the pragma first |
| D2 | The existing lock test takes the lock after `connect`, so it does not cover the check | New write-lock row takes the lock before `connect` |
| D3 | The create row passes on the current code, so "must fail first" was wrong for it | The plan names which tests must fail first |

The reviewer also found by experiment that a truncated or corrupt file is refused through the existing `sqlite3.DatabaseError` handler, and a second server during another's creation is refused cleanly (recorded under Interface change in the design).

A subagent reviewed `dfd4bc7` before the merge on 2026-11-14 (Opus, high effort). It found no blocker. Each new test caught at least one targeted mutation of the new code. Eight servers starting together without `create` on a live database with a held write lock failed 0 of 160 times.

| ID | Finding | Evidence | Resolution |
|----|---------|----------|------------|
| R1 | A first `--create-db` run killed between the schema DDL and the `schema_version` insert leaves a file that the next normal start refuses; `main` re-ran `migrate` and repaired it | Scratch run that killed the child at the insert | Not changed: the window is one statement long, and the error's advice works, since one more `--create-db` run repairs the file. Recorded under Interface change in the design |
| R2 | Design step 5 had no test: requiring the current version exactly passed every test | Mutation | Test added for a file with version 0 |
| R3 | The `--create-db` help text said only "create the database if it does not exist" | Code read of `server.py` | Help text now also names setting up an existing empty file |
