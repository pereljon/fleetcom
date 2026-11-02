# AGENTS.md

Guidance for Claude Code when working in this repository. Shared rules live in `../AGENTS.md` and `~/Claude/AGENTS.md`; this file adds fleetcom specifics.

## Project

**Fleetcom (`fleetcom-mcp`)** -- Shared office notebook for the fleet. Written in Python on stdlib `sqlite3` and the official `mcp` SDK, it exposes tasks, events, contacts, and a daily agenda over the Model Context Protocol (stdio transport).

Internal infrastructure for the fleet (Hermes and Claude Code); optimize for correctness and simplicity.

## Design Principles

A shared notebook, not a distributed work queue.

- **Pull-Only:** Nothing watches a clock or pushes a notification. Agents query when they want to know something.
- **No Claims or Leases:** `owner` and `created_by` are plain strings, and concurrent writes are last-write-wins. The 2026-09-13 restart rejected atomic claiming (`docs/ISSUES.md`, Decisions).
- **No Daemon:** Each MCP client launches its own stdio server. Client configs point every server at one SQLite file in WAL mode, so a write must never leave a transaction open.
- **Separate Axes for Completion:** `status='completed'` is the owner's claim that the work is finished; on an unowned task it means acknowledged. `reviewed` says the claim was checked. Only `task_accept` sets `reviewed`, and any status change away from `completed` clears it. Editing a reviewed task's content does not clear it.
- **Reminders Are Tasks:** `remind_at` alone is a reminder, `due` alone is a deadline, and both together give a deadline with advance warning. There is no separate reminders primitive.

## Read First

`docs/ISSUES.md`. Read `dev/SKELETON.md` and `dev/CODEMAP.md` before changing code.

## Security Context

- **Users:** One person's fleet of Hermes profiles and Claude Code sessions, on one trusted machine. Fleetcom has no network port.
- **Untrusted inputs:** Tool arguments, and text in stored rows. An agent may store text taken from email or the web, and another agent later reads it.
- **Identity:** Handles such as `actor`, `owner`, and `created_by` are self-reported, so they are not proof of who wrote a row. Accept and reject records sit in `description`, which any `task_update` can overwrite.
- **Costliest mistakes:** Any client can rewrite or hard-delete any row, with no history. Beyond that, the costliest are letting a caller-supplied name reach an SQL identifier without an allow-list, and treating stored text as instructions.
- **Sensitive data:** Contacts, tasks, and events can hold personal data. Keep the database out of this repo and out of logs.
