#!/usr/bin/env bash
# promote.sh: Promote reviewed, committed source to deploy/ and install the MCP server.
#
# Run only on a clean main, after the changes being promoted passed review.
# Consumers symlink to deploy/skills/fleetcom/, so promotion is what makes
# content live for Hermes profiles and Claude Code sessions.
#
# A full promote installs and checks the server first, then swaps the skill.
#
# Usage:
#   scripts/promote.sh              # reinstall MCP server, then promote skill
#   scripts/promote.sh --skill-only # skill only; skips uv tool install

set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_DIR="$REPO_ROOT/deploy"
SKILL_SRC="$REPO_ROOT/src/skills/fleetcom"
SKILL_DST="$DEPLOY_DIR/skills/fleetcom"
SKILL_ONLY=false
case "$*" in
  "") ;;
  --skill-only) SKILL_ONLY=true ;;
  *)
    echo "usage: scripts/promote.sh [--skill-only]" >&2
    exit 2
    ;;
esac

cd "$REPO_ROOT"

if [ -n "$(git status --porcelain)" ]; then
  echo "ERROR: the working tree is not clean. Commit (after review) before promoting." >&2
  exit 1
fi
if [ "$(git branch --show-current)" != "main" ]; then
  echo "ERROR: promote only from main." >&2
  exit 1
fi
if ! uv lock --check; then
  echo "ERROR: uv.lock is out of date. Run uv lock and commit it." >&2
  exit 1
fi

uv run pytest -q
uv run ruff check
uv run ruff format --check

GIT_SHA="$(git rev-parse HEAD)"
mkdir -p "$DEPLOY_DIR/skills"

if [ "$SKILL_ONLY" = false ]; then
  TMP_DIR="$(mktemp -d)"
  trap 'rm -rf "$TMP_DIR"' EXIT
  # uv tool install ignores uv.lock; constraints keep the tested versions.
  uv export --frozen --no-dev --no-emit-project --no-hashes -o "$TMP_DIR/constraints.txt" >/dev/null
  uv tool install --python 3.11 --from "$REPO_ROOT" fleetcom \
    --force --reinstall --constraints "$TMP_DIR/constraints.txt" >/dev/null
  # Ask uv where it put the launcher; ~/.local/bin may not be on PATH here.
  LAUNCHER="$(uv tool dir --bin)/fleetcom-mcp"
  EXPECTED="fleetcom-mcp $(uv version --short)"
  INSTALLED="$("$LAUNCHER" --version)"
  if [ "$INSTALLED" != "$EXPECTED" ]; then
    echo "ERROR: installed '$INSTALLED', expected '$EXPECTED'. The skill was not changed." >&2
    exit 1
  fi
  echo "reinstalled $INSTALLED -> $LAUNCHER"
fi

# Swap in the new skill so a failed copy never leaves consumers without one.
rm -rf "$SKILL_DST.new" "$SKILL_DST.old"
cp -R "$SKILL_SRC" "$SKILL_DST.new"
printf '%s\n' "$GIT_SHA" > "$SKILL_DST.new/.promoted-sha"
if [ -e "$SKILL_DST" ]; then mv "$SKILL_DST" "$SKILL_DST.old"; fi
mv "$SKILL_DST.new" "$SKILL_DST"
rm -rf "$SKILL_DST.old"

if [ "$SKILL_ONLY" = false ]; then
  printf '%s\n' "$GIT_SHA" > "$DEPLOY_DIR/mcp.promoted-sha"
fi

# Claude Code's auto-updater has been reported to delete symlinked directories
# under ~/.claude/skills/, so re-assert the link on every run.
mkdir -p "$HOME/.claude/skills"
ln -sfn "$SKILL_DST" "$HOME/.claude/skills/fleetcom"

echo "promoted skill -> $SKILL_DST"
echo "symlinked -> $HOME/.claude/skills/fleetcom"
echo "promoted from git sha: $GIT_SHA"
