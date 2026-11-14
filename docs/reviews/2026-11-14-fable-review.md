# Fable review, 2026-11-14

This file holds a review of the fleetcom specs, feature docs, and plan against the code, at commit `ed0343e` (branch `db-open-safety`), written by the model claude-fable-5-2.

## Verdict

The code matches its specs on almost every point checked, and the suite passes (120 tests, ruff clean).
One gap remains in the Branch B goal: an existing empty file, or another application's SQLite file, still becomes a fleetcom database without `--create-db` (S1).
The designs for Branches C and D work when run: the Branch C code passed 144 tests in a scratch copy, and the Branch D install and version check passed in scratch tool folders.
Their defects are in ordering and reporting (P2, P3), not in logic.
`docs/ISSUES.md` is accurate about where the work stands, with two stale lines, one duplicate, and two decisions recorded only in the plan.

## Findings

Severity is in parentheses after each ID. "Scratch run" means a script or command run against a temp database or a copy of the source in the session scratchpad.

### Spec and code disagree

1. **S1 (high). An existing file that is not a fleetcom database is initialized as one, without `--create-db`.**
   - Specs that say otherwise: `README.md:81` ("a mistyped path fails at startup instead of starting an empty database"), `dev/SKELETON.md:28` ("`db.connect` never lets SQLite create a file. A mistyped path must fail instead of starting an empty database"), `dev/features/db-open-safety.md:9` ("It must never start on a new, empty database because of a mistyped path").
   - Evidence: scratch run of `server.main` with `--db` naming a zero-byte file, stdin closed. Exit status 0, and the file grew to 53,248 bytes with `tasks`, `events`, `contacts`, and `schema_version`. The same run on an SQLite file holding only a `notes` table also exited 0 and added the four tables next to `notes`.
   - Cause: `src/fleetcom/db.py:103` tests only that the file exists. `db.migrate` (`src/fleetcom/db.py:126-140`, called at `src/fleetcom/server.py:324`) runs the schema whenever `schema_version` is absent, whether or not `--create-db` was passed.
   - Why it can happen here: the 2026-11-01 decision in `docs/ISSUES.md` records that the old default path pointed at a zero-byte file, and `docs/ISSUES.md:50` expects stray empty databases at wrong paths.
   - The merge review of Branch B (R1 to R3 in `dev/features/db-open-safety-tests.md`) did not cover this case.
   - Fix: when the opened database has no `schema_version` table and `--create-db` was not passed, exit with status 1 and a one-line message that names the path and `--create-db`. Keep the migrate path for a fleetcom database with an older version. Add tests for the zero-byte file and for the foreign SQLite file, and add the rule to the `dev/SKELETON.md` invariant.

2. **S2 (medium). The skill's "everything this month" example drops the last day of the month.**
   - `src/skills/fleetcom/references/tools.md:26` gives `event_list(start="2026-09-01T00:00:00Z", end="2026-09-30T00:00:00Z")`.
   - Evidence: `src/fleetcom/events.py:35` filters `start >= ? AND start <= ?`. A scratch `event_list` call with those bounds returned events at 09-01 00:00, 09-29 23:00, and 09-30 00:00, and left out an event at 09-30 15:00.
   - Fix: end the example at `2026-09-30T23:59:59Z`. The promote copies this file to every agent, so fix it before the promote.

3. **S3 (low). Two specs omit Codex as a client.**
   - `dev/IMPLEMENTATION-SPEC.md:8` lists the clients as "(Claude Code, a Hermes profile)". `README.md:55-75` gives config examples for Claude Code and Hermes only. `AGENTS.md:9` and `AGENTS.md:27` name Codex as a client.
   - Evidence: code read of the four files.
   - Fix: add Codex to the spec line now. Add a README config example after a Codex call is confirmed (plan Task E3 Step 4). The working config text is outside the project, so it is an open question below.

4. **S4 (low). The package description lists reminders as a primitive.**
   - `pyproject.toml:4` says "tasks, reminders, events, contacts". `README.md:7` says three primitives, and `AGENTS.md` (Design Principles) says there is no separate reminders primitive.
   - Evidence: code read. `src/fleetcom/db.py` creates three entity tables.
   - Fix: drop "reminders" from the description in the Task E1 version-bump commit, which already edits `pyproject.toml`. The plan's keep-out list forbids other edits to that file.

5. **S5 (low). Two README statements mislead a reader.**
   - `README.md:49` says to run `uv tool list` to confirm the launcher path. `uv tool list` prints no paths without `--show-paths`. `uv tool dir --bin` prints the launcher folder. Evidence: both commands run against scratch tool folders.
   - `README.md:16` and `README.md:111` say "events happening today". The day is the UTC day, and only an event's `start` is matched. The `agenda_today` docstring (`src/fleetcom/server.py:290`) says UTC; the README does not.
   - Fix: change the command to `uv tool dir --bin`, and add "(UTC day, by start time)" to one of the two README lines.

### Feature docs

