# Changelog

## [Unreleased]

### Fixed

- **Template**: a project generated with a name longer than the default
  no longer fails its own `just lint` on day one. Copier substitutes the
  settings prefix into docstrings and comments, and `ruff format`
  cannot reflow prose. As a result, "Acme Ledger" produced one E501 and
  "Northwind Traders Platform" produced 34.
  `[tool.ruff.lint.pycodestyle] max-line-length` is now 100, while the
  formatter's `line-length` stays at 80. Code is unchanged, and prose
  now has room for a settings prefix of up to 30 characters.
  Contributors still write to 80.

### Added

- **Tests**: `tests/test_template_substitution.py` runs the real
  post-generation substitution over a copy of the tree with worst-case
  answers and lints the result. `just check` in this repository now
  fails before a generated project would. The test skips in generated
  projects, which do not ship the setup script.
- **CI**: the **Scaffold Smoke Test** now also generates with a long
  project name, author, and GitHub handle, alongside `--defaults`. The
  defaults are the one answer set short enough to hide this class of
  bug.

## [0.12.0] - 2026-09-09

Proof, not behaviour: every item here is a CI job, a script, or a
document, so `copier update` from `0.11.0` is expected to be
conflict-free end to end. The theme is closing the gap between what
this repository promises and what it verifies -- two promises were
checked only by a human running a command from memory, and one was not
written down at all.

### Added

- **CI**: a **Scaffold Smoke Test** workflow generates a project from
  the branch under review (`copier copy --vcs-ref=HEAD`) and runs that
  project's own `just check` against a Postgres service, then fails if
  the gate modified the generated tree. Until now nothing in CI
  exercised generated output — `v0.11.0` shipped a template whose
  generated `metadata.py` failed its own `just lint`, and only a manual
  run caught it. The job also asserts `copier.yml`,
  `scripts/copier_setup.py`, `ROADMAP.md`, and the two
  template-maintenance workflows below do not leak into the generated
  project.
- **Docs**: a new [Staying Current](../guides/staying-current.md)
  guide covers the adopter's side of the stability policy — what
  `copier update` actually merges, how to read a **manual
  reconciliation** note, resolving `.rej` conflicts, and why keeping
  `app/core/` unedited is what keeps future updates cheap. `0.11.0` was
  the first release to demand real reconciliation work; nothing until
  now documented how to do it.
