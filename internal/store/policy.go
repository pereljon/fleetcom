package store

const policyColumns = `policy_id, title, rule_text, level, scope, active, created_at, updated_at`

// CreatePolicy inserts a fleet policy row.
func (s *Store) CreatePolicy(p Policy) error {
	now := nowISO()
	if p.Scope == "" {
		p.Scope = "fleet"
	}
	_, err := s.db.Exec(
		`INSERT INTO policies (policy_id, title, rule_text, level, scope, active, created_at, updated_at)
		 VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
		p.PolicyID, p.Title, p.RuleText, p.Level, p.Scope, boolToInt(p.Active), now, now)
	return err
}

// GetPolicy fetches a single policy by id.
func (s *Store) GetPolicy(policyID string) (*Policy, error) {
	row := s.db.QueryRow(`SELECT `+policyColumns+` FROM policies WHERE policy_id = ?`, policyID)
	return scanPolicy(row)
}

// ListPolicies returns policies for a scope, optionally restricted to active ones.
func (s *Store) ListPolicies(scope string, activeOnly bool) ([]Policy, error) {
	query := `SELECT ` + policyColumns + ` FROM policies WHERE scope = ?`
	if activeOnly {
		query += ` AND active = 1`
	}
	query += ` ORDER BY policy_id`

	rows, err := s.db.Query(query, scope)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var policies []Policy
	for rows.Next() {
		p, err := scanPolicy(rows)
		if err != nil {
			return nil, err
		}
		policies = append(policies, *p)
	}
	return policies, rows.Err()
}

func scanPolicy(row interface{ Scan(...any) error }) (*Policy, error) {
	var p Policy
	var active int
	if err := row.Scan(&p.PolicyID, &p.Title, &p.RuleText, &p.Level, &p.Scope, &active, &p.CreatedAt, &p.UpdatedAt); err != nil {
		return nil, err
	}
	p.Active = active != 0
	return &p, nil
}