1. **F1 (low). The `db-open-safety` status line is one step behind.**
   - `dev/features/db-open-safety.md:5` says "built on branch `db-open-safety` (commit `e932aaa`), awaiting merge review".
   - Evidence: the review ran and its fixes are in `ad7d94d`; its findings R1 to R3 are recorded in `dev/features/db-open-safety-tests.md`.
   - Fix: update the line with the merge commit when Branch B merges.

2. **F2 (low). The `db-open-safety` test plan misses one test and cites old line numbers.**
   - The automated-test table (`dev/features/db-open-safety-tests.md:13-25`) has rows for "Startup, missing file" and "Startup, folder" but none for the not-a-database startup test added for R1 (`tests/test_cli.py:40`).
   - `dev/features/db-open-safety-tests.md:29` cites `tests/test_server.py:12` and `:253`, and `tests/test_db.py:101`, `:114`, `:123`, `:129`. The calls now sit at lines 13 and 254, and 103, 116, 125, 131. Evidence: `grep -n "create=True"` on both test files.
   - Fix: add the table row. Replace the line numbers with test names, which do not move.

The `db-move`, `list-truncation`, and `unknown-id-errors` docs describe what was built. Their open live checks match `docs/ISSUES.md`.

### Planned designs (Branches C to E)

How these were checked: the plan's Branch C code was applied to a scratch copy of `src/` and `tests/`, then run through the suite and through MCP calls. The plan's Branch D install commands were run against a scratch copy with `UV_TOOL_DIR` and `UV_TOOL_BIN_DIR` set to scratch folders. The repo's `uv.lock` did not change.

1. **P3 (medium). The planned `promote.sh` puts the new skill live before it knows the install worked.**
   - Plan lines 1135-1140 swap the skill and stamp `.promoted-sha`. Lines 1154-1164 install the server and check its version. The script runs under `set -e`.
   - Case: the install fails, or the version check fails. The script exits with the new skill live and the old server installed. After Branch C the new skill tells agents to pass `""` to clear `due`, and the old server stores `""`, which counts as permanently overdue (`docs/ISSUES.md:44`).
   - Evidence: code read of the planned script. To show it: in a scratch copy, make the version check fail and look at `deploy/skills/fleetcom/.promoted-sha`.
   - Fix: in a full promote, run the install and the version check first, then swap the skill. `--skill-only` keeps its current order.

2. **P2 (medium). The startup repair reports a count of values it could not fix, on every start, and never says which rows.**
   - Plan line 603 prints `normalized times in N rows to UTC; left M values`. Lines 980-984 print it whenever either count is non-zero.
   - Evidence: scratch database with one unparseable `due` and one event whose normalized `end` falls before its `start`. Three startups in a row each printed `fleetcom-mcp: normalized times in 0 rows to UTC; left 2 values`. Both rows stayed as stored.
   - Effect: every server start by every client repeats the line, and nobody can find the rows from it. An unparseable `due` never comes due.
   - Fix: print the table and id of each row left, without the value. Or put the query that lists them in `dev/features/utc-timestamps.md`, and add a step to Task E3 Step 3 that reads M and fixes those rows by hand.

3. **P1 (low). Task C5 leaves a false sentence in `dev/SKELETON.md`.**
   - `dev/SKELETON.md:13` says "A field can never be explicitly reset to empty/null this way". Task C5 (plan line 994) lists only "Timestamps invariant; Logic Flow first bullet" for that file. Line 13 is the `task_update` bullet.
   - Evidence: with the Branch C code, scratch MCP calls `task_update(due="")` and `event_update(end="")` returned `ok: true` and the field read back as null. `event_update(start="")` returned a tool error for the NOT NULL column.
   - Fix: add the `task_update` bullet to Task C5 Step 3. State that `""` clears `due`, `remind_at`, and `end`, and that other fields cannot be cleared.

4. **P4 (low). Task C1 Step 3 cannot be run as written.**
   - Plan line 619 asks for the count of values "`to_utc` cannot parse", using the `sqlite3` command-line tool. `to_utc` is written in Task C2, and the command-line tool cannot call it.
   - Evidence: plan order (C1 before C2). The read-only open in that step works: checked on a scratch database in WAL (write-ahead log) mode.
   - Fix: say in the step that the parse count comes from a one-off Python script in the scratchpad that opens the database read-only, applies `datetime.fromisoformat`, and prints counts only.

5. **P5 (low). Task E1 Step 2 leaves the changelog saying nothing was released.**
   - Plan line 1203 moves "the four branches' CHANGELOG lines" under a `0.2.0` heading. The lines that stay under "Unreleased" describe what was promoted at `371acda` as version 0.1.0, under an intro that says "Nothing in this project has been released yet" (`CHANGELOG.md:7`).
   - Evidence: code read of `CHANGELOG.md` and `pyproject.toml` (version `0.1.0`).
   - Fix: in the same step, put the remaining lines under a `0.1.0` heading and rewrite the intro. This needs the user's decision (open question 4).

6. **P6 (low). Two docs give different paths for the same live check.**
   - Plan line 1218 (Task E3 Step 2) uses `/tmp/does-not-exist.db`. `dev/features/db-open-safety-tests.md:35` uses `<scratch folder>/does-not-exist.db`.
   - Fix: use the scratch folder path in the plan step.

