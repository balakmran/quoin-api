# AI Agent Instructions

## Project Overview

**QuoinAPI** (pronounced "koyn") is a high-performance, scalable foundation designed to serve as the structural cornerstone for modern Python backends. Built with **FastAPI**, **SQLModel**, and the **Astral stack** (uv, ruff, ty), it provides a battle-tested "Golden Path" for developers who prioritize architectural integrity, type safety, and observability.
*Note: This repository also functions natively as a Copier template. Updating core scaffolding logic dynamically requires syncing standard overrides against `copier.yml` or `scripts/copier_setup.py.jinja`.*

## 🛠 Tech Stack & Tools

- **Framework:** FastAPI
- **Database:** PostgreSQL (using `asyncpg` driver)
- **ORM:** SQLModel (SQLAlchemy wrapper)
- **Migrations:** Alembic
- **Package Manager:** `uv` (Fast Python package installer)
- **Task Runner:** `just`
- **Linting/Formatting:** Ruff
- **Type Checking:** ty (Static type checker via Pyright)
- **Testing:** Pytest, pytest-cov
- **Observability:** OpenTelemetry, Structlog
- **Documentation:** Zensical (MkDocs Material)
- **Quality Pipeline:** `prek` (Rust-based Git Hooks replacing generic pre-commit)

## 🚀 Key Commands (via `just`)

The project uses `just` to automate common tasks.
**Rule:** Use `@` prefix to suppress generic bash statement echoes to stdout. **Do not use emojis or icons** in echo commands to ensure generic terminal compatibility.

| Command                    | Action                                                      |
| :------------------------- | :---------------------------------------------------------- |
| `just setup`               | Setup project (install dependencies and prek hooks).        |
| `just install`             | Install all dependencies (dev included) using `uv`.         |
| `just dev`                 | Start DB, apply migrations, and run the dev server.         |
| `just run`                 | Start the local development server (auto-reload enabled).   |
| `just up`                  | Start all services (App + DB) via Docker Compose.           |
| `just db`                  | Start only the PostgreSQL database container.               |
| `just down`                | Stop and remove all Docker containers.                      |
| `just logs`                | Tail live logs from the API container.                      |
| `just check`               | Run **all** quality checks (format, lint, typecheck, test). |
| `just format`              | Auto-format code with Ruff.                                 |
| `just lint`                | Check code quality with Ruff.                               |
| `just typecheck`           | Verify type annotations with ty.                            |
| `just test`                | Run test suite with coverage (requires DB running).         |
| `just clean`               | Remove build artifacts and cache.                           |
| `just pi`                  | Install prek hooks.                                         |
| `just pr`                  | Run prek hooks on all files.                                |
| `just docb`                | Build documentation.                                        |
| `just ds`                  | Serve documentation locally.                                |
| `just migrate-gen "<msg>"` | Generate a new Alembic migration.                           |
| `just migrate-up`          | Apply pending database migrations.                          |
| `just migrate-down`        | Rollback last migration.                                    |
| `just reset-db`            | Reset DB (stop, restart, re-apply migrations).              |
| `just new <module>`        | Scaffold a new feature module with all required files.      |
| `just bump part="<type>"` | Bump version (patch, minor, major).                         |
| `just tag`                 | Create and push git tag for release.                        |

## 📂 Architecture

The project follows a modular structure within the `app/` directory:

- **`app/main.py`**: Application entry point. Configures lifecycle, middleware,
  and exception handlers.
- **`app/core/`**: Core infrastructure.
  - `config.py`: Application settings using `pydantic-settings` (prioritizes `QUOIN_ENV`).
  - `logging.py`: Structured logging setup (structlog).
  - `metadata.py`: Application metadata (QuoinAPI branding).
  - `openapi.py`: OpenAPI/Swagger configuration.
  - `telemetry.py`: OpenTelemetry instrumentation.
  - `middlewares.py`: Middleware configuration (`*.orb.local` CORS host bounds natively).
  - `exceptions.py`, `exception_handlers.py`: Global error handling (`QuoinError`).
