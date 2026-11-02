# List truncation tests

Owns: the test plan and review findings for list truncation. Does NOT hold the design (`list-truncation.md`).

Tests use temp databases and no sleeps. Tests set `created_at` directly to control order. These tests are single-process, so they cannot hang.

Flags exist only above the entity layer. Run flag tests through the in-memory `Client`, or through `agenda.today` for the agenda.

## Automated tests

| Area | Case | Expected result |
|------|------|-----------------|
| Reported bug | 51 tasks, then an unfiltered `task_list` | The newest task is first, and `truncated` is true |
| Same second | 51 tasks with one `created_at` | The last task created is first |
| Boundary | 50 rows, then 51 rows, on `task_list`, `event_list`, `contact_search`, and `task_list(due_now=True)` | `truncated` is false at 50 and true at 51, with 50 rows returned |
| Larger limit | 51 rows with `limit=51` | All 51 rows, and `truncated` is false |
| Old live work | One old task and 60 newer completed tasks, run for `open`, `in-progress`, and `blocked` | The active task is returned |
| Review queue | One old unreviewed completed task and 60 newer accepted tasks | The unreviewed task is returned |
| CoS query | The same data through `task_list(status="completed")` | The unreviewed task is first |
| Order | Active task oldest, unreviewed in the middle, reviewed newest, with `open`, `in-progress`, and `blocked` rows | Active, then unreviewed, then reviewed |
| Order within tiers | Two rows each in the unreviewed and reviewed tiers | Newest first in each tier |
| Active with `reviewed=1` | An older active row with `reviewed=1` set directly, and a newer active row | Newest first, and both come before completed rows |
| Still flagged | 61 live tasks | 50 rows, and `truncated` is true |
| Owner filter | One old open task and 50 newer completed tasks for an owner, plus another owner's rows | The old open task is returned, and no other owner's row appears |
| `due_now` | More than 50 overdue tasks | Oldest-due order is unchanged, and `truncated` is true |
| Agenda flags | 50 and 51 due tasks with 50 and 51 events, in the two crossed pairings | Each flag follows its own list, and each list returns 50 rows |
| Agenda widening | 51 due tasks and 51 events today, then the calls that the docstring names | Each call returns all 51 rows |
| Flag position | `res.content[0].text` from each list tool and `agenda_today` | Flags come before any row data |
| Invalid limit | `limit` of 0, -1, and `MAX_LIMIT + 1` on each list tool, on an empty table | The tool returns an error that names `limit` |
| Limit edges | `limit=1` and `limit=MAX_LIMIT` | Both succeed |
| Tool text | Each list tool's description | It mentions `truncated` |

The first test must fail on the current code before the fix lands.

## Live checks

1. Promote the build, then restart the servers straight away.
2. Create a task, so that the table holds over 50 rows. Confirm an unfiltered `task_list` returns that task first, with `truncated` true, then delete it.
3. Confirm `agenda_today` returns both flags first through a Hermes client.
4. Run one `task_list` from Hermes, Claude Code, and Codex. Codex may need an interactive session, because `codex exec` refuses the tool call under approval policy `never`.

## Review findings

A `Plan` agent reviewed both docs on 2026-11-01 (Opus, high effort), using in-memory SQLite and in-memory MCP clients. The main session confirmed the Hermes 50,000 character threshold in source, the code findings in `src/`, and the live counts with read-only SQL. The other findings rest on the reviewer's evidence.

| ID | Finding | Evidence | Resolution |
|----|---------|----------|------------|
| B1 | Agenda flags at the tail vanish when Hermes spills a result | `agenda.py:11-16`; flag offset 44,548 of 44,601; Hermes preview is 1,500 characters | Flags come first; Flag position test |
| S1 | `truncated` stays true on the common call, even when only history was cut | No code archives rows | `task_list` docstring gives the last-row rule |
| S2 | The retry advice does not fit `agenda_today`, and docstrings omit `limit` | `server.py:77,161,221,258` | Exact widening calls in the docstrings |
| S3 | `order_by` adds an unguarded SQL parameter for one caller | `crud.list_rows` has one caller, `tasks.py:70` | Bespoke query; `crud.list_rows` deleted, pending the user's approval |
| S4 | `crud.page` has the wrong module and shape for the agenda | Touches no table; fixed key name | `util.capped` |
| S5 | The review queue can overflow with unowned acknowledged rows (uncertain) | 0 unreviewed completed rows live | Not a problem today; CoS follow-up for hermes-manager |
| S6 | The Allow-list row cited a test that does not exist | Grep of `tests/` | Row deleted |
| S7 | The Order test passes on current code | Reproduced by the reviewer | Dates now run against the expected order |
| S8 | The Agenda test missed crossed flags and off-by-one errors | Plan review | Crossed 50 and 51 pairings |
| S9 | Two tests pass under the regressions they target | Plan review | Owner test uses an old task; Old live work runs per status |
| S10 | Designed behavior had no test | Plan review | Flag position, Limit edges, Tool text; test level stated |
| S11 | Live checks never saw a true flag and skipped clients | Plan review | Live checks 2 and 4 |
| M1 | `limit=2**63-1` overflows with a bare error | Reproduced by the reviewer | `MAX_LIMIT` |
| M2 | Schema validation could replace `ValueError` | `Field(ge=1)` worked in a probe | Rejected; see Decisions |
| M3 | The stated reason for rejecting `offset` and `total` was wrong | `COUNT(*) OVER()` is one statement | Reason reworded |
| M4 | 160 KB understated 200 rows | The SDK indents JSON | Now about 178 KB |
| M5 | An active row with `reviewed=1` sorts low in its tier | 1 live row | Second sort term; test added |
| M6 | Smaller test gaps | Plan review | Three cases added |
| M7 | Step 7 omitted three files | Plan review | Added |
| M8 | Docs can describe a key that an old server lacks | `promote.sh` replaces the skill first | Restart straight after promote |
