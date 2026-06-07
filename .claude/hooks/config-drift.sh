#!/usr/bin/env bash
# Stop hook: advisory check for configuration drift.
#
# When app/core/config.py is among the changed files but neither
# .env.example nor docs/guides/configuration.md is, the QUOIN_ settings
# surface and its docs have likely fallen out of sync (a CLAUDE.md rule).
# Emits a non-blocking warning via systemMessage; never blocks the turn,
# because not every config.py edit adds or renames a setting.
set -euo pipefail

cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0

changed=$(git status --porcelain 2>/dev/null | awk '{print $2}') || exit 0
[ -z "$changed" ] && exit 0

echo "$changed" | grep -q '^app/core/config\.py$' || exit 0

if echo "$changed" | grep -q '^\.env\.example$'; then exit 0; fi
if echo "$changed" | grep -q '^docs/guides/configuration\.md$'; then exit 0; fi

jq -n '{
  systemMessage: ("Config drift: app/core/config.py changed but .env.example "
    + "and docs/guides/configuration.md did not. If this edit added, renamed, "
    + "or removed a QUOIN_ setting, update both to match. If not, ignore this.")
}'
exit 0
