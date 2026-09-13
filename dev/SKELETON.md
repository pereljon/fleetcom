# SKELETON - how it works

Owns: the logic flow and key invariants of the codebase, as prose or pseudocode. Does NOT hold per-function purposes (dev/CODEMAP.md).
Maintain: update when control flow, call sequences, or invariants change.

## Logic Flow

- `store.Open(path)` creates parent dirs, opens SQLite via `modernc.org/sqlite` with WAL/busy_timeout/foreign_keys set through the DSN (applies to every pooled connection). `Migrate()` then runs the idempotent DDL and stamps `schema_version`.
- `office_items` unifies tasks/events/reminders (`kind`). Task claiming is a single atomic `UPDATE ... WHERE (claimed_by IS NULL OR claim_expires_at < :now) AND status IN (...) AND (owner_agent IS NULL OR owner_agent = :agent_id)`; `RowsAffected() == 1` means the caller won the race, `0` means someone else holds a live lease.
- `ProgressItem` renews `claim_expires_at` (crash-lease extension); `ReleaseItem` clears the claim back to `needs-action`; `CompleteItem` requires the caller to still hold the claim.
- Every create/claim/renew/release/complete call writes one row to `activity_log` via `logActivity`.
- `cmd/fleetcom-mcp` wires a `*store.Store` into `mcpserver.NewServer`, which registers 13 `fleetcom_*` tools (task, event, agent-directory, policy) built with the official `github.com/modelcontextprotocol/go-sdk`'s generic `mcp.AddTool[In, Out]`. Each handler is a thin adapter: decode typed input (schema auto-inferred from the Go struct) -> call one store method -> return a typed output struct (auto-marshaled to `StructuredContent`). No business logic lives in the MCP layer.
- `fleetcom_event_list` filters by `dtstart` range in Go after fetching all `kind='event'` rows, rather than adding a SQL date-range query to `store` — acceptable at expected fleet-calendar volume; revisit if event counts grow.

## Key Invariants

- All timestamps are Go-formatted `time.RFC3339` strings (`nowISO()`), computed in Go rather than SQLite's `datetime()`. Mixing the two formats broke the claim comparison during development (SQLite's `datetime()` output uses a space separator, no `Z`, which sorts differently than RFC3339 — see `context/decisions.md`); every new timestamp column must go through `nowISO()` or a Go-computed expiry, never `datetime('now', ...)` in SQL.
- Claim state has one source of truth: `claimed_by IS NOT NULL`, not a separate boolean/status flag.
- `ClaimItem`/`ProgressItem`/`ReleaseItem`/`CompleteItem` all gate their `UPDATE` on `claimed_by = :agent_id` (or the claim-availability predicate) so a losing/foreign caller gets zero rows affected, never a partial mutation.
