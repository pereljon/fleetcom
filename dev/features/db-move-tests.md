# Database move tests

Owns: the test plan and review findings for the database move. Does NOT hold the design or the runbook (`db-move.md`).

Tests use `tmp_path`, never the live database. Tests use no sleeps. The project has no `pytest-timeout`, so each multi-process test bounds its own wait with `subprocess` or `join` timeouts. Single-process tests cannot block, because they patch the clock and `sleep`.

## Automated tests

| Area | Case | Expected result |
|------|------|-----------------|
| Happy path | `default_db_path` with no env var and a patched home | Returns `<home>/.fleetcom/fleetcom.db` |
| Config precedence | `FLEETCOM_DB_PATH` set | The env var wins over the default (existing test) |
| Config precedence | `--db` and the env var both set | The flag wins (existing test) |
| Startup race | Six processes released by a `multiprocessing.Barrier` run `connect` and `migrate` on one new file, 20 rounds | Every process exits 0, and the file is in WAL mode |
| Retry recovers | The pragma raises `database is locked` twice, then succeeds | `connect` returns, and the `busy_timeout` and `foreign_keys` pragmas ran |
| Retry limit | The pragma always raises `database is locked`, with the clock and `sleep` patched | `connect` re-raises after 10 seconds of patched time |
| Retry scope | The pragma raises an `OperationalError` without `locked` | `connect` re-raises on the first try |

The startup race test must fail on the current `db.connect` before the fix lands.

`sqlite3.Connection.execute` cannot be patched on an instance, so the retry tests patch `db.sqlite3.connect` to return a connection subclass.

## Runbook rehearsal

Rehearse steps 7 to 12 of the runbook on a generated database in a temp folder, before the real cutover. Use the Homebrew `sqlite3` binary that the runbook names.

1. Generate rows in all three tables, update one row, then end the writer with `os._exit`. This leaves a populated WAL, which a clean close would remove.
2. Hold a second connection open. Confirm that step 7 reports the holder, step 8's `ls` lists the `-wal` file, and the step 11 guard prints nothing.
3. Close that connection. Confirm that step 8's `ls` lists no sidecars.
4. Run the guarded move and step 12. Confirm `moved`, `ok`, `wal`, a matching hash, no sidecars, and a `.dump` of `$N.pre-move` with the same hash.
5. Reset, then create a folder at the destination. Confirm that the guard prints nothing and the source stays intact.
6. Reverse the move with the Rollback commands. Confirm a matching hash at the old path.

## Live checks

These are runbook steps 12 to 16. The user runs them at cutover.

- The `.dump` hash at the new path matches the hash from step 8.
- The installed build prints the new default path.
- A real write and read work from Hermes, Claude Code, and Codex.
- No `fleetcom.db` exists at the old path after every client restarts.
- `tmutil isexcluded ~/.fleetcom` prints `[Included]`.

Codex may need an interactive session, because `codex exec` refuses the tool call under approval policy `never`.

## Interface and migration impact

- The schema does not change, so `SCHEMA_VERSION` stays at 1.
- The tool interface does not change, so no prompt or tool doc changes.
- The default path changes. Step 2 finds any client that relies on it.

## Results

2026-11-01, on branch `db-move`:

- `uv run pytest`: 54 passed. `ruff check` and `ruff format --check`: clean.
- The startup race test failed on the old `db.connect` with `database is locked`, then passed with the fix.
- Rehearsal passed on a generated database, with runbook commands run literally under a temp `HOME`. A held connection was reported and refused. The clean run gave `moved`, `ok`, `wal`, matching hashes for the file and the copy, and no sidecars. A folder at the destination was refused with the source intact. Rollback restored a matching hash.
- The live checks have not run.

## Review findings

A subagent reviewed both docs on 2026-11-01 (Opus, high effort). The main session reproduced B1, B2, and B3 on generated files. The other findings rest on the reviewer's evidence.

| ID | Finding | Evidence | Resolution |
|----|---------|----------|------------|
| B1 | The first draft's step 5 "no `-wal`" check could not pass with Apple's `sqlite3`, and it could not see a holder | Apple's CLI left `-shm` and `-wal` with no holder; Homebrew's left the main file only (reproduced) | Runbook names the Homebrew binary and drops the checkpoint line, because close already checkpoints |
| B2 | `mv` onto a destination with a stale WAL destroys all rows while `integrity_check` prints `ok` | Table count 0 of 300 after the move (reproduced); `howtocorrupt.html` 1.4 | Guarded move refuses an existing destination; promote moved after the file move |
| B3 | The fact "a running server follows the moved file" was false | Holder saw 2 rows, while the new path had no table (reproduced); `howtocorrupt.html` 2.5 | Fact replaced with the fork result |
| S1 | Row counts miss lost updates | Main-only copy matched counts with old values | Compare `.dump` hashes |
| S2 | Config search could miss symlinks, clients with no `--db`, and project configs | `/usr/bin/grep -r` skipped a symlinked file | Search uses `-S`, three patterns, and more locations; runbook step 3 covers `.mcp.json` |
| S3 | Nothing verified config edits before the move | Review of runbook order | Runbook step 10 |
| S4 | The old-path check ran before all clients started and had no recovery | Review of runbook order | Check moved to step 16; Missed config procedure added |
| S5 | Rollback omitted the likely failures and literal commands | Review of Rollback section | Rollback rewritten with a boundary at the first real row |
| S6 | No holder check near the move | Config edits are slow, and a client could start meanwhile | `lsof` inside the step 11 guard; steps 5 and 6 confirm clients stay stopped |
| S7 | Rehearsal never met a populated WAL | A clean close removes the WAL | Rehearsal rewritten with `os._exit` and a destination-exists run |
| S8 | "Every test runs under a timeout" had no mechanism | `pytest-timeout` is not in `pyproject.toml` | Tests bound their own waits; no new dependency |
| S9 | Retry tests could pass with a broken retry | No deterministic recovery case; no stated delay | Retry recovers test added; 20 ms delay stated; barrier named |
| S10 | Live checks could pass on the old build | Every client passes `--db` | Step 13 prints the installed default |
| M1 | No pre-move copy | `mv` has no undo | The user approved a one-time copy; steps 11 and 17 |
| M2 | "Existing file" test could not observe a missing retry | Runs in one process | Test dropped; concurrent WAL opens measured 0 of 360 failures |
| M3 | `docs/ISSUES.md` said the crash matters for the move | WAL mode persists in the file header | Issue entry corrected |