- **CI**: the **Copier Update Check** workflow now runs the *updated*
  project's own `just check` (via `just verify-template-update ...
  --check`), against a Postgres service. It previously proved only that
  the update applied without conflicts, not that what an adopter is
  left holding still works.
- **CI**: a **Dependency Audit** workflow runs `just audit` and
  `just audit-prod` every Monday at 07:00 UTC (and on demand), filing
  findings as a GitHub issue labelled `dependency-audit` and commenting
  on that issue rather than opening a duplicate while it stays open. It
  is deliberately not part of `ci.yml`: the result depends on the OSV
  database rather than on your code, so an advisory published overnight
  would otherwise fail pull requests that changed nothing.

### Changed

- **Release tooling**: `just tag` (alias `just release`) now publishes
  the GitHub Release as well as pushing the tag, using that version's
  `CHANGELOG.md` section as the body. No tag-triggered workflow creates
  one -- `copier-update.yml` only verifies the `copier update` path --
  so every release from `v0.8.0` to `v0.11.0` was published by hand.

  Both halves are idempotent: an existing tag is not recreated, an
  existing release is left alone, so re-running after a partial failure
  is safe. `gh` is now required, and both its presence and its
  authentication are checked *before* the tag is created, so a missing
  prerequisite costs nothing instead of leaving a pushed tag with no
  release. `just tag --no-release` keeps the old tag-only behaviour and
  needs no `gh`.

  **Manual reconciliation**: this is a breaking change to a covered CLI
  recipe under the [stability
  policy](../guides/api-stability.md#breaking-vs-non-breaking) -- it
  gives an existing recipe a new outward-facing side effect and a new
  required tool. After `copier update`, decide which you want for your
  own repository: install and authenticate `gh` to publish releases, or
  run `just tag --no-release` (and consider making that the default in
  your `justfile`) to keep tagging alone. The stability guide gains two
  rows covering `justfile` recipe changes, which the table previously
  addressed only for `just new` scaffold output.

- **Infrastructure**: `mock-oauth2-server` 4.0.0 → 6.0.2. The local
  mock's token endpoint, its `scope`-into-`aud` injection, and its JWKS
  document are all unchanged, so `just token` and the roles it encodes
  behave as before -- verified by validating a minted token through
  `validate_token` against the running mock. The image is now
  Wolfi-based and still ships the `wget` the Compose health check calls.

### Fixed

- **Template**: `copier copy` now produces an already-formatted project.
  Substituting identifiers changes both line length and import sort
  order, so five files arrived unformatted — a longer `env_prefix`
  splits a line that fit, a shorter exception name lets one join, and a
  renamed import moves in the isort ordering. No wrapping choice in the
  template source can satisfy every project name at once, so
  `scripts/copier_setup.py` now runs `ruff check --fix` and
  `ruff format` after substitution. Previously a fresh clone's first
  `just check` passed but left five modified files in the working tree.
- **Template**: `scaffold-smoke.yml` and `copier-update.yml` no longer
  ship to generated projects. Both are template-maintenance CI that
  only ever fails there — `copier.yml` self-destructs during setup, so
  a generated project is never a template — and their `QUOINAPI_*`
  service variables were never rewritten either: the substitution key
  is `QUOIN_`, so `QUOINAPI_ENV` doesn't match it and would have
  pointed an adopter's gate at a prefix their project never reads. Any
  adopter whose project wasn't named "QuoinAPI" hit a failing CI gate
  on day one. The post-gen ruff format also now pins to the version
  the generated project's own `pyproject.toml` locks instead of
  whatever `uvx` resolves, and reports a failed format instead of
  silently claiming success.

## [0.11.0] - 2026-09-07

### Added

- **Security**: `QUOIN_OAUTH_SUPERUSER_ROLE` and
  `QUOIN_OAUTH_SUPERUSER_ENABLED` make the `require_roles()` global
  bypass configurable — rename it, or switch it off, if your IdP could
  issue a role named `api.superuser` to callers who should not hold
  global authority. Defaults preserve the previous behaviour.
- **Security**: `QUOIN_SECURITY_CSP_DOCS` and
  `QUOIN_SECURITY_CSP_REDOC` are applied to `/docs` and `/redoc` alone,
  so the default `QUOIN_SECURITY_CSP` no longer needs
  `'unsafe-inline'` in `script-src`, nor `data:`, `blob:`, or
  `cdn.redoc.ly` for the doc UIs. Both doc routes are unregistered in
  production, so neither relaxed policy is emitted there.
- **OpenAPI**: `DEFAULT_ERROR_RESPONSES` and `error_responses()` in
  `app/core/openapi.py` centralize RFC 9457 error declarations. Module
  routers carry the default set (401, 403, 422, 500); routes add their
  own codes. `just new <module>` now scaffolds routers with the default
  set, so new modules document their error bodies out of the box.
- **Observability**: SQL queries are now traced
  (`instrument_sqlalchemy_engine`), completing the trace hierarchy the
  guide already documented. The access log also records the matched
  route template (`route`) alongside the literal request `path`, so
  dashboards can aggregate per-endpoint without a cardinality
  explosion.
- **Tooling**: `just check` now runs `just migrate-check`
  (`alembic upgrade head && alembic check`), failing the build if a
  model change in `models.py` is missing its migration.
- **Roadmap**: added a "Known Correctness Issues" lane in
  `ROADMAP.md` for confirmed bugs that fit neither the launch
  checklist nor the demand-gated backlog.

### Changed

- **Testing**: `just check` now enforces **100% branch coverage**
  (`fail_under = 100` in `pyproject.toml`); any uncovered line fails the
  build. **Manual reconciliation**: a generated project below 100% must
  add the missing tests, or relax `fail_under`, after `copier update`.
- **Security**: the JWKS cache now lives on `app.state`, created
  lazily per application instance, instead of a process-wide module
  global — matching the shared HTTP client.
- **Dependencies**: transitive lock refresh (`uv lock --upgrade`); no
  direct pins changed. `just audit` reports no known vulnerabilities.

### Fixed

- **Database**: `get_session` now commits (or rolls back) before the
  response is sent, not after, via a new `SessionDep` that pins
  `scope="function"`. **Manual reconciliation**: switch any
  `Depends(get_session)` in your own modules to `SessionDep`.
- **Validation errors**: a `field_validator` raising `ValueError` no
  longer crashes into a 500 — errors are sanitized with
  `jsonable_encoder`, and `errors[]` drops the Pydantic docs `url` and
  truncates `input` (dropping it instead when it is an over-long object
  or array, so the field's JSON type stays stable).
- **Error handling**: an unhandled exception's 500 response now still
  carries `X-Request-ID`, security, and CORS headers, via a new
  innermost `UnhandledErrorMiddleware`.
- **Configuration**: `QUOIN_LOG_LEVEL` now actually controls log
  verbosity. It accepts any casing (`debug` works as well as `DEBUG`)
  but an unrecognised level now fails at startup rather than being
  silently ignored. A bare `ENV` (no `QUOIN_` prefix) no longer selects
  a different `.env` file or diverges from `Settings.ENV`.
- **Security**: `validate_token` now *requires* `exp`, `iat`, `sub`,
  `aud`, and `iss` rather than verifying only the claims a token
  happens to carry — a token minted without `exp` was previously
  accepted forever. `exp`/`iat` allow 10 s of clock skew, and a token
  whose `sub` is empty is rejected instead of resolving to a
  `ServicePrincipal` with an empty subject.
- **Security**: one malformed key in the IdP's JWKS document no longer
  raises out of the cache refresh as a 500 — and, because the fetch
  timestamp went unset, re-raises for the whole backoff window. Keys
  are parsed individually, bad ones are logged and skipped, and a
  document with no usable key falls to the existing "signing key not
  found" 401.
- **Security**: production boot validation is no longer OAuth-only.
  `validate_production_oauth()` is now
  `validate_production_settings()` and additionally requires an
  explicit `QUOIN_ALLOWED_HOSTS` — the development default rejects
  every real `Host` with a 400, which reads as an outage rather than a
  config error — and warns on `localhost` CORS origins.
  **Manual reconciliation**: rename the call if you import it, and set
  `QUOIN_ALLOWED_HOSTS` in your production environment.
- **Security**: the landing page's inline `<script>` moved to
  `app/static/js/home.js`, letting the default CSP drop
  `'unsafe-inline'` from `script-src` on every path but the two doc
  UIs, which are served under their own policies.
- **Security**: `/redoc` and `/docs` no longer log CSP violations.
  ReDoc's `data:` anchor icons, its `cdn.redoc.ly` logo, and its
  `blob:` search worker were all being blocked — the worker silently,
  because an unset `worker-src` falls back to `script-src`, where
  `blob:` never matched. Swagger UI's `data:` toolbar icons were
  blocked the same way. Both predate the `script-src` tightening above.
- **Users**: `get_by_email` now matches case-insensitively via
  `lower(email)` (with a migration backfilling legacy mixed-case rows),
  and the `q` search filter matches `%`/`_` literally instead of as SQL
  `LIKE` wildcards.
- **Observability**: the tracing `Resource` now carries
  `service.version` and `deployment.environment`; production with
  `QUOIN_OTEL_ENABLED=true` and no OTLP endpoint now warns once instead
  of printing every span to stdout.
- **OpenAPI**: error responses are now documented as
  `application/problem+json` instead of `application/json`, matching
  what the exception handlers actually send.
- **OpenAPI**: `422` responses are now documented as `ProblemDetail`
  instead of FastAPI's built-in `HTTPValidationError`, which described
  a payload this API never returns. `HTTPValidationError` and
  `ValidationError` no longer appear in `components.schemas`.

  Both fixes change generated client SDKs: error models for `422` and
  the content type of every error response. The wire format is
  unchanged — only the documented contract was wrong.
- **Error handling**: an unmatched route (404) or a route matched with
  the wrong method (405) — Starlette's own `HTTPException`, raised
  internally rather than by app code — now returns
  `application/problem+json` like every other error, instead of a bare
  `{"detail": ...}` body. A new httpx event hook on the test suite's
  `client` fixture checks this contract on every non-2xx response
  going forward.
- **Error handling**: an `HTTPException` raised with a bodyless status
  (`204`, `304`, `1xx`) no longer gets a problem+json body — a body
  there is a protocol violation, and the client received a truncated
  response. A non-string `detail` (`detail={"code": ...}`, valid
  FastAPI usage) is now JSON-encoded rather than rendered as a
  single-quoted Python `repr` no client can parse.
- **Logging**: `setup_logging()` runs on every `create_app()`, and each
  call handed structlog a freshly built processor list, discarding its
  cached configuration. The list's identity is now stable across calls.
- **Template**: `copier copy` no longer produces a project that fails
  its own `just lint`. `APP_LONG_DESCRIPTION` is real source, so a
  `long_description` answer over 80 characters — including the default,
  at 123 — tripped E501 in the generated `app/core/metadata.py`.

## [0.10.0] - 2026-07-27

### Known Issues

- **CI**: the `Copier Update Check` workflow below will show a red run on
  this tag. It diffs against the previous tag, `v0.9.0`, which predates
  the `.copier-answers.yml` persistence fix in this release — a project
  generated from `v0.9.0` has no answers file for `copier update` to
  diff against, and no later change can retroactively add one to an
  already-tagged release. Confirmed locally via
  `just verify-template-update v0.9.0 v0.10.0`. Verification is clean
  from `v0.11.0` onward, once both sides of the diff carry the answers
  file.

### Added

- **CI**: a `Copier Update Check` workflow runs on every `v*` tag push,
  verifying that `copier update` from the previous release applies
  cleanly. Also runnable locally via `just verify-template-update`.
- **Security**: `just audit` scans the locked dependencies for known
  CVEs (via `uv audit` / OSV), with `audit-prod` and `audit-fix`
  variants. See the
  [Dependency Scanning guide](../guides/dependency-scanning.md).
- **Docs**: an
  [API Stability & SemVer guide](../guides/api-stability.md) documents
  the versioning guarantee across the template surface.
- **Docs**: a v1.0 launch checklist on the roadmap gates the `1.0.0`
  release on the template contract, behaviour and quality, security and
  distribution, and a final release decision. Task lists now render on
  the documentation site.
- **Docs**: an
  [Optimistic Concurrency guide](../guides/optimistic-concurrency.md)
  documents the ETag / `If-Match` pattern — version column, the
  `version_id_col` mapper argument, a 412 domain exception, and the
  route/service/repository split — replacing the backlog item with a
  pattern you can apply per-endpoint.

### Changed

- **Tooling**: lowered `requires-python` from `>=3.14` to `>=3.12` and
  added a CI matrix across 3.12–3.14 to widen adoption. The dev
  toolchain and production image stay on 3.14.
- **Docs**: reorganised the documentation-site navigation for
  discoverability; no document URLs changed.
- **Docs**: the architecture decision log no longer advertises features
  the roadmap defers. It promised a Redis cache, a background worker,
  Prometheus metrics, and read-replica routing — two with sample code
  for APIs that do not exist — and listed Redis session storage despite
  authentication being stateless JWT validation.
- **Docs**: pruned the roadmap backlog to demand-gated features only.
- **Docs**: dropped seven backlog items that do not belong in a backend
  template at any point — rate limiting (belongs at the edge), a secrets
  manager adapter (sidecars already inject env), PII classification and
  field-level encryption, feature flags, the audit log table, retention
  and erasure jobs (all business-specific), and ETag concurrency, which
  is now a guide instead. Ten demand-gated items remain.
- **Dependencies**: upgraded FastAPI, SQLModel, greenlet, and the
  ruff/ty/prek/zensical toolchain, plus a transitive lock refresh.
- **Dependencies**: added `httpx2` to the `test` group to silence a
  Starlette testclient deprecation; runtime code stays on `httpx`.

### Fixed

- **Template**: generated projects now persist a `.copier-answers.yml`,
  so `copier update` works — previously the template omitted the answers
  file entirely, leaving every generated project unable to take updates.
- **Template**: the post-generation script no longer silently skips
  pruning the roadmap entry from `scripts/sync_docs.py`. It matched the
  entry with the path-adjust flag pinned to one literal value, so once
  that flag changed the pattern stopped matching while still reporting
  success, and generated projects shipped a sync script referencing a
  `ROADMAP.md` the template excludes. The flag is now matched
  generically and a miss raises instead of passing quietly. The module
  docstring no longer lists the roadmap either.

## [0.9.0] - 2026-07-07

### Added

- **API**: every list endpoint now returns a standard `Page[T]`
  envelope (`{ items, total, limit, offset }`) via
  `app/core/pagination.py`, with shared `limit`/`offset` params and a
  whitelist-validated `sort` (unknown field → 400). The `user` module
  adds `is_active` and `q` search filters — see the
  [Pagination guide](../guides/pagination.md).
- **API**: a `deprecated()` dependency (`app/core/versioning.py`) stamps
  the RFC 8594 `Deprecation`, `Sunset`, and `Link` headers so a single
  endpoint can be retired ahead of a URL version bump. See the
  [Deprecating Endpoints guide](../guides/deprecating-endpoints.md).
- **Observability**: a structured access log (`AccessLogMiddleware`)
  emits one `http_request` INFO line per request with `method`, `path`,
  `status`, `duration_ms`, and `request_id`. Probe paths are excluded;
  toggle with `QUOIN_ACCESS_LOG_ENABLED` (default on).
- **Docker**: the image now ships a `HEALTHCHECK` that polls `/health`
  via the stdlib, so orchestrators can gate on container health.

### Changed

- **Users**: `DELETE /users/{id}` is now a soft delete — it stamps a
  system-owned `deleted_at` tombstone (retained, excluded from all
  reads) and the unique email index is now partial
  (`WHERE deleted_at IS NULL`) so a deleted address frees up for reuse.
  `is_active` stays an independent client flag, and since delete is now
  an `UPDATE` the `UserInUseError` 409 path is gone — see the
  [Soft Delete guide](../guides/soft-delete.md).
- **API**: `GET /users` now returns the `Page` envelope instead of a
  bare array, and its pagination param is `offset` (was `skip`). Clients
  reading the list must switch to `response.items`.
- **Scaffolding**: `just new <module>` now generates minimally-working
  stubs (repository/service classes, a base schema, an example
  exception, a router-prefix test) instead of empty files. The output
  passes `just check` as-is; only `models.py` stays empty.
- **Logging**: production log timestamps are now emitted in **UTC**
  (`TimeStamper(utc=True)`) so aggregated JSON logs share one timezone,
  while development and test keep host-local time.
- **Docker**: the uv build stage is now pinned by manifest digest in
  addition to its version tag, for byte-for-byte reproducible builds.
- **Testing**: the test schema is now built by running the Alembic
  migration chain (reversed at teardown) instead of `create_all`, so
  model/migration drift fails the suite and down-migrations are
  exercised. A genuine two-connection test now covers the
  email-uniqueness race.
- **Database**: connection-pool sizing is now tunable via
  `QUOIN_DB_POOL_SIZE`, `QUOIN_DB_MAX_OVERFLOW`, `QUOIN_DB_POOL_TIMEOUT`,
  `QUOIN_DB_POOL_RECYCLE`, and `QUOIN_DB_POOL_PRE_PING` instead of
  hardcoded literals. Defaults match the previous behaviour.
- **Middleware**: `TimeoutMiddleware`, `RequestIDMiddleware`, and
  `SecurityHeadersMiddleware` are now pure ASGI, shedding per-request
  task overhead and the streaming penalty. A timeout firing after the
  response has started now aborts instead of emitting an illegal second
  response.
- **Security**: JWKS keys are now fetched through the shared resilient
  HTTP client (retries, circuit breaker, OpenTelemetry) instead of a
  bare client per refresh. A transport-level JWKS failure now surfaces
  as `502`/`503`/`504` instead of a mislabeled `401` (a genuine HTTP
  error response like `404` still maps to `401`).
- **Persistence**: transactions now follow a unit-of-work boundary —
  `get_session` commits once when the handler returns and rolls back on
  error, and repositories `flush()` instead of `commit()`. Constraint
  violations are discriminated by name, so only the `lower(email)` index
  maps to 409 `DuplicateEmailError` and any other `IntegrityError`
  becomes a 500 instead of a mislabeled duplicate.

### Fixed

- **Users**: `GET /users` now orders by `created_at, id` so pagination
  is stable across pages instead of relying on Postgres's default
  ordering.
- **Users**: a uniqueness race on concurrent creates/updates with the
  same email now returns 409 `DuplicateEmailError` instead of an
  unhandled 500. The repository catches the commit-time `IntegrityError`
  on top of the existing check-then-insert fast path.
- **Users**: email is now compared and stored case-insensitively
  (lowercased on write, matched via a functional unique index), so
  `Foo@example.com` and `foo@example.com` are the same user.
- **Users**: `full_name`/`email` on create are now capped at 255 chars
  (matching the DB column), so an over-length value is rejected with 422
  instead of a raw DB error.
- **Users**: `created_at`/`updated_at` now have a `server_default`, so
  non-ORM writes can no longer violate `NOT NULL` on those columns.
- **Errors**: a bare `pydantic.ValidationError` raised while
  constructing an internal model now falls through to the catch-all
  handler as a 500 instead of a misleading 422, since it signals a
  server bug rather than a client mistake.
- **Middleware**: inner-middleware error responses (504 timeout, 413
  size limit) now carry CORS/security headers plus `X-Request-ID`
  instead of arriving bare. `TrustedHostMiddleware` was reordered
  outside `CORSMiddleware` so Host validation applies to every request
  including a CORS preflight, closing a forged-`Host` bypass.
- **Security**: `openapi.json` is now disabled in production, matching
  the existing `/docs`/`/redoc` behaviour.

### Security

- **Fail-fast posture**: in `production`, the app now crash-loops at
  startup when the OAuth JWKS URI, issuer, or audience is missing (or
  the JWKS URI isn't `https://`), instead of booting and serving 401s
  while looking healthy.
