# Database open safety

Owns: the design for refusing a missing database file, expanding `~` in database paths, private modes on new database files, and lock errors at startup and in tool calls. Does NOT hold test cases or review findings (`db-open-safety-tests.md`).

Status: merged to `main` on 2026-11-14; shipped in 0.2.0 (`3b693f3`), promoted 2026-11-14. Finding S1 of `docs/reviews/2026-11-14-fable-review.md`, an existing empty or non-fleetcom SQLite file initialized without `--create-db`, is fixed by `dev/features/existing-db-check.md`. Investigated against `main` at `a177129`, SQLite 3.53.1, and Python 3.11.15. Plan: `docs/superpowers/plans/2026-11-14-status-review-fixes.md`, Branch B.

## Goal

A server must start on the live database or fail with a message that says why. It must never start on a new, empty database because of a mistyped path. A caller that hits a held write lock must see the reason and know to retry.

## Verified facts

- `db.connect` creates the parent folder and the file for any path (`src/fleetcom/db.py:93-103`). A mistyped `--db` or `FLEETCOM_DB_PATH` starts an empty database. A Hermes pipeline wrote to such a second database on 2026-11-13 (`docs/ISSUES.md`, Bugs).
- `db.connect` does not expand `~`. An MCP client starts the server without a shell, so `--db ~/.fleetcom/fleetcom.db` names a folder literally called `~` under the client's working folder. The README's config examples pass exactly that path (`README.md:62`, `:74`).
- A database created this way gets folder mode 755 and file mode 644 under umask 022, although it can hold personal data (`docs/ISSUES.md`, Planned).
- `_anticipated` catches `ValueError` and `sqlite3.IntegrityError` only (`src/fleetcom/server.py:35`). `database is locked` is an `OperationalError`, so the caller sees "Error executing tool X" with no reason.
- `db.migrate` writes `schema_version` on every startup (`db.py:109-114`). If another server holds the write lock past the busy timeout, startup crashes. `CREATE TABLE IF NOT EXISTS` on existing tables needs no write lock; only the `schema_version` write does (plan review experiment, 2026-11-14).
- `Path.touch(exist_ok=True)` opens with `O_CREAT` and without `O_EXCL`, so concurrent servers creating one new file cannot fail on it. SQLite gives the `-wal` and `-shm` files the main file's mode. `Path.resolve().as_uri()` with `?mode=rw` opens paths that hold spaces, `?`, `#`, `%`, and non-ASCII characters (plan review experiments, 2026-11-14).
- SQLite opened with `mode=rw` on a folder raises `OperationalError`, not `FileNotFoundError` (plan review experiment).

## Design

1. `db.connect(path, *, create=False)` expands `~` with `Path(path).expanduser()`.
2. With `create=False`, `db.connect` raises `FileNotFoundError("database not found: <path> (pass --create-db to create it)")` when the file does not exist.
3. With `create=True`, `db.connect` creates a missing parent folder with mode 700 and a missing file with mode 600. An existing folder or file keeps its mode.
4. `db.connect` opens the file with the URI `file:<absolute path>?mode=rw`, so SQLite never creates a file itself.
5. `server._parse_args(argv)` replaces `_resolve_db_path`. It adds the `--create-db` flag and resolves the path from `--db`, then `FLEETCOM_DB_PATH`, then the default.
6. `server.main` exits with status 1 and a one-line message on stderr when `db.connect` raises `FileNotFoundError`, another `OSError` (such as a read-only folder under `--create-db`), or `sqlite3.DatabaseError` (such as a file that is not a database). The MCP client then reports that the server failed to start.
7. `_anticipated` turns an `OperationalError` whose message contains `locked` into a `ToolError` that says another fleetcom server held the write lock and that the caller should retry. Other `OperationalError`s propagate as before.
8. `db.migrate` reads `schema_version` first. When the stored version equals `SCHEMA_VERSION`, it returns without writing. A new file runs the DDL and the stamp as before.

## Interface change

- A missing database file is a startup error unless `--create-db` is passed. Every client config passes `--db` with the path of the existing live database (db-move cutover, 2026-11-01), so no config needs the flag (inferred; the user or hermes-manager confirms before the promote, plan Task E1).
- `~` in `--db` or `FLEETCOM_DB_PATH` now means the home folder. A config that passes `~/...` today writes to a folder literally named `~`; after the change, it reaches the real path. The same confirmation in Task E1 checks whether any config does this.
- `database is locked` becomes a tool error with a reason. The response shape for success is unchanged.
- The schema does not change, so old and new servers can share the database.

## Decisions

### 2026-11-14 - A missing database is an error unless `--create-db` is passed (`ok`)
Why: a mistyped path must fail, not start an empty database. Recorded in `docs/ISSUES.md` (Decisions).
Rejected: keeping silent auto-create. Rejected: creating a missing file only for the default path, because the default path is a mistake too when the live database is elsewhere.

### 2026-11-14 - Private modes only on newly created files (`ok`)
Why: the live database already has mode 600 in a mode 700 folder from the db-move runbook. The user approved this on 2026-11-14 (plan, Q4).
Rejected: changing modes on an existing file at startup.
