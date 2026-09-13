package mcpserver

import (
	"context"
	"encoding/json"
	"path/filepath"
	"testing"

	"github.com/modelcontextprotocol/go-sdk/mcp"

	"github.com/pereljon/fleetcom/internal/store"
)

func connectTest(t *testing.T) (*mcp.ClientSession, *store.Store) {
	t.Helper()
	s, err := store.Open(filepath.Join(t.TempDir(), "fleetcom.db"))
	if err != nil {
		t.Fatalf("store.Open: %v", err)
	}
	t.Cleanup(func() { s.Close() })
	if err := s.Migrate(); err != nil {
		t.Fatalf("Migrate: %v", err)
	}

	server := NewServer(s)
	t1, t2 := mcp.NewInMemoryTransports()
	ctx := context.Background()
	if _, err := server.Connect(ctx, t1, nil); err != nil {
		t.Fatalf("server.Connect: %v", err)
	}
	client := mcp.NewClient(&mcp.Implementation{Name: "test-client", Version: "v0.0.1"}, nil)
	cs, err := client.Connect(ctx, t2, nil)
	if err != nil {
		t.Fatalf("client.Connect: %v", err)
	}
	t.Cleanup(func() { cs.Close() })
	return cs, s
}

// call invokes a tool and decodes its structured output into out (skipped if out is nil).
func call(t *testing.T, cs *mcp.ClientSession, name string, args map[string]any, out any) *mcp.CallToolResult {
	t.Helper()
	res, err := cs.CallTool(context.Background(), &mcp.CallToolParams{Name: name, Arguments: args})
	if err != nil {
		t.Fatalf("CallTool(%s): %v", name, err)
	}
	if res.IsError {
		t.Fatalf("CallTool(%s) returned tool error: %+v", name, res.Content)
	}
	if out != nil {
		b, err := json.Marshal(res.StructuredContent)
		if err != nil {
			t.Fatalf("marshal structured content: %v", err)
		}
		if err := json.Unmarshal(b, out); err != nil {
			t.Fatalf("unmarshal into %T: %v", out, err)
		}
	}
	return res
}

func TestAgentRegisterHeartbeatDirectory(t *testing.T) {
	cs, _ := connectTest(t)

	call(t, cs, "fleetcom_agent_register", map[string]any{
		"agent_id": "agent-1", "kind": "claude-session", "name": "Builder",
		"cwd": "/tmp", "role": "builder", "capabilities": []string{"go", "sqlite"},
	}, nil)

	call(t, cs, "fleetcom_agent_heartbeat", map[string]any{"agent_id": "agent-1", "status": "idle"}, nil)

	var dir struct {
		Agents []struct {
			AgentID string `json:"agent_id"`
			Status  string `json:"status"`
		} `json:"agents"`
	}
	call(t, cs, "fleetcom_directory_list", map[string]any{}, &dir)
	if len(dir.Agents) != 1 || dir.Agents[0].AgentID != "agent-1" || dir.Agents[0].Status != "idle" {
		t.Fatalf("directory_list = %+v, want one agent-1 with status idle", dir.Agents)
	}
}

func TestTaskLifecycle(t *testing.T) {
	cs, _ := connectTest(t)
	call(t, cs, "fleetcom_agent_register", map[string]any{
		"agent_id": "agent-1", "kind": "claude-session", "name": "a", "cwd": "/tmp", "role": "builder",
	}, nil)

	var created struct {
		UID string `json:"uid"`
	}
	call(t, cs, "fleetcom_task_create", map[string]any{
		"agent_id": "agent-1", "summary": "write tests", "priority": 2,
	}, &created)
	if created.UID == "" {
		t.Fatal("task_create returned empty uid")
	}

	var listed struct {
		Items []struct {
			UID     string `json:"uid"`
			Summary string `json:"summary"`
		} `json:"items"`
	}
	call(t, cs, "fleetcom_task_list", map[string]any{"pool_only": true}, &listed)
	if len(listed.Items) != 1 || listed.Items[0].UID != created.UID {
		t.Fatalf("task_list = %+v, want one item %s", listed.Items, created.UID)
	}

	var claimed struct {
		Claimed bool `json:"claimed"`
	}
	call(t, cs, "fleetcom_task_claim", map[string]any{
		"task_uid": created.UID, "agent_id": "agent-1", "lease_minutes": 30,
	}, &claimed)
	if !claimed.Claimed {
		t.Fatal("task_claim: claimed=false, want true")
	}

	call(t, cs, "fleetcom_task_progress", map[string]any{
		"task_uid": created.UID, "agent_id": "agent-1", "note": "halfway", "extend_lease_minutes": 15,
	}, nil)

	call(t, cs, "fleetcom_task_complete", map[string]any{
		"task_uid": created.UID, "agent_id": "agent-1", "outcome_summary": "done",
	}, nil)

	var afterComplete struct {
		Items []struct {
			Status string `json:"status"`
		} `json:"items"`
	}
	call(t, cs, "fleetcom_task_list", map[string]any{"status": "completed"}, &afterComplete)
	if len(afterComplete.Items) != 1 || afterComplete.Items[0].Status != "completed" {
		t.Fatalf("task_list(status=completed) = %+v", afterComplete.Items)
	}
}

