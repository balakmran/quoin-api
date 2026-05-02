---
title: Docs
---

# QuoinAPI

[![CI](https://github.com/balakmran/quoin-api/actions/workflows/ci.yml/badge.svg)](https://github.com/balakmran/quoin-api/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.135.3-teal.svg)](https://fastapi.tiangolo.com/)
[![SQLModel](https://img.shields.io/badge/SQLModel-0.0.38-blue.svg)](https://sqlmodel.tiangolo.com/)
[![prek](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/j178/prek/master/docs/assets/badge-v0.json)](https://github.com/j178/prek)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**QuoinAPI** (pronounced "koyn") is a high-performance, scalable foundation
for modern Python backends. Built with **FastAPI**, **SQLModel**, and the
**Astral stack** (uv, ruff, ty), it provides a battle-tested "Golden Path"
for developers who prioritize architectural integrity, type safety, and
observability.

New here? Start with the [Getting Started Guide](guides/getting-started.md).

## Quick Start

=== "Using Copier (recommended)"

    ```bash
    copier copy gh:balakmran/quoin-api my-api
    cd my-api
    cp .env.example .env
    just setup
    just dev
    ```

=== "Clone directly"

    ```bash
    git clone https://github.com/balakmran/quoin-api.git my-api
    cd my-api
    cp .env.example .env
    just setup
    just dev
    ```

Visit [http://localhost:8000/docs](http://localhost:8000/docs) for the
interactive API docs.

### Key recipes

| Command | What it does |
|---|---|
| `just setup` | Install deps and wire commit hooks — run once |
| `just dev` | Start Postgres, mock OAuth, apply migrations, and run the server |
| `just new <module>` | Scaffold a complete DDD module (models, schemas, repo, service, routes) |
| `just check` | Run format → lint → typecheck → test in one gate |
| `just migrate-gen "<msg>"` | Generate an Alembic migration from your model changes |
| `just token` | Mint a signed JWT against the local mock OAuth server |

!!! tip "Run `just --list` for the full menu."

## Architecture

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

Read the [full architecture documentation →](architecture/overview.md).

## Tech Stack

- **Framework:** FastAPI
- **Database:** PostgreSQL (using `asyncpg` driver)
- **ORM:** SQLModel (SQLAlchemy wrapper)
- **Migrations:** Alembic
- **Package Manager:** `uv`
- **Task Runner:** `just`
- **Linting/Formatting:** Ruff
- **Type Checking:** ty
- **Pre-commit Hooks:** prek
- **Testing:** Pytest, pytest-cov
- **Observability:** OpenTelemetry, Structlog
- **Documentation:** Zensical (MkDocs Material)

See the [decision log](architecture/decision-log.md) for the reasoning
behind these choices.

## Where next

- [Guides](guides/getting-started.md) — setup, development, operations
- [Architecture](architecture/overview.md) — system design and decisions
- [API Reference](api/overview.md) — module and endpoint documentation
- [Roadmap](project/roadmap.md) — what's planned and shipped
- [Contributing](project/contributing.md) — how to get involved
