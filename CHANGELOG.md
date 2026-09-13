# Changelog

All notable changes to this project will be documented in this file.

## Unreleased

- Add `internal/store`: SQLite (WAL) schema for `agents`, `office_items`, `policies`, `activity_log`, with atomic task claiming, agent directory, and policy CRUD.
- Add `cmd/fleetcom-mcp`: stdio MCP server exposing 13 `fleetcom_*` tools (tasks, calendar events, agent directory, fleet policy) over `internal/mcpserver`.
