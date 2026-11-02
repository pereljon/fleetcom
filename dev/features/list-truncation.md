# List truncation

Owns: the design for fixing silent truncation on list tools. Does NOT hold test cases or review findings (`list-truncation-tests.md`).

Status: designed 2026-11-01, not built. Investigated against commit `07dd569` and SQLite 3.53.1.

## Goal

A caller of any list tool must never lose rows without knowing it, and a new or active task must stay visible as finished tasks accumulate. Fleetcom is a shared notebook, so `task_list(owner=...)` is how an agent learns about assigned work (`src/skills/fleetcom/SKILL.md:28`).

## Verified facts

Two read-only reviews on 2026-11-01 ran these on scratch databases. Neither touched the live database.

- **The oldest rows win.** `crud.list_rows` sorts by `created_at` ascending with `LIMIT 50`, so row 51 is the row cut. Raising `limit` reveals it, which rules out a stale read across processes.
- **The live database is at the edge.** It holds 50 tasks, so the next task is the first row cut from an unfiltered list.
- **Every list path has the cap.** `task_list` with any filter, `due_now`, `event_list`, `contact_search`, and `agenda_today` all cut silently.
- **A caller cannot detect truncation.** Tables of 50 and 51 rows give identical responses.
- **`agenda_today` cannot widen.** The tool has no arguments, so a caller must use `task_list` and `event_list` instead.
- **Newest first alone regresses.** With one old open task and 60 newer completed tasks, that order hides the open task, and all 54 existing tests still pass.
- **Timestamps tie.** `util.now_iso()` has one-second resolution, and `created_at DESC` alone kept the newest of same-second rows hidden. Adding `rowid DESC` fixed it.
- **`limit` is unvalidated.** `limit=0` returns nothing, and a negative limit returns every row. With a `limit + 1` fetch, `limit=-1` becomes `LIMIT 0`, which returns nothing and no flag.
- **The added key is schema-safe.** `outputSchema` allows additional properties. Hermes and Codex clients have not been tested with it.

## Design

1. Sort tasks by active, then unreviewed, then newest:
   ```sql
   ORDER BY status = 'completed', reviewed, created_at DESC, rowid DESC
   ```
2. Keep that clause as a literal in `tasks.py`, and pass it to `crud.list_rows` as `order_by`. The value never comes from a tool argument, because `dev/SKELETON.md` forbids caller-controlled SQL identifiers. `crud` gains no knowledge of task status.
3. Add `crud.page(key, limit, fetch)`. It rejects `limit < 1` with `ValueError`, calls `fetch(limit + 1)`, and returns `{"truncated": bool, key: rows[:limit]}`. `_anticipated` already turns `ValueError` into `ToolError`.
4. Use `crud.page` in `task_list`, `event_list`, and `contact_search`. Entity functions keep returning lists.
5. Add `tasks_truncated` and `events_truncated` to `agenda.today`.
6. Keep the default limit of 50, and the `due_now`, event, and contact sort orders.
7. Update the tool docstrings, `SKILL.md`, `references/tools.md`, `README.md`, `dev/SKELETON.md`, `dev/CODEMAP.md`, and `CHANGELOG.md`. Each must say that a true flag means a narrower filter or a larger `limit`.

`truncated` comes first in the dict, so it survives a client that shortens long output. That client behavior is inferred.

## Interface change

- The new keys are additive.
- The default task order changes.
- `limit < 1` becomes an error, so `limit=-1` stops returning every row.
- The schema does not change, so old and new servers can share the database. Each client keeps old code until its server restarts.

hermes-manager has been asked whether Hermes depends on any of these. The answer is not in yet.

## Decisions

### 2026-11-01 - Active, then unreviewed, then newest (`firm`)
Why: the order must keep live work and the review queue visible while finished rows pile up. The user approved it.
Rejected: newest first alone, which hides old live work. Rejected: hiding completed tasks by default, because an unfiltered list would stop being unfiltered.

### 2026-11-01 - A `truncated` flag, no paging or total (`firm`)
Why: the flag closes the silent miss, and no requirement needs paging. A caller retries with a narrower filter or a larger `limit`.
Rejected: `offset` and `total`, which add a second query at four sites and are not atomic across processes. Rejected: only raising the default, which delays the bug, and 200 rows would cost about 160 KB of output (calculated).

### 2026-11-01 - Reject `limit < 1` (`firm`)
Why: `limit + 1` makes a negative limit return nothing with no flag.
Rejected: leaving `limit` unvalidated.
