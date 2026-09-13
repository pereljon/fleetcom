package store

import "time"

func nowISO() string { return time.Now().UTC().Format(time.RFC3339) }

// RegisterAgent inserts or updates an agent's directory entry.
func (s *Store) RegisterAgent(a Agent) error {
	now := nowISO()
	if a.LastHeartbeat == "" {
		a.LastHeartbeat = now
	}
	if a.Status == "" {
		a.Status = "active"
	}
	if a.HeartbeatTTL == 0 {
		a.HeartbeatTTL = 300
	}
	_, err := s.db.Exec(`
		INSERT INTO agents (agent_id, kind, name, cwd, role, capabilities, status, last_heartbeat, heartbeat_ttl, created_at, updated_at)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
		ON CONFLICT(agent_id) DO UPDATE SET
			kind=excluded.kind, name=excluded.name, cwd=excluded.cwd, role=excluded.role,
			capabilities=excluded.capabilities, status=excluded.status,
			last_heartbeat=excluded.last_heartbeat, heartbeat_ttl=excluded.heartbeat_ttl,
			updated_at=excluded.updated_at`,
		a.AgentID, a.Kind, a.Name, a.Cwd, a.Role, a.Capabilities, a.Status,
		a.LastHeartbeat, a.HeartbeatTTL, now, now)
	return err
}

// GetAgent fetches a single agent by id.
func (s *Store) GetAgent(agentID string) (*Agent, error) {
	var a Agent
	err := s.db.QueryRow(`
		SELECT agent_id, kind, name, cwd, role, capabilities, status, last_heartbeat, heartbeat_ttl, created_at, updated_at
		FROM agents WHERE agent_id = ?`, agentID,
	).Scan(&a.AgentID, &a.Kind, &a.Name, &a.Cwd, &a.Role, &a.Capabilities, &a.Status,
		&a.LastHeartbeat, &a.HeartbeatTTL, &a.CreatedAt, &a.UpdatedAt)
	if err != nil {
		return nil, err
	}
	return &a, nil
}

// Heartbeat updates an agent's liveness timestamp and status.
func (s *Store) Heartbeat(agentID, status string) error {
	if status == "" {
		status = "active"
	}
	_, err := s.db.Exec(
		`UPDATE agents SET status = ?, last_heartbeat = ?, updated_at = ? WHERE agent_id = ?`,
		status, nowISO(), nowISO(), agentID)
	return err
}

// ListAgents returns the full agent directory.
func (s *Store) ListAgents() ([]Agent, error) {
	rows, err := s.db.Query(`
		SELECT agent_id, kind, name, cwd, role, capabilities, status, last_heartbeat, heartbeat_ttl, created_at, updated_at
		FROM agents ORDER BY agent_id`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var agents []Agent
	for rows.Next() {
		var a Agent
		if err := rows.Scan(&a.AgentID, &a.Kind, &a.Name, &a.Cwd, &a.Role, &a.Capabilities, &a.Status,
			&a.LastHeartbeat, &a.HeartbeatTTL, &a.CreatedAt, &a.UpdatedAt); err != nil {
			return nil, err
		}
		agents = append(agents, a)
	}
	return agents, rows.Err()
}
