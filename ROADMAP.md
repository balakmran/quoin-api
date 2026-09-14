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
project builds and updates; `0.14.0` the day-two proof. The 2026-09-13
full audit that followed it found no High, but it found the edges the
suite never reaches: a JWT header PyJWT now rejects, a database that is
down, a forged `Host`, one log profile, one HTML attribute. `0.15` and
`0.16` close every one of those findings so the release candidate
starts with nothing open.

**`0.10.0` was the last feature release before `1.0`.** `0.15` and
`0.16` are fix releases: no backlog item is promoted, nobody is blocked
on one, and after `1.0` a feature is an ordinary minor release.

The backlog lists only demand-gated features. Operational concerns
(alerting, deploy runbooks, backups) belong in your infrastructure repo.
Features better solved elsewhere — rate limiting, secrets managers, PII
encryption, feature flags, audit tables, retention jobs — were dropped;
ETag concurrency became a
[guide](docs/guides/optimistic-concurrency.md). Observability follows
OpenTelemetry, with no vendor-specific tooling.

---

## v0.15.0 — Hostile-input hardening

Theme: the request path under inputs the suite never sent. Every item
is a confirmed bug or a hardening gap from the 2026-09-13 audit, each
lands with the regression test that would have caught it, and each
touches only `app/core` or the two built-in UIs. Adopters see two
default changes, both called out in the changelog: the default CSP no
longer allows `cdn.jsdelivr.net` scripts on every route, and the Host
check is a QuoinAPI middleware rather than Starlette's.

| Status | Item | Why now |
| :----- | :--- | :------ |
| 📋 | **Malformed JWT headers are a `401`** — `validate_token` catches `jwt.InvalidTokenError` (the parent of `DecodeError`) around `get_unverified_header`; tests send a non-string `kid` and an unsupported `crit` | PyJWT 2.10+ validates the header there; a caller with no credentials can log a traceback at ERROR on every request, and the authentication guide promises a `401` |
| 📋 | **`/ready` is a `503` whenever the check fails** — the probe catches `Exception`, not `SQLAlchemyError`, and logs at WARNING; a test points the engine at a closed port | asyncpg's connect failure is a plain `OSError` that SQLAlchemy never wraps, so a database outage is a `500` with a traceback per poll, and the deployment guide says `503` |
| 📋 | **JWKS stale-while-revalidate** — `get_signing_key` reads the key set without the lock, takes it only around the refresh, serves a cached key while a stale set refreshes, and fetches with a short dedicated timeout; a slow `MockTransport` test pins the latency bound | The refresh holds the lock for up to ~33 s of retries, longer than the 30 s request timeout, so a slow IdP turns every request on the worker into a `504`, cache hits included |
| 📋 | **Host rejection is problem-details** — a pure-ASGI host check sends the same RFC 9457 `400` as every other manufactured error; the CORS preflight rejection is documented as the one `text/plain` exception | A wrong `QUOIN_ALLOWED_HOSTS` is the likeliest production misconfiguration, and its symptom should look like every other error; the contract hook cannot see it because the fixture's `Host` is always allowed |
| 📋 | **CORS guard covers the origin list** — `configure_cors` also rejects `*` in `QUOIN_BACKEND_CORS_ORIGINS` with `allow_credentials` outside development | Starlette reflects the request's `Origin` for that combination, the one footgun the guard exists to catch and the one it skipped |
| 📋 | **Narrow the default CSP** — `script-src 'self'`; the fonts and icon hosts move to a scoped policy for `/`, and the docs policies keep `cdn.jsdelivr.net` | Only `/docs` and `/redoc` load from jsdelivr, and both already have their own policy; an XSS under the default policy could load any script it hosts |
| 📋 | **Landing page under its own CSP** — the `onclick` attribute moves into `home.js`; the `/docs` link is hidden when docs are disabled; `swagger_ui_oauth2_redirect_url` is `None`; a test renders the page and greps for inline handlers | The copy button is blocked today, the link is a `404` in production, and the redirect page carries an inline script nothing under `HTTPBearer` uses |
| 📋 | **Error bodies stop naming settings** — the three "OAuth not configured" `401`s and the host-less-URL `500` return generic text and log the specifics | Deployment errors belong in the log line, not in a body any caller can read |
| 📋 | **`504` closes the connection** — `TimeoutMiddleware` passes `close=True` like the `413` and `500` paths | A request that times out before its body was read leaves a reused keep-alive connection mid-body |
| 📋 | **Docs drift rows land with their fix** — deployment (`503`), error handling (the preflight exception), security (no inline handlers), authentication (`401` for a bad header) | The four rows in the audit each trace to a bug above, not to neglect; fixing one without the other reopens the drift |

