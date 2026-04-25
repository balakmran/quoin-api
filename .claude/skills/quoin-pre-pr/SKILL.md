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

Two steps must happen before opening a PR. Neither is optional.

## 1. Update `CHANGELOG.md`

Open `CHANGELOG.md` and add a concise entry under `## [Unreleased]`.

If `## [Unreleased]` has no `### Added` / `### Changed` / `### Fixed` section
yet, create the appropriate one. Section order within a release:
Added → Changed → Deprecated → Removed → Fixed → Security.

Keep entries user-visible and impact-focused — what changed and why it
matters, not what files were edited. Group related bullets under a bold
sub-label when it helps scanning (see existing entries for the style).

If `[Unreleased]` already has an accurate entry for this work, skip ahead.

## 2. Run the docs build

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

## 3. Create the PR

Once both steps are green, open the PR normally (via `gh pr create` or the
`commit-commands` plugin). The PR description should reference the changelog
entry — reviewers read the PR body, not the diff, to understand what shipped.