- **Auth**: `QUOIN_OAUTH_ISSUER` is now required during token
  validation, closing the PyJWT `issuer=None` skip so tokens are always
  checked against `iss`.
- **Auth**: an unknown-`kid` token can no longer hammer the JWKS
  endpoint — refetches are bounded to one per
  `QUOIN_OAUTH_JWKS_MIN_REFRESH_SECONDS`, with the backoff armed before
  the fetch so failed fetches also back off.
- **Config**: `POSTGRES_PASSWORD` is now a `SecretStr` and
  `DATABASE_URL` a plain property, so the credential no longer leaks via
  `model_dump()` or the OpenAPI schema. Unknown `QUOIN_*` env vars are
  now ignored (`extra="ignore"`) so a typo can't masquerade as valid
  config.
- **Observability**: inbound `X-Request-ID` is validated (safe charset,
  64-char cap) and replaced with a fresh UUID otherwise, preventing log
  injection and header reflection.
- **Supply chain**: the `Dockerfile` pins `uv` to a released version,
  all GitHub Actions are SHA-pinned, and a `docker` Dependabot ecosystem
  keeps those pins fresh.
- **Docs**: the deployment guide now states that health/readiness probes
  must not be internet-routable and that the template assumes edge rate
  limiting.

## [0.8.0] - 2026-06-21

