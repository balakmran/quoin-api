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

The template contract is locked. The pagination envelope, soft delete,
and the deprecation mechanism shipped in `0.9.0`; the stability and
semver policy followed in `0.10.0`; `0.11.0` closed the request-path
correctness work; and `0.12.0` turned the repository's two remaining
hand-run promises into CI. A generated project is now gated on every
pull request, and the `copier update` path is gated on every tag.

**`0.10.0` was the last feature release before `1.0`**, and that has not
changed. What has changed is what the proof found. The 2026-09-08 code
analysis was the first one run against a green suite *and* against
generated projects rather than as a static read, and it turned up two
things that must precede a `1.0` whose entire promise is "the project
you generate works":

- A project generated with any name longer than the default fails its
  own `just lint` on day one. Substituting a longer settings prefix
  pushes prose lines in docstrings and comments past the 80-column
  limit, and the formatter `0.12.0` added cannot reflow prose. The
  smoke job is green only because the default answers happen to fit.
- The release tooling cannot cut the `1.0.0-rc.1` this document calls
  for: `just tag` accepts only `X.Y.Z`, and the update-check workflow
  mis-orders pre-release tags once one exists.

Neither is a feature, so neither breaks the freeze. They get two more
`0.x` releases — `0.13` for the fixes and their regression guards,
`0.14` for proof that an adopter's *day-two* workflows survive a
renamed project — and then the rehearsal proceeds as planned. Still
**no backlog item is promoted**: the backlog's bar ("a concrete user is
blocked") has not been met by anyone yet, and under semver a feature
added after `1.0` is an ordinary minor bump, so nothing gets cheaper by
racing the freeze.

The backlog below is deliberately narrow: it lists only demand-gated
*features* — application code we would ship behind a feature flag or as
an example module when a concrete user is blocked. Operational and
deployer-specific concerns (alert thresholds, deploy/rollback workflows,
backup runbooks) and rot-prone checklists were dropped outright rather
than parked — they belong in your infrastructure repo, not a backend
code template. All observability follows OpenTelemetry and CNCF
standards — no vendor-specific tooling.

Features are dropped rather than parked on the same test: shipping them
would be wrong regardless of demand, because they are better solved at
the edge, depend on facts only the deployer knows, or would compete
badly with a mature product category. Rate limiting, a secrets-manager
adapter, PII encryption, feature flags, an audit table, and retention
jobs all failed it. ETag concurrency left the backlog too, but as a
[guide](docs/guides/optimistic-concurrency.md) rather than a deletion —
the pattern is worth documenting even though the code isn't worth
shipping.

---

## v0.13.0 — Hardening

Theme: fixes and the regression guards that would have caught them.
No new features, no new settings beyond one additive CORS list.
Update-safe throughout, with one **manual reconciliation** note where
the fixed pattern also lives in adopters' own modules.

