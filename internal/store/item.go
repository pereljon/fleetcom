package store

import (
	"database/sql"
	"fmt"
	"time"
)

const itemColumns = `uid, kind, summary, description, status, priority,
	dtstart, dtend, due, tzid, all_day, sequence,
	created_by, owner_agent, claimed_by, claimed_at, claim_expires_at, completed_at, result_summary,
	created_at, updated_at`

func scanItem(row interface{ Scan(...any) error }) (*Item, error) {
	var it Item
	var description, dtstart, dtend, due, ownerAgent, claimedBy, claimedAt, claimExpiresAt, completedAt, resultSummary sql.NullString
	var allDay int
	err := row.Scan(
		&it.UID, &it.Kind, &it.Summary, &description, &it.Status, &it.Priority,
		&dtstart, &dtend, &due, &it.TZID, &allDay, &it.Seq,
		&it.CreatedBy, &ownerAgent, &claimedBy, &claimedAt, &claimExpiresAt, &completedAt, &resultSummary,
		&it.CreatedAt, &it.UpdatedAt,
	)
	if err != nil {
		return nil, err
	}
	it.Description = description.String
	it.DtStart = dtstart.String
	it.DtEnd = dtend.String
	it.Due = due.String
	it.OwnerAgent = ownerAgent.String
	it.ClaimedBy = claimedBy.String
	it.ClaimedAt = claimedAt.String
	it.ClaimExpiresAt = claimExpiresAt.String
	it.CompletedAt = completedAt.String
	it.ResultSummary = resultSummary.String
	it.AllDay = allDay != 0
	return &it, nil
}

// CreateItem inserts a new office_items row (task, event, or reminder).
func (s *Store) CreateItem(it Item) error {
	now := nowISO()
	if it.Status == "" {
		it.Status = "needs-action"
	}
	if it.Priority == 0 {
		it.Priority = 3
	}
	if it.TZID == "" {
		it.TZID = "America/Los_Angeles"
	}
	_, err := s.db.Exec(fmt.Sprintf(`INSERT INTO office_items (%s) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`, itemColumns),
		it.UID, it.Kind, it.Summary, nullable(it.Description), it.Status, it.Priority,
		nullable(it.DtStart), nullable(it.DtEnd), nullable(it.Due), it.TZID, boolToInt(it.AllDay), it.Seq,
		it.CreatedBy, nullable(it.OwnerAgent), nullable(it.ClaimedBy), nullable(it.ClaimedAt),
		nullable(it.ClaimExpiresAt), nullable(it.CompletedAt), nullable(it.ResultSummary),
		now, now)
	if err != nil {
		return err
	}
	return s.logActivity(it.CreatedBy, "create", it.UID, it.Summary)
}

// GetItem fetches a single office_items row by uid.
func (s *Store) GetItem(uid string) (*Item, error) {
	row := s.db.QueryRow(fmt.Sprintf(`SELECT %s FROM office_items WHERE uid = ?`, itemColumns), uid)
	return scanItem(row)
}

