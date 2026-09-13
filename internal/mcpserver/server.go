// Package mcpserver exposes fleetcom's store over the Model Context Protocol
// (stdio JSON-RPC), per dev/IMPLEMENTATION-SPEC.md section 5.
package mcpserver

import (
	"github.com/modelcontextprotocol/go-sdk/mcp"

	"github.com/pereljon/fleetcom/internal/store"
)

// NewServer builds an MCP server exposing the fleetcom_* tool surface over s.
func NewServer(s *store.Store) *mcp.Server {
	server := mcp.NewServer(&mcp.Implementation{Name: "fleetcom", Version: "0.1.0"}, nil)
	registerAgentTools(server, s)
	registerTaskTools(server, s)
	registerEventTools(server, s)
	registerPolicyTools(server, s)
	return server
}
