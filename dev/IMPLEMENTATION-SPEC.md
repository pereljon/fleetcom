# Product Design Record (PDR): Fleetcom MCP Service (`fleetcom-mcp`)

- **Document Version**: 1.2.0
- **Project Name**: Fleetcom (`fleetcom-mcp`)
- **Status**: Ready for Orchestrator Review
- **Author**: Builder Agent (`[HERMES:BUILDER]`)
- **Date**: 2026-09-13
- **Primary Stakeholders**: Chief-of-Staff, Secretary, Coach, Builder, Orchestrator (`~/Claude/development/orchestrator`)

---

## 1. Executive Summary & Intent

**Fleetcom** (`fleetcom-mcp`) is the shared communications, operations, and coordination center for autonomous AI agents across the Jonathan Perel (jP) fleet.

It delivers five core operational capabilities over a single Model Context Protocol (MCP) server:
1. **Tasks & Backlog**: Multi-agent backlog with race-free atomic claims and automated crash-lease recovery.
2. **Calendar & Milestones**: RFC-5545 compliant scheduled events with per-agent ownership.
3. **Reminders & Nudges**: Time-anchored alerts for proactive agent execution.
4. **Agent Directory**: Active roster of agent capabilities, roles, working directories, and live heartbeat presence.
5. **Fleet Policy**: Machine-readable RFC-2119 operational constraints and boundaries.

Both **Hermes Agent profiles** and **Claude Code sessions** connect to Fleetcom as peer MCP clients over stdio, backed by a high-concurrency SQLite database (`WAL` mode).

---

## 2. Architecture Decisions & Standalone Scope

### 2.1 Standalone Project Scope
Per the architecture decision in `orchestrator/context/decisions.md:10-12`:
- **Location**: Standalone repository at `~/Claude/development/fleetcom/` (bootstrapped with `development-project.md` via `claude-mux`).
- **Separation**: Observability (tmux session monitoring, pane scraping, liveness) remains in `claude-mux` and `orchestrator`. Fleetcom owns the shared data plane (tasks, calendar, directory, policy).
- **Code Reuse**: Ports and extends the tested database schema and types from `~/Claude/development/orchestrator/internal/store/schema.go`.

### 2.2 Rejection of `builderz-labs/mission-control` (Verified Prior Art)
We conducted an empirical source code audit of `builderz-labs/mission-control` (`scripts/mc-mcp-server.cjs`) to resolve the open item in `decisions.md:22`:
1. **Zero Calendar Support**: Mission Control has no calendar/event primitives (`VEVENT`, `dtstart`, `dtend`, or scheduling). It only supports cron-style recurring task intervals.
2. **No Atomic Task Claiming**: Its task queue relies on standard REST endpoints (`GET /api/tasks/queue`, `PUT /api/tasks/:id` with `assigned_to`). It lacks an atomic compare-and-swap claim query, leaving concurrent autonomous workers vulnerable to race conditions.
3. **Heavy Footprint**: Requires a persistent Node.js 22 + Next.js web application running on port 3000.
*Conclusion*: Mission Control is rejected as our fleet substrate. Fleetcom requires a lean, native Go stdio binary.

### 2.3 Implementation Stack: Go Static Binary (CGO-Free)
- **Language**: Go 1.22+.
- **Database Driver**: Pure-Go SQLite (`modernc.org/sqlite`), CGO-free.
- **Transport**: Stdio JSON-RPC 2.0 (MCP protocol). Zero open network ports, zero daemons, zero Python/Node venv dependencies.

---

## 3. Data Model & Database Architecture

- **Engine**: SQLite 3 with `PRAGMA journal_mode = WAL;`, `PRAGMA busy_timeout = 5000;`, and foreign keys enabled.
- **Database Path**: `~/Claude/-hermes/fleetcom.db` (configurable via `FLEETCOM_DB_PATH`).

### 3.1 Agent Directory (`agents`)
Tracks registered agents, working directories, and live heartbeat presence.

```sql
CREATE TABLE IF NOT EXISTS agents (
  agent_id        TEXT PRIMARY KEY,                -- e.g. 'hermes:builder', 'cc:orchestrator', 'hermes:cos'
  kind            TEXT NOT NULL CHECK (kind IN ('hermes-profile', 'claude-session', 'external')),
  name            TEXT NOT NULL,
  cwd             TEXT NOT NULL,
  role            TEXT NOT NULL,
  capabilities    TEXT,                            -- JSON array of toolsets/skills
  status          TEXT NOT NULL DEFAULT 'active'
                  CHECK (status IN ('active', 'idle', 'blocked', 'done', 'offline')),
  last_heartbeat  TEXT NOT NULL,                   -- ISO-8601 timestamp
  heartbeat_ttl   INTEGER NOT NULL DEFAULT 300,    -- Seconds before agent is considered stale
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status);
```