// ListItems returns office_items matching the given filter.
func (s *Store) ListItems(f ItemFilter) ([]Item, error) {
	query := fmt.Sprintf(`SELECT %s FROM office_items WHERE 1=1`, itemColumns)
	var args []any
	if f.Kind != "" {
		query += ` AND kind = ?`
		args = append(args, f.Kind)
	}
	if f.Status != "" {
		query += ` AND status = ?`
		args = append(args, f.Status)
	}
	if f.Priority != 0 {
		query += ` AND priority = ?`
		args = append(args, f.Priority)
	}
	if f.PoolOnly {
		query += ` AND (claimed_by IS NULL OR claim_expires_at < ?)`
		args = append(args, nowISO())
	}
	query += ` ORDER BY created_at`
	if f.Limit > 0 {
		query += fmt.Sprintf(` LIMIT %d`, f.Limit)
	}

	rows, err := s.db.Query(query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var items []Item
	for rows.Next() {
		it, err := scanItem(rows)
		if err != nil {
			return nil, err
		}
		items = append(items, *it)
	}
	return items, rows.Err()
}

// ClaimItem atomically claims an open or expired-lease task for agentID.
// It returns false (no error) when another agent already holds a live lease.
func (s *Store) ClaimItem(uid, agentID string, leaseMinutes int) (bool, error) {
	if leaseMinutes <= 0 {
		leaseMinutes = 30
	}
	now := nowISO()
	expires := time.Now().UTC().Add(time.Duration(leaseMinutes) * time.Minute).Format(time.RFC3339)
	res, err := s.db.Exec(`
		UPDATE office_items
		SET claimed_by = ?,
		    claimed_at = ?,
		    claim_expires_at = ?,
		    status = 'in-process',
		    sequence = sequence + 1,
		    updated_at = ?
		WHERE uid = ?
		  AND (claimed_by IS NULL OR claim_expires_at < ?)
		  AND status IN ('needs-action', 'in-process')
		  AND (owner_agent IS NULL OR owner_agent = ?)`,
		agentID, now, expires, now, uid, now, agentID)
	if err != nil {
		return false, err
	}
	n, err := res.RowsAffected()
	if err != nil {
		return false, err
	}
	if n == 0 {
		return false, nil
	}
	if err := s.logActivity(agentID, "claim", uid, ""); err != nil {
		return true, err
	}
	return true, nil
}

// ProgressItem renews an active claim's lease and records a progress note.
func (s *Store) ProgressItem(uid, agentID, note string, extendMinutes int) error {
	if extendMinutes <= 0 {
		extendMinutes = 30
	}
	now := nowISO()
	expires := time.Now().UTC().Add(time.Duration(extendMinutes) * time.Minute).Format(time.RFC3339)
	res, err := s.db.Exec(`
		UPDATE office_items
		SET claim_expires_at = ?,
		    updated_at = ?
		WHERE uid = ? AND claimed_by = ?`,
		expires, now, uid, agentID)
	if err != nil {
		return err
	}
	if n, _ := res.RowsAffected(); n == 0 {
		return fmt.Errorf("fleetcom: item %q is not claimed by %q", uid, agentID)
	}
	return s.logActivity(agentID, "renew", uid, note)
}

// ReleaseItem clears a claim and returns the item to the open pool.
func (s *Store) ReleaseItem(uid, agentID, reason string) error {
	now := nowISO()
	res, err := s.db.Exec(`
		UPDATE office_items
		SET claimed_by = NULL,
		    claimed_at = NULL,
		    claim_expires_at = NULL,
		    status = 'needs-action',
		    sequence = sequence + 1,
		    updated_at = ?
		WHERE uid = ? AND claimed_by = ?`,
		now, uid, agentID)
	if err != nil {
		return err
	}
	if n, _ := res.RowsAffected(); n == 0 {
		return fmt.Errorf("fleetcom: item %q is not claimed by %q", uid, agentID)
	}
	return s.logActivity(agentID, "release", uid, reason)
}

// CompleteItem marks a claimed item completed with an outcome summary.
func (s *Store) CompleteItem(uid, agentID, outcomeSummary string) error {
	now := nowISO()
	res, err := s.db.Exec(`
		UPDATE office_items
		SET status = 'completed',
		    completed_at = ?,
		    result_summary = ?,
		    sequence = sequence + 1,
		    updated_at = ?
		WHERE uid = ? AND claimed_by = ?`,
		now, outcomeSummary, now, uid, agentID)
	if err != nil {
		return err
	}
	if n, _ := res.RowsAffected(); n == 0 {
		return fmt.Errorf("fleetcom: item %q is not claimed by %q", uid, agentID)
	}
	return s.logActivity(agentID, "complete", uid, outcomeSummary)
}

func nullable(v string) any {
	if v == "" {
		return nil
	}
	return v
}

func boolToInt(b bool) int {
	if b {
		return 1
	}
	return 0
}
