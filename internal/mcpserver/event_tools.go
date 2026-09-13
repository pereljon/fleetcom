package mcpserver

import (
	"context"

	"github.com/google/uuid"
	"github.com/modelcontextprotocol/go-sdk/mcp"

	"github.com/pereljon/fleetcom/internal/store"
)

type eventCreateInput struct {
	AgentID     string `json:"agent_id" jsonschema:"the creating agent's id"`
	Summary     string `json:"summary"`
	Description string `json:"description,omitempty"`
	DtStart     string `json:"dtstart" jsonschema:"ISO-8601 start timestamp"`
	DtEnd       string `json:"dtend" jsonschema:"ISO-8601 end timestamp"`
}

type eventListInput struct {
	StartISO string `json:"start_iso"`
	EndISO   string `json:"end_iso"`
}

func registerEventTools(server *mcp.Server, s *store.Store) {
	mcp.AddTool(server, &mcp.Tool{
		Name:        "fleetcom_event_create",
		Description: "Create a calendar event.",
	}, func(_ context.Context, _ *mcp.CallToolRequest, in eventCreateInput) (*mcp.CallToolResult, uidOutput, error) {
		uid := uuid.NewString()
		if err := s.CreateItem(store.Item{
			UID: uid, Kind: "event", Summary: in.Summary, Description: in.Description,
			DtStart: in.DtStart, DtEnd: in.DtEnd, CreatedBy: in.AgentID,
		}); err != nil {
			return nil, uidOutput{}, err
		}
		return nil, uidOutput{UID: uid}, nil
	})

	mcp.AddTool(server, &mcp.Tool{
		Name:        "fleetcom_event_list",
		Description: "List calendar events with dtstart in [start_iso, end_iso].",
	}, func(_ context.Context, _ *mcp.CallToolRequest, in eventListInput) (*mcp.CallToolResult, itemListOutput, error) {
		items, err := s.ListItems(store.ItemFilter{Kind: "event"})
		if err != nil {
			return nil, itemListOutput{}, err
		}
		var inRange []store.Item
		for _, it := range items {
			if it.DtStart >= in.StartISO && it.DtStart <= in.EndISO {
				inRange = append(inRange, it)
			}
		}
		return nil, itemListOutput{Items: itemViews(inRange)}, nil
	})
}
