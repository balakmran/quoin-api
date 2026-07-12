# API Stability & SemVer Policy

QuoinAPI is a Copier **template**: you `copier copy` it once and own
every line of the generated project, including the `user` module and
its `/api/v1/users` routes. Those routes are a worked example of a
complete CRUD module, not a contract this repository promises to keep
stable — rename, reshape, or delete them the moment you generate a
project. If you want to run your own stability policy for *your*
endpoints, the mechanism is in the
[Deprecating Endpoints guide](deprecating-endpoints.md); the [API
Conventions reference](../api/conventions.md) covers the `/api/v{n}`
URL-versioning scheme.

This document is about a different surface: the **template itself** —
the code, settings, and tooling a generated project depends on, and
that `copier update` must reconcile on every pull. That is the thing
QuoinAPI can and does make a versioning promise about.

## What SemVer means here

Git tags (`vX.Y.Z`) version the template repository, not a published
package — QuoinAPI is never `pip install`-ed (see
[Non-goal: no importable core package](#non-goal-no-importable-core-package)
below).

- **MAJOR** — a breaking change to the template surface (below). A
  generated project must take deliberate action when pulling it in via
  `copier update`.
- **MINOR** — additive: a new opt-in setting, middleware, skill, or
  scaffold capability that doesn't change existing behaviour.
- **PATCH** — bug fixes, dependency bumps, and doc corrections with no
  behavioural change.

**Pre-1.0 caveat:** QuoinAPI is currently `0.x`. Per standard SemVer, a
`0.x` MINOR bump may still contain breaking changes to the template
surface — the CHANGELOG calls these out, but the strict MAJOR-only
rule below takes full effect starting at `1.0.0`.

## The template surface this policy covers

- **`app/core/*` public contracts** used by every module: the
  `get_session` dependency, `require_roles`, the `QuoinError` exception
  hierarchy (`NotFoundError`, `ConflictError`, `BadRequestError`,
  `ForbiddenError`, `InternalServerError`, etc. in
  `app/core/exceptions.py`), the middleware classes and their default
  ordering, and the `deprecated()` / pagination helpers.
- **Settings** — every `QUOIN_*` environment variable's name, type,
  and default in `.env.example` and `app/core/config.py`.
- **CLI** — `justfile` recipe names and flags (`just dev`,
  `just check`, `just new`, `just migrate-gen`, …).
- **Scaffold output** — what `just new <module>` generates and where.
- **`copier.yml` variables** — the prompts a project is generated
  from (`project_name`, `env_prefix`, `google_analytics_id`, …).
- **The migration contract** — that Alembic is the schema source of
  truth and the test schema is built from the migration chain — not
  the content of any individual migration script.

**Not covered** — yours the moment you generate:

- The `user` module's routes, schemas, and response shapes.
- Anything under your own `app/modules/<yours>/`.
- Business logic and data.

## Breaking vs. non-breaking

| Change | Classification |
| :--- | :--- |
| Rename or remove a `QUOIN_*` setting | Breaking |
| Add a `QUOIN_*` setting whose default preserves current behaviour | Non-breaking |
| Change a middleware's default ordering or behaviour | Breaking |
| Add a new middleware, off by default | Non-breaking |
| Change the signature of `require_roles`, `get_session`, or the type of a raised domain exception | Breaking |
| Add a new domain exception type | Non-breaking |
| Change what `just new` scaffolds (new required files or deps) | Breaking |
| Fix a bug in generated scaffold output | Non-breaking (patch) |
| Change what a generated project must run to build its test/migration schema | Breaking |

## `copier update` compatibility

- Every release states in `CHANGELOG.md` whether a change is
  **update-safe** (merges cleanly via `copier update`) or needs
  **manual reconciliation** (a template-owned file you've likely since
  edited).
- Template-owned files (`app/core/`, tooling, CI, skills) live apart
  from user-owned files (`app/modules/`, your business logic) — the
  [architecture overview](../architecture/overview.md) documents this
  layering. Keeping the two separate is what lets `copier update`
  diffs stay small.
- This is currently a manually-maintained guarantee, not a CI-enforced
  one: there is no automated job yet that generates a project from the
  previous tag, runs `copier update` to `HEAD`, and asserts
  `just check` still passes. Treat the guarantees above as best-effort
  until that lands.

## Deprecation & removal (template surface)

Same three-step shape as the [endpoint deprecation
policy](deprecating-endpoints.md#a-suggested-policy), applied to
settings, CLI recipes, and scaffold behaviour instead of routes:

1. **Announce** — call it out in `CHANGELOG.md` and the relevant guide
   (e.g. the settings table in
   [Configuration](configuration.md)); keep it working for at least
   one MINOR release (one full cycle pre-1.0).
2. **Overlap** — old and new behaviour coexist; a deprecated setting
   may log a startup warning instead of failing.
3. **Remove** — only in a MAJOR release, called out in the
   CHANGELOG's `Removed` section.

## Supported versions

Same table as [`SECURITY.md`](../project/security-policy.md#supported-versions):
`main` and the latest tag are supported; older tags aren't backported
to. Taking a fix means pulling it in via `copier update` or
cherry-picking the commit.

## Non-goal: no importable core package

QuoinAPI will not be published as an installable package (no
`import quoin_core`, no `pip install quoin-api`). The template's
entire value is that the generated project is 100% the team's code —
auditable and modifiable without asking permission. Publishing
`app/core` as a dependency would flip that: every consumer would then
need QuoinAPI to maintain backwards compatibility forever, which is a
different (and heavier) promise than this document makes. If a
generated project ever needs to move off SQLModel, the repository
pattern already isolates it to `models.py` plus the repositories —
that migration stays contained regardless of this policy.

## See also

- [Deprecating Endpoints](deprecating-endpoints.md) — the
  RFC 8594 mechanism for your own endpoint-level deprecations.
- [Release Workflow](release-workflow.md) — how a version bump and
  tag actually ship.
- [Security Policy](../project/security-policy.md) — supported
  versions and vulnerability reporting.
- [Configuration](configuration.md) — the current `QUOIN_*` settings
  table.
- [Architecture Overview](../architecture/overview.md) — the layer
  separation between `app/core/` and `app/modules/`.