### Added

- **Scaffold**: `just new <module>` now auto-registers the new
  module's router in `app/api.py`, eliminating the manual wiring
  step.
- **Supply chain**: Dependabot keeps dependencies patched with weekly,
  grouped pull requests. `.github/dependabot.yml` watches two
  ecosystems — `uv` (Python `dependencies` in `pyproject.toml` +
  `uv.lock`) and `github-actions` (the actions pinned in
  `.github/workflows/`) — collapsing minor and patch bumps into a
  single PR per ecosystem while keeping majors separate. The new
  Dependency Scanning guide documents the cadence, how to enable
  GitHub-native secret scanning and push protection (repository
  settings, not files), and how enterprises layer Snyk / Black Duck /
  GHAS on top.
- **Migrations**: a zero-downtime migration playbook. The Database
  Migrations guide documents the expand/contract (parallel-change)
  pattern with recipes for renaming a column, dropping a column,
  changing a type, adding a NOT NULL column, and building an index
  concurrently. `just migrate-gen` now runs a non-blocking guard
  (`scripts/migration_guard.py`) that parses the generated script's
  AST and flags destructive or locking operations — drops, type
  changes, NOT NULL on populated tables, non-concurrent indexes, and
  destructive raw SQL — for review.
- **Integrations**: a shared, resilient outbound HTTP client
  (`app.http`). A single `httpx.AsyncClient` is lifecycle-managed in
  the lifespan and injected via `HTTPClientDep`. Every call is guarded
  by a per-host circuit breaker (purgatory) wrapping a retry loop with
  exponential backoff (stamina), and is OpenTelemetry-instrumented
  when `QUOIN_OTEL_ENABLED`. Transport failures map to
  `BadGatewayError` (502), `GatewayTimeoutError` (504), and
  `ServiceUnavailableError` (503, circuit open); response status codes
  are left for callers to interpret. Tunable via
  `QUOIN_HTTP_TIMEOUT_SECONDS` and `QUOIN_HTTP_RETRY_ATTEMPTS`. See
  the Outbound HTTP Client guide.
