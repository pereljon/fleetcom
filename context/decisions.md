# decisions - decisions made and rejected

Owns: dated decisions, including options considered and turned down, with reasoning. Does NOT hold open questions (context/open_questions.md) or tasks (context/todo.md).
Maintain: append-only; never rewrite a past entry.
Entry format:
## YYYY-MM-DD - <decision>
Why: <reasoning>
Rejected: <option turned down, if any>

## 2026-09-13 - Timestamps computed in Go (`time.RFC3339`), never via SQLite `datetime()`
Why: `ClaimItem`'s atomic-claim `UPDATE` originally computed `claim_expires_at` with SQLite's `datetime(?, '+N minutes')`, which outputs `YYYY-MM-DD HH:MM:SS` (space separator, no `Z`), while `nowISO()` produces RFC3339 (`T` separator, `Z` suffix). String-compared, the space sorts before `T`, so `claim_expires_at < :now` was always true and every claim looked expired — the concurrent-claim test (`TestClaimItem_ConcurrentClaims_OnlyOneWins`) caught 10/10 goroutines winning instead of 1. Fixed by computing `claim_expires_at` in Go (`time.Now().UTC().Add(...).Format(time.RFC3339)`) so every timestamp column shares one sortable format.
Rejected: formatting the SQL `now` parameter to match SQLite's `datetime()` output instead — rejected because it leaves a second timestamp convention alive in the codebase, more surface area for the next occurrence of this bug.

## 2026-09-13 - `ListItems(PoolOnly: true)` treats an expired claim as pool-visible
Why: pre-commit review found `PoolOnly` filtered on `claimed_by IS NULL` only, so a task with a stale `claim_expires_at` (crash recovery case, PDR section 4.2) stayed invisible to `fleetcom_task_list(pool_only=true)` even though `ClaimItem` would let another agent take it. Fixed the filter to `(claimed_by IS NULL OR claim_expires_at < now)`, matching `ClaimItem`'s own availability predicate. Added `TestListItems_PoolOnly_IncludesItemsWithExpiredLease` and `TestClaimItem_ExpiredLease_CanBeReclaimedByAnotherAgent`.

## 2026-09-13 - MCP server built on `github.com/modelcontextprotocol/go-sdk` (v1.7.0)
Why: it's the official Go SDK for the Model Context Protocol, supports stdio transport (`mcp.StdioTransport`) and generic typed tool handlers (`mcp.AddTool[In, Out]`) that auto-infer JSON schema from Go structs and auto-populate `StructuredContent` — matches the PDR's "Stdio JSON-RPC 2.0 (MCP protocol)" requirement (section 2.3) with minimal boilerplate.
Rejected: hand-rolling JSON-RPC framing over stdio — rejected as needless reimplementation of a spec the official SDK already implements and tests.

## 2026-09-13 - `fleetcom_task_create`/`fleetcom_event_create` take an `agent_id` param not in the PDR's literal tool signature
Why: `dev/IMPLEMENTATION-SPEC.md` section 5.1/5.2 lists `fleetcom_task_create(summary, description, due, priority, target_agent)` and `fleetcom_event_create(summary, dtstart, dtend, description)` with no creator/caller field, but `office_items.created_by` is `NOT NULL REFERENCES agents(agent_id)` (section 3.2) — the schema requires a creator that the PDR's tool signature never supplies. Added a required `agent_id` input to both tools to satisfy the FK; this is a PDR gap, not a reinterpretation of an explicit decision.

## 2026-09-13 - Task/event UIDs are generated server-side via `github.com/google/uuid`
Why: the PDR (section 3.2) says `uid` is "UUID or nanoid" but neither the schema nor the tool signatures say who generates it. Generating in the MCP handler (`uuid.NewString()`) rather than asking the caller to supply one avoids collision risk from multiple agents picking their own ids, and matches `google/uuid` already being pulled in transitively by the SQLite driver chain.

## 2026-09-13 - Go module is `github.com/metro18/fleetcom`
Why: matches the existing `github.com/metro18/orchestrator` naming, and the `metro18` SSH/GitHub identity is the one already used for `development/` Go projects on this machine.

## 2026-09-13 - SUPERSEDES the above: module renamed to `github.com/pereljon/fleetcom`; `go` directive lowered to 1.25.0
Why: found during READM review (requested by [HERMES:BUILDER]) that `git remote -v` for this repo is already `git@github.com-pereljon:pereljon/fleetcom.git`, with real commits already pushed there by another process. The metro18 decision above was made by analogy to `orchestrator` without checking this repo's actual remote — orchestrator has no configured remote at all, so the analogy didn't transfer. Kept the metro18 entry above rather than deleting it (decisions.md is append-only) but it is superseded: the module path is now `github.com/pereljon/fleetcom`, matching the real origin, which is also what the checked-in README's `go install`/`git clone` instructions assume.
Also lowered `go.mod`'s `go` directive from `1.27.1` (auto-stamped by `go mod init` to the exact local toolchain) to `1.25.0`, the actual floor required by both real dependencies (`modelcontextprotocol/go-sdk` and `modernc.org/sqlite` both declare `go 1.25.0`) — 1.27.1 was an accidental over-constraint, not a deliberate choice.