---

## v0.16.0 — Operational hygiene

Theme: what an operator or a CI run sees, none of it on the request
path. Configuration, logging, build, and the gate itself. No adopter
action beyond a `copier update`.

| Status | Item | Why now |
| :----- | :--- | :------ |
| 📋 | **One predicate for the log pipeline** — renderer and logger factory are chosen by the same `ENV` test, or the structlog chain ends in `wrap_for_formatter` when the stdlib factory is in use; a test asserts the `test` profile emits one plain line | `test` is the one profile that gets the console renderer *and* the stdlib route, so every line in `just test` and the `Quality Checks` job is an ANSI string wrapped in JSON |
| 📋 | **Python 3.12 in CI** — a second matrix entry in `ci.yml` on the floor `requires-python` declares | The suite passes on 3.12.14 today, but no gate checks it; a floor nothing tests is a promise, not a guarantee |
| 📋 | **Read-only workflow tokens** — `permissions: contents: read` on `ci.yml`, `scaffold-smoke.yml`, and `copier-update.yml` | Only the audit and docs workflows declare permissions; the other three inherit the repository default |
| 📋 | **JWKS TTL is a setting** — `QUOIN_OAUTH_JWKS_TTL_SECONDS` beside the refresh backoff, documented in the configuration guide and `.env.example` | The one-hour TTL is a constructor default with no knob, unlike the backoff next to it |
| 📋 | **Bound the search term** — `UserListQuery.q` gets `max_length=255` to match the columns it searches | An unbounded term feeds two `ILIKE` predicates over a sequential scan |
| 📋 | **Migration guard flags unbounded data updates** — `op.execute` with an `UPDATE` and no `WHERE` is an advisory flag | `f76b93d38f43` rewrote every row to lowercase emails that were already lowercase; applied migrations are frozen, so the lesson goes into the guard |
| 📋 | **`.dockerignore`** — `.venv`, `.git`, `htmlcov`, `site`, and the caches | Nothing leaks into the image (`COPY` is scoped), but every build uploads hundreds of megabytes it never reads |
| 📋 | **Drop `future=True`** from `create_async_engine` | A 1.4-era flag SQLAlchemy 2.0 accepts and ignores |
| 📋 | **Pagination guide notes the two-statement page** — `total` and `items` are separate statements at READ COMMITTED and can disagree under concurrent writes | Acceptable for a template, surprising if undocumented |

---

## v1.0.0-rc.1 — Rehearsal

Cut a pre-release tag rather than a `0.17`. It costs nothing and buys
two things: the `v*` workflows run against a candidate that can still
be withdrawn, and the launch checklist below is executed once for real
before it counts. Cut it with `just bump major --rc` and `just tag` once
`0.16` ships; the Copier Update Check then verifies `v0.16.0 →
v1.0.0-rc.1` and `v0.15.0 → v1.0.0-rc.1` with the updated project's
gate.

