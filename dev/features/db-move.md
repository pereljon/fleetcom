# Database move

Owns: the design and cutover runbook for moving the live database to `~/.fleetcom/`. Does NOT hold test cases or review findings (`db-move-tests.md`).

Status: shipped 2026-11-01. The cutover ran at 20:52 PST from a live session, with the changes listed under Cutover as run. Investigated against commit `08abf75`, Python's SQLite 3.53.1, and Homebrew's `sqlite3` CLI 3.54.1.

## Goal

The live database moves from `~/Claude/-hermes/db/fleetcom.db` to `~/.fleetcom/fleetcom.db`, with no rows lost. Claude Code, Hermes, and Codex all share this file, so it should not sit in the Hermes folder or its git working tree (`docs/ISSUES.md`, Decisions, 2026-11-01).

Two defects are in scope:

- The code default still names the old path.
- Servers that start together on a new file crash at `PRAGMA journal_mode = WAL`.

Ongoing backups stay out of this design. They belong to the user.

## Verified facts

These results come from tests on generated files, on 2026-11-01. None touched the live database.

- **The main file alone is not the database.** A copy of only the main file, taken while the write-ahead log (WAL) held the data, failed with `no such table: t`. The live main file is 73 KB, dated Oct 20, and the live `fleetcom.db-wal` is 1.1 MB. A plain `mv` or `cp` of `fleetcom.db` would therefore lose recent data.
- **Row counts cannot prove a good move.** With an `UPDATE` only in the WAL, a main-only copy had the right counts and passed `integrity_check`, but held the old values. The runbook compares a hash of `.dump` instead.
- **The `sqlite3` binary matters.** Homebrew's CLI removes `-wal` and `-shm` when the last connection closes. Apple's `/usr/bin/sqlite3` 3.54.0 leaves both behind with no process holding the file, which is the default in a plain terminal. Only Homebrew's result separates an idle holder from no holder, so the runbook names that binary.
- **A stale WAL at the destination destroys the data.** After a server exited at the destination without closing, `mv` over its main file left the real database beside that server's WAL. The next open applied the WAL, leaving none of the 300 rows, and `integrity_check` still printed `ok`. The runbook refuses to run if `~/.fleetcom` exists.
- **A server open across the move forks the data.** A separate process held the database across a rename, and its write went to the WAL at the old path. It saw two rows, while a reader at the new path found no table. The review's longer run showed those rows lost for good once the old path was reopened. SQLite documents renaming an open database as undefined (`howtocorrupt.html`, 2.5).
- **The startup crash reproduces.** Four processes opening a new file together failed in 66 of 120 opens. Failures returned within 0.07 s, although Python's `sqlite3.connect` sets a 5 second busy timeout, so the timeout does not cover this error.
- **A bounded retry fixes the crash.** With a retry around the pragma, 0 of 120 opens failed. The review measured 0 of 360 with `connect` and `migrate` together, at a 20 ms delay.
- **The move stays on one volume.** `~` and `~/Claude/-hermes/db` are both on `/dev/disk3s5`, so `mv` is a rename and does not copy data.
- **A move does not trigger the crash.** WAL mode persists in the file header, and concurrent opens of a WAL-mode file failed in 0 of 360 opens. The crash fix matters for a new or mistyped path. The cutover does not depend on it.

## Assumptions not verified

- The client config list comes from `docs/ISSUES.md`, `src/skills/fleetcom/SKILL.md`, and hermes-manager. This session did not read those configs. Step 2 closes this gap.
- Which client started each process. Steps 5 and 6 stop them all, and the guard in step 11 checks again.
- Whether `reconcile-fleet-dbs.sh` has already run, and whether legacy root files remain. Neither affects the move, because the runbook only retires the script.

## Code changes