- **Reliability**: graceful shutdown drains in-flight requests before
  the database engine is disposed. On shutdown the readiness probe
  flips to 503 (so orchestrators stop routing new traffic),
  `InFlightRequestMiddleware` tracks active requests, and the lifespan
  handler waits for them to drain — bounded by
  `QUOIN_SHUTDOWN_DRAIN_TIMEOUT` (default 30s; `<=0` skips the wait)
  — before disposing the engine. See the Graceful Shutdown section in
  the deployment guide for the uvicorn relationship and Kubernetes
  wiring.
- **Security**: `SecurityHeadersMiddleware` emits HSTS, CSP,
  X-Frame-Options, X-Content-Type-Options, Referrer-Policy, and
  Permissions-Policy on every response. All values configurable via
  `QUOIN_SECURITY_*` settings; toggle with
  `QUOIN_SECURITY_HEADERS_ENABLED`.
- **Security**: `RequestSizeLimitMiddleware` rejects oversize bodies
  before they reach route handlers by checking the advertised
  `Content-Length`. Returns 413 RFC 9457 `payload_too_large`.
  Configurable via `QUOIN_MAX_REQUEST_BODY_BYTES` (default 1 MiB;
  `<=0` disables). Conforming clients always send `Content-Length`;
  the uvicorn/h11 layer caps raw protocol buffers for the chunked
  edge case.

### Changed

- **Branding**: project tagline updated to "The Foundation for your
  Python backend API" across README, pyproject.toml, OpenAPI metadata,
  docs, and Copier template defaults.
- **Dependencies**: FastAPI 0.136.3 → 0.138.0, structlog 25.5.0 →
  26.1.0, greenlet 3.5.1 → 3.5.2, pydantic-settings 2.14.1 →
  2.14.2, pytest 9.0.3 → 9.1.1, pytest-asyncio 1.3.0 → 1.4.0.
  Tooling: ruff 0.15.14 → 0.15.18, ty 0.0.39 → 0.0.51,
  prek 0.4.1 → 0.4.5, zensical 0.0.43 → 0.0.46,
  mkdocstrings-python 2.0.3 → 2.0.5. New runtime deps: `httpx`,
  `purgatory`, `stamina`, `opentelemetry-instrumentation-httpx`.
