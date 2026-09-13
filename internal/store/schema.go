package store

// schemaDDL is the full fleetcom schema per dev/IMPLEMENTATION-SPEC.md section 3.
const schemaDDL = `
CREATE TABLE IF NOT EXISTS agents (
  agent_id        TEXT PRIMARY KEY,
  kind            TEXT NOT NULL CHECK (kind IN ('hermes-profile', 'claude-session', 'external')),
  name            TEXT NOT NULL,
  cwd             TEXT NOT NULL,
  role            TEXT NOT NULL,
  capabilities    TEXT,
  status          TEXT NOT NULL DEFAULT 'active'
                  CHECK (status IN ('active', 'idle', 'blocked', 'done', 'offline')),
  last_heartbeat  TEXT NOT NULL,
  heartbeat_ttl   INTEGER NOT NULL DEFAULT 300,
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status);

CREATE TABLE IF NOT EXISTS office_items (
  uid             TEXT PRIMARY KEY,
  kind            TEXT NOT NULL CHECK (kind IN ('event', 'todo', 'reminder')),
  summary         TEXT NOT NULL,
  description     TEXT,
  status          TEXT NOT NULL DEFAULT 'needs-action'
                  CHECK (status IN ('needs-action', 'in-process', 'completed', 'cancelled', 'confirmed')),
  priority        INTEGER NOT NULL DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),

  dtstart         TEXT,
  dtend           TEXT,
  due             TEXT,
  tzid            TEXT NOT NULL DEFAULT 'America/Los_Angeles',
  all_day         INTEGER NOT NULL DEFAULT 0 CHECK (all_day IN (0, 1)),
  sequence        INTEGER NOT NULL DEFAULT 0,

  repeat_every    INTEGER,
  repeat_unit     TEXT CHECK (repeat_unit IN ('day', 'week')),
  remind_at       TEXT,
  remind_lead     INTEGER,

  created_by      TEXT NOT NULL REFERENCES agents(agent_id),
  owner_agent     TEXT REFERENCES agents(agent_id),
  claimed_by      TEXT REFERENCES agents(agent_id),
  claimed_at      TEXT,
  claim_expires_at TEXT,
  completed_at    TEXT,
  result_summary  TEXT,

  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL,

  CHECK (dtend IS NULL OR kind = 'event'),
  CHECK (dtend IS NULL OR dtstart IS NULL OR dtend >= dtstart),
  CHECK (repeat_every IS NULL OR repeat_every > 0),
  CHECK ((repeat_every IS NULL) = (repeat_unit IS NULL)),
  CHECK (remind_lead IS NULL OR remind_lead >= 0)
);
CREATE INDEX IF NOT EXISTS idx_items_kind_status ON office_items(kind, status);
CREATE INDEX IF NOT EXISTS idx_items_due ON office_items(due);
CREATE INDEX IF NOT EXISTS idx_items_dtstart ON office_items(dtstart);
CREATE INDEX IF NOT EXISTS idx_items_remind ON office_items(remind_at);
CREATE INDEX IF NOT EXISTS idx_items_claimed_by ON office_items(claimed_by);
CREATE INDEX IF NOT EXISTS idx_items_claim_expires ON office_items(claim_expires_at);

CREATE TABLE IF NOT EXISTS policies (
  policy_id       TEXT PRIMARY KEY,
  title           TEXT NOT NULL,
  rule_text       TEXT NOT NULL,
  level           TEXT NOT NULL CHECK (level IN ('MUST', 'MUST_NOT', 'SHOULD', 'SHOULD_NOT', 'MAY')),
  scope           TEXT NOT NULL DEFAULT 'fleet',
  active          INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_policies_scope ON policies(scope, active);

CREATE TABLE IF NOT EXISTS activity_log (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_id    TEXT NOT NULL REFERENCES agents(agent_id),
  verb        TEXT NOT NULL CHECK (verb IN ('create', 'claim', 'renew', 'release', 'complete', 'cancel', 'update')),
  target_uid  TEXT NOT NULL,
  summary     TEXT,
  ts          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_activity_ts ON activity_log(ts);

CREATE TABLE IF NOT EXISTS schema_version (
  id       INTEGER PRIMARY KEY CHECK (id = 1),
  version  INTEGER NOT NULL
);
`

// Migrate creates all tables (idempotent) and records the schema version.
func (s *Store) Migrate() error {
	if _, err := s.db.Exec(schemaDDL); err != nil {
		return err
	}
	_, err := s.db.Exec(
		`INSERT INTO schema_version (id, version) VALUES (1, ?)
		 ON CONFLICT(id) DO UPDATE SET version=excluded.version`, SchemaVersion)
	return err
}
