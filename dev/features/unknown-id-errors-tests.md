# Unknown-id errors tests

Owns: the test plan and review findings for unknown-id errors. Does NOT hold the design (`unknown-id-errors.md`).

Tests use temp databases and no sleeps. Each in-memory MCP call runs under `asyncio.wait_for` with a 10-second timeout, so a hang fails the test.

## Baseline

On branch `unknown-id-errors` at `188bca6`, 2026-11-14: `uv run pytest -q` gave 99 passed, and `uv run ruff check` was clean. `uv run ruff format --check` flagged Python blocks in the committed plan file. That file is formatted on this branch.

## Automated tests

| Area | Case | Expected result |
|------|------|-----------------|
| Entity update | `tasks.update` with an unknown id and a field | `crud.NotFoundError` naming the id |
| Entity update, no fields | `tasks.update` with an unknown id and no field | `crud.NotFoundError` naming the id |
| No-op update | `tasks.update` with an existing id and no field | `False`; passes before and after the change |
| Entity delete | Delete a task, then delete it again | `True`, then `crud.NotFoundError` naming the id |
| Tools | `task_update`, `task_delete`, `event_update`, `event_delete`, `contact_update`, `contact_delete`, `task_accept`, and `task_reject`, each with id `missing-1`, through the in-memory `Client` | `is_error` is true, and the text contains `missing-1` |
| Accept gate | `task_accept` on an existing task that is not completed | `ok` is false, not an error (existing test) |
| Reject gate | `task_reject` on an existing task that is not completed | `ok` is false, not an error |
| Unknown field | `task_update` with only an unrecognized argument on an existing task | `ok` is false, not an error (existing test) |

The tool tests must fail on the current code before the fix lands.

Existing tests that assert `False` for an unknown id change to expect the error: `test_update_nonexistent_id_returns_false` and the last line of `test_delete_removes_row` in `tests/test_tasks.py`.

## Live checks

After the promote and client restarts (plan, Task E3):

1. Call `task_update` with a made-up id through the installed `fleetcom-mcp`. Expect an error that names the id.
2. Call `task_delete` with a made-up id. Expect the same error, and confirm the task count is unchanged.

## Results

2026-11-14, on branch `unknown-id-errors` at `c8e9d5c`:

- `uv run pytest -q`: 110 passed. `ruff check` and `ruff format --check`: clean.
- The 11 new tests failed on the old code before the fix. The 8 tool cases failed on behavior. The 3 entity tests failed with `AttributeError`, because `crud.NotFoundError` did not exist yet.
- Two new tests also pass on the old code by design: the no-field update on an existing id, and reject on a task that is not completed. They guard against the new checks catching more than missing rows.

Live, 2026-11-15, after release 0.2.0 (`3b693f3`): `task_update` with id `e3-check-nonexistent-id` through a live client returned `tasks: no row with id 'e3-check-nonexistent-id'`. `task_delete` with a made-up id was not run live.

## Review findings

A subagent reviewed `c8e9d5c` before the merge on 2026-11-14 (Opus, high effort), limited to findings with a clear execution path. It found none.

- Every caller of the four changed functions is a tool adapter in `server.py` that returns the result directly. None relies on `False` for a missing row (code read).
- After each of 8 paths, including every raise, `conn.in_transaction` was false and a second connection could write at once (scratch script).
- An id holding quotes, a newline, and a right-to-left override character appears in the message as one quoted, escaped literal (scratch script).
- Six mutations were each caught by at least one test: dropping either existence check, raising on any zero-row accept or reject, and returning `False` from update or delete.
