# todo - outstanding tasks and their state

Owns: open tasks and their status. Does NOT hold permanent facts or decisions (those live in dev/ docs and context/decisions.md).
Maintain: update whenever a task is added, changes state, or completes.
Entry format: `- [ ] task`  /  done: `- [x] task (done YYYY-MM-DD)`
- [x] `internal/store` schema (agents, office_items, policies, activity_log) + Migrate (done 2026-09-13)
- [x] office_items CRUD + atomic ClaimItem/ProgressItem/ReleaseItem/CompleteItem, agent directory, policy CRUD (done 2026-09-13)
- [x] Unit tests: schema creation, item CRUD, concurrent atomic task claiming (14 tests, `go test -race` green) (done 2026-09-13)
- [x] MCP stdio server (`cmd/fleetcom-mcp`) exposing the `fleetcom_*` tool surface from `dev/IMPLEMENTATION-SPEC.md` section 5 — 13 tools, 7 integration tests (in-memory transport) + one real-binary end-to-end smoke test over actual stdio (done 2026-09-13)
- [ ] Wrap each item mutation (`CreateItem`/`ClaimItem`/`ProgressItem`/`ReleaseItem`/`CompleteItem`) and its `logActivity` call in one `sql.Tx`, so a crash between the two can't leave the audit trail out of sync with `office_items` (found in 2026-09-13 pre-commit review; not a data-race, since the FK on `activity_log.agent_id`/`office_items.claimed_by` already keeps them consistent for the invalid-agent case, but a mid-write crash is still a real gap)
- [ ] Seed `policies` table once the source for the "119 fleet policies" is found (see context/open_questions.md)
- [x] Fix module path (`metro18` -> `pereljon`, matching the real git remote) and lower the `go` directive to the actual dependency floor (1.25.0), found during README review (done 2026-09-13)
- [ ] README.md fixes (reported to [HERMES:BUILDER], not applied by this session): Tools Reference table is missing `fleetcom_policy_get`; "Requires Go 1.22+" should read "Go 1.25+"; the "Heartbeat" step in the task lifecycle narrative conflates `fleetcom_agent_heartbeat` (agent liveness) with `fleetcom_task_progress` (lease renewal) — only the latter extends `claim_expires_at`; the "Fleet Policies" bullet describes read+enforce distribution but only list/get exist and zero policies are seeded yet
- [ ] Wire `fleetcom-mcp` into Hermes (`~/.hermes/config.yaml`) and Claude Code (`~/.claude.json`) per IMPLEMENTATION-SPEC.md section 6
