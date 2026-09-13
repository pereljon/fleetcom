package store

import (
	"database/sql"
	"fmt"
	"os"
	"path/filepath"

	_ "modernc.org/sqlite"
)

const SchemaVersion = 1

type Store struct{ db *sql.DB }

func (s *Store) DB() *sql.DB  { return s.db }
func (s *Store) Close() error { return s.db.Close() }

// Open opens (creating if needed) the SQLite DB at path and applies the
// connection PRAGMAs every connection in the pool must carry.
func Open(path string) (*Store, error) {
	if dir := filepath.Dir(path); dir != "" {
		if err := os.MkdirAll(dir, 0o755); err != nil {
			return nil, err
		}
	}
	dsn := fmt.Sprintf("file:%s?_pragma=journal_mode(WAL)&_pragma=busy_timeout(5000)&_pragma=foreign_keys(ON)", path)
	db, err := sql.Open("sqlite", dsn)
	if err != nil {
		return nil, err
	}
	if err := db.Ping(); err != nil {
		db.Close()
		return nil, err
	}
	return &Store{db: db}, nil
}

// DefaultDBPath returns the fleetcom DB path, honoring FLEETCOM_DB_PATH.
func DefaultDBPath() string {
	if p := os.Getenv("FLEETCOM_DB_PATH"); p != "" {
		return p
	}
	home, err := os.UserHomeDir()
	if err != nil {
		return ".fleetcom/fleetcom.db"
	}
	return filepath.Join(home, "Claude", "-hermes", "fleetcom.db")
}