- **`app/db/`**: Database configuration. Engine stored on `app.state.engine`.
- **`app/modules/`**: Feature modules (Domain-Driven Design).
  - Example: `app/modules/user/` contains `models.py`, `schemas.py`,
    `routes.py`, `service.py`, `repository.py`, `exceptions.py`.
  - `system/`: Health checks and system status endpoints.
- **`tests/`**: Test suite mirroring the app structure.
- **`alembic/`**: Database migration scripts.
- **`docs/`**: Zensical-powered documentation site.
- **`scripts/`**: Utility scripts (e.g., docs sync).

## 📝 Development Conventions

### Code Quality

- **Formatting & Linting:** Strictly enforced by **Ruff**.
- **Type Safety:** 100% type hint coverage expected. Checked by `ty`. When silencing type checker warnings, always use a standard blanket comment (`# type: ignore`) rather than MyPy-style categorized tags (e.g., `# type: ignore[arg-type]`). The Pyright engine will fail validation on unrecognized tags.
- **FastAPI Exception Handlers**: Exception handlers injected directly into FastAPI `app.add_exception_handler` MUST map payload signatures to `exc: Any` to satisfy Pyright's strict parameter dependency tracking dynamically.
- **Docstrings:** Google-style docstrings are used (configured in
  `pyproject.toml`).
- **Line Length:** Maximum 80 characters for both Code (Python) and
  Documentation (Markdown). **Exception:** Tables and code blocks are exempt.
- **Quality Checks:** Run `just check` before committing. All checks must pass.
- **Post-Update Check:** After updating any code, you MUST run `just check`. If any errors are found, you must fix them before concluding.

### Coding Standards

- **Python:** Adhere to the
  [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html).
