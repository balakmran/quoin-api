# Roadmap

This document outlines the planned evolution of QuoinAPI. It reflects the
current thinking of the maintainers and is subject to change based on community
feedback and shifting priorities.

!!! note
    This is a living document. Completed items are moved to
    [CHANGELOG.md](changelog.md).

## Status Legend

| Symbol | Meaning |
| :----- | :------ |
| ✅ | Completed (unreleased) |
| 🚧 | In Progress |
| 📋 | Planned |
| 💡 | Under Consideration |
| ❌ | Deferred / Won't Do |

## Where things stand

The template contract is locked. `0.9.0` shipped pagination, soft
delete, and deprecation; `0.10.0` the stability policy; `0.11.0` to
`0.13.0` the correctness fixes and the CI that proves a generated
project builds and updates. `0.14` proves day two: scaffolding and
migrating a module inside a renamed project, and updating from two
earlier releases.

**`0.10.0` was the last feature release before `1.0`.** What remains is
the `1.0.0-rc.1` rehearsal. No backlog item is promoted: nobody is
blocked on one, and after `1.0` a feature is an ordinary minor release.

The backlog lists only demand-gated features. Operational concerns
(alerting, deploy runbooks, backups) belong in your infrastructure repo.
Features better solved elsewhere — rate limiting, secrets managers, PII
encryption, feature flags, audit tables, retention jobs — were dropped;
ETag concurrency became a
[guide](docs/guides/optimistic-concurrency.md). Observability follows
OpenTelemetry, with no vendor-specific tooling.

---

## v0.14.0 — Day-two proof

