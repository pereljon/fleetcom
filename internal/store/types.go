package store

// Agent is a row in the agents directory table.
type Agent struct {
	AgentID       string
	Kind          string
	Name          string
	Cwd           string
	Role          string
	Capabilities  string
	Status        string
	LastHeartbeat string
	HeartbeatTTL  int
	CreatedAt     string
	UpdatedAt     string
}

// Item is a row in office_items: a task, event, or reminder.
type Item struct {
	UID         string
	Kind        string
	Summary     string
	Description string
	Status      string
	Priority    int

	DtStart string
	DtEnd   string
	Due     string
	TZID    string
	AllDay  bool
	Seq     int

	CreatedBy      string
	OwnerAgent     string
	ClaimedBy      string
	ClaimedAt      string
	ClaimExpiresAt string
	CompletedAt    string
	ResultSummary  string

	CreatedAt string
	UpdatedAt string
}

// ItemFilter selects a subset of office_items for ListItems.
type ItemFilter struct {
	Kind     string
	Status   string
	Priority int
	PoolOnly bool
	Limit    int
}

// Policy is a row in the policies table.
type Policy struct {
	PolicyID  string
	Title     string
	RuleText  string
	Level     string
	Scope     string
	Active    bool
	CreatedAt string
	UpdatedAt string
}
