# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

QuoinAPI (pronounced "koyn") is a high-performance FastAPI + SQLModel + PostgreSQL backend template/boilerplate. It doubles as a working API and a Copier template for generating new projects. The Astral stack (uv, ruff, ty) is used throughout.

Copier note: updating core scaffolding logic requires syncing against `copier.yml` or `scripts/copier_setup.py.jinja`.

## Tech Stack

- **Framework:** FastAPI
- **Database:** PostgreSQL 18 via `asyncpg` driver
- **ORM:** SQLModel (SQLAlchemy wrapper)
- **Migrations:** Alembic
- **Package Manager:** uv
- **Task Runner:** just
- **Linting/Formatting:** Ruff
- **Type Checking:** ty (Pyright engine)
- **Testing:** pytest, pytest-asyncio, pytest-cov
- **Observability:** OpenTelemetry, Structlog
- **Documentation:** Zensical (MkDocs Material)
- **Git Hooks:** prek (Rust-based, replaces pre-commit)

## Commands

All commands run via `just` (task runner). `.env` is auto-loaded.

| Command | Action |
| :--- | :--- |
| `just setup` | Install deps + prek git hooks (first-time) |
| `just install` | `uv sync --all-groups` |
| `just clean` | Remove `__pycache__`, `.pyc`, `.coverage`, `htmlcov`, caches |
| `just dev` | Start DB + OAuth, apply migrations, run dev server |
| `just run` | `fastapi dev app/main.py` (auto-reload) |
| `just up` | Build + start all services via Docker Compose |
| `just down` | `docker compose down` |
| `just logs` | Tail live logs from the API container |
| `just db` | `docker compose up -d --wait db` |
| `just oauth` | `docker compose up oauth -d --wait` |
| `just token [--sub X] [--roles Y]` | Generate a signed JWT via `scripts/gen_token.py` |
| `just check` | format → lint → typecheck → test |
| `just format` | `ruff format .` |
| `just lint` | `ruff check . --fix` |
| `just typecheck` | `ty check` |
| `just test` | `pytest -q --cov=app --cov-report=html --cov-report=term:skip-covered --tb=line tests/` (requires DB running) |
| `just migrate-gen "<msg>"` | `alembic revision --autogenerate -m "<msg>"` |
| `just migrate-up` | `alembic upgrade head` |
| `just migrate-down` | `alembic downgrade -1` |
| `just reset-db` | `down -v` → restart DB → `migrate-up` |
| `just new <module>` | Scaffold DDD module skeleton + test stub |
| `just pi` / `just pr` | Install / run prek hooks |
| `just bump part="<type>"` | Bump version via `scripts/bump_version.py` (patch/minor/major) |
| `just tag` / `just release` | Create + push git tag via `scripts/tag_release.py` |
| `just docb` / `just ds` | Build / serve docs locally (port 8001) |

### Running a Single Test

```bash
uv run pytest tests/modules/user/test_routes.py -v
uv run pytest tests/modules/user/test_routes.py::test_create_user -v
```

Tests require a running PostgreSQL DB — run `just db` first.

## Architecture

### Key Files

- `app/main.py` — FastAPI application factory; configures lifecycle, middleware, exception handlers
- `app/api.py` — router registration; all user endpoints under `/api/v1/`
- `justfile` — all task recipes
- `pyproject.toml` — dependencies, Ruff, pytest, coverage config
- `docker-compose.yml` — local dev services (db, oauth, api, docs)
- `Dockerfile` — multi-stage production image
- `zensical.toml` — documentation site config

### `app/core/` — Infrastructure

- `config.py` — pydantic-settings; `QUOIN_ENV` controls active profile
- `logging.py` — structlog setup (JSON in production)
- `middlewares.py` — CORS bounds (`*.orb.local` natively supported)
- `telemetry.py` — OpenTelemetry instrumentation
- `exceptions.py` / `exception_handlers.py` — `QuoinError` base + global handlers
- `security.py` — JWT validation, JWKS caching, `require_roles()` dependency

### Module Structure (Domain-Driven Design)

Each feature lives in `app/modules/{feature}/`:

