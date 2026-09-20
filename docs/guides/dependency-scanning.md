# Dependency Scanning

QuoinAPI stays patched with three layers: **`uv audit`** for on-demand
CVE scanning, **Dependabot** for automated version updates, and
**secret scanning** for leaked credentials. This guide covers what
ships in the repo, what you enable in repository settings, and how an
enterprise fork layers commercial scanners on top.

---

## `uv audit`

`uv audit` checks the locked dependency tree against the
[OSV](https://osv.dev) vulnerability database. It reads `uv.lock`
directly — it never builds an environment — so it runs in about a
second.

| Recipe | Scans |
| :--- | :--- |
| `just audit` (alias `just au`) | every group: runtime, dev, test, docs |
| `just audit-prod` | runtime dependencies only — what ships in the image |
| `just audit-fix <package>` | bumps one package, re-syncs, re-audits |

`just audit` forwards extra arguments straight to `uv audit`, so
`just audit --output-format json` works for scripting.

Both recipes pass `--locked`, which asserts `uv.lock` is already
consistent with `pyproject.toml`. If the audit fails with a lockfile
error rather than a CVE list, run `uv lock` first — you are auditing a
dependency set that does not match what you declared.

!!! note "Experimental command"

    `uv audit` is a preview feature; the recipes pass
    `--preview-features audit-command` to opt in and silence the
    warning. Its name and output format may change in a future uv
    release. CI installs the same uv version the `Dockerfile` pins, so
    that change arrives only with a deliberate uv bump — rerun
    `just audit` locally when you make one.

### Where it runs

`uv audit` is **not** wired into `just check`, the `prek` hooks, or any
commit-triggered CI job. It needs network access, and its result depends
on the OSV database rather than on your code, so an advisory published
overnight would otherwise block unrelated commits, pushes, and pull
requests that changed nothing.

It does run on a schedule. The
[`dependency-audit.yml`](../../.github/workflows/dependency-audit.yml)
workflow runs both recipes every Monday at 07:00 UTC — and on demand via
*Run workflow* — filing the report as a GitHub issue labelled
`dependency-audit` when either finds something. A second finding while
that issue is still open is added as a comment rather than a new issue,
so a long-lived advisory doesn't file a fresh ticket every week.

Two things to know about scheduled workflows: GitHub runs them only from
the default branch, and disables them after 60 days without repository
activity. A red run means triage the advisory, not that CI broke.

Run the recipes yourself at the points where the answer matters sooner
than next Monday:

- **After any dependency change** — `uv lock --upgrade`, a new `uv add`,
  or reviewing a Dependabot PR. The
  [`quoin-deps-upgrade`](ai-setup.md) skill includes this step.
- **Before cutting a release** — see the
  [release workflow](release-workflow.md).
- **Before merging anything you intend to tag.** The weekly run reports
  on `main` as it stood on Monday, not on your branch.

The schedule's real job is the case you cannot prompt yourself to check:
an advisory filed against a dependency that has *not* changed. Nothing
in a commit-triggered pipeline will ever surface those.

!!! tip "Tuning the schedule"

    Change the `cron` expression in
    [`dependency-audit.yml`](../../.github/workflows/dependency-audit.yml)
    for a different cadence, or delete the `schedule:` trigger to leave
    only the manual *Run workflow* button. The job needs no `uv sync` —
    both recipes read `uv.lock` without building an environment — so it
    stays cheap whatever cadence you pick.

### Remediating a finding

Work down this list; stop at the first option that applies.

1. **Bump the package.** If the advisory lists a fixed version,
   `just audit-fix <package>` bumps that one package and re-audits.
   For a transitive dependency, name the transitive package — uv will
   pull a newer version if the parent's constraints allow it.
2. **Bump the parent.** If step 1 reports the package is pinned by
   another dependency, upgrade that parent instead
   (`just audit-fix <parent>`), or run `uv lock --upgrade` for a full
   refresh and review the resulting diff.
3. **Force a floor with a constraint.** When the parent's range is too
   tight but the newer transitive version is actually compatible, add a
   lower bound under `[tool.uv]` in `pyproject.toml`:

    ```toml
    [tool.uv]
    constraint-dependencies = ["urllib3>=2.5.0"]  # CVE-2025-50181
    ```

    Prefer `constraint-dependencies` over `override-dependencies` —
    constraints narrow the resolution, overrides ignore the parent's
    declared requirements and can produce a broken install.

4. **Assess reachability, then accept.** If no fix exists yet, decide
   whether the vulnerable code path is reachable from this service. A
   CVE in a docs-only or test-only dependency does not ship in the
   container — confirm with `just audit-prod`. To accept it, add the
   advisory ID to `audit_ignore` in the `justfile`:

    ```just
    # GHSA-xxxx: test-only (pytest plugin), not in the runtime image.
    # No fix upstream as of 2026-07-19. Re-check by 2026-10-19.
    audit_ignore := "--ignore-until-fixed GHSA-xxxx-xxxx-xxxx"
    ```

    Use `--ignore-until-fixed` rather than `--ignore`: it suppresses the
    advisory only while no fix is available, so the entry re-arms itself
    the moment upstream ships a patch. Every entry needs a dated comment
    with the reasoning and a re-check date.

### How this differs from Dependabot alerts

They overlap but are not redundant. Dependabot alerts are asynchronous
and live in the GitHub UI, where they are easy to leave unread;
`uv audit` answers the question in your terminal, right now, at the
moment you are deciding whether a lockfile is safe to ship. It also
covers forks and private mirrors where Dependabot alerts may be
disabled, and it audits the *locked* tree — the exact versions that
will be installed — rather than the declared ranges.

### What it does not cover

`uv audit` scans Python packages only. The **OS packages in the
container base image** (`python:3.14-slim-bookworm`) are outside its
scope, and Dependabot's `docker` ecosystem bumps the pinned tag and
digest without scanning the resulting image. Nothing in this repo closes
that gap by design — the template does not build or publish an image, so
image scanning belongs in whatever pipeline does. If you publish a
container, add an image scanner (Trivy, Grype, or your registry's built-in
scanning) to that pipeline and rebuild on base-image updates.

---

## Dependabot

The committed configuration lives in
[`.github/dependabot.yml`](../../.github/dependabot.yml). It opens
**weekly, grouped** pull requests for three ecosystems.

| Ecosystem | Watches | Commit prefix |
| :--- | :--- | :--- |
| `uv` | `pyproject.toml` + `uv.lock` | `chore(deps)` |
| `docker` | the Python base image and `uv` build stage pinned in the `Dockerfile` | `chore(deps)` |
| `github-actions` | actions pinned in `.github/workflows/*.yml` | `chore(deps)` |

### Grouping and cadence

Each ecosystem checks once a week. Minor and patch bumps are collapsed
into a **single grouped PR** per ecosystem (`python-minor-patch`,
`docker-minor-patch`, `actions-minor-patch`), so routine updates arrive
as one reviewable change instead of a flood. **Major** version bumps are
deliberately left **ungrouped** — they can carry breaking changes and
deserve their own PR and review. `open-pull-requests-limit` is `5` per ecosystem.

Commit messages use the `chore(deps): …` prefix so Dependabot's PRs
satisfy the project's [Conventional Commits](quality-checks.md) rule.

### Reviewing Dependabot PRs

1. CI runs the full `just check` suite against the bump — let it go
   green before merging.
2. For the grouped minor/patch PR, skim the changelog links Dependabot
   includes; merge once CI passes.
3. For a major bump, read the upstream release notes for breaking
   changes and test locally if the dependency is load-bearing
   (FastAPI, SQLModel, Pydantic, asyncpg).

### Known limitation

Dependabot's `uv` support reliably bumps runtime **`dependencies`** (all
of which carry version constraints in `pyproject.toml`). Packages
declared **only** under `[dependency-groups]` (dev, test, tooling, docs)
may not be updated automatically — an upstream limitation. Bump those
manually with `uv lock --upgrade` when needed.