| Status | Item | Why now |
| :----- | :--- | :------ |
| ✅ | **Generated projects lint clean for any answers** — give prose lines headroom (`[tool.ruff.lint.pycodestyle] max-line-length` above the formatter's 80, or shorten the lines that carry a substitutable token), add a long-name answer set to the smoke matrix, and add a template-side test that applies the substitution map with worst-case answers and lints the result, so `just check` *here* fails before an adopter does | Probe on `main`: "Acme Ledger" (prefix six characters longer than `QUOIN`) → one E501 and the gate stops at lint; "Northwind Traders Platform" → 34 E501 across 15 files. With that one line wrapped, the renamed project passes everything else: types, `alembic check`, 315 tests at 100% coverage. The mechanism works; only the headroom is missing |
| 📋 | **Explicit `null` in a PATCH → 422, not 500** — `UserUpdate` accepts `null` for `email` and `is_active`, both `NOT NULL`, so the flush fails and the client gets a 500. Reject `None` for non-nullable columns, add the regression test, and document the pattern in the module guide, whose `ProductUpdate` example teaches the same shape. **Manual reconciliation**: any update schema copied from it | Probe: `{"email": null}` → 500, `{"is_active": null}` → 500, `{"full_name": null}` → 200. Every generated module inherits the shape |
| 📋 | **Pre-releases in the release tooling** — `just bump rc` and `just tag` accept `X.Y.Z-rc.N` and pass `--prerelease`; the update-check workflow sorts with `versionsort.suffix=-rc` so a patch after `1.0.0` compares against `1.0.0`, not `rc.2` | Blocks the rehearsal below. The mis-sort was reproduced: with `v1.0.0-rc.2` present, `git tag --sort=-v:refname` puts it above `v1.0.0` |
| 📋 | **Finish de-branding** — `QuoinRequestValidationError` and a stray "Quoin" docstring survive `copier copy`; rename them at generation and grep the generated tree for `Quoin` and for the maintainer's identity, using non-default author answers | The smoke job checks leaked *files*, not identifiers, and with `--defaults` it cannot see an identity leak at all |
| 📋 | **CORS exposes the headers the API relies on** — `QUOIN_BACKEND_CORS_EXPOSE_HEADERS`, defaulting to `X-Request-ID`, `Deprecation`, `Sunset`, and `Link`; derive the allow-list entry from `QUOIN_REQUEST_ID_HEADER` instead of hard-coding it. Additive | A browser caller cannot read `X-Request-ID` today — `expose_headers` is never set — so a front end cannot quote it in a bug report, and the deprecation headers are invisible to the clients they exist for |
| 📋 | **Log-level hygiene** — 5xx domain errors at ERROR with a traceback, 404/405 at INFO, and the caller's `sub` bound to the log context for the rest of the request. Additive | A deliberate 503 from `/ready` and a scanner's 404 share the WARNING channel, and no log line records who the caller was |
| 📋 | **Small robustness fixes** — a JWKS body that is JSON but not an object → 401 rather than a 500 that repeats for the backoff window; warn on the default database password in production; emit `deployment.environment.name`, the key the current semantic conventions replaced `deployment.environment` with | Each is a few lines and a test |
| 📋 | **Docs sweep** — the release-workflow guide still says the update check runs no `just check`; its pre-release section bypasses `just tag`; `CLAUDE.md` lists three of the six hooks; the testing guide never mentions the problem-details contract hook | Found by the analysis; a `quoin-docs-audit` pass |

---

## v0.14.0 — Day-two proof

Theme: `0.12` proved day one — generate, gate. `0.14` proves the
workflows an adopter runs on day two, and wires the promises the
[After 1.0](#after-10) section makes before they are made. Additive
only; no application behaviour changes.

| Status | Item | Why now |
| :----- | :--- | :------ |
| 📋 | **Day-two smoke job** — inside the generated project: `just new widget`, `just migrate-gen`, then `just check` | `test_scaffold_module.py` proves the scaffold in *this* repository. Nothing proves it in a generated one, where the base exception, the settings prefix, and the problem URN all differ |
| 📋 | **Update check from the previous two tags** — matrix the Copier Update Check over `N-1 → N` and `N-2 → N` | "After 1.0" promises this for every minor; wire it while `0.x` is cheap to get wrong |
| 📋 | **Supply-chain pins** — pin `uv` in the four workflows to the version the Dockerfile already pins by digest; digest-pin the Python base image (Dependabot bumps digests); record `uv audit`'s preview status in the audit workflow | CI installs `uv` `latest` while the image is reproducible; a `uv` release can rename the preview audit command and turn a Monday red for a reason that is not a CVE |
| 📋 | **Contract hook validates the body** — parse every 4xx/5xx body as `ProblemDetail` and assert `instance` is the request path | The hook checks the content type and `X-Request-ID`; a malformed body would pass it today |
| 📋 | **Python 3.15 in the CI matrix** — when it ships (October 2026) | Annual cadence; the matrix has covered three versions since `0.8` |

---

## v1.0.0-rc.1 — Rehearsal

Cut a pre-release tag rather than a `0.15`. It costs nothing and buys
two things: the `v*` workflows run against a candidate that can still
be withdrawn, and the launch checklist below is executed once for real
before it counts. Cut it with `just bump rc` and `just tag` once `0.13`
lands; the Copier Update Check then verifies `v0.14.0 → v1.0.0-rc.1`
with the updated project's gate.

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
    release instead of the candidate. `HEAD` includes only committed
    changes, so commit or stash first. The scaffold smoke job runs the
    same thing on every pull request; this is a confirmation with
    non-default answers, not a first run.

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
    just verify-template-update v0.14.0 v1.0.0 --check
    ```

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
    (`0.11.0`), and the substitution-headroom test and the null-PATCH
    test (`0.13.0`).
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
| 📋 | `PATCH /api/v1/users/{id}` with an explicit `null` for `email` or `is_active` returns 500: the `NOT NULL` violation surfaces as an unhandled `IntegrityError` instead of a 422. Fix in `0.13.0` | 2026-09-08 analysis, HTTP probe |
| 📋 | The Copier Update Check picks the previous tag with `git tag --sort=-v:refname`, which orders `v1.0.0-rc.2` above `v1.0.0`; the first patch after `1.0.0` would verify its update path from the wrong tag. Latent until the first pre-release tag exists. Fix in `0.13.0` | 2026-09-08 analysis, git probe |

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
currently blocks a known user on any of them, and the 2026-09-08
analysis proposed nothing for this table — every finding was a defect
or a proof gap, which is what a freeze is supposed to produce.

---

## After 1.0

Intent, not commitments — this section exists so that work deferred
*until* `1.0` isn't confused with work deferred *pending demand*.

- **Boring is the brand.** Strict semver, quarterly minors, security
  patches immediately. The cadence work is already dated: Python 3.15
  into the matrix when it ships (October 2026), Python 3.12 dropped at
  its end of life (October 2028), Postgres 19 in Compose and CI once it
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
