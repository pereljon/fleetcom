# List truncation

Owns: the design for fixing silent truncation on list tools. Does NOT hold test cases or review findings (`list-truncation-tests.md`).

Status: shipped 2026-11-02, merged as `371acda` and promoted. Client checks wait on server restarts. Investigated against commit `07dd569` and SQLite 3.53.1.

## Goal

A caller of any list tool must never lose rows without knowing it, and a new or active task must stay visible as finished tasks accumulate. Fleetcom is a shared notebook, so `task_list(owner=...)` is how an agent learns about assigned work (`src/skills/fleetcom/SKILL.md:28`).

## Verified facts

Two read-only reviews on 2026-11-01 ran these on scratch databases. Neither touched the live database.

- **The oldest rows win.** `crud.list_rows` sorts by `created_at` ascending with `LIMIT 50`, so row 51 is the row cut. Raising `limit` reveals it, which rules out a stale read across processes.
- **The live database is at the edge.** It holds 50 tasks, 41 of them active, so the next task is the first row cut from an unfiltered list. It holds no unreviewed completed rows, and one active row has `reviewed=1` (read-only counts, 2026-11-01).
- **Every list path has the cap.** `task_list` with any filter, `due_now`, `event_list`, `contact_search`, and `agenda_today` all cut silently.
- **A caller cannot detect truncation.** Tables of 50 and 51 rows give identical responses.
- **`agenda_today` cannot widen.** The tool has no arguments, so a caller must use `task_list` and `event_list` instead.
- **Newest first alone regresses.** With one old open task and 60 newer completed tasks, that order hides the open task, and all 54 existing tests still pass.
- **Timestamps tie.** `util.now_iso()` has one-second resolution, and `created_at DESC` alone kept the newest of same-second rows hidden. Adding `rowid DESC` fixed it.
- **`limit` is unvalidated.** `limit=0` returns nothing, and a negative limit returns every row. With a `limit + 1` fetch, `limit=-1` becomes `LIMIT 0`, which returns nothing and no flag.
- **The added key is schema-safe.** `outputSchema` allows additional properties. Hermes and Codex clients have not been tested with it.
- **Hermes spills large results.** An MCP result over 50,000 characters becomes a 1,500-character preview plus a file path (`~/.hermes/hermes-agent/tools/budget_config.py`). The architect review calculated about 47,400 characters for 50 rows of 800 bytes, and found a tail agenda flag at offset 44,548 of 44,601. A flag outside the preview is lost in the case it exists for.

## Design

1. Sort tasks by active, then unreviewed, then newest:
   ```sql
   ORDER BY status = 'completed', status = 'completed' AND reviewed, created_at DESC, rowid DESC
   ```
   The second term keeps an active row with `reviewed=1` in date order among active rows.
2. Move the plain list into `tasks.list`, so one bespoke query serves both branches with two literal sort clauses. Delete `crud.list_rows` and `tasks.FILTERS`. The filter names become literals, so no filter name is interpolated. The user approved this on 2026-11-01.
3. Add `util.capped(fetch, limit)`. It raises `ValueError` unless `limit` is between 1 and `MAX_LIMIT`, calls `fetch(limit + 1)`, and returns `(rows[:limit], truncated)`. `_anticipated` already turns `ValueError` into `ToolError`. `util.DEFAULT_LIMIT` is 50 and `util.MAX_LIMIT` is 1,000,000.
4. Use `util.capped` in `task_list`, `event_list`, and `contact_search`. Each returns `truncated` as the first key. Entity functions keep returning lists.
5. Use `util.capped` in `agenda.today`, and return `tasks_truncated`, `events_truncated`, `tasks_due`, and `events_today` in that order.
6. Keep the default limit of 50, and the `due_now`, event, and contact sort orders.
7. Update the four tool docstrings, `SKILL.md`, `references/tools.md`, `README.md`, `dev/SKELETON.md`, `dev/CODEMAP.md`, `dev/IMPLEMENTATION-SPEC.md`, the `crud.py` module docstring, `CHANGELOG.md`, and the bug entry in `docs/ISSUES.md`.

### Text that agents read