1. Change `db.default_db_path` to return `~/.fleetcom/fleetcom.db`.
2. Add a bounded retry around `PRAGMA journal_mode = WAL` in `db.connect`. Retry only on an `OperationalError` that contains `locked`, every 20 ms, and start no new attempt after 10 seconds. One attempt can still spend the busy timeout, so the worst case is about 23 seconds (inferred).
3. Update `README.md`, `src/skills/fleetcom/SKILL.md`, `dev/IMPLEMENTATION-SPEC.md`, `CHANGELOG.md`, and `tests/test_db.py` for the new default.
4. Keep the `README.md` note that MCP configs need an absolute path. Fleetcom does not expand `~`, so a literal `--db ~/...` creates a folder named `~`. The examples keep `~`, because a real path would put a home folder in a public repo.

The `--db` flag, `FLEETCOM_DB_PATH`, and their precedence do not change.

## Cutover runbook

The user runs this runbook in one plain terminal, because steps 5 and 6 stop every agent session. Replace `<home>` with the absolute home path. Set these variables first:

```sh
S=/opt/homebrew/opt/sqlite/bin/sqlite3
D=~/Claude/-hermes/db/fleetcom.db
N=~/.fleetcom/fleetcom.db
```

1. Merge the code. Do not run `scripts/promote.sh` yet, because the new default must not go live before the destination exists.
2. Search every client location. Note each hit, and ignore logs:
   ```sh
   /usr/bin/grep -rnS -e fleetcom.db -e fleetcom-mcp -e FLEETCOM_DB_PATH \
     ~/.claude.json ~/.claude ~/.codex/config.toml ~/.hermes/config.yaml \
     ~/.hermes/profiles ~/Library/LaunchAgents ~/.zshrc ~/.zprofile
   ```
3. Search each project's `.mcp.json` for the same three strings. Add any hit to the list from step 2.
4. Close the Hermes desktop app, and keep it closed until step 14. hermes-manager saw the gateway return about 90 seconds after an unload while the app was open, and inferred that the app caused it.
5. Stop the launchd jobs `ai.hermes.gateway` and `ai.hermes.dashboard`, then stop any dashboard outside launchd, such as the one found on 2026-11-01 with parent PID 1. Both jobs have `RunAtLoad` and restart after a non-zero exit, so a login or a crash can bring them back.
6. Stop every Claude Code and Codex session. Confirm with `launchctl list` and `ps` that nothing Hermes has returned.
7. Confirm that no process holds the database. If this prints anything, stop that client and repeat this step:
   ```sh
   lsof "$D"*
   ```
8. Hash the contents, then list the files. If `ls` lists `-wal` or `-shm`, return to step 7. Keep the output, because rollback needs the file mode:
   ```sh
   "$S" "$D" .dump | shasum -a 256 > /tmp/fleetcom-before
   ls -la "$D"*
   ```
9. Edit each config from steps 2 and 3 to pass `--db <home>/.fleetcom/fleetcom.db`. Follow the gateway-ops skill for the five Hermes configs.
10. Run the search from step 2 again. Stop if any hit names `-hermes/db/fleetcom.db` or a literal `<home>`.
11. Run the guarded move. Stop unless this prints `moved`. It refuses a holder, a WAL, or an existing destination. It also keeps a one-time copy at `$N.pre-move`:
    ```sh
    [ -z "$(lsof "$D"* 2>/dev/null)" ] && [ ! -e "$D-wal" ] && [ ! -e ~/.fleetcom ] \
      && mkdir -m 700 ~/.fleetcom && cp -n "$D" "$N.pre-move" && chmod 600 "$N.pre-move" \
      && mv -n "$D" "$N" && chmod 600 "$N" && echo moved
    ```
12. Check the moved file. Expect `ok`, `wal`, and no output from `cmp`. If either check fails, follow Rollback:
    ```sh
    "$S" "$N" 'PRAGMA integrity_check; PRAGMA journal_mode;'
    "$S" "$N" .dump | shasum -a 256 | cmp - /tmp/fleetcom-before
    ```
13. Run `scripts/promote.sh`, then confirm the installed build. Expect the new path:
    ```sh
    env -u FLEETCOM_DB_PATH ~/.local/share/uv/tools/fleetcom/bin/python \
      -c 'from fleetcom import db; print(db.default_db_path())'
    ```
