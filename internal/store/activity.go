package store

// logActivity appends an audit-trail entry. verb must match the activity_log CHECK constraint.
func (s *Store) logActivity(agentID, verb, targetUID, summary string) error {
	_, err := s.db.Exec(
		`INSERT INTO activity_log (agent_id, verb, target_uid, summary, ts) VALUES (?, ?, ?, ?, ?)`,
		agentID, verb, targetUID, nullable(summary), nowISO())
	return err
}