```
models.py       → SQLModel DB tables
schemas.py      → Pydantic request/response models (use EmailStr for email fields)
routes.py       → FastAPI endpoints with RBAC dependencies
service.py      → Business logic
repository.py   → Database access (CRUD only)
exceptions.py   → Domain-specific exceptions extending QuoinError
__init__.py     → Exposes router as `router`
```

Use `just new <module>` to scaffold all of these at once, then register the router in `app/api.py`.

**New module workflow:**
1. Define models → `just migrate-gen "add X model"` → review migration
2. Define schemas → implement repository → implement service → create routes
3. Register router in `app/api.py`
4. Write tests in `tests/modules/<module>/`

### Request Flow

```
HTTP Request → FastAPI Router (routes.py)
             → require_roles() RBAC dependency
             → Service (service.py)
             → Repository (repository.py)
             → SQLModel / AsyncPG
             → PostgreSQL
```

### Security & Auth

- JWT validated against OAuth server JWKS endpoint (auto-refreshed on key rotation)
- Routes use `require_roles("scope.action")` FastAPI dependency
- `ServicePrincipal` model represents the authenticated caller
- Superuser bypass via `api.superuser` role
- Local dev uses mock OAuth2 server (`just oauth`)

### Testing Infrastructure

- Session-scoped `initialize_db` fixture creates/drops all tables once; connects to the `postgres` default database (not `app_db`) via URL substitution to avoid dropping the developer's schema on teardown
- Per-test SAVEPOINT rollback — no test pollution
- Pre-built fixtures: `client`, `admin_client`, `read_client`, `db_session`, `caller_read`, `caller_admin`
- Integration tests over real DB preferred; mock only external APIs
- All endpoints must be prefixed with `/api/v1/`
- Maintain ≥95% test coverage for new features

## Code Conventions

- **Run `just check` after every code change** — format, lint, typecheck, and tests must all pass. Fix any errors before ending a turn; do not skip this step.
- **100% type hints** — use `# type: ignore` (blanket), not MyPy-style tags like `# type: ignore[arg-type]`; the Pyright engine rejects unrecognized tags
- **FastAPI exception handlers** added via `app.add_exception_handler` must type the `exc` parameter as `Any` to satisfy Pyright
- **80-character line limit** — applies to both Python and Markdown; enforced by Ruff for Python; tables and code blocks are exempt in both
- **Async-first** — all DB calls and service methods are `async def`
- **Google-style docstrings** — configured in `pyproject.toml`; follow the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- **No emojis or icons** in `justfile` echo commands (terminal compatibility); use `@` prefix on recipes to suppress command echoing
- **Conventional Commits** — `<type>(<scope>): <description>`; types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`
- Feature branches from `main`, merge via PR

## Error Handling

Raise domain exceptions, never raw `HTTPException`, in service or repository code:

- Available: `NotFoundError`, `ConflictError`, `BadRequestError`, `ForbiddenError`, `InternalServerError`
- Exception handlers in `app/core/exception_handlers.py` map these to standardized JSON responses

## Database Changes

Never modify the schema manually. Always:
1. Define/update the SQLModel model
2. `just migrate-gen "description"` → review the generated script
3. `just migrate-up` to apply

## Configuration

All env vars use `QUOIN_` prefix. Key variables (see `.env.example` for full list):

```
QUOIN_ENV=development|test|production
QUOIN_POSTGRES_HOST / _PORT / _USER / _PASSWORD / _DB
QUOIN_OAUTH_JWKS_URI=http://oauth:8080/default/jwks
QUOIN_OAUTH_ISSUER=http://oauth:8080/default
QUOIN_OAUTH_AUDIENCE=default
QUOIN_OAUTH_ROLES_CLAIM=roles
QUOIN_LOG_LEVEL=INFO
```

`.env.test` overrides apply automatically during `just test`.

Docker notes:
- Postgres persistence volumes must map to `/var/lib/postgresql` (not `/data`) for Postgres 18 compatibility
- Dockerfile runs as non-root user `quoin`

## Release Process

1. Update `CHANGELOG.md` `[Unreleased]` section
2. `just bump part="<patch|minor|major>"`
3. Move `[Unreleased]` to new version in `CHANGELOG.md`
4. `git commit -m "docs: update changelog for vX.Y.Z"` → merge to `main`
5. `just tag` — GitHub Actions creates the release automatically

Changelog section order within a release: Added → Changed → Deprecated → Removed → Fixed → Security.