### `docs/ISSUES.md` accuracy

1. **I1 (low). Two Bugs lines are stale.**
   - `docs/ISSUES.md:9` says "fixed 2026-11-14 on branch unknown-id-errors". The fix merged to `main` as `a177129` and is not promoted (`dev/features/unknown-id-errors.md:5` says so).
   - `docs/ISSUES.md:8` ends "Options: normalize to UTC on write, or reject non-UTC values. Both need a design doc". The decision at `docs/ISSUES.md:77-80` chose normalize, and plan Branch C holds the design.
   - Fix: write "merged as `a177129`, not yet promoted" on line 9. Replace the options sentence on line 8 with a pointer to the decision and to plan Branch C.

2. **I2 (low). One Codex task appears twice in Next steps.**
   - `docs/ISSUES.md:59` ("Confirm a fleetcom call from Codex at the new path") and `docs/ISSUES.md:61` ("Confirm a Codex fleetcom call in an interactive session") are the same task. Plan Task E3 Step 6 already calls them "the two Codex confirmation steps".
   - Fix: keep line 61, which carries the `codex exec` reason, and mark line 59 cancelled as a duplicate.

3. **I3 (low). Two answered questions are recorded only in the plan.**
   - The user answered Q5 (defer the reviewed-content change) and Q6 (one promote after all branches) on 2026-11-14 (plan lines 68-69). Neither is under Decisions in `docs/ISSUES.md`.
   - `docs/ISSUES.md:39` still says "Decide whether content edits clear `reviewed`". `docs/ISSUES.md:53` (restart the clients, then run the client checks) does not say it waits for the single promote in plan Task E3.
   - Fix: add one dated Decisions entry for both answers. Note the deferral on line 39 and the wait on line 53.

4. **I4. S1 has no entry.** Add it under Bugs once the user accepts it.

Checked and found correct: the tool count (15), limit bounds and `truncated` flags, unknown-id errors, startup exits for a missing file, a folder, a non-database file, and a truncated database, the lock mapping, the tests named in `dev/SKELETON.md`, the `deploy/` skill copy against `371acda`, the planned `promote.sh` under `bash -n` and shellcheck, `uv lock --check`, and the planned install with lock constraints (`mcp` 2.2.0 installed, `fleetcom-mcp --version` printed `fleetcom-mcp 0.1.0`).

## Already planned

- UTC-offset times misjudged by `due_now` and `agenda_today`: Branch C.
- `due=""` counts as permanently overdue: Branch C.
- Unvalidated time strings (`docs/ISSUES.md:40`, a duplicate of the offset bug): Branch C, Task C5 Step 5.
- `--skill-only` stamps `mcp.promoted-sha` without an install: Branch D.
- `promote.sh` guard covers only `src/`, allows any branch, and runs no tests: Branch D.
- `rm -rf` then `cp` can leave consumers with no skill: Branch D.
- The install ignores `uv.lock`: Branch D.
- No `fleetcom-mcp --version`: Branch D, Task D2.
- Deploy flow missing from README, CODEMAP, and `AGENTS.md`: Branch D, Task D4.
- `uv.lock` out of date after the version bump: Task E1 Step 2.
- Open list-truncation client checks and the Codex call: Task E3 Step 4.
- Hermes review-queue job update and the retired reconcile script: Task E4.

## Open questions for the user

1. Does a zero-byte or stray `fleetcom.db` still exist at any path a client config could name, such as the old default in the Hermes folder? With S1 open, a config that names one starts an empty database. This review could not look outside the project.
2. Does every client config pass `--db` with the live path, and none with a `~` path? This is plan Task E1 Step 3 and `docs/ISSUES.md:50`.
3. `development/AGENTS.md` says not to write the user's name in a project's files unless that project's `AGENTS.md` allows it. `LICENSE:3`, `README.md:128`, and `pyproject.toml:6` hold it. Recommended: allow the copyright and author lines by name in `AGENTS.md`.
4. Which changelog lines belong under `0.2.0`, and should a `0.1.0` heading hold what was promoted at `371acda`? Recommended: yes, add the `0.1.0` heading.
5. Should the README carry a Codex config example, and what is its working form? Recommended: add it after Task E3 Step 4 confirms a Codex call.

## Recommended next steps

1. Decide S1 before the promote. Recommended: fix it on a small branch right after Branch B merges, with its own short design note in `dev/features/db-open-safety.md`, so the Branch B goal holds when the installed server changes.
2. Merge Branch B after approval. Re-run the tests and linters on `main`. Update the status line (F1) and the test table (F2) in the same docs commit.
3. Fix the `event_list` example (S2) in the next docs change, before the promote copies the skill.
4. Build Branch C. Fold P1, P2, and P4 into its design doc and plan steps first.
5. Build Branch D. Reorder the install and the skill swap (P3) in its design doc first.
6. Run Task E: settle the changelog question (P5), confirm the client configs (open questions 1 and 2), bump, promote, restart, run the live checks.
7. Tidy `docs/ISSUES.md` (I1 to I4) and the low doc items (S3 to S5, P6) in one docs commit.