- **Security**: CORS configuration now requires explicit allowlists
  for methods and headers (`QUOIN_BACKEND_CORS_ALLOW_METHODS`,
  `QUOIN_BACKEND_CORS_ALLOW_HEADERS`,
  `QUOIN_BACKEND_CORS_ALLOW_CREDENTIALS`). Wildcard methods/headers
  combined with `allow_credentials=True` outside `development` are
  rejected at startup — that combination is silently ignored by
  browsers and was a credentialed-CORS footgun.
- **Tooling**: `uv` resolution is now bounded by a 7-day dependency
  cooldown (`exclude-newer = "7 days"`) for more reproducible
  installs, and `required-version` pins the minimum `uv` version so
  contributors and CI stay in sync. Ruff now lints naming conventions
  (`N` / pep8-naming) and formats code samples embedded in docstrings
  (`docstring-code-format`). `pyproject.toml`'s dependency lists and
  tool sections are sorted alphabetically for easier scanning and
  fewer merge conflicts.
- **Developer Experience**: Claude Code workflow improvements distilled
  from recurring manual chores — three new skills (`quoin-coverage`
  for the drive-to-100% coverage loop, `quoin-deps-upgrade` for the
  dependency and GitHub Actions upgrade ritual, `quoin-docs-audit` for
  docs-to-code drift sweeps), a `migration-reviewer` subagent that
  audits autogenerated Alembic scripts, two advisory `Stop` hooks
  (`config-drift` when `app/core/config.py` changes without matching
  `.env.example` / `docs/guides/configuration.md` updates, and
  `migration-reminder` when a `models.py` changes without a new
  migration), a read-only `postgres` MCP server for live schema
  introspection, a `just sync-main` recipe for post-merge branch
  cleanup, and `just test`/`just check` now auto-start Postgres
  instead of failing. `quoin-pre-pr` now gates on `just check`
  passing at 100% coverage. `.env.example` now documents the
  `QUOIN_ALLOWED_HOSTS` setting.
- **Template**: `copier copy` now produces a clean, de-branded
  starter. QuoinAPI-specific docs are excluded at copy time (the
  marketing `docs.md`, the architecture decision log, the roadmap,
  and the custom home-page JavaScript), and the post-generation
  script rewrites the remaining chrome — a fresh `README.md` and
  minimal `docs/index.md`, a trimmed documentation nav with the
  personal social links removed, and the error-type URN namespace
  rebranded from `urn:quoin:error:*` to `urn:<project-slug>:error:*`.
  The guides, architecture overview, and full API reference (including
  the `user` module) are retained.

### Fixed

- **Errors**: unhandled exceptions (bare `KeyError`, non-transport
  `httpx` errors, etc.) now return RFC 9457 `application/problem+json`
  instead of Starlette's default `text/plain` 500. A catch-all
  `Exception` handler logs the traceback and maps to
  `InternalServerError`.
- **Template**: scoped the Copier post-generation substitutions by
  filename so they can no longer corrupt unrelated files. The author
  email rewrite was previously applied to every file and overwrote
  `email = "..."` values in test fixtures, breaking a freshly
  generated project's test suite; the `APP_DESCRIPTION` rewrite
  matched only a parenthesised form the source never used, so the
  default API description leaked into generated projects. Both now
  target their intended file.

## [0.7.0] - 2026-05-25

### Added

- **Observability**: `RequestIDMiddleware` propagates `X-Request-ID`
  (configurable via `QUOIN_REQUEST_ID_HEADER`) and binds it to every
  structlog event.
- **Observability**: OpenTelemetry trace/log correlation — `trace_id` and
  `span_id` injected into structlog events when an active span exists.
  Vendor-neutral OTLP/Jaeger setup documented.
- **Operability**: `TimeoutMiddleware` enforces a per-request wall-clock
  timeout via `anyio.fail_after()`; configurable via
  `QUOIN_REQUEST_TIMEOUT_SECONDS` (default 30 s); returns 504 RFC 9457
  `GatewayTimeoutError`. Uses `anyio` cancel scopes for nested-task safety.
- **Errors**: RFC 9457 Problem Details — all error responses use
  `application/problem+json` with `type`, `title`, `status`, `detail`,
  `instance`, and an `errors` array on 422. `ProblemDetail` model in
  `app/core/schemas.py` replaces `ErrorResponse`.
- **Errors**: `GatewayTimeoutError` (504) and `ServiceUnavailableError`
  (503) domain exceptions; `/ready` now raises the latter on DB failure.
- **Developer Experience**: Claude Code workflow integration — 6 skills in
  `.claude/skills/`, `Stop` hook running `just format && just lint && just
  typecheck` after dirty turns, `PreToolUse` hook blocking edits to `.env`,
  `uv.lock`, and applied migrations, 5 plugins, and `context7` MCP server.
- **Quality**: Pre-push pytest gate in `prek.toml`; `just setup` installs
  both commit and pre-push hooks.

### Changed

- **Python**: Runtime upgraded 3.12 → 3.14 (3.14.5).
- **Dependencies**: FastAPI 0.135.3 → 0.136.3, OpenTelemetry 1.41.0 →
  1.42.1 (instrumentation 0.62b0 → 0.63b1), plus `psycopg`, `greenlet`,
  `PyJWT`, `pydantic-settings`. Tooling: `ruff` 0.15.14, `ty` 0.0.39,
  `prek` 0.4.1, `zensical` 0.0.43.
- **Infrastructure**: `mock-oauth2-server` 3.0.1 → 4.0.0. HTTP 422 phrase
  updated to `"Unprocessable Content"` per RFC 9110.
- **Errors**: `quoin_exception_handler` now emits a structured warning log
  (`event="quoin_error"`) before returning.
