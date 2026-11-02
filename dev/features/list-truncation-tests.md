# List truncation tests

Owns: the test plan and review findings for list truncation. Does NOT hold the design (`list-truncation.md`).

Tests use temp databases and no sleeps. Tests set `created_at` directly to control order. These tests are single-process, so they cannot hang.

## Automated tests

| Area | Case | Expected result |
|------|------|-----------------|
| Reported bug | 51 tasks, then an unfiltered `task_list` | The newest task is first, and `truncated` is true |
| Same second | 51 tasks with one `created_at` | The last task created is first |
| Boundary | 50 rows, then 51 rows, on `task_list`, `event_list`, and `contact_search` | `truncated` is false at 50 and true at 51, with 50 rows returned |
| Larger limit | 51 rows with `limit=51` | All 51 rows, and `truncated` is false |
| Old live work | One old open task and 60 newer completed tasks | The open task is returned |
| Review queue | One old unreviewed completed task and 60 newer accepted tasks | The unreviewed task is returned |
| Order | One task in each state | Active, then unreviewed, then reviewed |
| Still flagged | 61 live tasks | 50 rows, and `truncated` is true |
| Owner filter | 50 completed tasks and one new open task for an owner | The open task is returned |
| `due_now` | More than 50 overdue tasks | Oldest-due order is unchanged, and `truncated` is true |
| Agenda | Over 50 due tasks and over 50 events today | `tasks_truncated` and `events_truncated` are true; each is false under the limit |
| Invalid limit | `limit` of 0 and -1 on each list tool | The tool returns an error with the reason |
| Allow-list | `crud.list_rows` with a default order | Filter names stay validated (existing test) |

The first test must fail on the current code before the fix lands.

## Live checks

1. Promote the build, then restart the servers.
2. Confirm an unfiltered `task_list` on the live database returns a new task first, then delete that task.
3. Confirm `agenda_today` returns both flags through a Hermes client.

## Review findings

None yet.