- **General:** For other languages or aspects, refer to the
  [Google Style Guides](https://google.github.io/styleguide/) for consistent
  coding standards across the project.

### Database Changes

- **Never modify the database schema manually.**
- Always define models in code (SQLModel) and run `just migrate-gen "message"`
  to generate a migration script.
- Review the generated migration before applying.
- Apply changes with `just migrate-up`.
- Rollback if needed with `just migrate-down`.

### Configuration & Docker

- Environment variables are managed via `.env` files.
- **Prefix**: All environment variables use `QUOIN_` prefix (e.g., `QUOIN_ENV`, `QUOIN_DB_URL`).
- **Environment**: Controlled by `QUOIN_ENV` (`development`, `test`, `production`).
- **Docker Volumes**: Postgres persistence volumes must strictly map into the parent directory `/var/lib/postgresql` (rather than `/data`) natively targeting Postgres 18 compatibility.
- **Permissions**: Dockerfiles instantiate execution boundaries bound strictly to the `quoin` non-root user.

### Testing Boundaries

- Tests are written using `pytest`.
- Run `just test` to execute the suite with coverage.
- Run `just check` to run all quality checks (includes tests).
- Ensure ≥95% test coverage for new features.
- **Integration Preference**: Tests execute HTTPX clients natively over real database engines hooking `SAVEPOINT` rollbacks.
- **Fixture Event Scope**: The `initialize_db` teardown fixture in `conftest.py` MUST remain explicitly on the `function` scope. Attempting to optimize schema provisioning to `session` scope causes critical ASGI worker pool loop closures against `asyncpg`. Tests must remain globally isolated to execute in `< 3 seconds`.

## 🔑 Key Files

- `justfile`: Definition of all executable task commands.
- `pyproject.toml`: Project configuration, dependencies, and tool settings.
- `docker-compose.yml`: Definition of local dev services (Postgres, QuoinAPI).
- `Dockerfile`: Production-ready container image.
- `app/main.py`: The FastAPI application factory.
- `zensical.toml`: Documentation site configuration.

### 🧩 Feature Module Template

When creating a new module (e.g., `app/modules/product/`), follow this
structure:

- `models.py`: SQLModel database tables.
- `schemas.py`: Pydantic models for Request/Response. **Rule**: Always map validation of emails specifically to `EmailStr` symmetrically.
- `repository.py`: CRUD operations (database interaction only).
- `service.py`: Business logic (calls repository).
- `routes.py`: FastAPI router endpoints (calls service).
- `exceptions.py`: Module-specific exceptions inheriting from `QuoinError`.
- `__init__.py`: Expose the router as `router`.

**Scaffold quickly with**:

```bash
just new <module_name>
```

This creates the full module skeleton in `app/modules/<module>/`
and a test stub in `tests/modules/<module>/`.


**Example workflow**:

1. Create models in `models.py`
2. Generate migration: `just migrate-gen "add product model"`
3. Create schemas in `schemas.py`
4. Implement repository in `repository.py`
5. Implement service in `service.py`
6. Create routes in `routes.py`
7. Register router in `app/api.py`
8. Write tests in `tests/modules/product/`

### 🧪 Testing Guidelines

- **Fixtures:** Use `conftest.py` for shared resources (db session, async client).
- **Integration over Unit:** Prioritize integration tests for routes
  (`tests/modules/user/test_routes.py`).
- **Mocking:** Mock external APIs, but use a real (test) database for repository tests.
- **Naming:** Test functions must start with `test_` and be descriptive.
- **Coverage:** Maintain ≥95% coverage. View reports with
  `pytest --cov=app --cov-report=html`.
- **API Versioning**: All endpoints must be prefixed with `/api/v1/`.

### 📦 Git & Commits

- **Conventional Commits:** Use the format `<type>(<scope>): <description>`.
  - Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`.
- **Prek Hooks:** Fast pipeline git-hooks executed natively via `prek` (replaces standard pre-commit). Install with `just pi`, run manually with `just pr`.
- **Branches:** Feature branches from `main`, merge via PR.

### ⚠️ Error Handling

- Use the custom `QuoinError` (or specific subclasses) for logic errors.
- **Do not** raise generic HTTPExceptions (`HTTPException(status_code=400)`) in
  services; raise domain exceptions instead, and let the router or exception
  handler map them to HTTP status codes.
- **Available exceptions**: `NotFoundError`, `ConflictError`, `BadRequestError`,
  `ForbiddenError`, `InternalServerError`.
- Exception handlers map FastAPI `RequestValidationError` structs directly to standardized JSON outputs seamlessly.

### 🚀 Release Process

- **Versioning:** Use Semantic Versioning (Major.Minor.Patch).
- **Workflow:**
  1. Update `CHANGELOG.md` [Unreleased] section
  2. Run `just bump <type>` (patch/minor/major)
  3. Update `CHANGELOG.md` - move [Unreleased] to new version
  4. Commit changelog: `git commit -m "docs: update changelog for vX.Y.Z"`
  5. Merge to `main`
  6. Run `just tag` to create and push git tag
  7. GitHub Actions automatically creates release

- **Changelog:**
  - **Update Policy**: `CHANGELOG.md` MUST be updated after **every** meaningful
    code change.
  - **Section Order**: Within a release, group changes in the following strict
    order:
    1. `### Added` (for new features)
    2. `### Changed` (for changes in existing functionality)
    3. `### Deprecated` (for soon-to-be removed features)
    4. `### Removed` (for now removed features)
    5. `### Fixed` (for any bug fixes)
    6. `### Security` (in case of vulnerabilities)
  - Always update the `[Unreleased]` section until a new version is bumped.

### 📚 Documentation

- **Source:** All docs in `docs/` directory
- **Build:** Run `just docb` to build docs
- **Serve:** Run `just ds` to serve locally at `http://localhost:8001`
- **Sync:** Project files (CONTRIBUTING.md, CHANGELOG.md, LICENSE) are
  automatically synced to `docs/project/` during build
- **Navigation:** Configured in `zensical.toml`

**Guide Structure**:

1. Getting Started
2. Configuration
3. Database Migrations
4. Error Handling
5. Testing
6. Quality Checks
7. Observability
8. Deployment
9. Release Workflow
10. Troubleshooting
