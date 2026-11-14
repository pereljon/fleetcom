# UTC timestamps

Owns: the design for storing `due`, `remind_at`, `start`, and `end` in UTC, rejecting unparseable times, clearing a time with `""`, and repairing stored rows at startup. Does NOT hold test cases or review findings (`utc-timestamps-tests.md`).

Status: designing on branch `utc-timestamps`. Investigated against `main` at `923a5e8`, Python 3.11. Plan: `docs/superpowers/plans/2026-11-14-status-review-fixes.md`, Branch C, which holds the code for each step.

## Goal

`due_now` and `agenda_today` must judge a time by its instant, whatever offset the caller wrote. A caller must be able to clear a time, and must get an error for a time fleetcom cannot read.

## Verified facts

- `tasks.list(due_now=True)` compares `due` and `remind_at` with `util.now_iso()` as strings (`src/fleetcom/tasks.py`, `list`). `2026-11-02T09:00:00-08:00` sorts as 09:00 UTC, not 17:00 UTC, so a negative offset flags a task early by the size of the offset.
- `due=""` sorts before every time, so it counts as overdue forever. `server._updated_fields` drops `None` but passes `""`, and no tool can clear a field today.
- Live database, read-only count on 2026-11-14 with a Python script that printed counts only: 65 tasks and 0 events. 37 `due` values and 37 `remind_at` values are not in `now_iso()` format; 28 and 29 of them sit on active tasks. Every one of them parses with `datetime.fromisoformat`, and none is `""`.
- Python 3.11 `datetime.fromisoformat` accepts `Z`, offsets, fractional seconds, date-only values, and a space separator. `astimezone` raises `OverflowError` for `0001-01-01T00:00:00+05:00` (checked 2026-11-14).
- The Fable review applied the plan's Branch C code to a scratch copy on 2026-11-14: 144 tests passed, `""` cleared `due` and `end`, and `start=""` returned a tool error (`docs/reviews/2026-11-14-fable-review.md`).

## Design

1. `util.to_utc(value)` returns `None` for `None` and for `""`. It parses any other value with `datetime.fromisoformat`, reads a value without an offset as UTC, and returns `%Y-%m-%dT%H:%M:%SZ`. Fractional seconds are dropped, and a date-only value becomes midnight UTC.
2. `to_utc` raises `ValueError("not an ISO-8601 time: <value>")` for a value it cannot parse or cannot convert to UTC. `_anticipated` turns it into a tool error.
3. `util.normalize_times(fields, names)` returns a copy with each named field passed through `to_utc`, and puts the field name in any error.
4. `tasks.create` and `tasks.update` normalize `due` and `remind_at`. `events.create` and `events.update` normalize `start` and `end`. `events.list_in_range` normalizes its two bounds.
5. `task_update(due="")` therefore stores `NULL`, which is the clearing path for `due`, `remind_at`, and `end`. `start` is `NOT NULL`, so `event_update(start="")` fails on the constraint and returns a tool error.
6. `db.normalize_stored_times(conn)` runs in `server.main` after `db.migrate`, at every startup:
   1. It selects only rows with a time that is not null and does not match the `now_iso()` pattern, so a clean database costs no write.
   2. It rewrites all of a row's time columns in one `UPDATE`, guarded by the old values, inside one `with conn:` block. One statement per row keeps the events `CHECK (end >= start)` true.
   3. It skips a value `to_utc` cannot read and a row whose `UPDATE` breaks a constraint, and lists both.
   4. If the write lock is held past the busy timeout, it skips the repair, and the next startup retries. Startup never fails because of the repair.
   5. It does not change `updated_at`, because the content did not change.
   6. It returns the number of rows fixed and the list of rows left, as `table id` pairs.
7. `server.main` prints `fleetcom-mcp: normalized times in N rows to UTC` to stderr when it fixed any row. When rows were left, it prints `fleetcom-mcp: could not normalize times in tasks <id>, ...`, naming each row by table and id and never by value. The MCP channel is stdout, so stderr is safe.

The repair runs at every startup because servers that have not restarted keep writing offset times until they do. The next new server fixes those rows.

## Interface change

- Stored times are UTC. A caller that reads back a time written with an offset gets the same instant in `Z` form.
- An unparseable time becomes a tool error that names the field. Today it is stored and never comes due.
- `""` clears `due`, `remind_at`, and `end`.
- `event_list` bounds are normalized the same way, so a bound with an offset selects by instant.
- The schema does not change. Old servers that are still running can share the database, and the repair fixes what they write.

## Decisions

### 2026-11-14 - Normalize to UTC on write and repair stored rows at startup (`ok`)
Why: the user chose normalizing over rejecting non-UTC values (`docs/ISSUES.md`, Decisions, 2026-11-14).
Rejected: a one-time repair script, because an old server still running can write offset times after it. Rejected: comparing with SQLite `datetime()` in queries, which leaves stored strings mixed and does not fix the events `CHECK`. Rejected: a schema version bump that runs the repair once, which has the same gap as the script.

### 2026-11-14 - `""` clears a time, and an unparseable time is an error (`ok`)
Why: the user approved both recommendations (plan, Q2 and Q3).
Rejected: rejecting `""` as unparseable, which leaves no way to clear a time.

### 2026-11-14 - The startup message names the rows it could not fix (`ok`)
Why: a count alone repeats on every startup and gives nobody a way to find the rows (Fable review, finding P2). Ids are UUIDs and carry no personal data; values can, so they are never printed.
Rejected: printing a count only, as the plan first proposed.