- **Observability**: Guide rewritten to be vendor-neutral (Jaeger/CNCF only).
- **UI**: Homepage redesigned to match documentation site styling; mobile
  overflow on small screens resolved.
- **CI**: GitHub Actions workflows upgraded to latest versions with Node 24
  support.

### Fixed

- **Auth**: OAuth audience validation now enforced — `aud` claim is verified
  against `QUOIN_OAUTH_AUDIENCE`; previously the check was skipped.
- **Core**: `datetime.now()` replaced with `datetime.now(UTC)` in system
  routes; request validation error handling hardened.

## [0.6.0] - 2026-04-18

### Added

- **Security**: Full OAuth 2.0/2.1 S2S authentication stack — `JWKSCache`
  (JWKS rotation), `validate_token`, `get_current_caller`, and `require_roles`
  dependency factory in `app/core/security.py`.
- **Security**: `ServicePrincipal` Pydantic model (`subject`, `roles`,
  `claims`) as the resolved caller identity; `api.superuser` bypass for local
  dev; `UnauthorizedError` (401) with RFC 6750 `WWW-Authenticate: Bearer`.
- **Security**: DDD role scopes — `[domain].[action]` strings (e.g.
  `users.read`, `users.write`) declared explicitly per route, no global roles.
- **OpenAPI**: `ErrorResponse` schema in `app/core/schemas.py`; all `users/`
  endpoints fully document `401`, `403`, `404`, `409`, `500` responses.
- **Configuration**: `QUOIN_OAUTH_*` settings for binding to any OIDC
  provider; `mock-oauth2-server` Docker service + `just token --roles <roles>`
  for local RS256 JWT generation.
- **Developer Experience**: `just dev` — starts DB (with healthcheck), applies
  migrations, and runs the server in one command. `just reset-db` purges
  volumes with `docker compose down -v` for a clean slate.
- **Testing**: Dual-layer auth — live tokens via `mock-oauth2-server`;
  `ServicePrincipal` fixture injection via `dependency_overrides` for
  zero-container unit tests. DB isolation fix prevents test teardown from
  wiping the dev `app_db` schema.
- **Copier**: Added `copier.yml` and `scripts/copier_setup.py.jinja`.
- **Documentation**: `docs/guides/authentication.md` covering DDD scopes,
  `api.superuser` bypass, dependency graph, and both testing layers.

### Changed

- **Security**: Role strings declared at route level with DDD scope syntax;
  no global `OAUTH_READ_ROLE` / `OAUTH_ADMIN_ROLE` settings.
- **Developer Experience**: `justfile` — added `dev`, `reset-db`, `logs`,
  `migrate-down`, `new`, and `oauth` recipes.
- **Docker**: Non-root user renamed to `quoin`; PostgreSQL volume mapped to
  `/var/lib/postgresql` for v18 compatibility; `pg_isready` healthcheck added.
- **Configuration**: Added `*.orb.local` to allowed CORS hosts.
- **Documentation**: Reorganized navigation; added authentication,
  module creation, and quality-checks guides.

### Fixed

- **Tests**: `initialize_db` teardown no longer drops tables from the dev
  `app_db` after `just check`.
- **Validation**: Enforced `EmailStr` on `UserRead` outbound mapping.
- **Error Handling**: Hooked `RequestValidationError` to return standard
  `{"detail": ...}` JSON instead of FastAPI's default 422 shape.

## [0.5.0] - 2026-02-16

### Added

- **API Versioning**: Introduced `/api/v1/` prefix to all endpoints for future-proof API evolution.
- **Module-Level Exceptions**: Added `app/modules/user/exceptions.py` and `SystemError` (in system module) for domain-specific error handling.
- **Environment Configuration**: Added `Environment` enum and `.env.test`/`.env.production` support.
- **Project Rename**: Officially renamed project from "FastAPI Backend" to **QuoinAPI** (pronounced "koyn").
- **Architectural Branding**: Updated README and Metadata with "Structural Integrity", "High-Performance Core", and "Built-in Observability" pillars.

### Changed

- **Configuration**:
  - Renamed environment variable prefix from `APP_` to `QUOIN_` (e.g., `QUOIN_ENV`, `QUOIN_DB_URL`).
  - Enforced `QUOIN_ENV` (or fallback `ENV`) to select configuration files.
  - Replaced `DEBUG` boolean with `LOG_LEVEL` string (default: "INFO").
- **Error Handling**:
  - Renamed `AppError` to `QuoinError` as the base exception class.
  - Standardized error responses with `QuoinRequestValidationError` for Pydantic errors.
  - Updated `exception_handlers.py` to use new exception hierarchy.
- **Docker**:
  - Renamed services and images to `quoin-api` and `quoin-api-docs`.
  - Updated `docker-compose.yml` to use `QUOIN_ENV` and `QUOIN_POSTGRES_*` variables.
- **Documentation**:
  - Updated all guides to reflect `QuoinAPI` naming and `QUOIN_` configuration prefix.
  - Updated branding assets and repository URLs to `balakmran/quoin-api`.

### Removed

- **Legacy Config**: Removed support for `APP_ENV` (use `QUOIN_ENV`).
- **Legacy Naming**: Removed references to `fastapi-backend` in all documentation and config files.

## [0.4.0] - 2026-02-15

### Added

- **Domain Exceptions**: `NotFoundError`, `ConflictError`, `BadRequestError`,
  `ForbiddenError` subclasses for better error handling granularity.
- **`__all__` Exports**: Explicit public API exports in all core modules and
  domain routers.
- **Pagination Guards**: `Query(ge=0)`, `Query(ge=1, le=100)` constraints on
  pagination parameters to prevent abuse.
- **Alembic in Docker**: Copied `alembic/` directory and `alembic.ini` into
  Docker image for production database migrations.