Scope: **fixes only** — anything that fails the checklist becomes
`rc.2`. If the checklist passes clean, `1.0.0` is the same commit with a
version bump. The audit findings are deliberately *not* rc material:
`0.15` and `0.16` exist so the candidate starts with the Known
Correctness Issues table empty rather than emptying it under the rc.

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
    just verify-template-update v0.16.0 v1.0.0 --check
    ```

    Both baselines mirror the workflow: the preceding tag, then the
    newest final release before it. With `rc.2` cut, use it instead of
    `rc.1`.

- [ ] Confirm the generated project's `.copier-answers.yml` records the
    candidate tag after updating from `v0.16.0`.

### Behaviour and quality

- [ ] Run `just check` from a clean checkout and confirm 100% coverage.
- [ ] Run `just docb`; review the built site for broken links, navigation,
    API-reference rendering, and the current configuration tables.
- [ ] Start the local stack with `just dev`; verify `/health`, `/ready`,
    `/docs`, one authenticated request, and one denied request. Stop
    the database and confirm `/ready` returns `503`, not `500`.
- [ ] Open the landing page with the browser console visible and confirm
    no CSP violation is reported; the copy button must work.
- [ ] Verify production configuration fails closed when the OAuth issuer,
    audience, or HTTPS JWKS URI is absent or invalid, or when
    `QUOIN_ALLOWED_HOSTS` is left at its development default.
- [ ] Confirm a bare `ENV=production` (no `QUOIN_` prefix) is ignored
    rather than half-applying the production profile.
- [ ] Confirm `QUOIN_LOG_LEVEL=WARNING` visibly suppresses the access log
    in a `just dev` session, and that `just test` output is plain
    single-line logs rather than JSON-wrapped console lines.
- [ ] Confirm the regression guards are present and green: the
    problem-details contract hook and the commit-before-send test
    (`0.11.0`); the substitution-headroom test and the null-PATCH test
    (`0.13.0`); the hook's body tests, the tool-pin test, and the
    Scaffold Smoke Test's day-two step (`0.14.0`); the malformed-header,
    database-down readiness, forged-`Host`, slow-JWKS, and landing-page
    CSP tests (`0.15.0`); and the log-profile test and the Python 3.12
    job (`0.16.0`).
- [ ] Review the public OpenAPI document and RFC 9457 error examples for
    intentional endpoint, response, and security-scheme changes only.

### Security and distribution

- [ ] Confirm GitHub Actions remain SHA-pinned with read-only default
    permissions, `uv` is pinned in the workflows, the Docker base image
    is digest-pinned, and Dependabot covers Python, Docker, and GitHub
    Actions dependencies.
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
| 📋 `0.15` | A JWT whose `kid` is not a string, or whose `crit` names an unsupported extension, is a `500`: `validate_token` catches `DecodeError` but PyJWT 2.10+ raises its parent `InvalidTokenError` | 2026-09-13 audit (B1) |
| 📋 `0.15` | `/ready` is a `500` when the database is unreachable: the probe catches `SQLAlchemyError`, and asyncpg's connect failure is a plain `OSError` | 2026-09-13 audit (B2) |
| 📋 `0.15` | The landing page's copy button is blocked by the default CSP; the `onclick` attribute is an inline handler | 2026-09-13 audit (B3) |
| 📋 `0.16` | In the `test` profile every log line is a console-rendered ANSI string wrapped in JSON | 2026-09-13 audit (B4) |
| 📋 `0.15` | The Host-check `400` and the CORS preflight `400` are `text/plain`, not `application/problem+json` | 2026-09-13 audit (B5) |

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
currently blocks a known user on any of them, and none of the three
2026-09 analyses proposed anything for this table — every finding was
a defect, a hardening gap, or a proof gap, which is what a freeze is
supposed to produce.

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
- **Hostile-input tests are the next proof.** `0.15` showed that 100%
  branch coverage measured which lines ran, not which input classes
  reached them. A property-based or fault-injection layer over the
  request path (malformed tokens, dropped dependencies, forged
  headers) is the proof most worth adding once the surface is frozen.
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
