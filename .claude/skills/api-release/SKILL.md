---
name: api-release
description: Use this skill whenever the user wants to cut a release, ship a version, bump the version, tag a release, publish a new version, prepare a changelog entry, or do anything that ends with a `vX.Y.Z` git tag on this QuoinAPI project. Triggers include phrases like "release 0.7.0", "cut a patch release", "ship a new version", "bump the minor version", "tag the release", "prepare the changelog for release", or "let's release". Do NOT use for editing the changelog mid-development without releasing, hotfix/emergency-patch releases (that is `api-hotfix`), or generating release notes for an already-tagged version.
allowed-tools: Read, Edit, Bash
model: haiku
---

# Releasing QuoinAPI

A QuoinAPI release is a small, ordered ritual: changelog → version bump → changelog rename → commit → merge → tag. `just tag` publishes the GitHub Release itself — no workflow does, so the recipe does. The long-form rationale lives in [docs/guides/release-workflow.md](../../../docs/guides/release-workflow.md); this skill is the in-the-moment checklist.

## Before you start

Confirm three things with the user (or from the repo state) before touching anything:

1. **Bump type** — `patch` (bug fixes), `minor` (new features, backwards-compatible), `major` (breaking). SemVer rules apply.
2. **Branch** — you should be on a clean working branch off `main`, not on `main` directly. The changelog/version commit goes through PR review like any other change.
3. **What's actually shipping** — skim `git log <last-tag>..HEAD` so the changelog reflects reality. The `[Unreleased]` section is often stale or incomplete.

Then run `just audit` **and** `just audit-prod` — CVE scanning is not in CI, so a release is the
last checkpoint before shipping vulnerable dependencies, and the second is the subset that actually
reaches production. Every ID left in `audit_ignore` needs a current dated justification. Remediation
ladder in [docs/guides/dependency-scanning.md](../../../docs/guides/dependency-scanning.md).

## Workflow

### 1. Curate the `[Unreleased]` section in `CHANGELOG.md`

Open `CHANGELOG.md`. The top-most section is `## [Unreleased]`. Make sure it accurately captures everything merged since the last tag.

**Section order within a release** (omit any that are empty):

1. Added
2. Changed
3. Deprecated
4. Removed
5. Fixed
6. Security

This order is non-negotiable — it matches Keep a Changelog and the project's prior releases. Don't invent new section names.

Each entry is a bullet describing user-visible impact, not the diff. Group related bullets under a bold sub-label when it helps scanning (see prior releases for the `**Security**:`, `**Developer Experience**:` style).

### 2. Bump the version

```bash
just bump patch          # or minor, or major
just bump major --rc     # first release candidate, e.g. 0.14.0 -> 1.0.0-rc.1
just bump rc             # next candidate, 1.0.0-rc.1 -> 1.0.0-rc.2
just bump release        # finalise, 1.0.0-rc.2 -> 1.0.0
```

This updates the version string in **both** `pyproject.toml` and `app/__init__.py` via `scripts/bump_version.py`, and refuses if they disagree. From a candidate, `major`/`minor`/`patch` are refused; use `rc` or `release`. It does not touch the changelog or git.

After running, note the new version — you'll use it in the next two steps.

### 3. Promote `[Unreleased]` to the new version in `CHANGELOG.md`

Rename the heading from `## [Unreleased]` to `## [X.Y.Z] - YYYY-MM-DD` using today's date, and insert a fresh empty `## [Unreleased]` section above it so the next cycle has somewhere to land entries.

Example transition:

```markdown
## [Unreleased]

## [0.7.0] - 2026-04-25

### Added
- ...
```

### 4. Commit and merge

```bash
git add CHANGELOG.md pyproject.toml app/__init__.py uv.lock
git commit -m "docs: update changelog for vX.Y.Z"
```

`uv.lock` records the project's own version, so `just bump` changes it too. Leave it out and `prek`
reverts the commit instead of making it: the hook's own formatting conflicts with the unstaged lock.

Push the branch and merge the PR to `main` the normal way. **Do not tag from a feature branch** — the tag must point at the merge commit on `main` so the release reflects what's actually shipped.

### 5. Prove the release before the tag is public

