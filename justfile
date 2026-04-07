# Justfile

# Set environment variables from .env file
set dotenv-load

# List all recipes
default:
    just --list

# Aliases
alias pi := prek-install
alias pr := prek-run
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

# Install pre-commit hooks
prek-install:
    uv run prek install

# Run pre-commit hooks on all files
prek-run:
    uv run prek run --all-files

# =============================================================================
# Database
# =============================================================================

# Start only the database container
db:
    docker compose up -d db

# Generate a new migration
migrate-gen message:
    uv run alembic revision --autogenerate -m "{{message}}"

# Apply migrations
migrate-up:
    uv run alembic upgrade head

# =============================================================================
# Docker
# =============================================================================

# Start Docker containers (all services)
up:
    VERSION=$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml) docker compose up -d --build

# Stop Docker containers
down:
    docker compose down

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

# Run tests with coverage
test:
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
