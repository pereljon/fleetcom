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
| Repair, commit | The repair test above, with the fixed value read back through a second connection | The value is committed and the connection under test holds no transaction |
| Repair, constraint | An event that breaks `CHECK (end >= start)` after conversion, beside a task with an offset `due` | The event is listed and unchanged; the task is fixed |
| Repair, partial row | A task with an unreadable `due` and an offset `remind_at` | `remind_at` is rewritten; the row counts as fixed and is also listed |
| `event_list`, bad bound | `events.list_in_range(start="x", ...)` | `ValueError` naming `start` |
| `event_list`, empty bound | `events.list_in_range(start="", ...)` | `ValueError`; no rows are returned |

Every case above must fail on the current code before the fix lands, except the clean-repair case, which needs the new function to exist and guards against the repair writing on a clean database.

## Live checks

After the promote and client restarts (plan, Task E3):

1. Re-run the read-only count script on the live database. Expect no value outside `now_iso()` format.
2. Check one server's stderr log for the `normalized times in N rows` line, and confirm no `could not normalize` line.
3. Create a task with `due` in `-08:00` through a live client, read it back in UTC, then delete it.

## Results

- On the old code (`1b7abe4`, tests only): 26 new tests failed and 126 passed.
- With the code (`4561a9b`): 152 passed.
- After the review follow-ups (`807d9d6`, `b174145`): 156 passed. `ruff check` and `ruff format --check` are clean.
- Manual run of the real `fleetcom-mcp` on a scratch database: an offset `due` became `17:00:00Z`, a date-only `remind_at` became midnight UTC, and `updated_at` did not change. stderr printed `normalized times in 1 rows to UTC` and `could not normalize times in tasks b`, without the stored value. A second start printed only the second line. Each start exited 0.
- A held write lock delayed startup by about 13 s in the reviewer's run, not the 5 s busy timeout. This predates the branch, startup still succeeds, and the cause was not investigated.
- Live checks: not run. They follow the promote (plan, Task E3).

## Review findings

A pre-merge review on 2026-11-14 (Opus, high effort) found no code blocker.

| ID | Finding | Evidence | Resolution |
|----|---------|----------|------------|
| R1 | Test gap: no test checked that the repair commits | Mutation: `with conn:` to `if True:` passed all tests | Tests added in `807d9d6`; the mutation now fails two tests |
| R2 | Test gap: the `IntegrityError` path was untested | Mutation: `except KeyError` passed all tests | Test added with an event whose end precedes its start only in UTC; the mutation now fails it |
| R3 | Rollout limitation: during a rollout, `events.update` that passes only `start` or only `end` compares a UTC value with the other stored time in offset form | Experiment against rows an old server wrote | Recorded in `docs/ISSUES.md`; no code change |
| R4 | `event_list` with `start=""` returned nothing, and a bad bound's error did not name it | Experiment | Fixed in `b174145` |
| R5 | The repair's old-value guard and fixed count were untested | Mutations | Recorded in `docs/ISSUES.md` |
| R6 | One `to_utc` test catches the missing naive-as-UTC step only when the host is not in UTC | Review reading of the test | Not changed: the repo has no CI, and local runs catch it |

The partial rewrite of a row with one unreadable time was judged acceptable. It is in the design and covered by a test.
