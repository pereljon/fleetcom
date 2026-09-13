# CODEMAP - where things live

Owns: a one-line purpose for each function or module, for locating code. Does NOT hold logic flow (dev/SKELETON.md) or architecture (dev/IMPLEMENTATION-SPEC.md).
Maintain: add a row when code lands; keep each purpose to one line.

| function/module | one-line purpose |
|-----------------|------------------|
| `internal/store/store.go` | `Store`, `Open`/`Close`/`DB`, `DefaultDBPath` (honors `FLEETCOM_DB_PATH`) |
| `internal/store/schema.go` | DDL for `agents`, `office_items`, `policies`, `activity_log`, `schema_version`; `Migrate` |
| `internal/store/types.go` | `Agent`, `Item`, `ItemFilter`, `Policy` structs |
| `internal/store/agent.go` | `RegisterAgent` (upsert), `GetAgent`, `Heartbeat`, `ListAgents` |
| `internal/store/item.go` | office_items CRUD: `CreateItem`, `GetItem`, `ListItems`, `ClaimItem`, `ProgressItem`, `ReleaseItem`, `CompleteItem` |
| `internal/store/policy.go` | `CreatePolicy`, `GetPolicy`, `ListPolicies` |
| `internal/store/activity.go` | `logActivity` audit-trail helper used by item/claim mutations |
| `cmd/fleetcom-mcp/main.go` | binary entrypoint: `--db` flag, `store.Open`+`Migrate`, `mcpserver.NewServer(...).Run` over stdio |
| `internal/mcpserver/server.go` | `NewServer(s)` builds the `*mcp.Server` and registers all tool groups |
| `internal/mcpserver/views.go` | `ItemView`/`PolicyView` wire types + `itemView(s)`/`policyView(s)` converters from store types |
| `internal/mcpserver/agent_tools.go` | `fleetcom_agent_register`, `fleetcom_agent_heartbeat`, `fleetcom_directory_list` |
| `internal/mcpserver/task_tools.go` | `fleetcom_task_{create,list,claim,progress,complete,release}` |
| `internal/mcpserver/event_tools.go` | `fleetcom_event_{create,list}` (date-range filtering done in Go, not SQL) |
| `internal/mcpserver/policy_tools.go` | `fleetcom_policy_{list,get}` |
