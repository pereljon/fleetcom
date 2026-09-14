# todo - outstanding tasks and their state

Owns: open tasks and their status. Does NOT hold permanent facts or decisions (those live in dev/ docs and context/decisions.md).
Maintain: update whenever a task is added, changes state, or completes.
Entry format: `- [ ] task`  /  done: `- [x] task (done YYYY-MM-DD)`

- [x] Full restart: remove Go implementation, rebuild as Python office primitives (tasks/reminders/events/contacts) per `INTENT.md` (done 2026-09-13)
- [x] `src/fleetcom/db.py` schema (4 tables) + `crud.py` generic engine + per-entity CRUD modules, TDD throughout (done 2026-09-13)
- [x] `src/fleetcom/server.py`: 17 MCP tools via official `mcp` SDK's `MCPServer`, `fleetcom-mcp` console-script entry point (done 2026-09-13)
- [x] 28 tests (unit + in-memory MCP integration) green; `ruff check`/`ruff format` clean; real end-to-end smoke test against the built `fleetcom-mcp` binary over actual stdio (done 2026-09-13)
- [x] Updated README.md, dev/CODEMAP.md, dev/SKELETON.md, dev/IMPLEMENTATION-SPEC.md, context/decisions.md, context/open_questions.md, CHANGELOG.md for the restart (done 2026-09-13)
- [x] Propose commit message for the restart; wait for explicit approval before committing (done 2026-09-13: committed as `4e6d5a2`, pushed to `origin/main`)
- [x] Design review (4 rounds, `HERMES_RESULT.md`/`RESULT.md`): merge reminders into tasks (not events), add `blocked`/`blocked_reason`, split `completed`/`reviewed` via bespoke `accept`/`reject` rather than enum expansion (done 2026-09-13)
- [x] Implement the approved two-table schema: drop `reminders` table/module, absorb into `tasks` (`remind_at`, `blocked_reason`, `result_summary`, `reviewed`), add `tasks.accept`/`tasks.reject`, add `agenda.today` aggregator + `agenda_today` tool. 37 tests green, `ruff` clean, real end-to-end smoke test against the built binary (done 2026-09-13)
- [x] Updated README.md, dev/CODEMAP.md, dev/SKELETON.md, dev/IMPLEMENTATION-SPEC.md, context/decisions.md, CHANGELOG.md for the schema merge (done 2026-09-13)
- [ ] Wire `fleetcom-mcp` into Hermes (`~/.hermes/config.yaml`) and Claude Code (`~/.claude.json`) per the README's Quick Start
- [ ] `HERMES_TASK.md`'s own tool count ("17 -> 13") is internally inconsistent with its own tool list (which includes `task_accept`/`task_reject`, making it 15) — implemented as 15 and flagged in the pre-commit review; worth a one-line correction to that file or its successor if this round-trip process continues
- [ ] Propose commit message for this round's schema-merge changes; wait for explicit approval before committing
