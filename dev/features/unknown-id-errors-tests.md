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

## Review findings

None yet.
