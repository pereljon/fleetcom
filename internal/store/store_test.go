package store

import (
	"path/filepath"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

func openTemp(t *testing.T) *Store {
	t.Helper()
	s, err := Open(filepath.Join(t.TempDir(), "fleetcom.db"))
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	t.Cleanup(func() { s.Close() })
	if err := s.Migrate(); err != nil {
		t.Fatalf("Migrate: %v", err)
	}
	return s
}

func TestMigrate_CreatesAllTables(t *testing.T) {
	s := openTemp(t)
	want := []string{"agents", "office_items", "policies", "activity_log", "schema_version"}
	for _, name := range want {
		var got string
		err := s.DB().QueryRow(
			`SELECT name FROM sqlite_master WHERE type='table' AND name=?`, name,
		).Scan(&got)
		if err != nil {
			t.Fatalf("table %q missing: %v", name, err)
		}
	}
}

func TestMigrate_IsIdempotent(t *testing.T) {
	s := openTemp(t)
	if err := s.Migrate(); err != nil {
		t.Fatalf("second Migrate: %v", err)
	}
	var v int
	if err := s.DB().QueryRow(`SELECT version FROM schema_version WHERE id=1`).Scan(&v); err != nil {
		t.Fatal(err)
	}
	if v != SchemaVersion {
		t.Fatalf("schema_version = %d, want %d", v, SchemaVersion)
	}
}

func TestOpen_SetsForeignKeysAndWAL(t *testing.T) {
	s := openTemp(t)
	var fk int
	if err := s.DB().QueryRow(`PRAGMA foreign_keys`).Scan(&fk); err != nil {
		t.Fatal(err)
	}
	if fk != 1 {
		t.Fatalf("foreign_keys = %d, want 1", fk)
	}
	var mode string
	if err := s.DB().QueryRow(`PRAGMA journal_mode`).Scan(&mode); err != nil {
		t.Fatal(err)
	}
	if mode != "wal" {
		t.Fatalf("journal_mode = %q, want wal", mode)
	}
}

func TestOfficeItems_FKRejectsUnknownCreator(t *testing.T) {
	s := openTemp(t)
	_, err := s.DB().Exec(
		`INSERT INTO office_items (uid,kind,summary,status,priority,tzid,all_day,sequence,created_by,created_at,updated_at)
		 VALUES ('u1','todo','x','needs-action',3,'America/Los_Angeles',0,0,'ghost','t','t')`)
	if err == nil {
		t.Fatal("insert with unknown created_by succeeded, want FK violation")
	}
}

func mustAgent(t *testing.T, s *Store, agentID string) {
	t.Helper()
	now := time.Now().UTC().Format(time.RFC3339)
	a := Agent{
		AgentID:       agentID,
		Kind:          "claude-session",
		Name:          agentID,
		Cwd:           "/tmp",
		Role:          "builder",
		Status:        "active",
		LastHeartbeat: now,
	}
	if err := s.RegisterAgent(a); err != nil {
		t.Fatalf("RegisterAgent(%s): %v", agentID, err)
	}
}

func TestRegisterAgent_AndGet(t *testing.T) {
	s := openTemp(t)
	mustAgent(t, s, "agent-1")

	got, err := s.GetAgent("agent-1")
	if err != nil {
		t.Fatalf("GetAgent: %v", err)
	}
	if got.AgentID != "agent-1" || got.Role != "builder" || got.Status != "active" {
		t.Fatalf("GetAgent returned %+v, want agent-1/builder/active", got)
	}
}

func TestCreateItem_AndGet(t *testing.T) {
	s := openTemp(t)
	mustAgent(t, s, "agent-1")

	item := Item{
		UID:       "item-1",
		Kind:      "todo",
		Summary:   "write tests",
		Priority:  2,
		CreatedBy: "agent-1",
	}
	if err := s.CreateItem(item); err != nil {
		t.Fatalf("CreateItem: %v", err)
	}

	got, err := s.GetItem("item-1")
	if err != nil {
		t.Fatalf("GetItem: %v", err)
	}
	if got.Summary != "write tests" || got.Status != "needs-action" || got.Priority != 2 {
		t.Fatalf("GetItem returned %+v, want summary/status/priority set", got)
	}
}

func TestListItems_FiltersByKindAndStatus(t *testing.T) {
	s := openTemp(t)
	mustAgent(t, s, "agent-1")
	s.CreateItem(Item{UID: "t1", Kind: "todo", Summary: "a", CreatedBy: "agent-1"})
	s.CreateItem(Item{UID: "t2", Kind: "todo", Summary: "b", CreatedBy: "agent-1"})
	s.CreateItem(Item{UID: "e1", Kind: "event", Summary: "c", CreatedBy: "agent-1", DtStart: "2026-09-13T00:00:00Z"})

	todos, err := s.ListItems(ItemFilter{Kind: "todo"})
	if err != nil {
		t.Fatalf("ListItems: %v", err)
	}
	if len(todos) != 2 {
		t.Fatalf("ListItems(kind=todo) returned %d items, want 2", len(todos))
	}
}

func TestListItems_FiltersByPriority(t *testing.T) {
	s := openTemp(t)
	mustAgent(t, s, "agent-1")
	s.CreateItem(Item{UID: "t1", Kind: "todo", Summary: "a", Priority: 1, CreatedBy: "agent-1"})
	s.CreateItem(Item{UID: "t2", Kind: "todo", Summary: "b", Priority: 3, CreatedBy: "agent-1"})

	urgent, err := s.ListItems(ItemFilter{Priority: 1})
	if err != nil {
		t.Fatalf("ListItems: %v", err)
	}
	if len(urgent) != 1 || urgent[0].UID != "t1" {
		t.Fatalf("ListItems(priority=1) = %+v, want just t1", urgent)
	}
}

func TestClaimItem_Succeeds_SetsInProcess(t *testing.T) {
	s := openTemp(t)
	mustAgent(t, s, "agent-1")
	s.CreateItem(Item{UID: "task-1", Kind: "todo", Summary: "a", CreatedBy: "agent-1"})

	claimed, err := s.ClaimItem("task-1", "agent-1", 30)
	if err != nil {
		t.Fatalf("ClaimItem: %v", err)
	}
	if !claimed {
		t.Fatal("ClaimItem returned false, want true for unclaimed task")
	}

	got, err := s.GetItem("task-1")
	if err != nil {
		t.Fatal(err)
	}
	if got.Status != "in-process" || got.ClaimedBy != "agent-1" {
		t.Fatalf("GetItem after claim = %+v, want status=in-process claimed_by=agent-1", got)
	}
}

func TestClaimItem_AlreadyClaimed_Fails(t *testing.T) {
	s := openTemp(t)
	mustAgent(t, s, "agent-1")
	mustAgent(t, s, "agent-2")
	s.CreateItem(Item{UID: "task-1", Kind: "todo", Summary: "a", CreatedBy: "agent-1"})

	if claimed, err := s.ClaimItem("task-1", "agent-1", 30); err != nil || !claimed {
		t.Fatalf("first claim: claimed=%v err=%v", claimed, err)
	}
	claimed, err := s.ClaimItem("task-1", "agent-2", 30)
	if err != nil {
		t.Fatalf("ClaimItem: %v", err)
	}
	if claimed {
		t.Fatal("second ClaimItem returned true, want false: task already held")
	}
}

func expireClaim(t *testing.T, s *Store, uid string) {
	t.Helper()
	past := time.Now().UTC().Add(-time.Hour).Format(time.RFC3339)
	if _, err := s.DB().Exec(`UPDATE office_items SET claim_expires_at = ? WHERE uid = ?`, past, uid); err != nil {
		t.Fatalf("expireClaim: %v", err)
	}
}

func TestClaimItem_ExpiredLease_CanBeReclaimedByAnotherAgent(t *testing.T) {
	s := openTemp(t)
	mustAgent(t, s, "agent-1")
	mustAgent(t, s, "agent-2")
	s.CreateItem(Item{UID: "task-1", Kind: "todo", Summary: "a", CreatedBy: "agent-1"})
	if claimed, err := s.ClaimItem("task-1", "agent-1", 30); err != nil || !claimed {
		t.Fatalf("first claim: claimed=%v err=%v", claimed, err)
	}
	expireClaim(t, s, "task-1")

	claimed, err := s.ClaimItem("task-1", "agent-2", 30)
	if err != nil {
		t.Fatalf("ClaimItem after expiry: %v", err)
	}
	if !claimed {
		t.Fatal("ClaimItem on an expired lease returned false, want true: crash recovery must let another agent reclaim")
	}
	got, err := s.GetItem("task-1")
	if err != nil {
		t.Fatal(err)
	}
	if got.ClaimedBy != "agent-2" {
		t.Fatalf("claimed_by = %q after reclaim, want agent-2", got.ClaimedBy)
	}
}

func TestListItems_PoolOnly_IncludesItemsWithExpiredLease(t *testing.T) {
	s := openTemp(t)
	mustAgent(t, s, "agent-1")
	s.CreateItem(Item{UID: "task-1", Kind: "todo", Summary: "a", CreatedBy: "agent-1"})
	s.ClaimItem("task-1", "agent-1", 30)
	expireClaim(t, s, "task-1")

	pool, err := s.ListItems(ItemFilter{PoolOnly: true})
	if err != nil {
		t.Fatalf("ListItems: %v", err)
	}
	if len(pool) != 1 || pool[0].UID != "task-1" {
		t.Fatalf("ListItems(PoolOnly) = %+v, want task-1 visible once its lease expired", pool)
	}
}

func TestReleaseItem_ReturnsToPool(t *testing.T) {
	s := openTemp(t)
	mustAgent(t, s, "agent-1")
	s.CreateItem(Item{UID: "task-1", Kind: "todo", Summary: "a", CreatedBy: "agent-1"})
	s.ClaimItem("task-1", "agent-1", 30)

	if err := s.ReleaseItem("task-1", "agent-1", "blocked"); err != nil {
		t.Fatalf("ReleaseItem: %v", err)
	}
	got, err := s.GetItem("task-1")
	if err != nil {
		t.Fatal(err)
	}
	if got.Status != "needs-action" || got.ClaimedBy != "" {
		t.Fatalf("GetItem after release = %+v, want status=needs-action claimed_by empty", got)
	}
}

func TestCompleteItem_SetsCompletedStatus(t *testing.T) {
	s := openTemp(t)
	mustAgent(t, s, "agent-1")
	s.CreateItem(Item{UID: "task-1", Kind: "todo", Summary: "a", CreatedBy: "agent-1"})
	s.ClaimItem("task-1", "agent-1", 30)

	if err := s.CompleteItem("task-1", "agent-1", "done"); err != nil {
		t.Fatalf("CompleteItem: %v", err)
	}
	got, err := s.GetItem("task-1")
	if err != nil {
		t.Fatal(err)
	}
	if got.Status != "completed" || got.ResultSummary != "done" {
		t.Fatalf("GetItem after complete = %+v, want status=completed result_summary=done", got)
	}
}

func TestClaimItem_ConcurrentClaims_OnlyOneWins(t *testing.T) {
	s := openTemp(t)
	for i := 0; i < 10; i++ {
		mustAgent(t, s, agentName(i))
	}
	s.CreateItem(Item{UID: "task-1", Kind: "todo", Summary: "a", CreatedBy: agentName(0)})

	var wins int64
	var wg sync.WaitGroup
	for i := 0; i < 10; i++ {
		wg.Add(1)
		go func(agentID string) {
			defer wg.Done()
			claimed, err := s.ClaimItem("task-1", agentID, 30)
			if err != nil {
				t.Errorf("ClaimItem(%s): %v", agentID, err)
				return
			}
			if claimed {
				atomic.AddInt64(&wins, 1)
			}
		}(agentName(i))
	}
	wg.Wait()

	if wins != 1 {
		t.Fatalf("wins = %d, want exactly 1 (race-free atomic claim)", wins)
	}
	got, err := s.GetItem("task-1")
	if err != nil {
		t.Fatal(err)
	}
	if got.ClaimedBy == "" {
		t.Fatal("task has no claimed_by after concurrent claim race")
	}
}

func agentName(i int) string {
	return "agent-" + string(rune('a'+i))
}

func TestCreatePolicy_AndGet(t *testing.T) {
	s := openTemp(t)
	p := Policy{
		PolicyID: "POL-GIT-001",
		Title:    "no force push to main",
		RuleText: "Agents MUST NOT force-push to main.",
		Level:    "MUST_NOT",
		Scope:    "fleet",
		Active:   true,
	}
	if err := s.CreatePolicy(p); err != nil {
		t.Fatalf("CreatePolicy: %v", err)
	}

	got, err := s.GetPolicy("POL-GIT-001")
	if err != nil {
		t.Fatalf("GetPolicy: %v", err)
	}
	if got.Title != p.Title || got.Level != "MUST_NOT" || !got.Active {
		t.Fatalf("GetPolicy returned %+v, want %+v", got, p)
	}
}

func TestListPolicies_FiltersByScopeAndActive(t *testing.T) {
	s := openTemp(t)
	s.CreatePolicy(Policy{PolicyID: "POL-1", Title: "a", RuleText: "x", Level: "MUST", Scope: "fleet", Active: true})
	s.CreatePolicy(Policy{PolicyID: "POL-2", Title: "b", RuleText: "y", Level: "MAY", Scope: "fleet", Active: false})
	s.CreatePolicy(Policy{PolicyID: "POL-3", Title: "c", RuleText: "z", Level: "MUST", Scope: "hermes", Active: true})

	active, err := s.ListPolicies("fleet", true)
	if err != nil {
		t.Fatalf("ListPolicies: %v", err)
	}
	if len(active) != 1 || active[0].PolicyID != "POL-1" {
		t.Fatalf("ListPolicies(fleet, activeOnly) = %+v, want just POL-1", active)
	}

	all, err := s.ListPolicies("fleet", false)
	if err != nil {
		t.Fatalf("ListPolicies: %v", err)
	}
	if len(all) != 2 {
		t.Fatalf("ListPolicies(fleet, all) returned %d, want 2", len(all))
	}
}
