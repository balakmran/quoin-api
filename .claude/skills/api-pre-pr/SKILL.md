---
name: api-pre-pr
description: Use when work is finished and heading for review — the user asks
  to open a PR, says a feature is done, or is ready to merge. Run this
  checklist before creating the PR, not after. Not for mid-development
  commits, the release flow (`api-release`), or hotfix branches whose
  changelog entry is already written.
allowed-tools: Read, Edit, Bash
model: haiku
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
[api-coverage](../api-coverage/SKILL.md) skill covers the gap-closing loop.

## 2. Update `CHANGELOG.md`

Open `CHANGELOG.md` and add a concise entry under `## [Unreleased]`.

If `## [Unreleased]` has no `### Added` / `### Changed` / `### Fixed` section
yet, create the appropriate one. Section order within a release:
Added → Changed → Deprecated → Removed → Fixed → Security.

Keep entries to one or two lines per bullet: what changed, and anything an
adopter must do. Prefix each bullet with a bold sub-label (`**API**`,
`**Tooling**`, `**Docs**`, `**Dependencies**`, …). Rationale, mechanics, and
file-level notes belong in the commit and `docs/guides/`. Example:

```markdown
- **Tooling**: uv 0.12.17 in the `Dockerfile` and every workflow.
  Update-safe; upgrade a local uv with `uv self update`.
```

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

**If this PR changed `requires-python` or the Postgres major version,**
update the matching Shields badge in `README.md` — the only badge block. See
[api-docs-audit](../api-docs-audit/SKILL.md) for which badges carry versions.

## 4. Create the PR

Once all steps are green, open the PR normally (via `gh pr create` or the
`commit-commands` plugin). The PR description should reference the changelog
entry — reviewers read the PR body, not the diff, to understand what shipped.
