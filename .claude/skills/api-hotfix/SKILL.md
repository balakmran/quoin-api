---
name: api-hotfix
description: Use when an urgent fix must ship on its own, outside the normal
  release cadence, as an emergency patch release. Not for a normal release of
  accumulated changes (`api-release`), or a fix that can wait for the next
  release (fix it and let `api-pre-pr` and `api-release` handle it).
allowed-tools: Read, Edit, Bash
model: haiku
---

# Hotfixing a QuoinAPI Release

A hotfix is a `api-release` cut down to one change and one urgency level:
branch from `main` (not from in-flight feature work), fix, patch-bump, tag.
The full ritual and rationale live in
[docs/guides/release-workflow.md#hotfix-releases](../../../docs/guides/release-workflow.md#hotfix-releases);
this skill is the fast path. For a normal release with the usual
accumulated `[Unreleased]` entries, use
[api-release](../api-release/SKILL.md) instead — don't use this skill to
smuggle in unrelated changes just because it's faster.

## Before you start

Confirm with the user: what's the bug, and is it actually urgent enough to
skip the normal release cycle? A hotfix bypasses the usual "let
`[Unreleased]` accumulate, then release" cadence — reserve it for things
that can't wait (a security issue, a production-breaking regression), not
convenience.

## Workflow

### 1. Branch from `main`, not from feature work

```bash
git checkout -b hotfix/short-description main
```

Branching from `main` (rather than an in-progress feature branch) keeps the
fix isolated from anything not yet ready to ship.

### 2. Fix the bug

Make the minimal change that resolves the issue. Resist scope creep — a
hotfix branch is not the place for adjacent cleanup; note anything else
worth doing and let it go through the normal flow.

### 3. Run the quality gate

```bash
just check
```

Same bar as any other change — coverage, lint, typecheck, tests must all
pass. A hotfix that breaks CI isn't faster, it's blocked.

### 4. Bump the patch version

```bash
just bump patch
```

Hotfixes are patch releases by definition — if the fix needs a minor or
major bump, it's not a hotfix, it's a release; switch to `api-release`.

### 5. Update the changelog

Add a `### Fixed` entry under `## [Unreleased]` in `CHANGELOG.md` describing
the fix's user-visible impact. Then promote it the same way `api-release`
does: rename `## [Unreleased]` to `## [X.Y.Z] - YYYY-MM-DD` and insert a
fresh empty `## [Unreleased]` above it. **Only include this fix** — don't
pull in unrelated `[Unreleased]` entries that happen to be sitting there
from other in-progress work; those ship in the next normal release.

### 6. Commit, merge, tag

```bash
git add CHANGELOG.md pyproject.toml app/__init__.py
git commit -m "fix: <short description of the critical fix>"
```

Push the branch, merge to `main` (through PR review — a hotfix still gets
reviewed, just fast), pull `main` locally, then:

```bash
just tag
```

Same as `api-release`: never tag from the hotfix branch — the tag must
point at the merge commit on `main`.

## After the tag

Verify the release landed (Actions tab, GitHub Release page,
`git describe --tags`) — same checklist as `api-release`.

## Things that bite

- **Branching from a feature branch instead of `main`.** Pulls in unreviewed
  work alongside the fix — always branch from `main`.
- **Bundling unrelated `[Unreleased]` entries into the hotfix changelog
  section.** Only the fix being hotfixed belongs in that release; everything
  else waits for the next normal release.
- **Skipping `just check` because it's urgent.** A hotfix that fails in
  production because CI was skipped is worse than a ten-minute delay.
- **Using a minor/major bump.** If the fix isn't patch-level, it isn't a
  hotfix — use `api-release` and the normal cadence instead.
