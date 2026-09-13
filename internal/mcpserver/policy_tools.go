package mcpserver

import (
	"context"

	"github.com/modelcontextprotocol/go-sdk/mcp"

	"github.com/pereljon/fleetcom/internal/store"
)

type policyListInput struct {
	Scope      string `json:"scope,omitempty" jsonschema:"defaults to fleet"`
	ActiveOnly *bool  `json:"active_only,omitempty" jsonschema:"defaults to true"`
}

type policyListOutput struct {
	Policies []PolicyView `json:"policies"`
}

type policyGetInput struct {
	PolicyID string `json:"policy_id"`
}

func registerPolicyTools(server *mcp.Server, s *store.Store) {
	mcp.AddTool(server, &mcp.Tool{
		Name:        "fleetcom_policy_list",
		Description: "List fleet policies for a scope.",
	}, func(_ context.Context, _ *mcp.CallToolRequest, in policyListInput) (*mcp.CallToolResult, policyListOutput, error) {
		scope := in.Scope
		if scope == "" {
			scope = "fleet"
		}
		activeOnly := true
		if in.ActiveOnly != nil {
			activeOnly = *in.ActiveOnly
		}
		policies, err := s.ListPolicies(scope, activeOnly)
		if err != nil {
			return nil, policyListOutput{}, err
		}
		return nil, policyListOutput{Policies: policyViews(policies)}, nil
	})

	mcp.AddTool(server, &mcp.Tool{
		Name:        "fleetcom_policy_get",
		Description: "Fetch a single fleet policy by id.",
	}, func(_ context.Context, _ *mcp.CallToolRequest, in policyGetInput) (*mcp.CallToolResult, PolicyView, error) {
		p, err := s.GetPolicy(in.PolicyID)
		if err != nil {
			return nil, PolicyView{}, err
		}
		return nil, policyView(*p), nil
	})
}
