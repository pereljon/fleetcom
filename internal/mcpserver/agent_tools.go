package mcpserver

import (
	"context"
	"encoding/json"

	"github.com/modelcontextprotocol/go-sdk/mcp"

	"github.com/pereljon/fleetcom/internal/store"
)

type agentRegisterInput struct {
	AgentID      string   `json:"agent_id" jsonschema:"the registering agent's stable id, e.g. 'hermes:builder'"`
	Kind         string   `json:"kind" jsonschema:"one of hermes-profile, claude-session, external"`
	Name         string   `json:"name"`
	Cwd          string   `json:"cwd" jsonschema:"the agent's working directory"`
	Role         string   `json:"role"`
	Capabilities []string `json:"capabilities,omitempty" jsonschema:"toolsets/skills the agent has"`
}

type okOutput struct {
	OK bool `json:"ok"`
}

type agentHeartbeatInput struct {
	AgentID string `json:"agent_id"`
	Status  string `json:"status,omitempty" jsonschema:"active, idle, blocked, done, or offline; defaults to active"`
}

type directoryListInput struct{}

type directoryListOutput struct {
	Agents []agentView `json:"agents"`
}

type agentView struct {
	AgentID       string   `json:"agent_id"`
	Kind          string   `json:"kind"`
	Name          string   `json:"name"`
	Cwd           string   `json:"cwd"`
	Role          string   `json:"role"`
	Capabilities  []string `json:"capabilities,omitempty"`
	Status        string   `json:"status"`
	LastHeartbeat string   `json:"last_heartbeat"`
}

func registerAgentTools(server *mcp.Server, s *store.Store) {
	mcp.AddTool(server, &mcp.Tool{
		Name:        "fleetcom_agent_register",
		Description: "Register or update an agent in the fleet directory.",
	}, func(_ context.Context, _ *mcp.CallToolRequest, in agentRegisterInput) (*mcp.CallToolResult, okOutput, error) {
		var capsJSON string
		if len(in.Capabilities) > 0 {
			b, err := json.Marshal(in.Capabilities)
			if err != nil {
				return nil, okOutput{}, err
			}
			capsJSON = string(b)
		}
		if err := s.RegisterAgent(store.Agent{
			AgentID: in.AgentID, Kind: in.Kind, Name: in.Name,
			Cwd: in.Cwd, Role: in.Role, Capabilities: capsJSON,
		}); err != nil {
			return nil, okOutput{}, err
		}
		return nil, okOutput{OK: true}, nil
	})

	mcp.AddTool(server, &mcp.Tool{
		Name:        "fleetcom_agent_heartbeat",
		Description: "Record liveness for an already-registered agent.",
	}, func(_ context.Context, _ *mcp.CallToolRequest, in agentHeartbeatInput) (*mcp.CallToolResult, okOutput, error) {
		if err := s.Heartbeat(in.AgentID, in.Status); err != nil {
			return nil, okOutput{}, err
		}
		return nil, okOutput{OK: true}, nil
	})

	mcp.AddTool(server, &mcp.Tool{
		Name:        "fleetcom_directory_list",
		Description: "List the active agent directory.",
	}, func(_ context.Context, _ *mcp.CallToolRequest, _ directoryListInput) (*mcp.CallToolResult, directoryListOutput, error) {
		agents, err := s.ListAgents()
		if err != nil {
			return nil, directoryListOutput{}, err
		}
		views := make([]agentView, len(agents))
		for i, a := range agents {
			var caps []string
			if a.Capabilities != "" {
				_ = json.Unmarshal([]byte(a.Capabilities), &caps)
			}
			views[i] = agentView{
				AgentID: a.AgentID, Kind: a.Kind, Name: a.Name, Cwd: a.Cwd, Role: a.Role,
				Capabilities: caps, Status: a.Status, LastHeartbeat: a.LastHeartbeat,
			}
		}
		return nil, directoryListOutput{Agents: views}, nil
	})
}