Tool docstrings are the one channel known to reach every client, so each list docstring carries its rule.

- All list tools: "`truncated` true means rows were cut. Try a narrower filter, range, or query first, then a larger `limit`. The default `limit` is 50."
- `task_list`, when `due_now` is off: "Rows sort active, then unreviewed, then reviewed. If the last row is `completed` with `reviewed=1`, only accepted history was cut, so no retry is needed."
- `agenda_today`: "If a flag is true, call `task_list(due_now=True, limit=N)` or `event_list` from `T00:00:00Z` to `T23:59:59Z` on the current UTC date."
- `SKILL.md`: add the review queue query, `task_list(status="completed")`, with the same `truncated` rule.

The flags come first because Hermes shows only the head of a spilled result. Hermes reads the text block, and the SDK keeps dict order there (architect review). Codex and Claude Code behavior for long output is inferred.

## Interface change

- The new keys are additive.
- The default task order changes.
- `limit < 1` becomes an error, so `limit=-1` stops returning every row.
- The schema does not change, so old and new servers can share the database. Each client keeps old code until its server restarts, while `promote.sh` replaces the skill at once. Restart the servers straight after promote.

hermes-manager scanned Hermes skills, cron definitions, config, and scripts on 2026-11-01, and found no dependency:

- No scanned file passes `limit=-1` or `limit=0` to a Fleetcom tool (verified).
- No script consumes `task_list` results, and the consumers are LLM agents, so row order and extra keys should not matter (inferred).
- CoS finds its review queue with `task_list(status="completed")`, then filters on `reviewed == 0` itself (verified from the latest `fleet-sync-daily` output, because the `fleet-sync` skill source was not found). The `reviewed` sort term puts unreviewed rows first in that query, so the queue stays visible.

A scan cannot rule out an ad hoc call by an LLM agent.

After shipping, hermes-manager updates the CoS job, because Hermes owns it: a true `truncated` on the review queue query means raise `limit`. The queue fits today, with no unreviewed completed rows. Unowned acknowledged tasks stay unreviewed, so that tier can grow.

## Decisions

### 2026-11-01 - Active, then unreviewed, then newest (`firm`)
Why: the order must keep live work and the review queue visible while finished rows pile up. The user approved it.
Rejected: newest first alone, which hides old live work. Rejected: hiding completed tasks by default, because an unfiltered list would stop being unfiltered.

### 2026-11-01 - A `truncated` flag, no paging or total (`firm`)
Why: the flag closes the silent miss, and no requirement needs paging. A caller retries with a narrower filter or a larger `limit`.
Rejected: `offset` and `total`, because no requirement needs them. Rejected: only raising the default, which delays the bug, and 200 rows would cost about 178 KB of text (calculated from 800-byte rows).

### 2026-11-01 - Reject `limit < 1` (`firm`)
Why: `limit + 1` makes a negative limit return nothing with no flag.
Rejected: leaving `limit` unvalidated.

### 2026-11-01 - Delete `crud.list_rows` and its filter allow-list (`firm`)
Why: `tasks.list` was its one caller, and literal filter names leave nothing to guard. The user approved the removal.
Rejected: keeping `list_rows` with an `order_by` parameter, which adds raw SQL to the generic engine.

### 2026-11-01 - An upper bound on `limit` (`delegated`)
Why: `limit + 1` overflows SQLite's integer at `2**63 - 1`, and the bare error hides the reason. Agents that lose `limit=-1` may try a huge number. One million is far above any list this notebook holds.
Rejected: no bound. Rejected: pydantic `Field` bounds in tool signatures, because `ValueError` already reaches the caller and `Field` pass-through in `server.py` is untested.

### 2026-11-01 - `util.capped`, not `crud.page` (`delegated`)
Why: the helper touches no table, and the agenda needs its own key names, so a tuple suits every caller.
Rejected: `crud.page(key, limit, fetch)`, which fixes one key name and sits in the wrong module.

### 2026-11-01 - No server-written hint string (`delegated`)
Why: the docstrings carry the rule, and a hint adds a key that no requirement needs.
Rejected: a `hint` value present only when truncated.
