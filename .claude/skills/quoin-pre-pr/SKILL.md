---
name: quoin-pre-pr
description: Use this skill whenever the user is about to open a pull request,
  says a feature is done, asks to create a PR, or says "ready to merge",
  "ship this", "open a PR", "create a pull request", "I'm done with this
  feature", or any phrase that signals the work is complete and heading for
  review. Always run this checklist before creating the PR — do not skip
  straight to `gh pr create`. Do NOT use for: mid-development commits, the
  release tagging flow (that is `quoin-release`), or hotfix branches where
  the changelog entry was already written.
---

# Pre-PR Checklist

These steps precede opening a PR. Steps 1, 3, and 4 are never skipped; the
changelog (step 2) has one carve-out, noted below.

## 1. Pass the full quality gate

```bash
just check
```

This runs format → lint → typecheck → tests **with coverage**. `just test`
auto-starts Postgres if it isn't running, so there's no separate `just db`
step. The PR must not be opened until this is green.

Coverage is **100%** on this project — every feature ships fully covered. If
`just check` reports a gap, close it before continuing; the
[quoin-coverage](../quoin-coverage/SKILL.md) skill covers the gap-closing loop.

## 2. Update `CHANGELOG.md`

Open `CHANGELOG.md` and add a concise entry under `## [Unreleased]`.

If `## [Unreleased]` has no `### Added` / `### Changed` / `### Fixed` section
yet, create the appropriate one. Section order within a release:
Added → Changed → Deprecated → Removed → Fixed → Security.

Keep entries user-visible and impact-focused — what changed and why it
matters, not what files were edited. Group related bullets under a bold
sub-label when it helps scanning (see existing entries for the style).

If `[Unreleased]` already has an accurate entry for this work, skip ahead.

**Docs-only / chore carve-out.** If the change has no user-visible behaviour —
a README or badge refresh, a docs-audit fix, a comment or skill cleanup — skip
the changelog; an entry for it is just noise. The test: would a user of the API
notice? If not, no entry. (This is why a pure README/badges PR ships without
touching `CHANGELOG.md`.)

## 3. Run the docs build

```bash
just docb
```

This verifies that any doc changes (new guides, nav additions, docstring
updates) render without errors. A broken docs build blocks the CI pipeline
the same as a failing test — catch it here, not in the PR.

`just docb` also syncs `CHANGELOG.md` → `docs/project/changelog.md` (and
similarly for `CONTRIBUTING.md`, `ROADMAP.md`, `LICENSE`). **Commit the
synced files** — they are checked-in build artifacts, not gitignored.

If `just docb` fails, fix the docs issue before continuing.

**If this PR changed a dependency version or `requires-python`,** update the
matching Shields badge in **both** `README.md` and
`docs/guides/getting-started.md` (FastAPI/SQLModel/Python/`PostgreSQL-<major>`).
The two badge blocks are duplicated and drift apart otherwise — see the
[quoin-docs-audit](../quoin-docs-audit/SKILL.md) skill for the full parity check.

## 4. Create the PR

Once all steps are green, open the PR normally (via `gh pr create` or the
`commit-commands` plugin). The PR description should reference the changelog
entry — reviewers read the PR body, not the diff, to understand what shipped.
