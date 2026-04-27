---
title: Home
---

# QuoinAPI

[![CI](https://github.com/balakmran/quoin-api/actions/workflows/ci.yml/badge.svg)](https://github.com/balakmran/quoin-api/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.135.3-teal.svg)](https://fastapi.tiangolo.com/)
[![SQLModel](https://img.shields.io/badge/SQLModel-0.0.38-blue.svg)](https://sqlmodel.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

![QuoinAPI](assets/images/quoin-api-banner.png)

> **The architectural cornerstone for high-performance, scalable Python services.**

**QuoinAPI** (pronounced "koyn") is a high-performance, scalable foundation
designed to serve as the structural cornerstone for modern Python backends.
Built with **FastAPI**, **SQLModel**, and the **Astral stack** (uv, ruff, ty),
it provides a battle-tested "Golden Path" for developers who prioritize
architectural integrity, type safety, and observability.

## Key Highlights

#### High-Performance Core

- **Async-first** patterns with FastAPI and async PostgreSQL via `asyncpg`
- **Lightning-fast tooling** powered by `uv` for dependency management
- **Optimized** for production workloads with connection pooling

#### Structural Integrity

- **100% type-annotated** code verified by `ty` and strict linting via `ruff`
- **Domain-driven design** with module-level exceptions and rich error context
- **API versioning** with `/api/v1/` prefix for future-proof evolution

#### Built-in Observability

- **Integrated OpenTelemetry** for distributed tracing
- **Structured logging** with Structlog for machine-readable logs
- **Health checks** and readiness endpoints out of the box

#### Architectural Efficiency

- **Ready-to-use template** that eliminates boilerplate
- **Environment-based configuration** with `.env` file selection
- **Just-based automation** for common development tasks

## Tech Stack

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

Learn more about our [technology choices and decision log →](architecture/decision-log.md)

## Quick Start

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

**Need help?** Check out the [Getting Started Guide →](guides/getting-started.md)

## Running Application

![QuoinAPI Home Page](assets/images/quoin-api-homepage.png)

The application home page provides real-time health indicators and quick links
to API documentation.

## ️Architecture

```mermaid
graph TB
    Client[Client/Browser] -->|HTTP| FastAPI[FastAPI Application]
    FastAPI -->|Business Logic| Service[Service Layer]
    Service -->|Database Access| Repository[Repository Layer]
    Repository -->|SQL| PostgreSQL[(PostgreSQL)]

    FastAPI -->|Structured Logs| Structlog[Structlog]
    FastAPI -->|Traces| OTEL[OpenTelemetry]

    Service -->|Domain Exceptions| Handlers[Exception Handlers]
    Handlers -->|JSON Response| Client
```

Read the [full architecture documentation →](architecture/overview.md)

## Project Structure

```plaintext
├── app/
│   ├── core/
│   │   ├── config.py             # Pydantic settings
│   │   ├── exception_handlers.py # Global exception handlers
│   │   ├── exceptions.py         # Custom exceptions
│   │   ├── logging.py            # Structlog configuration
│   │   ├── metadata.py           # Application metadata
│   │   ├── middlewares.py        # Middleware configuration
│   │   ├── openapi.py            # OpenAPI configuration
│   │   ├── schemas.py            # Pydantic schemas
│   │   ├── security.py           # Security utilities
│   │   └── telemetry.py          # OpenTelemetry instrumentation
│   ├── db/                       # Database connection & base models
│   │   ├── base.py               # Base models
│   │   └── session.py            # Database session
│   ├── modules/
│   │   ├── system/               # System health & status
│   │   └── user/                 # User management module
│   │       ├── exceptions.py     # Domain-specific exceptions
│   │       ├── models.py         # SQLModel database tables
│   │       ├── schemas.py        # Pydantic request/response models
│   │       ├── repository.py     # Database access (CRUD)
│   │       ├── service.py        # Business logic
│   │       └── routes.py         # FastAPI router endpoints
│   ├── static/                   # Static assets
│   ├── templates/                # Jinja2 templates
│   │   └── index.html            # Home page
│   ├── api.py                    # API Route structure
│   └── main.py                   # Application entry point
├── tests/                        # Pytest test suite
├── alembic/                      # Database migrations
├── docs/                         # This documentation
├── scripts/                      # Utility scripts
├── .env.example                  # Environment variables template
├── docker-compose.yml            # Local dev environment
├── Dockerfile                    # Production Docker image
├── AGENTS.md                     # AI Agent instructions
├── justfile                      # Task runner
└── pyproject.toml                # Dependencies & config
```

## Documentation

| Section                                      | Description                                                                                                             |
| -------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| **[Guides](guides/getting-started.md)**      | Step-by-step guides for getting started, configuration, error handling, testing, database migrations, and observability |
| **[Architecture](architecture/overview.md)** | System architecture overview, design decisions, component diagrams, and data flow                                       |
| **[API Reference](api/overview.md)**         | Complete API documentation with core modules, user module, REST endpoints, and code examples                            |
| **[Project Info](project/contributing.md)**  | Contributing guide, changelog, license (MIT), and GitHub repository                                                     |

## Roadmap

See the [Roadmap](project/roadmap.md) for planned features and upcoming milestones.

## Contributing

We welcome contributions! Please read our [Contributing Guide](project/contributing.md)
to learn about our development process, coding standards, and how to submit pull
requests.

## License

This project is licensed under the **MIT License**. See the [LICENSE](project/license.md)
for details.
