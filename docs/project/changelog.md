# Changelog

## [Unreleased]

### Added

- **Reliability**: graceful shutdown drains in-flight requests before
  the database engine is disposed. On shutdown the readiness probe
  flips to 503 (so orchestrators stop routing new traffic),
  `InFlightRequestMiddleware` tracks active requests, and the lifespan
  handler waits for them to drain — bounded by
  `QUOIN_SHUTDOWN_DRAIN_TIMEOUT` (default 30s; `<=0` skips the wait) —
  before disposing the engine. See the Graceful Shutdown section in the
  deployment guide for the uvicorn relationship and Kubernetes wiring.
- **Security**: `SecurityHeadersMiddleware` emits HSTS, CSP,
  X-Frame-Options, X-Content-Type-Options, Referrer-Policy, and
  Permissions-Policy on every response. All values configurable via
  `QUOIN_SECURITY_*` settings; toggle with
  `QUOIN_SECURITY_HEADERS_ENABLED`.
- **Security**: `RequestSizeLimitMiddleware` rejects oversize bodies
  before they reach route handlers by checking the advertised
  `Content-Length`. Returns 413 RFC 9457 `payload_too_large`.
  Configurable via `QUOIN_MAX_REQUEST_BODY_BYTES` (default 1 MiB; `<=0`
  disables). Conforming clients always send `Content-Length`; the
  uvicorn/h11 layer caps raw protocol buffers for the chunked edge
  case.

### Changed

- **Security**: CORS configuration now requires explicit allowlists for
  methods and headers (`QUOIN_BACKEND_CORS_ALLOW_METHODS`,
  `QUOIN_BACKEND_CORS_ALLOW_HEADERS`,
  `QUOIN_BACKEND_CORS_ALLOW_CREDENTIALS`). Wildcard methods/headers
  combined with `allow_credentials=True` outside `development` are
  rejected at startup — that combination is silently ignored by
  browsers and was a credentialed-CORS footgun.

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

[Unreleased]: https://github.com/balakmran/quoin-api/compare/v0.7.0...HEAD
[0.7.0]: https://github.com/balakmran/quoin-api/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/balakmran/quoin-api/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/balakmran/quoin-api/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/balakmran/quoin-api/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/balakmran/quoin-api/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/balakmran/quoin-api/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/balakmran/quoin-api/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/balakmran/quoin-api/releases/tag/v0.1.0
