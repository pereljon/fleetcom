# Existing database check

Owns: the design for refusing an existing file that is not a fleetcom database unless `--create-db` is passed. Does NOT hold test cases or review findings (`existing-db-check-tests.md`).

Status: designing on branch `existing-db-check`. Investigated against `main` at `104283d`, Python 3.11 with its bundled SQLite. Source: finding S1 in `docs/reviews/2026-11-14-fable-review.md`.

## Goal

A server started without `--create-db` must open only an existing fleetcom database. An empty file or another application's SQLite file at the `--db` path must stop startup with a message, and stay unchanged. This completes the goal of `dev/features/db-open-safety.md`.

## Verified facts

- `db.connect` refuses a missing file, but accepts any existing file (`src/fleetcom/db.py`, `connect`). `server.main` then calls `db.migrate`, which runs the schema DDL whenever `schema_version` is absent.
- Starting `fleetcom-mcp --db <zero-byte file>` exits 0 and turns the file into an empty fleetcom database of 53,248 bytes (reproduced 2026-11-14 on `db-open-safety`, and by the Fable review). The same happens to an SQLite file that holds other tables.
- The old default path once held a zero-byte `fleetcom.db` (`docs/ISSUES.md`, Decisions, 2026-11-01), so this case has occurred on this machine.
- `connect` switches the file to WAL (write-ahead log) mode before anything reads it. On another application's file, that switch is itself a change.
- Opening a zero-byte file or a foreign SQLite file with `mode=rw` and reading `schema_version` raises `no such table`. The zero-byte file stays at 0 bytes, and the foreign file keeps its journal mode (scratch run, 2026-11-14).
- `server.main` already turns `sqlite3.DatabaseError` from `connect` into exit status 1 with `fleetcom-mcp: cannot open database <path>: <reason>`.

## Design

1. In `db.connect`, move `PRAGMA busy_timeout` above `_enable_wal`. When `create` is false, read the stored schema version right after it, before `_enable_wal`.
2. If `_stored_version` returns `None`, close the connection and raise `sqlite3.DatabaseError("not a fleetcom database (no schema_version); check the path, and pass --create-db only to set up a new database")`.
3. `server.main` needs no change: its existing `sqlite3.DatabaseError` handler prints the path and the reason, and exits with status 1.
4. With `create=True`, `connect` skips the check, and `migrate` initializes the file as today. This keeps `--create-db` working on a zero-byte file and on a new file.
5. A database whose stored version is older than `SCHEMA_VERSION` still passes the check, so `migrate` can upgrade it.

The check reads before the WAL switch, so a refused file is never changed. The read runs under the busy timeout, so a server that holds the write lock on a live WAL database does not block it.

## Interface change

- An existing empty or non-fleetcom file at the database path becomes a startup error unless `--create-db` is passed.
- A live fleetcom database is unaffected. The schema does not change.
- A server started without `--create-db` while another server is still creating the file exits with the same error, until the creating server commits `migrate`. `--create-db` is a one-time setup run, so this overlap is narrow (design review, 2026-11-14).
- `--create-db` on another application's SQLite file still adds the fleetcom tables to it. The flag means "set up this file", and the user passes it on purpose.

## Decisions

### 2026-11-14 - Check for `schema_version`, not for any table (`ok`)
Why: `schema_version` is written only by `migrate`, so its presence identifies a fleetcom database. The user approved building the fix on its own branch on 2026-11-14.
Rejected: checking only for a zero-byte file, which misses another application's SQLite file. Rejected: checking in `server.main` after `connect`, because `connect` has already switched the file to WAL by then.
