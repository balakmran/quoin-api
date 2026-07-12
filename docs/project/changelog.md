# Changelog

## [Unreleased]

### Added

- **Docs**: an [API Stability & SemVer guide](../guides/api-stability.md)
  publishes the versioning guarantee on the template surface — `app/core`
  contracts, `QUOIN_*` settings, CLI recipes, scaffold output, and
  `copier.yml` variables — and how `copier update` compatibility and
  deprecations are handled. It explicitly does not cover the example
  `user` module's `/api/v1` routes, which remain yours to change freely.

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

[Unreleased]: https://github.com/balakmran/quoin-api/compare/v0.8.0...HEAD
[0.8.0]: https://github.com/balakmran/quoin-api/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/balakmran/quoin-api/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/balakmran/quoin-api/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/balakmran/quoin-api/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/balakmran/quoin-api/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/balakmran/quoin-api/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/balakmran/quoin-api/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/balakmran/quoin-api/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/balakmran/quoin-api/releases/tag/v0.1.0