### 3.2 Office Items (`office_items`)
Unified RFC-5545 compliant store for tasks, calendar events, and reminders.

```sql
CREATE TABLE IF NOT EXISTS office_items (
  uid             TEXT PRIMARY KEY,                -- UUID or nanoid
  kind            TEXT NOT NULL CHECK (kind IN ('event', 'todo', 'reminder')),
  summary         TEXT NOT NULL,
  description     TEXT,
  status          TEXT NOT NULL DEFAULT 'needs-action'
                  CHECK (status IN ('needs-action', 'in-process', 'completed', 'cancelled', 'confirmed')),
  priority        INTEGER NOT NULL DEFAULT 3 CHECK (priority BETWEEN 1 AND 5), -- 1=Urgent, 3=Normal, 5=Low
  
  -- Scheduling & Timing (RFC-5545)
  dtstart         TEXT,                            -- ISO-8601 (events)
  dtend           TEXT,                            -- ISO-8601 (events)
  due             TEXT,                            -- ISO-8601 (todos & reminders)
  tzid            TEXT NOT NULL DEFAULT 'America/Los_Angeles',
  all_day         INTEGER NOT NULL DEFAULT 0 CHECK (all_day IN (0, 1)),
  sequence        INTEGER NOT NULL DEFAULT 0,      -- RFC-5545 update sequence counter
  
  -- Recurrence & Alerting (Simple recurrence per decision B1)
  repeat_every    INTEGER,
  repeat_unit     TEXT CHECK (repeat_unit IN ('day', 'week')),
  remind_at       TEXT,                            -- Precomputed alert timestamp
  remind_lead     INTEGER,                         -- Minutes before event/due
  
  -- Ownership & Concurrency Claims
  created_by      TEXT NOT NULL REFERENCES agents(agent_id),
  owner_agent     TEXT REFERENCES agents(agent_id),-- Target assignee (nullable = open pool)
  claimed_by      TEXT REFERENCES agents(agent_id),-- Active worker (single source of truth for claim)
  claimed_at      TEXT,                            -- ISO-8601 timestamp of claim
  claim_expires_at TEXT,                          -- Automatic lease deadline for crash recovery
  completed_at    TEXT,                            -- ISO-8601 timestamp of completion
  result_summary  TEXT,                            -- Short summary of outcome / deliverable
  
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL,
  
  -- Invariants
  CHECK (dtend IS NULL OR kind = 'event'),
  CHECK (dtend IS NULL OR dtstart IS NULL OR dtend >= dtstart),
  CHECK (repeat_every IS NULL OR repeat_every > 0),
  CHECK ((repeat_every IS NULL) = (repeat_unit IS NULL)),
  CHECK (remind_lead IS NULL OR remind_lead >= 0)
);

CREATE INDEX IF NOT EXISTS idx_items_kind_status ON office_items(kind, status);
CREATE INDEX IF NOT EXISTS idx_items_due ON office_items(due);
CREATE INDEX IF NOT EXISTS idx_items_dtstart ON office_items(dtstart);
CREATE INDEX IF NOT EXISTS idx_items_remind ON office_items(remind_at);
CREATE INDEX IF NOT EXISTS idx_items_claimed_by ON office_items(claimed_by);
CREATE INDEX IF NOT EXISTS idx_items_claim_expires ON office_items(claim_expires_at);
```

### 3.3 Fleet Policies (`policies`)
Machine-readable RFC-2119 operational constraints.

```sql
CREATE TABLE IF NOT EXISTS policies (
  policy_id       TEXT PRIMARY KEY,                -- e.g. 'POL-GIT-001', 'POL-COMMS-002'
  title           TEXT NOT NULL,
  rule_text       TEXT NOT NULL,
  level           TEXT NOT NULL CHECK (level IN ('MUST', 'MUST_NOT', 'SHOULD', 'SHOULD_NOT', 'MAY')),
  scope           TEXT NOT NULL DEFAULT 'fleet',   -- 'fleet', 'hermes', 'claude-code', or agent_id
  active          INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_policies_scope ON policies(scope, active);
```

