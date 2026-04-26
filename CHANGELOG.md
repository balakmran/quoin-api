# Changelog

## [Unreleased]

### Added

- **Errors**: RFC 9457 Problem Details — all error responses now return
  `Content-Type: application/problem+json` with `type` (URN derived from
  the exception class), `title` (standard HTTP phrase), `status`, `detail`,
  `instance` (request path), and an `errors` array on 422 responses.
  `ProblemDetail` Pydantic model in `app/core/schemas.py`; `ErrorResponse`
  replaced throughout.
- **Errors**: `ServiceUnavailableError` (503) domain exception; `/ready`
  endpoint now raises it instead of `HTTPException` when the database is
  unreachable.
- **Observability**: `RequestIDMiddleware` — generates or propagates a
  request ID header (default `X-Request-ID`, configurable via
  `QUOIN_REQUEST_ID_HEADER`), binds it to every structlog event for the
  request, and echoes it on the response.
- **Observability**: OpenTelemetry trace/log correlation — `_add_otel_context`
  structlog processor injects `trace_id` and `span_id` into every log event
  when an active OTel span exists. Vendor-neutral OTLP setup documented with
  Jaeger local quickstart.
- **Developer Experience**: First-class Claude Code setup — 5 workflow skills
  (`quoin-new-module`, `quoin-db-migration`, `quoin-auth-route`,
  `quoin-write-tests`, `quoin-release`, `quoin-pre-pr`) loaded on-demand from
  `.claude/skills/`; `Stop` hook runs `just format && just lint &&
  just typecheck` after every dirty turn; `PreToolUse` hook blocks edits to
  `.env` credential files, `uv.lock`, and applied Alembic migrations; 5
  Claude plugins enabled (`commit-commands`, `pr-review-toolkit`,
  `security-guidance`, `claude-md-management`, `claude-code-setup`);
  `context7` MCP server committed in `.mcp.json` for live SDK docs.
- **Quality**: Pre-push pytest gate added to `prek.toml`; `just setup` now
  installs both commit and pre-push hooks.

### Changed

- **Errors**: `quoin_exception_handler` now emits a structured `warning` log
  (`event="quoin_error"`) before returning; previously it returned silently.
- **Observability**: Observability guide rewritten to be vendor-neutral —
  Jaeger/CNCF only, commercial backends removed.
- **Documentation**: `docs/guides/ai-setup.md` covering the full Claude Code
  setup with invocation patterns, first-time setup, and extension guide.

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

[Unreleased]: https://github.com/balakmran/quoin-api/compare/v0.6.0...HEAD
[0.6.0]: https://github.com/balakmran/quoin-api/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/balakmran/quoin-api/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/balakmran/quoin-api/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/balakmran/quoin-api/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/balakmran/quoin-api/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/balakmran/quoin-api/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/balakmran/quoin-api/releases/tag/v0.1.0