---

## Secret scanning and push protection

Secret scanning is a **repository setting**, not a file in the repo —
there is nothing to commit. Enable it once per repository under
**Settings → Code security**:

- **Secret scanning** — GitHub scans the repository (and its history)
  for known credential formats (cloud keys, tokens, etc.) and alerts
  maintainers. **Free for public repositories**; private repositories
  require GitHub Advanced Security (GHAS).
- **Push protection** — blocks a `git push` that contains a detected
  secret before it ever lands on the remote. Enable it alongside secret
  scanning; it is the cheapest way to stop a leak.
- **Dependabot alerts** — surface known vulnerabilities (CVEs) in your
  dependency graph. Pair them with the version-update PRs above so a
  flagged CVE has an obvious remediation path.

These complement, rather than replace, the local
[`prek` quality gates](quality-checks.md) that run on commit and push.

---

## Layering enterprise scanners

The GitHub-native built-ins cover the common cases for free. An
enterprise fork with compliance or procurement requirements typically
layers a commercial stack on top, swapping in tools it already licenses:

| Tool | Adds |
| :--- | :--- |
| **Snyk** | SCA + license policy + IaC scanning, PR gating |
| **Black Duck** | Deep SBOM / license-compliance reporting |
| **GHAS CodeQL** | Semantic static analysis (SAST) of the app code |

These are intentionally **not** shipped in the template — bundling a
four-tool default is opinion-as-debt, and forks will substitute their
own licensed stack regardless (see the
[Roadmap backlog](../project/roadmap.md)). The Dependabot + secret
scanning floor documented here is the baseline every fork inherits.

---

## See Also

- [Security guide](security.md) — runtime hardening middleware
- [Quality Checks](quality-checks.md) — local `prek` gates and CI
- [`.github/dependabot.yml`](../../.github/dependabot.yml) — the config
