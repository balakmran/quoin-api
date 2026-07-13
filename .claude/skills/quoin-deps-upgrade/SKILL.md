---
name: quoin-deps-upgrade
description: Use this skill whenever the user wants to upgrade dependencies or
  tooling versions in QuoinAPI — Python packages, the Python version itself,
  uv/ruff/ty, or the GitHub Actions pinned in workflows. Triggers include
  "upgrade the dependencies", "update deps", "bump the GitHub Actions",
  "upgrade to Python 3.x", "is there a newer version of X", "update uv / ruff /
  ty", or "check the actions for new versions". Do NOT use for adding a single
  new dependency to support a feature (just `uv add` it), or for the release /
  version-bump flow (that is `quoin-release`).
allowed-tools: Read, Edit, Write, Bash, Grep, Glob, WebFetch, WebSearch
---

# Upgrading Dependencies & Tooling

Version upgrades in this repo follow a repeatable ritual. The two failure modes
are (a) breaking a pin convention upstream changed, and (b) leaving stale
version strings scattered through docs. This skill covers both Python deps and
GitHub Actions; do the relevant half.

## Setup

Branch off `main` with a `chore/` name (`chore/update-deps`,
`chore/upgrade-gha-actions`). Commits are `chore(deps): ...`.

Don't guess version-specific behavior — read the upstream release notes (use
Context7 or the project's GitHub releases page) before changing a pin,
especially for major bumps.

## Python dependencies

1. **Respect `exclude-newer`.** `pyproject.toml` pins `exclude-newer = "7 days"`
   — uv ignores anything published more recently, so the lock is reproducible.
   Don't remove it to chase a same-day release.
2. **Upgrade the lock**, then sync:
   ```bash
   uv lock --upgrade
   uv sync --all-groups
   ```
   Review the `uv.lock` diff — never hand-edit the lock (a hook blocks it).
3. **Python version bump** (e.g. 3.14): the interpreter is managed by uv. Update
   `requires-python` in `pyproject.toml`, install the target with
   `uv python install <version>`, and re-lock. Then run the stale-reference
   sweep below — the version string lives in many places.

## GitHub Actions

Pinned in `.github/workflows/ci.yml` and `.github/workflows/docs.yml`.

1. For each action, check its release notes for **pinning guidance** — some
   drop floating tags. Example: `astral-sh/setup-uv` stopped publishing minor
   tags, so `@v8` / `@v8.0` no longer resolve; pin to a full `vX.Y.Z`.
2. Update the version in **both** workflow files (they often share actions).
3. Mind the runner/toolchain matrix (e.g. Node 24 support) when a bump requires
   a newer runtime.

## Stale-reference sweep (the step that gets forgotten)

After any version change, grep for the **old** version string and update every
hit — docs are the usual stragglers:

```bash
git grep -n "3\.12"   # or the old dep/action version you just replaced
```

Check at least: `README.md`, `docs/` guides, `Dockerfile`, `.env.example`,
`copier.yml` and `scripts/copier_setup.py.jinja` (this repo is also a Copier
template), and any badges.

## `.env` sync

If an upgrade adds, renames, or removes a setting, update `.env.example` and the
settings table in `docs/guides/configuration.md` to match (CLAUDE.md rule; the
config-drift Stop hook will also flag this).

## Verify and ship

```bash
just check    # format, lint, typecheck, tests at 100%
```

Then hand off to [quoin-pre-pr](../quoin-pre-pr/SKILL.md) — it covers the
changelog entry and `just docb` before the PR.

## Things that bite

- **Removing `exclude-newer` to get a fresh release** — breaks reproducibility
  for everyone. Wait out the window or change the duration deliberately.
- **Updating one workflow file but not the other** — `ci.yml` and `docs.yml`
  drift apart.
- **Hand-editing `uv.lock`** — always go through `uv lock` / `uv sync`.
- **Forgetting the stale-reference sweep** — the code works but docs now lie
  about the supported version.
