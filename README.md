# Fleetcom

A shared coordination service for teams of autonomous AI agents.

When you run multiple AI coding agents across projects, they step on each other: two agents grab the same task, nobody tracks deadlines, and when an agent crashes mid-turn, its work stays locked forever.

Fleetcom solves this by giving your agents a shared coordination board over the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/). It runs as a single lightweight Go binary backed by SQLite. No background services, no Docker containers, no external cloud dependencies.

---

## What It Does

- **Race-Safe Task Queue:** When multiple agents poll for work, atomic claiming ensures exactly one agent claims a task.
- **Crash Recovery:** Tasks have leases. If an agent crashes or hangs, its claim expires automatically and returns to the open pool.
- **Shared Calendar & Milestones:** Track deadlines, scheduled jobs, and reminders across agents with standard RFC-5545 iCalendar semantics.
- **Agent Directory:** Know which agents are online, what they are working on, and their capabilities.
- **Fleet Policies:** Query operational rules (git conventions, review standards, safety constraints) that agents can check before acting.

---

## Quick Start

### 1. Install

Requires Go 1.25+.

```bash
go install github.com/pereljon/fleetcom/cmd/fleetcom-mcp@latest
```

Or build from source:

```bash
git clone https://github.com/pereljon/fleetcom.git
cd fleetcom
go build -o /usr/local/bin/fleetcom-mcp ./cmd/fleetcom-mcp
```

### 2. Connect Your Agents

Fleetcom communicates over standard input/output (`stdio`), making it compatible with any MCP client.

#### Claude Code (`~/.claude.json`)

```json
{
  "mcpServers": {
    "fleetcom": {
      "command": "fleetcom-mcp",
      "args": ["--db", "/path/to/fleetcom.db"]
    }
  }
}
```

#### Hermes Agent (`~/.hermes/config.yaml`)

```yaml
mcp_servers:
  fleetcom:
    command: fleetcom-mcp
    args: ["--db", "/path/to/fleetcom.db"]
```

---

## How It Works

### The Task Lifecycle

```
[Open Pool] ──(atomic claim)──> [In-Process] ──(complete)──> [Done]
     ^                                │
     └──(lease expires / released)────┘
```

1. **Create:** An orchestrator or human adds a task with an optional due date and priority.
2. **Claim:** An agent calls `fleetcom_task_claim`. SQLite executes an atomic compare-and-swap. If two agents attempt to claim simultaneously, only one succeeds.
3. **Progress & Lease Renewal:** While working, the agent periodically calls `fleetcom_task_progress` to extend its task lease deadline.
4. **Complete or Recover:** The agent marks the task complete with a summary. If the agent crashes without completing, the lease expires and the task returns to the pool for another worker.

---

## Tools Reference

| Tool | Purpose |
|------|---------|
| `fleetcom_task_list` | List open, claimed, or completed tasks |
| `fleetcom_task_create` | Add a new task to the shared queue |
| `fleetcom_task_claim` | Atomically claim an open task with a lease |
| `fleetcom_task_progress` | Update status and extend lease deadline |
| `fleetcom_task_complete` | Mark task done with an outcome summary |
| `fleetcom_task_release` | Return a claimed task back to the open pool |
| `fleetcom_event_list` | Query calendar milestones within a date range |
| `fleetcom_event_create` | Schedule a shared event or milestone |
| `fleetcom_agent_register` | Register an agent and its capabilities |
| `fleetcom_agent_heartbeat` | Update agent presence and liveness |
| `fleetcom_directory_list` | List registered agents and active workers |
| `fleetcom_policy_list` | Read active operational rules and constraints |
| `fleetcom_policy_get` | Retrieve a specific policy rule by ID |

---

## Architecture Principles

- **Zero Daemons:** Runs on demand via stdio when an agent starts. Shuts down when the session ends.
- **Pure Go:** Uses `modernc.org/sqlite` (CGO-free). Compiles into a single portable binary.
- **Local SQLite:** All data lives in a local database with write-ahead logging (WAL) enabled for high concurrent read/write throughput.

---

## License

[MIT](LICENSE) © 2026 Jonathan Perel
