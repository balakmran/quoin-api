---
name: quoin-hotfix
description: Use this skill whenever the user wants to ship a critical fix
  outside the normal release cadence — a hotfix, an emergency patch release,
  or shipping a single urgent bug fix straight to production without
  bundling it with other in-flight work. Triggers include "hotfix this",
  "we need an emergency patch", "ship just this fix now", "cut a hotfix
  release", "critical bug needs to go out now", or "patch release for the
  security issue". Do NOT use for a normal release with the usual
  accumulated changes (that is `quoin-release`), or for a bug fix that isn't
  urgent enough to skip the normal cycle (fix it, let `quoin-pre-pr` and the
  next `quoin-release` handle it).
allowed-tools: Read, Edit, Bash
model: haiku
---

# Hotfixing a QuoinAPI Release

A hotfix is a `quoin-release` cut down to one change and one urgency level:
branch from `main` (not from in-flight feature work), fix, patch-bump, tag.
The full ritual and rationale live in
[docs/guides/release-workflow.md#hotfix-releases](../../../docs/guides/release-workflow.md#hotfix-releases);
this skill is the fast path. For a normal release with the usual
accumulated `[Unreleased]` entries, use
[quoin-release](../quoin-release/SKILL.md) instead — don't use this skill to
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
just bump part="patch"
```

Hotfixes are patch releases by definition — if the fix needs a minor or
major bump, it's not a hotfix, it's a release; switch to `quoin-release`.

### 5. Update the changelog

Add a `### Fixed` entry under `## [Unreleased]` in `CHANGELOG.md` describing
the fix's user-visible impact. Then promote it the same way `quoin-release`
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

Same as `quoin-release`: never tag from the hotfix branch — the tag must
point at the merge commit on `main`.

## After the tag

Verify the release landed (Actions tab, GitHub Release page,
`git describe --tags`) — same checklist as `quoin-release`.

## Things that bite

- **Branching from a feature branch instead of `main`.** Pulls in unreviewed
  work alongside the fix — always branch from `main`.
- **Bundling unrelated `[Unreleased]` entries into the hotfix changelog
  section.** Only the fix being hotfixed belongs in that release; everything
  else waits for the next normal release.
- **Skipping `just check` because it's urgent.** A hotfix that fails in
  production because CI was skipped is worse than a ten-minute delay.
- **Using a minor/major bump.** If the fix isn't patch-level, it isn't a
  hotfix — use `quoin-release` and the normal cadence instead.
