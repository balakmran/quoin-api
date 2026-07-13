#!/usr/bin/env bash
# Stop hook: advisory check for HTTPException leaking into service/repository
# code.
#
# QuoinAPI's rule is "never raise HTTPException in service or repository
# code" (CLAUDE.md) — raise a domain exception from app/core/exceptions
# instead, so the global exception handler can translate it. When a changed
# service.py or repository.py under app/modules/ references HTTPException,
# that rule was likely broken. Emits a non-blocking systemMessage; never
# blocks, because a hit can be a false positive (e.g. a comment or a type
# reference in a docstring).
set -euo pipefail

cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0

changed=$(git status --porcelain 2>/dev/null | awk '{print $NF}') || exit 0
[ -z "$changed" ] && exit 0

hits=""
for f in $changed; do
  case "$f" in
    app/modules/*/service.py | app/modules/*/repository.py) ;;
    *) continue ;;
  esac
  [ -f "$f" ] || continue
  if grep -q "HTTPException" "$f"; then
    hits="$hits $f"
  fi
done

[ -z "$hits" ] && exit 0

jq -n --arg files "${hits# }" '{
  systemMessage: ("HTTPException check: " + $files + " references "
    + "HTTPException. Service and repository code must raise a domain "
    + "exception (NotFoundError, ConflictError, BadRequestError, "
    + "ForbiddenError, InternalServerError, or a module subclass) from "
    + "app/core/exceptions instead — the global handler only translates "
    + "domain exceptions. If this is a false positive (e.g. a comment), "
    + "ignore this.")
}'
exit 0
