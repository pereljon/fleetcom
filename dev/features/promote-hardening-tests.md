# Promote hardening tests

Owns: the test plan and review findings for promote hardening. Does NOT hold the design (`promote-hardening.md`).

## Baseline

On branch `promote-hardening` at `ed1fdc6`, 2026-11-14: `uv run pytest -q` gave 156 passed, and `ruff check` and `ruff format --check` were clean.

## Automated test

| Area | Case | Expected result |
|------|------|-----------------|
| `--version` | `_parse_args(["--version"])` with `FLEETCOM_DB_PATH` naming a missing file | `SystemExit` with code 0; stdout is `fleetcom-mcp <version('fleetcom')>`; no database file is created |

The test must fail on the current code, where argparse exits with code 2 for an unknown argument.

## Script checks

The project has no shell test harness. These checks run by hand and their results go under Results.

1. Run `bash -n scripts/promote.sh` and `shellcheck scripts/promote.sh`. Expect no findings.
2. Run the script with the edit uncommitted. Expect "the working tree is not clean", and `deploy/` unchanged (same `.promoted-sha` contents and times).
3. Commit the script, then run it on `promote-hardening`. Expect "promote only from main", and `deploy/` unchanged.

Checks 4 to 7 run in a scratch clone of the branch, renamed to `main`, under the session scratch folder. Each run sets `HOME`, `UV_TOOL_DIR`, and `UV_TOOL_BIN_DIR` to scratch folders, and `UV_CACHE_DIR` to the real uv cache, so nothing live changes. Before check 4, confirm that `uv tool dir --bin` prints the scratch folder under these variables.

4. Full promote in the clean clone. Expect exit 0; the scratch launcher's `--version` prints `fleetcom-mcp 0.1.0`; both promoted-SHA stamps equal `git rev-parse HEAD`; the scratch `~/.claude/skills/fleetcom` link points at the clone's `deploy/skills/fleetcom`.
5. Constraints: every package in the scratch tool environment matches `uv export --frozen` (`mcp` alone proves nothing, because `pyproject.toml` already bounds it).
6. Install failure (finding P3): add an empty commit, make the scratch launcher folder read-only, and run a full promote. Expect a non-zero exit, and both promoted-SHA stamps and the deployed skill unchanged from check 4.
7. `--skill-only` after a new commit. Expect the skill's `.promoted-sha` to equal the new commit, `deploy/mcp.promoted-sha` unchanged, and no `fleetcom.new` or `fleetcom.old` left in `deploy/skills/`.
8. Unknown argument: `--skill_only` and `--help` each exit 2 with the usage line before any guard runs. `--skill-only` and no argument still reach the guards.

## Live checks

The real promote is plan Task E2, after the version bump in Task E1. Run `fleetcom-mcp --version` on the installed launcher and confirm that `deploy/mcp.promoted-sha` equals `git rev-parse HEAD`.

## Results

2026-11-14, on branch `promote-hardening`:

- On the old code, the `--version` test failed with exit code 2 (`e8ac15a`). With the code (`33bc8af`), `uv run pytest -q` gave 157 passed, and `ruff check` and `ruff format --check` were clean.
- Check 1: `bash -n` and `shellcheck` reported nothing on `3aea180`.
- Check 2: with an untracked file in the tree, `promote.sh --skill-only` exited 1 with "the working tree is not clean".
- Check 3: on the clean branch, `promote.sh` exited 1 with "promote only from main". After checks 2 and 3, both promoted-SHA stamps in `deploy/` had the same contents and modification times as before.
- Checks 4 to 7 ran in a scratch clone of `3aea180` renamed to `main`. `uv tool dir --bin` printed the scratch launcher folder under the scratch variables.
- Check 4: the full promote exited 0. The scratch launcher printed `fleetcom-mcp 0.1.0`, both stamps equalled `HEAD`, and the scratch skill link pointed at the clone's `deploy/skills/fleetcom`.
- Check 5: the pre-merge review compared `uv pip list` of the scratch tool environment with `uv export --frozen`. All 28 locked packages matched; two marker-excluded packages, `httpx2-jsfetch` and `pywin32`, are absent on macOS. An unconstrained resolve picks about 20 different versions, for example `starlette` 1.10.0 against 1.6.0 locked.
- Check 6: with the scratch launcher folder read-only, the full promote exited 2 at `uv tool install` ("Failed to install executable"). Both stamps still held the check 4 commit, and no `.new` or `.old` copy was left.
- Check 7: `--skill-only` after a new commit exited 0. The skill stamp held the new commit, `deploy/mcp.promoted-sha` still held the check 4 commit, and no `.new` or `.old` copy was left.
- Check 8: on the R1 commit `7890636`, `--skill_only`, `--help`, and `--skill-only extra` each exited 2 with `usage: scripts/promote.sh [--skill-only]`. Before the fix, the first two reached the branch guard instead. `--skill-only` and no argument still reach the guards.
- The real launcher in `~/.local/bin` and the real `~/.claude/skills/fleetcom` link were unchanged after all checks.

Finding from check 6: uv had already rebuilt the tool environment when it failed to link the launcher, and the existing launcher link then ran the rebuilt environment. So a failed install can still leave the new server live beside the old skill. The design accepts that direction: the old skill gives older advice, which the new server accepts.

## Review findings

A pre-merge review on 2026-11-14 (Opus, high effort) found no blocker.

| ID | Finding | Evidence | Resolution |
|----|---------|----------|------------|
| R1 | An unknown argument ran a full promote. | Code read | Fixed in `7890636`. |
| R2 | Ignored files pass the clean-tree guard and are deployed or installed. | Experiment with `.DS_Store`, a swap file, `.env`, and `build/stray.py` | Recorded in `docs/ISSUES.md`; nothing loads them. |
| R3 | A running client may read the new skill while its server is old, and the startup repair cannot fix a stored `""`. | Code and plan read; whether clients re-read the skill is uncertain | Documented in the design and README; clients restart right after a promote. |
| R4 | Check 5 did not prove the constraints work. | Experiment | Check replaced; result recorded above. |
| R5 | SKELETON lacked `--version`, and the design status was stale. | Code read | Fixed in the documentation commit. |

The review verified by experiment:

- Lock constraints hold for every transitive package.
- `--reinstall` rebuilds a source-only change.
- A detached HEAD and an unformatted file are refused before any change.
- An install that fails at resolution leaves the old environment working.
- `--version` works under `env -i` with no database.
