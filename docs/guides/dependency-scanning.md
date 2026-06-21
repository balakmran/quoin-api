# Dependency Scanning

QuoinAPI leans on GitHub's free, built-in supply-chain tooling to stay
patched with zero CI overhead: **Dependabot** for automated version
updates and **secret scanning** for leaked credentials. This guide
covers what ships in the repo, what you enable in repository settings,
and how an enterprise fork layers commercial scanners on top.

---

## Dependabot

The committed configuration lives in
[`.github/dependabot.yml`](../../.github/dependabot.yml). It opens
**weekly, grouped** pull requests for two ecosystems.

| Ecosystem | Watches | Commit prefix |
| :--- | :--- | :--- |
| `uv` | `pyproject.toml` + `uv.lock` | `chore(deps)` |
| `github-actions` | actions pinned in `.github/workflows/*.yml` | `chore(deps)` |

### Grouping and cadence

Each ecosystem checks once a week. Minor and patch bumps are collapsed
into a **single grouped PR** per ecosystem (`python-minor-patch`,
`actions-minor-patch`), so routine updates arrive as one reviewable
change instead of a flood. **Major** version bumps are deliberately left
**ungrouped** — they can carry breaking changes and deserve their own PR
and review. `open-pull-requests-limit` is `5` per ecosystem.

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