### Changed

- **Database Engine**: Refactored from global mutable engine to
  `app.state.engine` pattern for better test isolation and cleaner
  architecture.
- **Logging**: Moved `setup_logging()` call inside `create_app()` to prevent
  import-time side effects.
- **Schema Validation**: Added `extra="forbid"` to `UserBase` and `UserUpdate`
  schemas to reject extraneous fields.
- **Static Files**: Updated to use absolute paths for static files and
  templates, avoiding relative path fragility.
- **OTEL Service Name**: Now uses `metadata.APP_NAME` instead of hardcoded
  string.
- **Docker Compose**: Renamed `ENV` → `APP_ENV`, replaced stale `DATABASE_URL`
  with individual `POSTGRES_*` variables.
- **Test Fixtures**: Refactored to use `monkeypatch` for settings mutation in
  tests, avoiding direct global state modification.
- **CI Workflows**: Standardized `setup-uv` action version to `v7` across all
  workflows.
- **Documentation**: Updated Zensical config with instant navigation, prefetch,
  progress, and modern `mkdocstrings` TOML format.

### Fixed

- **`updated_at` Auto-update**: Added `onupdate` parameter to `User.updated_at`
  field to ensure automatic timestamp updates on mutations.
- **Timezone-aware Datetimes**: Fixed `datetime.now()` in `system/routes.py` to
  use `datetime.now(UTC)`.
- **Duplicate Email Status**: Changed HTTP status from `400` to `409` for
  duplicate email registration errors.
- **Alembic Offline Mode**: Fixed driver mismatch by using `postgresql+psycopg`
  instead of `postgresql+asyncpg` for offline SQL generation.
- **Exception Handler Logging**: Added structured logging for `AppError`
  exceptions in exception handlers.
- **Type Hints**: Added missing return type hints to `telemetry.py` functions.
- **Metadata References**: Fixed GEMINI.md and configuration.md to reference
  `metadata.py`, `app.state.engine`, and correct `AppError` class name.

## [0.3.1] - 2026-02-14

### Added

- **Justfile**: Added `setup` recipe to improved developer onboarding (`just setup`).

### Changed

- **Database**: Fixed `sessionmaker` usage in `app/db/session.py` to use `async_sessionmaker` for correct async support.
- **Documentation**: Updated installation guides to recommend `just setup`.
- **Prek**: Optimized `prek.toml` to use faster builtin hooks instead of GitHub pre-commit hooks.
- **Refactoring**: Extracted application metadata (version, description, URLs) to `app/core/metadata.py`.
- **Templates**: Injected dynamic metadata into `index.html` (title, description, version, copyright).
- **Swagger UI**: Hidden root endpoint (`GET /`) from API documentation.

## [0.3.0] - 2026-02-09

### Added

- **OpenTelemetry**: Integrated OpenTelemetry for production-grade distributed
  tracing and observability.
- **Zensical**: Migrated documentation engine to Zensical for a modern,
  high-performance static site.
- **Prek**: `prek` for faster hook management.

### Changed

- **Documentation**: Flattened navigation structure, added copyright footer, and
  improved Home page styling.
- **Code Quality**: Enforced stricter linting rules (80-char line limit) via
  `ruff`.

### Removed

- **Documentation**: Removed MkDocs documentation engine.
- **Pre-commit**: Removed pre-commit.

## [0.2.0] - 2025-12-08

### Added

- **Home Page**: A beautiful, dark-themed landing page with feature highlights
  and quick start snippet.
- **Readiness Probe**: New `/ready` endpoint to check database connectivity.
- **System Module**: dedicated `app/modules/system` for core endpoints (`/`,
  `/health`, `/ready`).
- **Favicon**: Official FastAPI logo served as the favicon.
- **AI Context**: Added `GEMINI.md` for AI agent instructions and project
  context.
- **Versioning**: Implemented dynamic versioning and automated bump workflow
  (`just bump`).
- **Release Automation**: Added `just tag` to automate git tagging and pushing.
- **Documentation**: Updated `CONTRIBUTING.md` and `GEMINI.md` with versioning
  workflow instructions.

### Changed

- **OpenAPI Metadata**: Improved title, summary, and description in `/docs`
  using detailed info from README.
- **Swagger UI**: Hidden "Schemas" section by default for a cleaner interface.
- **Refactoring**: Moved root and health endpoints out of `main.py` to `system`
  module.

## [0.1.0] - 2025-11-26

### Added

- Initial project setup with FastAPI, SQLModel, and PostgreSQL.
- User module with full CRUD operations (Create, Read, Update, Delete).
- Database migrations using Alembic.
- Structured logging with `structlog`.
- Docker and Docker Compose configuration for development.
- `justfile` for command automation.
- Comprehensive test suite setup with `pytest`.
- Static analysis with `ruff` and `ty`.
- Documentation with MkDocs.

[Unreleased]: https://github.com/balakmran/quoin-api/compare/v0.12.0...HEAD
[0.12.0]: https://github.com/balakmran/quoin-api/compare/v0.11.0...v0.12.0
[0.11.0]: https://github.com/balakmran/quoin-api/compare/v0.10.0...v0.11.0
[0.10.0]: https://github.com/balakmran/quoin-api/compare/v0.9.0...v0.10.0
[0.9.0]: https://github.com/balakmran/quoin-api/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/balakmran/quoin-api/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/balakmran/quoin-api/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/balakmran/quoin-api/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/balakmran/quoin-api/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/balakmran/quoin-api/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/balakmran/quoin-api/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/balakmran/quoin-api/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/balakmran/quoin-api/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/balakmran/quoin-api/releases/tag/v0.1.0
