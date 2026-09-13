# QuoinAPI

[![CI](https://github.com/balakmran/quoin-api/actions/workflows/ci.yml/badge.svg)](https://github.com/balakmran/quoin-api/actions/workflows/ci.yml)
[![Docs](https://github.com/balakmran/quoin-api/actions/workflows/docs.yml/badge.svg)](https://github.com/balakmran/quoin-api/actions/workflows/docs.yml)
[![Release](https://img.shields.io/github/v/release/balakmran/quoin-api)](https://github.com/balakmran/quoin-api/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-teal.svg)](https://fastapi.tiangolo.com/)
[![SQLModel](https://img.shields.io/badge/SQLModel-blue.svg)](https://sqlmodel.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-18-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![ty](https://img.shields.io/badge/ty-type_checked-8b5cf6)](https://github.com/astral-sh/ty)
[![prek](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/j178/prek/master/docs/assets/badge-v0.json)](https://github.com/j178/prek)

**The Foundation for your Python backend API.**

QuoinAPI (pronounced "koyn") is a production-ready Python backend
foundation built with FastAPI, SQLModel, PostgreSQL, and the Astral
stack (uv, ruff, ty). It's a working API and a
[Copier](https://copier.readthedocs.io/) template in one.

It's for teams starting a new async Python API who want auth,
observability, migrations, and CI already wired, rather than a minimal
hello-world they have to grow themselves.

## Key Highlights

- **Async-first** — FastAPI with async PostgreSQL via `asyncpg` and
  connection pooling
- **Type-safe** — 100% annotated, checked by `ty` and linted by `ruff`
- **Clean architecture** — domain-driven modules:
  route → service → repository → Postgres
- **Auth built in** — OAuth 2.0 / OIDC JWT validation and role-based
  access with `require_roles`
  ([guide](docs/guides/authentication.md))
- **Consistent errors** — domain exceptions rendered as RFC 9457
  Problem Details ([guide](docs/guides/error-handling.md))
- **List endpoints done right** — pagination and sorting
  ([guide](docs/guides/pagination.md))
- **Data-safety patterns** — soft delete
  ([guide](docs/guides/soft-delete.md)) and optimistic concurrency
  ([guide](docs/guides/optimistic-concurrency.md))
- **API evolution** — `/api/v1/` prefix and endpoint deprecation
  signalling ([guide](docs/guides/deprecating-endpoints.md))
- **Observable** — OpenTelemetry tracing, Structlog structured logs,
  health/readiness probes ([guide](docs/guides/observability.md))
- **Production-minded** — graceful shutdown, non-root Docker image,
  and a shared outbound HTTP client
  ([guide](docs/guides/outbound-http.md))
- **Quality gates everywhere** — `just check`, prek commit/push hooks,
  and CI
- **AI-ready** — project-specific Claude Code skills,
  quality-enforcement hooks, and subagents, pre-wired

## Start a New Project

Generate a new API from the template —
[`uvx`](https://docs.astral.sh/uv/) runs Copier without installing it:

```bash
uvx copier copy --trust gh:balakmran/quoin-api my-api
```

Copier prompts for your project name, env-var prefix, description, and
author details, then rewrites the project to match. The generated
project gets its own starter README, and QuoinAPI-specific pages such
as the roadmap and changelog are left out.

## Work on QuoinAPI Itself

### Prerequisites

- [Python 3.12+](https://www.python.org/downloads/)
- [`uv`](https://docs.astral.sh/uv/) — package & environment manager
- [`just`](https://github.com/casey/just) — task runner
- [Docker](https://www.docker.com/) — for the local PostgreSQL and mock
  OAuth services

### Setup

```bash
# 1. Clone the repository and configure environment
git clone https://github.com/balakmran/quoin-api.git
cd quoin-api
cp .env.example .env

# 2. Install dependencies and prek commit + pre-push hooks
just setup

# 3. Start Postgres + mock OAuth, apply migrations, and run the server
just dev
```

Visit the interactive API docs at
[http://localhost:8000/docs](http://localhost:8000/docs).

| Service          | Port |
| ---------------- | ---- |
| API              | 8000 |
| PostgreSQL       | 5432 |
| Mock OAuth2/OIDC | 8080 |

### Make an authenticated request

With `just dev` running, mint a token from the mock OAuth server in a
second terminal and call a protected endpoint:

```bash
TOKEN=$(just token --roles="users.read,users.write")
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/users/
```

### Quality checks

Run the full gate (format, lint, typecheck, migration check, tests) any
time with `just check`. The pre-push hook runs the test suite, so
Postgres must be running (`just db`) when you push.

## Project Structure

```plaintext
├── app/
│   ├── core/          # Config, security, errors, logging, telemetry, middleware
│   ├── db/            # Async engine and session dependency
│   ├── http/          # Shared outbound HTTP client
│   ├── modules/
│   │   ├── system/    # Health, readiness & home-page routes
│   │   └── user/      # Example domain module to mirror
│   ├── api.py         # Router registration under /api/v1/
│   └── main.py        # App factory
├── alembic/           # Database migrations
├── docs/              # Documentation site (Zensical)
├── scripts/           # Tooling and Copier post-generation setup
├── tests/             # Integration tests against a real database
├── copier.yml         # Template configuration
├── docker-compose.yml # Local Postgres, mock OAuth, and API
└── justfile           # Task runner recipes
```

See the [architecture overview](docs/architecture/overview.md) for how
the pieces fit together.

## Documentation

Full documentation is published at
**[balakmran.github.io/quoin-api](https://balakmran.github.io/quoin-api/)**.
Start here:

- [Getting Started](docs/guides/getting-started.md) — install, run,
  and explore the API
- [Configuration](docs/guides/configuration.md) — every `QUOIN_`
  setting and its default
- [Authentication](docs/guides/authentication.md) — OAuth 2.0 / OIDC
  and role-based access
- [Creating a Module](docs/guides/creating-a-module.md) — add a new
  domain to the API
- [Deployment](docs/guides/deployment.md) — run it in production
- [AI-Assisted Development](docs/guides/ai-setup.md) — Claude Code
  skills, hooks, and subagents

Browse the full set under [`docs/guides/`](docs/guides/), or serve them
locally with `just docs-serve`.

## Project

- [Contributing](CONTRIBUTING.md) — how to contribute
- [Security Policy](SECURITY.md) — how to report a vulnerability
- [Roadmap](ROADMAP.md) — planned features and milestones
- [Changelog](CHANGELOG.md) — version history
- [License](LICENSE) — MIT
