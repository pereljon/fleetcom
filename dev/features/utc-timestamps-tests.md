# UTC timestamps tests

Owns: the test plan and review findings for UTC timestamps. Does NOT hold the design (`utc-timestamps.md`).

Tests use temp databases and no sleeps. A test that holds a write lock sets `busy_timeout = 0` on the connection under test, so a wait fails at once. Each in-memory MCP call runs under `asyncio.wait_for` with a 10-second timeout.

## Baseline

On branch `utc-timestamps` at `923a5e8`, 2026-11-14: `uv run pytest -q` gave 126 passed, and `ruff check` and `ruff format --check` were clean.

## Automated tests

| Area | Case | Expected result |
|------|------|-----------------|
| `to_utc` | `-08:00`, `-08:00` across midnight, `+05:30`, `Z`, no offset, space separator, date only, fractional seconds, `None` | The same instant as `YYYY-MM-DDTHH:MM:SSZ`; `None` stays `None` |
| `to_utc`, clear | `""` | `None` |
| `to_utc`, reject | `"next tuesday"`, and `0001-01-01T00:00:00+05:00` (overflows in UTC) | `ValueError` naming ISO-8601 |
| `normalize_times` | A dict with time fields and another field | Only the named fields change |
| `normalize_times`, error | An unparseable `remind_at` | `ValueError` naming `remind_at` |
| Task create | `due` with `-08:00`, `remind_at` date only | Stored as `17:00:00Z` and `00:00:00Z` |
| `due_now` | A task due later today in `-08:00`, earlier than now only as a string | Not in `due_now` |
| Clear `due` | `tasks.update(due="")` on a task that is overdue | `due` is null; the task leaves `due_now` |
| Reject on create | `tasks.create(due="soon")` | `ValueError` naming `due` |
| Event times | `events.create` with offset `start` and `end` | Both stored in UTC |
| Range bounds | `events.list_in_range` with offset bounds around a UTC event | The event is returned |
| Tool error | `task_create(remind_at="tomorrow-ish")` through the in-memory client | `is_error` is true; the text names `remind_at` |
| Clear through a tool | `task_update(due="")` and `event_update(end="")` through the client | `ok` is true; the field reads back null |
| Repair | Rows with an offset `due`, a `""` `remind_at`, an unparseable `due`, and an event with offset `start` and `end` | Three rows fixed; the unparseable row listed as left with its table and id and unchanged; `updated_at` unchanged; event times in UTC |
| Repair, clean | A database with only UTC times | Nothing fixed, nothing left |
| Repair, locked | Another connection holds `BEGIN IMMEDIATE`; repair with `busy_timeout = 0`, then again after release | First call fixes nothing and raises nothing; second fixes the row |
| Startup message | `server.main` on a database with one fixed and one unreadable row, with `server.build_server` replaced by a stub whose `run` returns at once | stderr names the fixed count, and names the unreadable row by table and id, not by value |

Every case above must fail on the current code before the fix lands, except the clean-repair case, which needs the new function to exist and guards against the repair writing on a clean database.

## Live checks

After the promote and client restarts (plan, Task E3):

1. Re-run the read-only count script on the live database. Expect no value outside `now_iso()` format.
2. Check one server's stderr log for the `normalized times in N rows` line, and confirm no `could not normalize` line.
3. Create a task with `due` in `-08:00` through a live client, read it back in UTC, then delete it.

## Results

Not run yet.

## Review findings

None yet.
