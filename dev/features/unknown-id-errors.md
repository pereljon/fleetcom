# Unknown-id errors

Owns: the design for making an unknown id an error on update, delete, accept, and reject tools. Does NOT hold test cases or review findings (`unknown-id-errors-tests.md`).

Status: merged to `main` as `a177129` on 2026-11-14; not yet promoted. Investigated against `main` at `188bca6`. Plan: `docs/superpowers/plans/2026-11-14-status-review-fixes.md`, Branch A.

## Goal

A caller that names an id no row has must get an error that names the id. Today it gets `{"ok": false}`, the same result as an update that changes nothing, so a caller cannot tell "no such row" from a no-op.

## Verified facts

- `crud.update` and `crud.delete` return `cur.rowcount > 0` (`src/fleetcom/crud.py:62`, `:68`). An unknown id gives `False`.
- `crud.update` returns `False` before any SQL when no field is given (`crud.py:55-56`). `server._updated_fields` drops `None` arguments, so `task_update(task_id=...)` with no other argument reaches this path.
- `tasks.accept` and `tasks.reject` return `cur.rowcount > 0` from an `UPDATE ... WHERE id = ? AND status = 'completed'` (`src/fleetcom/tasks.py:128`, `:145`). An unknown id and a task that is not completed both give `False`.
- `server._anticipated` turns `ValueError` into the SDK's `ToolError`, which reaches the caller with its message. The SDK replaces any other exception's message with "Error executing tool X" (`mcp` 2.2.0, `tools/base.py:158`, read by the plan reviewer).
- On 2026-11-13, a Hermes caller spent two `task_update` calls on a task stored in a second database, and saw only `{"ok": false}` (`docs/ISSUES.md`, Bugs).

## Design

1. Add `class NotFoundError(ValueError)` to `crud.py`. It subclasses `ValueError`, so `_anticipated` turns it into a `ToolError` with no server change.
2. Build the message in one place, `crud._not_found(table, id_)`: `f"{table}: no row with id {id_!r}"`, for example `tasks: no row with id 'abc'`. The id comes from the caller, and `repr` quotes it, so its text cannot pose as part of the message.
3. `crud.update` raises `NotFoundError` when the `UPDATE` matches no row. With no fields, it checks that the row exists and raises if not; otherwise it returns `False`.
4. `crud.delete` raises `NotFoundError` when the `DELETE` matches no row; otherwise it returns `True`.
5. `tasks.accept` and `tasks.reject` raise `NotFoundError` when the `UPDATE` matches no row and no row has the id. A task that exists but is not `completed` still returns `False`.
6. Tool docstrings state the new meaning of each result.

After the change, the results mean:

| Tool | `ok: true` | `ok: false` | Error |
|------|-----------|-------------|-------|
| `task_update`, `event_update`, `contact_update` | A row changed | No argument changed anything | Unknown id, or a rejected value as today |
| `task_delete`, `event_delete`, `contact_delete` | The row was deleted | Never | Unknown id |
| `task_accept`, `task_reject` | The task was accepted or rejected | The task is not `completed` | Unknown id |

Every response keeps the `{"ok": bool}` shape.

The existence checks in steps 3 and 5 are separate reads after the write. Another server can delete the row between the two statements, and then the caller sees `ok: false` instead of an error, the same result as today. Tool calls in one server are serialized by `server._call_lock`, so only another process can cause this.

## Interface change

- Eight tools now return an error for an unknown id instead of `{"ok": false}`.
- Pre-1.0, there is no deprecation period (`dev/IMPLEMENTATION-SPEC.md`, Deprecation Policy).
- The schema does not change, so old and new servers can share the database.
- No scan of Hermes callers was made for code that depends on `ok: false` for an unknown id. The consumers are LLM agents, and an error that names the id carries more than `ok: false` (inferred). hermes-manager is told after the promote (plan, Task E4).

## Decisions

### 2026-11-14 - An unknown id is an error that names the id (`ok`)
Why: a caller must be able to tell "no such row" from a no-op. Recorded in `docs/ISSUES.md` (Decisions).
Rejected: a structured `{"ok": false, "reason": "not_found"}`, which callers can still read as a soft failure.

### 2026-11-14 - `task_accept` and `task_reject` follow the same rule (`ok`)
Why: they had the same ambiguity between an unknown id and a task that is not completed. The user approved this on 2026-11-14 (plan, Q1).
Rejected: leaving them with `ok: false` for both cases.