A pushed tag cannot be withdrawn, and the checks that would catch a bad one run too late: the Copier
Update Check only fires **after** the tag, and `just check` never exercises a generated project or
the image. Create the tag locally, verify, then let step 6 push it (`just tag` skips a tag that
already exists).

```bash
git status --porcelain   # must be empty: a dirty template is copied as-is, untracked files included
git tag vX.Y.Z           # local only
just verify-template-update <preceding-tag> vX.Y.Z --check
just verify-template-update <newest-final-release> vX.Y.Z --check
```

Both arguments must be real tags — the script compares them against the `_commit` recorded in
`.copier-answers.yml`, so `HEAD` or a branch name fails. `copier update` needs that file, which
first shipped in `0.10.0`; older baselines cannot be verified because they cannot update at all.

Then generate a project with **long, non-default answers** and run its gate. `--defaults` gives a
short name that hides every line which overflows once a real settings prefix is substituted, and 30
characters is the documented budget:

```bash
uvx copier copy --trust --vcs-ref=HEAD --defaults \
    --data project_name="Northwind Traders Platform API" . ../rel-smoke
cd ../rel-smoke && uv sync --all-groups && just check
```

Finally confirm the image: it builds, starts as the non-root user, and hides its docs in production
— `/docs`, `/redoc` and `/openapi.json` all `404` under `QUOIN_ENV=production`, while `/health` and
`/ready` still serve.

### 6. Tag the release

Once the changelog/bump commit is on `main` and you've pulled it locally:

```bash
just tag
```

`scripts/tag_release.py` reads the version from `app/__init__.py`, creates and pushes `vX.Y.Z`, then publishes the GitHub Release with that version's changelog section as the body. Both halves are idempotent: an existing tag is not recreated, an existing release is left alone, so a re-run after a partial failure is safe.

`gh` must be installed and authenticated. Both are checked **before** the tag is created, so a missing prerequisite costs nothing rather than leaving a pushed tag with no release. To tag without publishing:

```bash
just tag --no-release
```

The release matches every tag since `v0.8.0`: title is the bare tag (`v0.11.0`, no prose), body is the changelog section starting at `### Added`, neither draft nor pre-release.

A release candidate (`vX.Y.Z-rc.N`) goes through the same steps, with its own `## [X.Y.Z-rc.N] - date` changelog section; `just tag` publishes it as a GitHub pre-release. Only the `-rc.N` suffix is supported.

## After the tag

Verify the release landed:

- Confirm the GitHub Release page shows the `vX.Y.Z` entry with the changelog body.
- Check the Actions tab: CI on `main` and **Copier Update Check** on the tag
  should both be green. The update check is the one that matters — it proves
  `copier update` still applies cleanly across the release boundary.
- Pull `main` and confirm `git describe --tags` reports the new tag.

If the release step fails after the tag is pushed, **don't delete the tag** —
fix the problem and re-run `just tag`, which skips the existing tag and retries
only the release. The tag is already public and deleting it breaks anyone who
pulled it. If the *release* is wrong rather than the tag, edit it in place with
`gh release edit vX.Y.Z --notes-file -`.

## Things that bite

- **Forgetting to update the changelog before bumping** — the bump script doesn't check, and you'll end up with a `vX.Y.Z` tag whose changelog entry is empty or wrong. Always do step 1 first.
- **Tagging from the feature branch** — the tag will point at a commit that isn't on `main`, and the GitHub Release will reflect a tree no one else sees. Always merge first, pull `main`, then `just tag`.
- **Skipping a section out of section order** — if you add a `### Fixed` block above `### Added`, the reader's eye loses the convention. Reorder before committing.
- **Polling the container healthcheck too fast.** `HEALTHCHECK` declares `--start-period=10s
  --interval=30s`, so a tight `docker inspect` loop burns its iterations in under a second and
  reports `starting` forever. Poll with a real delay, or a healthy image looks broken.
- **Using `chore:` instead of `docs:` for the release commit** — convention here is `docs: update changelog for vX.Y.Z`. It keeps the release commits trivially greppable.

## When the user asks for "just bump the version"

If the user asks only to bump (not to release), do step 2 and stop — don't touch the changelog or push tags. A bare bump is sometimes useful mid-development to move a pre-release version forward; treat it as a different intent than a full release and confirm before going further.
