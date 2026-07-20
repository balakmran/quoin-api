# QuoinAPI

[![CI](https://github.com/balakmran/quoin-api/actions/workflows/ci.yml/badge.svg)](https://github.com/balakmran/quoin-api/actions/workflows/ci.yml)
[![Docs](https://github.com/balakmran/quoin-api/actions/workflows/docs.yml/badge.svg)](https://github.com/balakmran/quoin-api/actions/workflows/docs.yml)
[![Release](https://img.shields.io/github/v/release/balakmran/quoin-api)](https://github.com/balakmran/quoin-api/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.139.2-teal.svg)](https://fastapi.tiangolo.com/)
[![SQLModel](https://img.shields.io/badge/SQLModel-0.0.39-blue.svg)](https://sqlmodel.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-18-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![ty](https://img.shields.io/badge/ty-type_checked-8b5cf6)](https://github.com/astral-sh/ty)
[![prek](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/j178/prek/master/docs/assets/badge-v0.json)](https://github.com/j178/prek)

**The Foundation for your Python backend API.**

QuoinAPI (pronounced "koyn") is a production-ready Python backend
foundation built with FastAPI, SQLModel, and the Astral stack
(uv, ruff, ty). It gives you a battle-tested starting point with
type safety, observability, and clean architecture out of the box.

## Contents

- [Key Highlights](#key-highlights)
- [Tech Stack](#tech-stack)
- [Use as a Template](#use-as-a-template)
- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [Documentation](#documentation)
- [AI-Assisted Development](#ai-assisted-development)
- [Contributing](#contributing)
- [Roadmap](#roadmap)
- [Changelog](#changelog)
- [License](#license)

## Key Highlights

- **Async-first** — FastAPI with async PostgreSQL via `asyncpg` and connection pooling
- **Type-safe** — 100% annotated, checked by `ty` and linted by `ruff`
- **Clean architecture** — domain-driven modules with rich, module-level exceptions
- **Versioned API** — `/api/v1/` prefix for future-proof evolution
- **Observable** — OpenTelemetry tracing, Structlog structured logs, health/readiness probes
- **Batteries included** — `.env` config, `just` automation, and a Copier template to skip the boilerplate
- **AI-ready** — project-specific Claude Code skills, quality-enforcement hooks, and subagents, pre-wired

## Tech Stack

- **Framework:** FastAPI
- **Database:** PostgreSQL (using `asyncpg` driver)
- **ORM:** SQLModel (SQLAlchemy wrapper)
- **Migrations:** Alembic
- **Package Manager:** `uv` (Fast Python project & package manager)
- **Task Runner:** `just`
- **Linting/Formatting:** Ruff
- **Type Checking:** ty (Static type checker)
- **Testing:** Pytest, pytest-cov
- **Observability:** OpenTelemetry, Structlog
- **Documentation:** Zensical

## Use as a Template

QuoinAPI is a project generator via [Copier](https://copier.readthedocs.io/).
Generate a new API in one command — [`uvx`](https://docs.astral.sh/uv/) runs
Copier without installing it:

```bash
uvx copier copy https://github.com/balakmran/quoin-api.git my-awesome-api --trust
```

Copier prompts for your project name, database prefixes, and other configuration.

## Quick Start

### Prerequisites

- [Python 3.12+](https://www.python.org/downloads/)
- [`uv`](https://docs.astral.sh/uv/) — package & environment manager
- [`just`](https://github.com/casey/just) — task runner
- [Docker](https://www.docker.com/) — for the local PostgreSQL and mock OAuth services

### Setup

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

Run the full quality gate (format, lint, typecheck, test) any time with
`just check`.

## Project Structure

```plaintext
├── app/
│   ├── core/
│   │   ├── config.py             # Pydantic settings
│   │   ├── exceptions.py         # Custom exceptions
│   │   ├── exception_handlers.py # Global exception handlers
│   │   ├── lifecycle.py          # Graceful-shutdown request tracking
│   │   ├── logging.py            # Structlog configuration
│   │   ├── metadata.py           # Application metadata
│   │   ├── middlewares.py        # Middleware configuration
│   │   ├── openapi.py            # OpenAPI metadata & config
│   │   ├── pagination.py         # Pagination & sorting for lists
│   │   ├── schemas.py            # Shared response schemas (Problem Details)
│   │   ├── security.py           # OAuth2/OIDC auth & require_roles (RBAC)
│   │   ├── telemetry.py          # OpenTelemetry instrumentation
│   │   └── versioning.py         # Endpoint deprecation signalling
│   ├── db/                       # Database connection & base models
│   │   ├── session.py            # Database session
│   │   └── base.py               # Base models
│   ├── http/                     # Outbound HTTP client
│   │   └── client.py             # Shared async httpx client
│   ├── modules/
│   │   ├── system/               # Health, readiness & home-page routes
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
├── CLAUDE.md                     # AI agent instructions
├── justfile                      # Command runner
├── pyproject.toml                # Dependencies & config
└── zensical.toml                 # Documentation config
```

## Documentation

Full documentation is published at
**[balakmran.github.io/quoin-api](https://balakmran.github.io/quoin-api/)**.
Start here:

- [Getting Started](docs/guides/getting-started.md) — install, run, and explore the API
- [Configuration](docs/guides/configuration.md) — every `QUOIN_` setting and its default
- [Authentication](docs/guides/authentication.md) — OAuth 2.0 / OIDC and role-based access
- [Creating a Module](docs/guides/creating-a-module.md) — add a new domain to the API

Browse the full set under [`docs/guides/`](docs/guides/), or serve them
locally with `just docs-serve`.

## AI-Assisted Development

This project has a Claude Code setup with project-specific skills,
quality-enforcement hooks, and live SDK documentation via MCP.
See the [AI-Assisted Development guide](docs/guides/ai-setup.md) for
the full reference.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for details on how to contribute to this
project.

## Roadmap

See [ROADMAP.md](ROADMAP.md) for planned features and upcoming milestones.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.

## License

This project is licensed under the terms of the [MIT license](LICENSE).
