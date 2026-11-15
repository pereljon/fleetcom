# Promote hardening

Owns: the design for `fleetcom-mcp --version` and the checks and ordering in `scripts/promote.sh`. Does NOT hold test cases or review findings (`promote-hardening-tests.md`).

Status: merged to `main` as `dd13e30` on 2026-11-14; not yet promoted. Investigated against `main` at `ed1fdc6`, with uv 0.13.6 and Python 3.11. Plan: `docs/superpowers/plans/2026-11-14-status-review-fixes.md`, Branch D, which holds the code for each step.

## Goal

A promote must install only the tested, committed build from `main`. It must never leave consumers with a missing skill, or with a new skill beside an old server. Afterwards, the installed server must be able to report which build it is.

The ordering guarantee covers newly started servers. A running client keeps its old server until it restarts, and it may read the new skill meanwhile (whether running clients re-read the skill body was not checked). Clients restart right after a promote.

## Verified facts

- `scripts/promote.sh` checks only `src/` for uncommitted changes, does not check the branch, and runs no tests.
- The script removes the deployed skill and then copies the new one, so a failed copy leaves consumers with no skill.
- `--skill-only` still writes `deploy/mcp.promoted-sha`, although no install happened.
- `uv tool install` ignores `uv.lock`, so packages the project does not pin directly can differ from the tested set.
- `fleetcom-mcp` has no `--version`. `development/AGENTS.md` (Releases) requires one that works before config loads.
- `deploy/` is gitignored, so `git status` never shows what a promote wrote.
- uv 0.13.6, checked on 2026-11-14:
  - `uv lock --check` exits 0 on the current lock.
  - `uv export --frozen --no-dev --no-emit-project --no-hashes` lists `mcp==2.2.0`, the version in `uv.lock`.
  - `uv tool install` accepts `--constraints`, `--force`, and `--reinstall`.
  - `uv version --short` prints `0.1.0`, the version in `pyproject.toml`.
  - `uv tool dir --bin` prints the launcher folder.
- `shellcheck` is installed on this machine at `/opt/homebrew/bin/shellcheck`. The project does not depend on it.

## Design

1. `fleetcom-mcp --version` prints `fleetcom-mcp <version>` and exits 0. It reads the version with `importlib.metadata.version("fleetcom")` through argparse `action="version"`. It exits during argument parsing, before the database is opened, so it needs no config and no privileges.
2. `promote.sh` refuses to start, changing nothing, in any of these cases:
   1. An argument other than `--skill-only` is present. It exits 2 with `usage: scripts/promote.sh [--skill-only]` before any guard runs.
   2. The working tree is not clean (`git status --porcelain` prints anything).
   3. The current branch is not `main`.
   4. `uv lock --check` fails. Otherwise `uv run` would rewrite a stale lock partway through, and the export would read the stale lock.
   5. `uv run pytest -q`, `uv run ruff check`, or `uv run ruff format --check` fails.
3. A full promote installs and checks the server before it touches the skill (Fable review finding P3):
   1. It exports the locked versions with `uv export --frozen --no-dev --no-emit-project --no-hashes` to a temp file.
   2. It runs `uv tool install --python 3.11 --from <repo> fleetcom --force --reinstall --constraints <file>`.
   3. It requires that `<uv tool dir --bin>/fleetcom-mcp --version` prints `fleetcom-mcp <uv version --short>`. On a mismatch, it stops.
   4. Only then does it swap the skill and write both promoted-SHA stamps.
4. The skill swap copies to `skills/fleetcom.new`, moves the old copy to `skills/fleetcom.old`, moves the new copy into place, and removes the old one. A failed copy leaves the deployed skill as it was.
5. `--skill-only` runs the same guards, swaps the skill, and writes only the skill's `.promoted-sha`. It no longer writes `deploy/mcp.promoted-sha`.
6. The script still re-creates the `~/.claude/skills/fleetcom` symlink on every run.
7. The `deploy/mcp/promoted-sha` fallback is removed, because `deploy/` always exists after the script's `mkdir`.

If the install succeeds but a later step fails, the new server is installed and the old skill stays. That is the safe direction: the old skill gives older advice, which the new server still accepts.

## Interface change

- New flag: `fleetcom-mcp --version`.
- `promote.sh` refuses an unknown argument (exit 2), a dirty tree, a branch other than `main`, a stale lock, and failing tests or linters.
- After a promote, restart clients; a running client keeps its old server and may read the new skill meanwhile.
- A full promote can now fail after the install and before the skill swap. Re-run it after fixing the cause.
- The version check means each promote that changes code needs a version bump (plan, Task E1). Otherwise the check still passes, but the version no longer tells two builds apart.

## Decisions

### 2026-11-14 - Install and check before the skill swap (`ok`)
Why: a failed install must not leave a new skill beside an old server. After Branch C, the new skill tells agents that `""` clears a time, and the old server stores `""` as permanently overdue (Fable review, finding P3). The user approved folding P3 into Branch D on 2026-11-14.
Rejected: the plan's first order, which swapped the skill first.

### 2026-11-14 - Identify the build by version and promoted SHA (`ok`)
Why: the version from `--version` and `deploy/mcp.promoted-sha` together identify the build, as long as each promote that changes code bumps the version.
Rejected: embedding the git SHA in the package. It needs a generated file in the package, and whether `uv_build` includes an untracked file was not checked.

### 2026-11-14 - No shell test harness (`ok`)
Why: the script runs a few times per release, and a harness would be a new dependency. The test plan runs the script in a scratch clone with uv's tool folders and `HOME` pointed at scratch, so a full run touches nothing live.
Rejected: adding `bats` or a Python wrapper test.