14. Start the gateway and one session of each client. Make one real write and read through `task_create`, `task_list`, and `task_delete`, as the gateway-ops skill requires (line 125).
15. Start the remaining sessions.
16. Confirm that no client recreated the old path, and that the new folder is backed up. Expect `gone` and `[Included]`:
    ```sh
    [ ! -e "$D" ] && echo gone
    tmutil isexcluded ~/.fleetcom
    ```
17. Remove the one-time copy after step 16 passes:
    ```sh
    rm "$N.pre-move"
    ```

**Missed config:** If step 16 does not print `gone`, a client has written to a new empty database at the old path. Stop that client and fix its config. Look at the rows in the old file, and copy any real ones to the new database by hand. Remove the old file only after that.

**Rollback:** Roll back only before the first real row reaches the new path, including after a failed step 14 that wrote nothing. After that, fix forward.

1. Stop everything started since step 13, then confirm with `lsof "$N"*`.
2. Run `mv -n "$N" "$D"`, then restore the mode that step 8 recorded with `chmod`.
3. Revert the config edits from step 9.
4. Remove any sidecars and `$N.pre-move` at the destination after looking at them, then run `rmdir ~/.fleetcom`.

## Cutover as run

The runbook above is the plan. The live run differed in these ways:

- The session that ran it stayed up. It stopped four Claude Code fleetcom servers by PID instead of stopping the sessions, then restarted the sessions at the end.
- The five Hermes configs changed through `hermes config set`, with a read-back, because the gateway-ops skill forbids hand edits. `~/.claude.json` and `~/.codex/config.toml` changed by one exact string replacement.
- The search in step 2 was limited to config file types and skipped Hermes `sessions/` and `pending/` folders, which only hold old copies of the path.
- The dashboard stop used `launchctl bootout`, and a second dashboard outside launchd stopped by `kill -TERM`. The gateway and dashboard started with `launchctl bootstrap`, because a booted-out job has nothing for `kickstart` to act on.
- The real write ran through the installed `fleetcom-mcp` over stdio before Hermes started. Its row was checked with SQL, because `task_list` hides new rows past its limit (`docs/ISSUES.md`, Bugs).

## After the cutover

These files belong to Hermes, so hermes-manager changes them:

- Retire `~/Claude/-hermes/db/reconcile-fleet-dbs.sh`, or remove its fleetcom lines. It hardcodes the old path, and its opening steps can recreate an empty `db/fleetcom.db`, so nobody may rerun it after the move.
- Update `~/Claude/-hermes/AGENTS.md:55` and the gateway-ops skill. That `AGENTS.md` has uncommitted changes, so read the diff first.

## Decisions

### 2026-11-01 - Keep a one-time copy until the cutover checks pass (`firm`)
Why: `mv` has no undo, and the user approved the copy. It is not an ongoing backup.
Rejected: moving with no copy.

### 2026-11-01 - One manual runbook, not a migration script or server auto-migration (`delegated`)
Why: the move runs once, and its hardest steps are stopping clients and editing configs that belong to other tools.
Rejected: `scripts/move-db.sh`, which would be untested code for one run and could not stop the session running it. Rejected: moving the file at server startup, because several servers start at once and each would race to move a live database.

### 2026-11-01 - No symlink or placeholder at the old path (`delegated`)
Why: the goal is that nothing depends on the Hermes folder, and steps 10 and 16 catch a missed config.
Rejected: a symlink from old to new, which would hide a missed config and leave the dependency in place. Rejected: a directory at the old path, which fails loudly but leaves an odd object in the Hermes folder for a check that runs anyway.

### 2026-11-01 - Retry the pragma, keep auto-creation (`delegated`)
Why: the retry is the smallest change that fixes the crash. An explicit flag to create a database is a separate open item in `docs/ISSUES.md`.
Rejected: skipping the pragma when the file is already in WAL mode, which does nothing for a new file.

### 2026-11-01 - Promote after the move, not before (`delegated`)
Why: promoting first gives the installed default a path that does not exist yet, so a client without `--db` could create the stale WAL that destroys the move. All servers are stopped at step 13, so no running server mixes builds.
Rejected: promoting at step 1, as first drafted.
