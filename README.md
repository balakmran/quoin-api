# QuoinAPI

[![CI](https://github.com/balakmran/quoin-api/actions/workflows/ci.yml/badge.svg)](https://github.com/balakmran/quoin-api/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**The architectural cornerstone for high-performance, scalable Python services.**

![QuoinAPI](docs/assets/images/quoin-api-banner.png)

QuoinAPI (pronounced "koyn") is a high-performance, scalable foundation designed to serve as the structural cornerstone for modern Python backends. Built with FastAPI, SQLModel, and the Astral stack (uv, ruff, ty), it provides a battle-tested "Golden Path" for developers who prioritize architectural integrity, type safety, and observability.

## 🏗️ Key Highlights

### High-Performance Core

- **Async-first** patterns with FastAPI and async PostgreSQL via `asyncpg`
- **Lightning-fast tooling** powered by `uv` for dependency management
- **Optimized** for production workloads with connection pooling

### Structural Integrity

- **100% type-annotated** code verified by `ty` and strict linting via `ruff`
- **Domain-driven design** with module-level exceptions and rich error context
- **API versioning** with `/api/v1/` prefix for future-proof evolution

### Built-in Observability

- **Integrated OpenTelemetry** for distributed tracing
- **Structured logging** with Structlog for machine-readable logs
- **Health checks** and readiness endpoints out of the box

### Architectural Efficiency

- **Ready-to-use template** that eliminates boilerplate
- **Environment-based configuration** with `.env` file selection
- **Just-based automation** for common development tasks

## 🛠 Tech Stack & Tools

- **Framework:** FastAPI
- **Database:** PostgreSQL (using `asyncpg` driver)
- **ORM:** SQLModel (SQLAlchemy wrapper)
- **Migrations:** Alembic
- **Package Manager:** `uv` (Fast Python package installer)
- **Task Runner:** `just`
- **Linting/Formatting:** Ruff
- **Type Checking:** ty (Static type checker)
- **Testing:** Pytest, pytest-cov
- **Observability:** OpenTelemetry, Structlog
- **Documentation:** Zensical (MkDocs Material)

## 🚀 Use as a Template

QuoinAPI is designed to be used as a project generator via [Copier](https://copier.readthedocs.io/). To create a new API project using this architecture, first install Copier:

```bash
uv tool install copier
# OR
pipx install copier
```

Then generate your project:

```bash
copier copy https://github.com/balakmran/quoin-api.git my-awesome-api --trust
```

Copier will prompt you for your project name, database prefixes, and other configuration variables.

## ⚡️ Quick Start

```bash
# 1. Clone the repository and configure environment
git clone https://github.com/balakmran/quoin-api.git
cd quoin-api
cp .env.example .env

# 2. Setup project (install dependencies & pre-commit hooks)
just setup

# 3. Start DB, apply migrations, and run the server
just dev
```

Visit the API documentation at
[http://localhost:8000/docs](http://localhost:8000/docs).

## 📂 Project Structure

```plaintext
├── app/
│   ├── core/
│   │   ├── config.py             # Pydantic settings
│   │   ├── exceptions.py         # Custom exceptions
│   │   ├── exception_handlers.py # Global exception handlers
│   │   ├── logging.py            # Structlog configuration
│   │   ├── metadata.py           # Application metadata
│   │   ├── middlewares.py        # Middleware configuration
│   │   ├── openapi.py            # OpenAPI metadata & config
│   │   └── telemetry.py          # OpenTelemetry instrumentation
│   ├── db/                       # Database connection & base models
│   │   ├── session.py            # Database session
│   │   └── base.py               # Base models
│   ├── modules/
│   │   └── user/                 # Example domain module
│   │       ├── exceptions.py     # Domain-specific exceptions
│   │       ├── models.py         # SQLModel database tables
│   │       ├── schemas.py        # Pydantic request/response models
│   │       ├── repository.py     # Database access (CRUD)
│   │       ├── service.py        # Business logic
│   │       └── routes.py         # FastAPI router endpoints
│   ├── static/                   # Static assets (css, img)
│   ├── templates/                # Jinja2 templates
│   │   └── index.html            # Home page
│   ├── api.py                    # API Route structure
│   └── main.py                   # App entry point
├── tests/                        # Pytest suite
├── alembic/                      # Database migrations
├── docs/                         # Documentation
├── .env.example                  # Environment variables template
├── docker-compose.yml            # Local dev environment
├── Dockerfile                    # Production Docker image
├── AGENTS.md                     # AI Agent instructions
├── justfile                      # Command runner
├── pyproject.toml                # Dependencies & config
└── zensical.toml                 # Documentation config
```

## 📚 Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.

## 📜 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for details on how to contribute to this
project.

## License

This project is licensed under the terms of the [MIT license](LICENSE).
