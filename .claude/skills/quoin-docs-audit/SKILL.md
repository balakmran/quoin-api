---
name: quoin-docs-audit
description: Use this skill whenever the user wants to verify that QuoinAPI's
  documentation still matches the code — a docs-accuracy sweep. Triggers
  include "review the docs for accuracy", "check docs against the code", "audit
  docs/ for stale info", "are the docs still correct", "do the guides match the
  implementation", or "find outdated documentation". Do NOT use for fixing a
  broken docs build (that is `just docb`), writing a brand-new guide for a
  feature you just shipped (do that inline per the CLAUDE.md docs-coverage
  rule), or syncing root docs into `docs/project/` (that is `just docb` too).
---

# Auditing QuoinAPI Docs Against the Code

Periodic drift check: the guides in `docs/guides/` describe behavior that lives
in code, and the two slip apart over time. This skill is the systematic sweep
the project has done by hand before ("review all md under docs/ for accuracy",
"check for old refs to py 3.12"). It is read-and-report first — propose fixes,
then apply them in the same turn once the user agrees.

## Scope

Audit `docs/guides/*.md` and `README.md` against the live code. Skip
`docs/project/*.md` — those are build artifacts synced by `just docb` from the
root files (`CHANGELOG.md`, `CONTRIBUTING.md`, `ROADMAP.md`, `LICENSE`); fix the
root source, not the synced copy.

## The high-signal checks

1. **Settings table vs `config.py`.** The settings table in
   `docs/guides/configuration.md` must list every `QUOIN_` setting in
   `app/core/config.py`, with matching names and defaults. Diff the two:
   - Settings in code but missing from the table → add them.
   - Settings in the table but gone from code → remove them.
   - Defaults that disagree → fix the doc.
   Also cross-check `.env.example` carries the same surface.

2. **Endpoint lists vs routers.** Where a guide enumerates routes, confirm they
   exist in `app/modules/*/routes.py` and `app/api.py`, all under `/api/v1/`.

3. **Commands vs `justfile`.** Any `just <recipe>` mentioned in docs must exist
   (`just --list`). Flag renamed/removed recipes.

4. **Version strings.** Sweep for stale versions — Python, key deps, GitHub
   Actions: `git grep -nE "3\.(12|13)"` and similar. Compare against
   `pyproject.toml` (`requires-python`) and the workflow files. (This overlaps
   with `quoin-deps-upgrade`'s sweep — reuse it.)

5. **Shields badges (two files, kept in parity).** The badge block lives in
   **both** `README.md` and `docs/guides/getting-started.md`, and hardcoded
   badge versions drift silently. For each block:
   - FastAPI / SQLModel badge versions must match the `pyproject.toml` pins;
     the Python badge must match `requires-python`; the `PostgreSQL-<major>`
     badge must match `docker-compose.yml` (`postgres:18`).
   - The two blocks must carry the **same badges in the same order** — they
     have fallen out of sync before (one file got a badge fix, the other
     didn't). Diff them.
   Prefer self-updating endpoint badges (CI/Docs status, Release, Ruff, uv,
   prek) over hardcoded version strings, which are the drift-prone kind.

6. **Referenced files/paths & README structure.** Backtick paths like
   `app/core/...`, `scripts/...`, `.claude/...` in docs should still resolve.
   The `README.md` **Project Structure** tree must match the real `app/`
   layout — it goes stale as modules/files are added (it has been missing
   `app/http/`, `app/modules/system/`, and several `app/core/` files) — and the
   **Contents** ToC must list every `##` section, in document order.

7. **Code samples that claim to run.** Spot-check that example snippets use
   current APIs (e.g. SQLModel/SQLAlchemy 2.x async, Pydantic v2). Use the
   `context7` MCP server to confirm current library syntax rather than guessing.

8. **Docs build.** Finish with `just docb` — an audit that breaks the build
   helps no one.

## Output

Report findings grouped by file, each as: *what the doc says* → *what the code
says* → *proposed fix*. Then, once the user confirms, apply the edits and run
`just docb`. Don't silently rewrite docs — drift is sometimes the doc being
right and the code having regressed, which is worth surfacing, not papering
over.

## Things that bite

- **Editing `docs/project/*` directly.** Those are generated; your change will
  be overwritten on the next `just docb`. Edit the root source file.
- **Assuming a mismatch means the doc is wrong.** Sometimes the code drifted.
  Surface the discrepancy and let the user decide which side to fix.
- **Forgetting the settings table is the most drift-prone doc** — `config.py`
  changes land far more often than the table gets updated. Check it first.
- **Fixing a badge in one file but not the other.** Badges are duplicated in
  `README.md` and `docs/guides/getting-started.md`; a version bump or new badge
  must land in both, or they silently diverge.