### 3.4 Audit & Activity Log (`activity_log`)
Append-only audit trail.

```sql
CREATE TABLE IF NOT EXISTS activity_log (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_id    TEXT NOT NULL REFERENCES agents(agent_id),
  verb        TEXT NOT NULL CHECK (verb IN ('create', 'claim', 'renew', 'release', 'complete', 'cancel', 'update')),
  target_uid  TEXT NOT NULL,
  summary     TEXT,
  ts          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_activity_ts ON activity_log(ts);
```

---

## 4. Concurrency & Crash Recovery Engine

### 4.1 Single-Source-of-Truth Atomic Claim
Claim status is derived strictly from `claimed_by IS NOT NULL` rather than a duplicate status enum:

```sql
UPDATE office_items
SET claimed_by = :agent_id,
    claimed_at = :now,
    claim_expires_at = datetime(:now, '+' || :lease_seconds || ' seconds'),
    status = 'in-process',
    sequence = sequence + 1,
    updated_at = :now
WHERE uid = :uid
  AND (claimed_by IS NULL OR claim_expires_at < :now)
  AND status IN ('needs-action', 'in-process')
  AND (owner_agent IS NULL OR owner_agent = :agent_id);
```
- **Atomicity**: SQLite executes this update atomically. Exactly one agent receives `RowsAffected() == 1`. All concurrent competitors receive `RowsAffected() == 0`.

### 4.2 Automated Lease Expiry (Crash Protection)
- Every claim carries `claim_expires_at` (default 30 minutes, renewable via progress).
- If an agent crashes or hangs, its lease expires automatically. Subsequent queries re-expose the task to the pool without human intervention.
- Active workers renew their lease by calling `fleetcom_task_progress()`.

### 4.3 Clean Release
```sql
UPDATE office_items
SET claimed_by = NULL,
    claimed_at = NULL,
    claim_expires_at = NULL,
    status = 'needs-action',
    sequence = sequence + 1,
    updated_at = :now
WHERE uid = :uid AND claimed_by = :agent_id;
```

---

## 5. Model Context Protocol (MCP) Tool Surface

All tools carry the clean, authoritative prefix **`fleetcom_`**:

### 5.1 Task Management Tools
- `fleetcom_task_list(status: optional[str], priority: optional[int], pool_only: bool = false, limit: int = 50)`
- `fleetcom_task_create(summary: str, description: optional[str], due: optional[str], priority: int = 3, target_agent: optional[str] = null)`
- `fleetcom_task_claim(task_uid: str, agent_id: str, lease_minutes: int = 30)`
- `fleetcom_task_progress(task_uid: str, agent_id: str, note: str, extend_lease_minutes: int = 30)`
- `fleetcom_task_complete(task_uid: str, agent_id: str, outcome_summary: str)`
- `fleetcom_task_release(task_uid: str, agent_id: str, reason: str)`

### 5.2 Calendar & Scheduling Tools
- `fleetcom_event_list(start_iso: str, end_iso: str)`
- `fleetcom_event_create(summary: str, dtstart: str, dtend: str, description: optional[str])`

### 5.3 Directory & Presence Tools
- `fleetcom_agent_register(agent_id: str, kind: str, name: str, cwd: str, role: str, capabilities: list[str])`
- `fleetcom_agent_heartbeat(agent_id: str, status: str = "active")`
- `fleetcom_directory_list()`

### 5.4 Fleet Policy Tools
- `fleetcom_policy_list(scope: str = "fleet", active_only: bool = true)`
- `fleetcom_policy_get(policy_id: str)`

---

## 6. Implementation & Integration Plan

1. **Repository Setup**:
   - Create `~/Claude/development/fleetcom/` via `claude-mux -n fleetcom --template development-project.md --no-attach`.
2. **Go Build**:
   - Standalone binary built to `/Users/jonathan/bin/fleetcom-mcp`.
3. **MCP Client Configuration**:
   - **Hermes**: Added to `~/.hermes/config.yaml`:
     ```yaml
     mcp_servers:
       fleetcom:
         command: /Users/jonathan/bin/fleetcom-mcp
         args: ["--db", "/Users/jonathan/Claude/-hermes/fleetcom.db"]
     ```
   - **Claude Code**: Added to `~/.claude.json` under `mcpServers.fleetcom`.
