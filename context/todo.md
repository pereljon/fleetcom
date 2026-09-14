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
- [x] `HERMES_TASK.md`'s own tool count ("17 -> 13") was internally inconsistent (its own tool list includes `task_accept`/`task_reject`, making it 15) — implemented as 15, flagged in the pre-commit review (done 2026-09-13)
- [x] Propose commit message for the schema-merge changes; wait for explicit approval before committing (done 2026-09-13: committed as `51aa048`, pushed to `origin/main`)
- [x] Author `skills/fleetcom/SKILL.md` + `skills/fleetcom/references/tools.md` (done 2026-09-13)
- [x] Add `--db` CLI flag (`_resolve_db_path`, TDD) — `HERMES_TASK.md` assumed one already existed for the README to document; it didn't, so added it rather than document a nonexistent flag (done 2026-09-13)
- [x] Deploy via `uv tool install --from . fleetcom`; verified installed binary (`/Users/jonathan/.local/bin/fleetcom-mcp`) answers `tools/list` and a real tool call over actual stdio, launched directly (not via `uv run`) (done 2026-09-13)
- [x] Updated README.md (install/config sections point at the installed launcher, not the dev checkout), context/decisions.md, dev/CODEMAP.md, CHANGELOG.md for the deployment change (done 2026-09-13)
- [ ] Wire `fleetcom-mcp` into Hermes (`~/.hermes/config.yaml`) and Claude Code (`~/.claude.json`) — README's Quick Start now has the exact config, but the actual config files on this machine haven't been edited
- [ ] Symlink `skills/fleetcom/` into the fleet's shared skills directory — **not done**, no path for that directory was given anywhere in this session; see `context/decisions.md`. Need the actual path before this can happen.
- [ ] Propose commit message for the skill + deployment changes; wait for explicit approval before committing
