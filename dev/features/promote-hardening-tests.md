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
5. Constraints: the installed `mcp` version in the scratch tool folder equals the version in `uv.lock`.
6. Install failure (finding P3): add an empty commit, make the scratch launcher folder read-only, and run a full promote. Expect a non-zero exit, and both promoted-SHA stamps and the deployed skill unchanged from check 4.
7. `--skill-only` after a new commit. Expect the skill's `.promoted-sha` to equal the new commit, `deploy/mcp.promoted-sha` unchanged, and no `fleetcom.new` or `fleetcom.old` left in `deploy/skills/`.

## Live checks

The real promote is plan Task E2, after the version bump in Task E1. Run `fleetcom-mcp --version` on the installed launcher and confirm that `deploy/mcp.promoted-sha` equals `git rev-parse HEAD`.

## Results

Not run yet.

## Review findings

None yet.
