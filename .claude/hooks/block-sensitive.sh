#!/usr/bin/env bash
# PreToolUse hook: block edits to files that should never be modified by hand.
# Returns a deny decision via JSON stdout when the target matches.
set -euo pipefail

f=$(jq -r '.tool_input.file_path // empty')
[[ -z "$f" ]] && exit 0
base=$(basename "$f")

deny() {
  jq -n --arg reason "$1" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: $reason
    }
  }'
  exit 0
}

# .env files: allow committed config files, block gitignored credential files
case "$base" in
  .env.example|.env.test) ;;
  .env|.env.*)
    deny "Refusing to edit $base — credential leak risk. Edit .env.example instead." ;;
esac

# Lock files
case "$base" in
  uv.lock)
    deny "Refusing to edit uv.lock — change dependencies via 'uv add', 'uv remove', or 'uv sync' instead of hand-editing." ;;
esac

# Applied alembic migrations
case "$f" in
  *alembic/versions/*.py)
    deny "Refusing to edit applied alembic migrations. Generate a new migration via: just migrate-gen \"<message>\". Editing existing migrations breaks consumers who already ran them." ;;
esac

exit 0
