---
name: fleetcom
description: "Use when tracking fleet tasks, reminders, events, or contacts via the shared fleetcom MCP service."
---

Fleetcom is the fleet's shared office notebook: tasks, events, and contacts in one SQLite-backed MCP service, queried on demand. It is not a work queue, not a policy engine, and not a notification system — nothing in it pushes alerts. See `references/tools.md` for a usage example of every tool.

## When to use fleetcom vs. alternatives

- **Time-anchored work or attention request** -> `task_*` tools. A task with `remind_at` set *is* the reminder (no separate reminders primitive exists); `due` is a deadline. The two fields are independent — set one, both, or neither.
- **Something happening at a time** (a meeting, a milestone) -> `event_*` tools. Events have no completion concept; they just happen or they don't.
- **A fact with no deadline** (a preference, a piece of context that doesn't expire or need follow-up) -> the agent memory system, not fleetcom.
- **A pure broadcast that needs no record** (an FYI nobody will look up later) -> a chat message, not fleetcom.

If you're unsure whether something is a task or an event, ask: is there a deadline or a check-back point? If yes, task. If it's just "this happens at time T" with nothing to track afterward, event.

### fleetcom tasks vs. Hermes Kanban

Hermes also ships a kanban board (`hermes kanban`) — a durable SQLite task board with atomic claiming, dependency graphs, and a dispatcher that **spawns actual profile processes to execute tasks**. The two overlap on the surface (both track work with statuses and review gates) but answer different questions:

- **Kanban = execution.** A kanban task is dispatched to a Hermes profile worker: the daemon spawns the process, monitors it with heartbeats, retries failures, and enforces circuit breakers. Use it when you want a profile to *run* a multi-step build autonomously. Kanban is Hermes-only; Claude Code sessions have no kanban surface.
- **Fleetcom = coordination record.** A fleetcom task is a row stating who owns what and where it stands. No process is spawned; the owning agent polls and acts on its own runtime. It is readable and writable from **both** runtime families — Hermes profiles via the `fleetcom` MCP server and Claude Code sessions via `~/.claude.json` — which kanban cannot do.

Rule of thumb: if the work should be *executed by a spawned Hermes profile worker*, use kanban. If the state of work must be *recorded and visible across runtimes* (a CC session picking up work CoS assigned, an agent flagging something blocked), use fleetcom. Contacts, events, and agenda have no kanban equivalent and are always fleetcom.

## Task conventions

- Agents create and list their own tasks. Check `task_list(owner="<your handle>")` at the start of a session to pick up anything assigned to you.
- Handles are plain strings, not a registered identity: `hermes:builder`, `hermes:cos`, `cc:fleetcom`, `user`. Fleetcom does not verify who's calling — handles are self-reported.
- `owner="user"` means jP. His personal tasks live in Apple Reminders via the Secretary, not fleetcom. Agents may read `user`-owned tasks for context but must never mark them `completed` — that's jP's or the Secretary's call, not an agent's.
- Only CoS assigns tasks to other agents. Agents do not assign work to each other directly.
- Status lifecycle: `open` -> `in-progress` -> `blocked` (requires `blocked_reason`, enforced) -> `completed`. `blocked` is reachable from either `open` or `in-progress`.
- Mark `completed` only after verified execution, with `result_summary` filled in describing what was actually done. Evidence, not intent — don't mark something completed because you're about to do it.
- `task_accept`/`task_reject` are CoS's review gate on completed work, not something the task's own owner calls on themselves. An **unowned** task marked `completed` means "acknowledged" (someone saw it, no work was verified) — not the same claim as an owned task's `completed`, which means the owner is asserting the work is done.

## Wiring notes

- The database lives at `~/Claude/-hermes/fleetcom.db` by default; override with `FLEETCOM_DB_PATH` (env var) or `--db <path>` (CLI flag, takes precedence over the env var).
- Run the server via the installed `fleetcom-mcp` launcher (from `uv tool install`), never a bare `python3 -m fleetcom` or similar. The `mcp` package itself needs Python >=3.10 and this project targets >=3.11; macOS ships `/usr/bin/python3` at 3.9, which can't import `mcp` at all, and an MCP client config may not reliably fall back to a newer interpreter on your `PATH`. The installed launcher's shebang is pinned to the correct interpreter regardless of what `python3` resolves to in whatever environment the MCP client runs under.
- Everything is pull-only. Nothing in fleetcom watches a clock or pushes a notification. Check `task_list(due_now=True)` or `agenda_today` when you want to know what needs attention — fleetcom will never tell you first.
