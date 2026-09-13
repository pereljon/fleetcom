package mcpserver

import "github.com/pereljon/fleetcom/internal/store"

// ItemView is the wire representation of a store.Item returned by task/event tools.
type ItemView struct {
	UID            string `json:"uid"`
	Kind           string `json:"kind"`
	Summary        string `json:"summary"`
	Description    string `json:"description,omitempty"`
	Status         string `json:"status"`
	Priority       int    `json:"priority"`
	DtStart        string `json:"dtstart,omitempty"`
	DtEnd          string `json:"dtend,omitempty"`
	Due            string `json:"due,omitempty"`
	CreatedBy      string `json:"created_by"`
	OwnerAgent     string `json:"owner_agent,omitempty"`
	ClaimedBy      string `json:"claimed_by,omitempty"`
	ClaimExpiresAt string `json:"claim_expires_at,omitempty"`
	ResultSummary  string `json:"result_summary,omitempty"`
}

func itemView(it store.Item) ItemView {
	return ItemView{
		UID: it.UID, Kind: it.Kind, Summary: it.Summary, Description: it.Description,
		Status: it.Status, Priority: it.Priority,
		DtStart: it.DtStart, DtEnd: it.DtEnd, Due: it.Due,
		CreatedBy: it.CreatedBy, OwnerAgent: it.OwnerAgent,
		ClaimedBy: it.ClaimedBy, ClaimExpiresAt: it.ClaimExpiresAt,
		ResultSummary: it.ResultSummary,
	}
}

func itemViews(items []store.Item) []ItemView {
	views := make([]ItemView, len(items))
	for i, it := range items {
		views[i] = itemView(it)
	}
	return views
}

// PolicyView is the wire representation of a store.Policy.
type PolicyView struct {
	PolicyID string `json:"policy_id"`
	Title    string `json:"title"`
	RuleText string `json:"rule_text"`
	Level    string `json:"level"`
	Scope    string `json:"scope"`
	Active   bool   `json:"active"`
}

func policyView(p store.Policy) PolicyView {
	return PolicyView{
		PolicyID: p.PolicyID, Title: p.Title, RuleText: p.RuleText,
		Level: p.Level, Scope: p.Scope, Active: p.Active,
	}
}

func policyViews(policies []store.Policy) []PolicyView {
	views := make([]PolicyView, len(policies))
	for i, p := range policies {
		views[i] = policyView(p)
	}
	return views
}
