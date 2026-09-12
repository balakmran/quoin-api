#!/usr/bin/env bash
# PreToolUse hook: block edits to files that should never be modified by hand.
# Returns a deny decision via JSON stdout when the target matches.
#
# Covers Edit|Write|MultiEdit (by .tool_input.file_path) and Bash (by
# scanning .tool_input.command). The Bash arm exists because the file-path
# arm is trivially sidestepped: `python3 - <<'EOF' ... EOF` writing a
# guarded file never sets file_path.
set -euo pipefail

payload=$(cat)
tool=$(jq -r '.tool_name // empty' <<<"$payload")

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

# Shared reasons, so both arms explain a path the same way.
reason_for() {
  case "$1" in
    env) echo "credential leak risk. Edit .env.example instead." ;;
    lock) echo "change dependencies via 'uv add', 'uv remove', or 'uv sync' instead of hand-editing." ;;
    copier) echo "Copier template config. Edit intentionally outside Claude." ;;
    migration) echo "generate a new migration via: just migrate-gen \"<message>\". Editing existing migrations breaks consumers who already ran them." ;;
    synced) echo "it is a build artifact synced by 'just docb' from a root file (CHANGELOG.md, CONTRIBUTING.md, ROADMAP.md, SECURITY.md, or LICENSE). Edit the root file instead, then run 'just docb'." ;;
  esac
}

# --- Bash: deny writes to guarded paths, allow reads -------------------
if [[ "$tool" == "Bash" ]]; then
  cmd=$(jq -r '.tool_input.command // empty' <<<"$payload")
  [[ -z "$cmd" ]] && exit 0

  # Write intent. An interpreter counts as one: a heredoc can hide any
  # redirect from a pattern match, so python/perl/ruby/node touching a
  # guarded path is treated as a write regardless of what it does.
  write_re='(>|\btee\b|\bsed\b[[:space:]]+-[A-Za-z]*i|\bperl\b[[:space:]]+-[A-Za-z]*i'
  write_re+='|\bpython[0-9.]*\b|\bruby\b|\bnode\b|\bawk\b|\bcp\b|\bmv\b|\brm\b|\bdd\b'
  write_re+='|\btruncate\b|\btouch\b|\bln\b|\bchmod\b'
  write_re+='|\bgit[[:space:]]+(checkout|restore|apply|clean)\b)'
  grep -Eq "$write_re" <<<"$cmd" || exit 0

  kind=""
  if grep -Eq '(^|[^A-Za-z0-9_/-])copier\.ya?ml([^A-Za-z0-9_-]|$)' <<<"$cmd"; then
    kind=copier
  elif grep -Eq '(^|[^A-Za-z0-9_/-])uv\.lock([^A-Za-z0-9_-]|$)' <<<"$cmd"; then
    kind=lock
  elif grep -Eq 'alembic/versions/[^[:space:]]*\.py' <<<"$cmd"; then
    kind=migration
  elif grep -Eq 'docs/project/[A-Za-z0-9_.-]+\.md' <<<"$cmd"; then
    kind=synced
  else
    # .env variants, minus the two committed config files.
    while read -r tok; do
      case "$tok" in
        .env.example|.env.test) ;;
        .env|.env.*) kind=env; break ;;
      esac
    done < <(grep -oE '\.env[A-Za-z0-9_.-]*' <<<"$cmd" | sort -u)
  fi

  [[ -z "$kind" ]] && exit 0
  case "$kind" in
    env) what="an .env credential file" ;;
    lock) what="uv.lock" ;;
    copier) what="copier.yml" ;;
    migration) what="an applied Alembic migration" ;;
    synced) what="a doc synced by 'just docb'" ;;
  esac
  deny "Refusing this Bash command — it looks like it writes to $what. $(reason_for "$kind") Reading is fine: use Read or Grep instead."
fi

# --- Edit|Write|MultiEdit: deny by target path -------------------------
f=$(jq -r '.tool_input.file_path // empty' <<<"$payload")
[[ -z "$f" ]] && exit 0
base=$(basename "$f")

# .env files: allow committed config files, block gitignored credential files
case "$base" in
  .env.example|.env.test) ;;
  .env|.env.*)
    deny "Refusing to edit $base — $(reason_for env)" ;;
esac

# Lock files
case "$base" in
  uv.lock)
    deny "Refusing to edit uv.lock — $(reason_for lock)" ;;
esac

# Copier template config
case "$base" in
  copier.yml|copier.yaml)
    deny "Refusing to edit $base — $(reason_for copier)" ;;
esac

# Applied alembic migrations
case "$f" in
  *alembic/versions/*.py)
    deny "Refusing to edit applied alembic migrations. $(reason_for migration)" ;;
esac

# Generated docs synced from root files by 'just docb'
case "$f" in
  *docs/project/*.md)
    deny "Refusing to edit docs/project/$base — $(reason_for synced)" ;;
esac

exit 0
