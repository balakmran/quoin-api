# Justfile
# NOTE: Do not use emojis or icons in echo commands to ensure standard terminal compatibility.
# Set environment variables from .env file
set dotenv-load

# List all recipes
default:
    just --list

# Aliases
alias pi := prek-install
alias pr := prek-run
alias au := audit
alias docb := docs-build
alias ds := docs-serve
alias release := tag

# =============================================================================
# Development
# =============================================================================

# Setup project (install dependencies and pre-commit hooks)
setup: install prek-install

# Install all dependencies
install:
    uv sync --all-groups

# Clean build artifacts and cache
clean:
    @find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    @find . -type f -name "*.pyc" -delete 2>/dev/null || true
    @find . -type f -name "*.pyo" -delete 2>/dev/null || true
    @find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
    @find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
    @find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
    @find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
    @find . -type d -name "site" -exec rm -rf {} + 2>/dev/null || true
    @find . -type d -name ".cache" -exec rm -rf {} + 2>/dev/null || true
    @find . -type f -name ".coverage" -delete 2>/dev/null || true
    @echo "Clean complete!"

# Run local development server
run:
    uv run fastapi dev app/main.py

# Start DB + OAuth, apply migrations, and run the dev server
dev: db oauth migrate-up run

# Install pre-commit + pre-push hooks
prek-install:
    uv run prek install
    uv run prek install --hook-type pre-push

# Run pre-commit hooks on all files
prek-run:
    uv run prek run --all-files

# =============================================================================
# Git
# =============================================================================

# Switch to main, pull, and delete local branches whose remote is gone
sync-main:
    @git checkout main
    @git pull --prune
    @git branch -vv | awk '/: gone]/{print $1}' | xargs -r git branch -D
    @echo "On main, up to date, stale branches pruned."

# =============================================================================
# Scaffolding
# =============================================================================

# Scaffold a new feature module (e.g. just new product)
new module:
    @uv run python scripts/scaffold_module.py {{module}}

# =============================================================================
# Database
# =============================================================================

# Start only the database container
db:
    docker compose up -d --wait db

# Ensure the database container is running (internal guard; auto-starts it)
_db-check:
    @# Skip in GitHub Actions/CI, where Postgres is provisioned natively
    @if [ "${CI:-}" != "true" ]; then \
        docker compose ps db --format json 2>/dev/null | grep -q 'running' \
            || (echo "" && echo "Database not running; starting it..." && echo "" && docker compose up -d --wait db); \
    fi

# Generate a new migration (scans the result for unsafe operations)
migrate-gen message:
    uv run alembic revision --autogenerate -m "{{message}}"
    @uv run python scripts/migration_guard.py

# Apply pending database migrations
migrate-up:
    uv run alembic upgrade head

# Rollback the last database migration
migrate-down:
    uv run alembic downgrade -1

# Reset the database (stop, restart, and re-apply migrations)
reset-db:
    docker compose down -v
    docker compose up -d --wait db
    uv run alembic upgrade head
    @echo "Database reset complete!"

# =============================================================================
# Docker
# =============================================================================

# Start Docker containers (all services)
up:
    VERSION=$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml) docker compose up -d --build

# Start only the mock OAuth server
oauth:
    @docker compose up oauth -d --wait --wait-timeout 60

# Generate an access token from the mock OAuth server
@token +args="":
    python3 scripts/gen_token.py {{args}}

# Stop Docker containers
down:
    docker compose down

# Tail live logs from the API container
logs:
    docker compose logs -f api

# =============================================================================
# Quality
# =============================================================================

# Run linting
lint:
    @uv run ruff check . --fix

# Run formatting
format:
    @uv run ruff format .

# Run type checking
typecheck:
    @uv run ty check

# Run tests with coverage (auto-starts the DB if needed)
test: _db-check
    @uv run pytest -q --cov=app --cov-report=html --cov-report=term:skip-covered --tb=line tests/

# Run all quality checks
check:
    @echo ""
    @echo "Running formatter..."
    @echo "-----------------------------"
    @just format
    @echo ""
    @echo "Running linter..."
    @echo "-----------------------------"
    @just lint
    @echo ""
    @echo "Running type checker..."
    @echo "-----------------------------"
    @just typecheck
    @echo ""
    @echo "Running tests..."
    @echo "-----------------------------"
    @just test
    @echo ""
    @echo "All checks passed!"
    @echo ""

# =============================================================================
# Security
# =============================================================================

# Advisory IDs accepted after review. Every entry needs a dated comment in
# docs/guides/dependency-scanning.md explaining why it is tolerated.
audit_ignore := ""

# Scan the locked dependency tree for known CVEs (queries OSV; needs network)
audit *args:
    @uv audit --preview-features audit-command --locked {{ audit_ignore }} {{ args }}

# Audit only what ships in the container (runtime deps, no dev/test/docs groups)
audit-prod:
    @just audit --no-default-groups

# Bump one package to its newest compatible release, then re-audit
audit-fix package:
    @uv lock --upgrade-package {{ package }}
    @uv sync --all-groups
    @just audit

# =============================================================================
# Documentation
# =============================================================================

# Build documentation
docs-build:
    @uv run python scripts/sync_docs.py
    @uv run python -m zensical build --clean

# Serve documentation locally
docs-serve:
    @uv run python -m zensical serve --dev-addr localhost:8001

# =============================================================================
# Release
# =============================================================================

# Bump version
bump part="patch":
    @uv run python scripts/bump_version.py {{part}}

# Create and push git tag for current version
tag:
    @uv run python scripts/tag_release.py

# Verify `copier update` applies cleanly between two template tags
verify-template-update previous current:
    uv run python scripts/verify_template_update.py {{previous}} {{current}}
