#!/usr/bin/env bash
# Stop hook: advisory reminder to generate a migration.
#
# QuoinAPI's rule is "never modify the schema by hand": change the SQLModel
# in app/modules/<m>/models.py, then run `just migrate-gen`. When a models.py
# changed this turn but no new file appeared under alembic/versions/, the
# migration was probably forgotten. Emits a non-blocking systemMessage;
# never blocks, because some models.py edits (a docstring, a non-mapped
# attribute) don't need a migration.
set -euo pipefail

cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0

# $NF handles renames ("R old -> new") by taking the new path.
changed=$(git status --porcelain 2>/dev/null | awk '{print $NF}') || exit 0
[ -z "$changed" ] && exit 0

echo "$changed" | grep -qE '^app/modules/.*/models\.py$' || exit 0

# A new (added or untracked) migration script means it was generated.
if echo "$changed" | grep -qE '^alembic/versions/.*\.py$'; then exit 0; fi

jq -n '{
  systemMessage: ("Schema reminder: a models.py changed but no new "
    + "alembic/versions/ script was added. If this edit altered the schema "
    + "(columns, indexes, constraints), run `just migrate-gen \"<msg>\"`, "
    + "review the script, then `just migrate-up`. If it was a non-schema "
    + "change, ignore this.")
}'
exit 0
