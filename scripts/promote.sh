#!/usr/bin/env bash
# promote.sh: Promote reviewed, committed source to deploy/ and install the MCP server.
#
# Run only AFTER the changes being promoted are committed (and passed review).
# Consumers symlink to deploy/skills/fleetcom/, so promotion is what makes
# content live for Hermes profiles and Claude Code sessions.
#
# Usage:
#   scripts/promote.sh              # promote skill + reinstall MCP server
#   scripts/promote.sh --skill-only # skill only; skips uv tool install

set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_DIR="$REPO_ROOT/deploy"
SKILL_SRC="$REPO_ROOT/src/skills/fleetcom"
SKILL_DST="$DEPLOY_DIR/skills/fleetcom"

if [ -n "$(git -C "$REPO_ROOT" status --porcelain -- src/)" ]; then
  echo "ERROR: uncommitted changes in src/. Commit (after review) before promoting." >&2
  exit 1
fi

mkdir -p "$DEPLOY_DIR/skills"

# Promote skill
rm -rf "$SKILL_DST"
cp -R "$SKILL_SRC" "$SKILL_DST"

# Stamp what was promoted
GIT_SHA="$(git -C "$REPO_ROOT" rev-parse HEAD)"
printf '%s\n' "$GIT_SHA" > "$DEPLOY_DIR/skills/fleetcom/.promoted-sha"

# Reinstall MCP server (unless skill-only)
if [ "${1:-}" != "--skill-only" ]; then
  uv tool install --from "$REPO_ROOT" fleetcom --force >/dev/null
fi

printf '%s\n' "$GIT_SHA" > "$DEPLOY_DIR/mcp.promoted-sha" 2>/dev/null || {
  mkdir -p "$DEPLOY_DIR/mcp"
  printf '%s\n' "$GIT_SHA" > "$DEPLOY_DIR/mcp/promoted-sha"
}

echo "promoted skill -> $SKILL_DST"
if [ "${1:-}" != "--skill-only" ]; then
  echo "reinstalled fleetcom-mcp -> $(which fleetcom-mcp 2>/dev/null || echo ~/.local/bin/fleetcom-mcp)"
fi
echo "promoted from git sha: $GIT_SHA"
