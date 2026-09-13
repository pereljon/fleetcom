package mcpserver

import (
	"context"

	"github.com/google/uuid"
	"github.com/modelcontextprotocol/go-sdk/mcp"

	"github.com/pereljon/fleetcom/internal/store"
)

const defaultTaskListLimit = 50

type taskCreateInput struct {
	AgentID     string `json:"agent_id" jsonschema:"the creating agent's id"`
	Summary     string `json:"summary"`
	Description string `json:"description,omitempty"`
	Due         string `json:"due,omitempty" jsonschema:"ISO-8601 due timestamp"`
	Priority    int    `json:"priority,omitempty" jsonschema:"1 (urgent) to 5 (low); defaults to 3"`
	TargetAgent string `json:"target_agent,omitempty" jsonschema:"assign to this agent; omit to leave in the open pool"`
}

type uidOutput struct {
	UID string `json:"uid"`
}

type taskListInput struct {
	Status   string `json:"status,omitempty"`
	Priority int    `json:"priority,omitempty"`
	PoolOnly bool   `json:"pool_only,omitempty"`
	Limit    int    `json:"limit,omitempty" jsonschema:"defaults to 50"`
}

type itemListOutput struct {
	Items []ItemView `json:"items"`
}

type taskClaimInput struct {
	TaskUID      string `json:"task_uid"`
	AgentID      string `json:"agent_id"`
	LeaseMinutes int    `json:"lease_minutes,omitempty" jsonschema:"defaults to 30"`
}

type taskClaimOutput struct {
	Claimed bool `json:"claimed"`
}

type taskProgressInput struct {
	TaskUID            string `json:"task_uid"`
	AgentID            string `json:"agent_id"`
	Note               string `json:"note,omitempty"`
	ExtendLeaseMinutes int    `json:"extend_lease_minutes,omitempty" jsonschema:"defaults to 30"`
}

type taskCompleteInput struct {
	TaskUID        string `json:"task_uid"`
	AgentID        string `json:"agent_id"`
	OutcomeSummary string `json:"outcome_summary"`
}

type taskReleaseInput struct {
	TaskUID string `json:"task_uid"`
	AgentID string `json:"agent_id"`
	Reason  string `json:"reason,omitempty"`
}

func registerTaskTools(server *mcp.Server, s *store.Store) {
	mcp.AddTool(server, &mcp.Tool{
		Name:        "fleetcom_task_create",
		Description: "Create a new task on the shared backlog.",
	}, func(_ context.Context, _ *mcp.CallToolRequest, in taskCreateInput) (*mcp.CallToolResult, uidOutput, error) {
		uid := uuid.NewString()
		if err := s.CreateItem(store.Item{
			UID: uid, Kind: "todo", Summary: in.Summary, Description: in.Description,
			Due: in.Due, Priority: in.Priority, OwnerAgent: in.TargetAgent, CreatedBy: in.AgentID,
		}); err != nil {
			return nil, uidOutput{}, err
		}
		return nil, uidOutput{UID: uid}, nil
	})

	mcp.AddTool(server, &mcp.Tool{
		Name:        "fleetcom_task_list",
		Description: "List tasks, optionally filtered by status, priority, or the open pool.",
	}, func(_ context.Context, _ *mcp.CallToolRequest, in taskListInput) (*mcp.CallToolResult, itemListOutput, error) {
		limit := in.Limit
		if limit <= 0 {
			limit = defaultTaskListLimit
		}
		items, err := s.ListItems(store.ItemFilter{
			Kind: "todo", Status: in.Status, Priority: in.Priority, PoolOnly: in.PoolOnly, Limit: limit,
		})
		if err != nil {
			return nil, itemListOutput{}, err
		}
		return nil, itemListOutput{Items: itemViews(items)}, nil
	})

	mcp.AddTool(server, &mcp.Tool{
		Name:        "fleetcom_task_claim",
		Description: "Atomically claim an open (or lease-expired) task.",
	}, func(_ context.Context, _ *mcp.CallToolRequest, in taskClaimInput) (*mcp.CallToolResult, taskClaimOutput, error) {
		claimed, err := s.ClaimItem(in.TaskUID, in.AgentID, in.LeaseMinutes)
		if err != nil {
			return nil, taskClaimOutput{}, err
		}
		return nil, taskClaimOutput{Claimed: claimed}, nil
	})

	mcp.AddTool(server, &mcp.Tool{
		Name:        "fleetcom_task_progress",
		Description: "Renew a held claim's lease and record a progress note.",
	}, func(_ context.Context, _ *mcp.CallToolRequest, in taskProgressInput) (*mcp.CallToolResult, okOutput, error) {
		if err := s.ProgressItem(in.TaskUID, in.AgentID, in.Note, in.ExtendLeaseMinutes); err != nil {
			return nil, okOutput{}, err
		}
		return nil, okOutput{OK: true}, nil
	})

	mcp.AddTool(server, &mcp.Tool{
		Name:        "fleetcom_task_complete",
		Description: "Mark a held task completed with an outcome summary.",
	}, func(_ context.Context, _ *mcp.CallToolRequest, in taskCompleteInput) (*mcp.CallToolResult, okOutput, error) {
		if err := s.CompleteItem(in.TaskUID, in.AgentID, in.OutcomeSummary); err != nil {
			return nil, okOutput{}, err
		}
		return nil, okOutput{OK: true}, nil
	})

	mcp.AddTool(server, &mcp.Tool{
		Name:        "fleetcom_task_release",
		Description: "Release a held claim, returning the task to the open pool.",
	}, func(_ context.Context, _ *mcp.CallToolRequest, in taskReleaseInput) (*mcp.CallToolResult, okOutput, error) {
		if err := s.ReleaseItem(in.TaskUID, in.AgentID, in.Reason); err != nil {
			return nil, okOutput{}, err
		}
		return nil, okOutput{OK: true}, nil
	})
}