Theme: `0.12` proved day one — generate, gate. `0.14` proves the
workflows an adopter runs on day two, and wires the promises the
[After 1.0](#after-10) section makes before they are made. No
application behaviour changes. The template fixes the rehearsal found
are update-safe. The `httpx` → `httpx2` swap already in this release
needs adopters to change `httpx` imports in their own code.

| Status | Item | Why now |
| :----- | :--- | :------ |
| ✅ | **Day-two smoke job** — the Scaffold Smoke Test runs `just new widget`, adds a one-table model, runs `just migrate-up` and `just migrate-gen` (which must emit a `create_table`), then `just check` again in the generated project | `test_scaffold_module.py` proves the scaffold in *this* repository. Nothing proved it in a generated one, where the base exception, the settings prefix, and the problem URN all differ |
| ✅ | **Template bugs the day-two rehearsal found** — `alembic/script.py.mako` now punctuates the revision docstring (D415); the test session's schema reset drops tables through `app.db.base`; `just new` writes a `test_service.py` covering every stub layer | Its first local run failed three times. An adopter's first `just migrate-gen "add widget"` failed lint; a table whose model only `app/db/base.py` imports broke the next test run with "relation already exists"; and the scaffold's stubs fell below `fail_under`, contradicting "pass `just check` as-is" |
| ✅ | **Update check from two baselines** — the Copier Update Check runs a matrix: the preceding tag, then the newest *final* release before it (candidates are never the second baseline) | "After 1.0" promises this for every minor; wired while `0.x` is cheap to get wrong |
| ✅ | **Supply-chain pins** — every workflow installs uv 0.11.26, the Dockerfile's pin; the Python base image is digest-pinned; `tests/test_tool_pins.py` fails if the two uv pins drift; the audit workflow notes `uv audit`'s preview status | CI installed `uv` `latest` while the image was reproducible. Dependabot bumps the Dockerfile's uv but not `setup-uv`'s `version:`, which is why the pins need a test |
| ✅ | **Contract hook validates the body** — every 4xx/5xx body parses as `ProblemDetail`, with `status` and `instance` matching the response and request path; `tests/test_problem_details_hook.py` proves each check fails | The hook checked only the content type and `X-Request-ID`, so a malformed body would have passed it |
---

## v1.0.0-rc.1 — Rehearsal

Cut a pre-release tag rather than a `0.15`. It costs nothing and buys
two things: the `v*` workflows run against a candidate that can still
be withdrawn, and the launch checklist below is executed once for real
before it counts. Cut it with `just bump major --rc` and `just tag` once
`0.14` ships; the Copier Update Check then verifies `v0.14.0 →
v1.0.0-rc.1` and `v0.13.0 → v1.0.0-rc.1` with the updated project's
gate.

Scope: **fixes only** — anything that fails the checklist becomes
`rc.2`. If the checklist passes clean, `1.0.0` is the same commit with a
version bump.

---

## v1.0 Launch Checklist

This is a one-time repository release gate, not a deployment runbook for
generated projects. Check every item on the release candidate commit before
deciding whether to release `v1.0.0`.

### Template contract

- [ ] Review the [API Stability & SemVer Policy](docs/guides/api-stability.md)
    against every change since `v0.9.0`; classify any required consumer
    action in `CHANGELOG.md`.
- [ ] Confirm `copier.yml` prompts, `scripts/copier_setup.py.jinja`, and
    generated metadata still produce a de-branded project.
- [ ] Generate a clean project from the release candidate **with your
    own long answers**, not the defaults, and run its full gate. Pass
    `--vcs-ref=HEAD`: a local git template without it resolves to the
    latest *tag*, so the smoke test silently exercises the previous
    release instead of the candidate. A dirty local template is copied
    as its working tree, untracked files included, so the tree must be
    clean first. The scaffold smoke job runs the same thing, plus the
    day-two rehearsal, on every pull request; this is a confirmation
    with non-default answers, not a first run.

    ```bash
    git status --porcelain   # must be empty
    uvx copier copy --trust --vcs-ref=HEAD . ../quoinapi-v1-smoke
    cd ../quoinapi-v1-smoke
    uv sync --all-groups
    just check
    ```

- [ ] Confirm the generated project contains no QuoinAPI roadmap, release
    notes, contributor policy, or maintainer identity beyond the answers
    supplied to Copier — grep the tree for `Quoin` and for the
    maintainer's name and handle, not only for leaked files.
- [ ] Verify the `copier update` path from the previous release *before*
    pushing the tag — the Copier Update Check workflow only runs on `v*`
    tags, so it reports after the release decision, not before it. Create
    the candidate tag locally, verify, then let `just tag` push it (it
    skips a tag that already exists). Both arguments must be real tags:
    the check compares the tag string against the `_commit` recorded in
    `.copier-answers.yml`, so `HEAD` or a branch name fails.

    ```bash
    git tag v1.0.0
    just verify-template-update v1.0.0-rc.1 v1.0.0 --check
    just verify-template-update v0.14.0 v1.0.0 --check
    ```

    Both baselines mirror the workflow: the preceding tag, then the
    newest final release before it. With `rc.2` cut, use it instead of
    `rc.1`.

- [ ] Confirm the generated project's `.copier-answers.yml` records the
    candidate tag after updating from `v0.14.0`.

### Behaviour and quality

- [ ] Run `just check` from a clean checkout and confirm 100% coverage.
- [ ] Run `just docb`; review the built site for broken links, navigation,
    API-reference rendering, and the current configuration tables.
- [ ] Start the local stack with `just dev`; verify `/health`, `/ready`,
    `/docs`, one authenticated request, and one denied request.
- [ ] Verify production configuration fails closed when the OAuth issuer,
    audience, or HTTPS JWKS URI is absent or invalid, or when
    `QUOIN_ALLOWED_HOSTS` is left at its development default.
- [ ] Confirm a bare `ENV=production` (no `QUOIN_` prefix) is ignored
    rather than half-applying the production profile.
- [ ] Confirm `QUOIN_LOG_LEVEL=WARNING` visibly suppresses the access log
    in a `just dev` session.
- [ ] Confirm the regression guards are present and green: the
    problem-details contract hook and the commit-before-send test
    (`0.11.0`); the substitution-headroom test and the null-PATCH test
    (`0.13.0`); and the hook's body tests, the tool-pin test, and the
    Scaffold Smoke Test's day-two step (`0.14.0`).
- [ ] Review the public OpenAPI document and RFC 9457 error examples for
    intentional endpoint, response, and security-scheme changes only.

### Security and distribution

- [ ] Confirm GitHub Actions remain SHA-pinned, `uv` is pinned in the
    workflows, the Docker base image is digest-pinned, and Dependabot
    covers Python, Docker, and GitHub Actions dependencies.
- [ ] Run the CVE scan — it is deliberately not part of `just check`, so
    nothing else in the release path runs it. Every advisory left in
    `audit_ignore` needs a current dated justification in the
    [Dependency Scanning](docs/guides/dependency-scanning.md) guide.

    ```bash
    just audit
    just audit-prod
    ```

- [ ] Confirm the Docker image builds, starts as the non-root `quoin` user,
    passes its health check, and disables docs and OpenAPI in production.
- [ ] Review `.env.example`, the Configuration guide, and the Security and
    Deployment guides together; every supported `QUOIN_*` setting must be
    documented without committing a credential.
- [ ] Confirm the security policy names `main` and the latest tag as the
    supported template versions and provides a private reporting route.

### Release decision

- [ ] Triage every open issue and pull request as release-blocking,
    explicitly deferred, or post-`v1.0.0` work.
- [ ] Confirm the **Known Correctness Issues** table below is empty.
- [ ] Record the final scope and all intentional deferrals in the
    `CHANGELOG.md` release section.
- [ ] Obtain maintainer approval that the template contract is stable enough
    for the `1.x` major-version promise.
- [ ] Follow the [Release Workflow](docs/guides/release-workflow.md) to bump,
    merge, tag, and publish the release.

Once complete, move this checklist to the release notes and replace the
milestone above with the next demand-backed milestone.

---

## Known Correctness Issues

A confirmed bug fits neither the launch checklist above (a one-time
release gate) nor the backlog below (demand-gated features) — without
a lane of its own it tends to get triaged as one or the other and
lost. This table is that lane: add a row when a review or an incident
confirms a correctness bug that isn't fixed in the same change, and
remove the row once the fix ships (credit it in `CHANGELOG.md`
instead). Empty is the steady state, not a gap in review.

| Status | Issue | Found |
| :----- | :---- | :---- |

---

## Backlog

Documented now so they aren't lost. Promoted into a milestone only when
real demand surfaces — the bar is "a concrete user is blocked on this",
not "it would be nice to have".

| Status | Feature | Why deferred |
| :----- | :------ | :----------- |
| 💡 | **Idempotency keys (DB-backed store)** | Significant scope (replay logic, TTL semantics, key collision handling). Retry-safe idempotent verbs (`PUT`, `DELETE`) + client-supplied request IDs cover most cases. Build when actually needed. |
| 💡 | **OTel Metrics + `/metrics` endpoint** | RED metrics can be derived from the existing OTLP trace stream in the OTel Collector. Direct Prometheus scrape is duplicate plumbing unless a deployer specifically needs it. |
| 💡 | **Schemathesis contract testing in CI** | Pays off when external consumers lock against the schema. Adds CI minutes and flaky-test risk before that point. |
| 💡 | **Cursor-based pagination** | Premature unless a module hits million-row tables. Offset pagination is sufficient through `1.0`. |
| 💡 | **Background task worker** | Persistent async task queue for emails, webhooks, and long-running work; evaluate Arq (asyncio-native) vs Dramatiq (broker-agnostic). |
| 💡 | **Redis cache layer** | Shared Redis client and caching helpers; replaces DB-backed idempotency store at scale. |
| 💡 | **Multi-tenancy pattern** | Tenant-scoped query pattern with an example module. |
| 💡 | **Organizations + memberships + scopes** | Richer authorization model beyond `require_roles`. |
| 💡 | **API keys** | Hashed at rest, scoped, rotatable; for service-to-service callers. |
| 💡 | **Read-replica routing** | Repository-layer routing of reads to replicas. Pool sizing itself is already tunable via `QUOIN_DB_POOL_*`. |

Of these, the most plausible promotions in rough order of likelihood
are: background worker, API keys, Redis cache, multi-tenancy. Nothing
currently blocks a known user on any of them, and neither the
2026-09-08 analysis nor its 2026-09-13 refresh proposed anything for
this table — every finding was a defect or a proof gap, which is what
a freeze is supposed to produce.

---

## After 1.0

Intent, not commitments — this section exists so that work deferred
*until* `1.0` isn't confused with work deferred *pending demand*.

- **Boring is the brand.** Strict semver, quarterly minors, security
  patches immediately. The cadence work is already dated: Python 3.12
  dropped at its end of life (October 2028), Postgres 19 in Compose and CI once it
  is generally available, and OpenTelemetry semantic-convention
  renames followed as they stabilise rather than pinned forever.
- **The update path is the differentiator.** The verify script, the
  two smoke jobs, the two-tag update check, and `staying-current.md`
  are the assets worth investing in; a template nobody can upgrade is
  a snapshot. The next guide worth writing is a worked outbound
  integration on `ResilientHTTPClient`, which today has no in-tree
  consumer other than the JWKS fetch.
- **The agentic workflow is a product feature.** Twelve skills, two
  subagents, and six hooks are more than any comparable template
  ships. Package them as a Claude Code plugin in `1.1`, once the
  template surface is frozen, so they can version independently of
  the code.
- **Backlog promotions stay demand-gated.** Most plausible, in order:
  background worker, API keys, Redis cache, multi-tenancy. Each lands
  as an ordinary minor, behind a flag or as an example module.
- **Never extract a `quoin-core` package.** The
  [API stability guide](docs/guides/api-stability.md) states this as a
  non-goal; a template you can read end to end is the point.

---

## How to Contribute

1. Check if an issue already exists for the feature you want to work on.
2. Open a **Discussion** to align on approach before writing code.
3. Reference this roadmap item in your PR description.
4. Follow the [Contributing Guide](contributing.md) and ensure
   `just check` passes before requesting review.