func TestTaskClaim_AlreadyClaimed_ReturnsFalseNotError(t *testing.T) {
	cs, _ := connectTest(t)
	call(t, cs, "fleetcom_agent_register", map[string]any{"agent_id": "agent-1", "kind": "claude-session", "name": "a", "cwd": "/tmp", "role": "r"}, nil)
	call(t, cs, "fleetcom_agent_register", map[string]any{"agent_id": "agent-2", "kind": "claude-session", "name": "b", "cwd": "/tmp", "role": "r"}, nil)

	var created struct {
		UID string `json:"uid"`
	}
	call(t, cs, "fleetcom_task_create", map[string]any{"agent_id": "agent-1", "summary": "x"}, &created)

	var first, second struct {
		Claimed bool `json:"claimed"`
	}
	call(t, cs, "fleetcom_task_claim", map[string]any{"task_uid": created.UID, "agent_id": "agent-1"}, &first)
	call(t, cs, "fleetcom_task_claim", map[string]any{"task_uid": created.UID, "agent_id": "agent-2"}, &second)
	if !first.Claimed || second.Claimed {
		t.Fatalf("first.Claimed=%v second.Claimed=%v, want true then false", first.Claimed, second.Claimed)
	}
}

func TestTaskRelease_ReturnsToPool(t *testing.T) {
	cs, _ := connectTest(t)
	call(t, cs, "fleetcom_agent_register", map[string]any{"agent_id": "agent-1", "kind": "claude-session", "name": "a", "cwd": "/tmp", "role": "r"}, nil)

	var created struct {
		UID string `json:"uid"`
	}
	call(t, cs, "fleetcom_task_create", map[string]any{"agent_id": "agent-1", "summary": "x"}, &created)
	call(t, cs, "fleetcom_task_claim", map[string]any{"task_uid": created.UID, "agent_id": "agent-1"}, nil)
	call(t, cs, "fleetcom_task_release", map[string]any{"task_uid": created.UID, "agent_id": "agent-1", "reason": "blocked"}, nil)

	var pool struct {
		Items []struct{ UID string } `json:"items"`
	}
	call(t, cs, "fleetcom_task_list", map[string]any{"pool_only": true}, &pool)
	if len(pool.Items) != 1 {
		t.Fatalf("task_list(pool_only) after release = %+v, want the released task back in the pool", pool.Items)
	}
}

func TestEventCreateAndList(t *testing.T) {
	cs, _ := connectTest(t)
	call(t, cs, "fleetcom_agent_register", map[string]any{"agent_id": "agent-1", "kind": "claude-session", "name": "a", "cwd": "/tmp", "role": "r"}, nil)

	call(t, cs, "fleetcom_event_create", map[string]any{
		"agent_id": "agent-1", "summary": "standup",
		"dtstart": "2026-09-15T09:00:00Z", "dtend": "2026-09-15T09:30:00Z",
	}, nil)
	call(t, cs, "fleetcom_event_create", map[string]any{
		"agent_id": "agent-1", "summary": "out of range",
		"dtstart": "2026-10-01T09:00:00Z", "dtend": "2026-10-01T09:30:00Z",
	}, nil)

	var listed struct {
		Items []struct{ Summary string } `json:"items"`
	}
	call(t, cs, "fleetcom_event_list", map[string]any{
		"start_iso": "2026-09-01T00:00:00Z", "end_iso": "2026-09-30T00:00:00Z",
	}, &listed)
	if len(listed.Items) != 1 || listed.Items[0].Summary != "standup" {
		t.Fatalf("event_list = %+v, want just standup", listed.Items)
	}
}

func TestPolicyListAndGet(t *testing.T) {
	cs, s := connectTest(t)
	if err := s.CreatePolicy(store.Policy{
		PolicyID: "POL-1", Title: "no force push", RuleText: "MUST NOT force-push to main",
		Level: "MUST_NOT", Scope: "fleet", Active: true,
	}); err != nil {
		t.Fatalf("seed CreatePolicy: %v", err)
	}

	var listed struct {
		Policies []struct {
			PolicyID string `json:"policy_id"`
		} `json:"policies"`
	}
	call(t, cs, "fleetcom_policy_list", map[string]any{"scope": "fleet", "active_only": true}, &listed)
	if len(listed.Policies) != 1 || listed.Policies[0].PolicyID != "POL-1" {
		t.Fatalf("policy_list = %+v, want just POL-1", listed.Policies)
	}

	var got struct{ Title string }
	call(t, cs, "fleetcom_policy_get", map[string]any{"policy_id": "POL-1"}, &got)
	if got.Title != "no force push" {
		t.Fatalf("policy_get.Title = %q, want %q", got.Title, "no force push")
	}
}
