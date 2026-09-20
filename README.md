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

- **Stays current** — later template releases merge into your code with a
  single `copier update`, so your project keeps getting fixes instead of
  aging into a snapshot.
- **Secure by default** — security headers, a Host allowlist, strict
  CORS, and request size and time limits ship wired up, and an
  incomplete production config fails at startup rather than in traffic.
- **Auth ready for your IdP** — point it at any OIDC provider for JWT
  validation and per-route role checks, with a local mock server minting
  real tokens so you can build against auth immediately.
- **One error contract** — every failure, including 404s and uncaught
  500s, returns an RFC 9457 problem document, and list endpoints share
  one paginated envelope.
- **Ready to run in production** — logs and traces correlate by request
  and caller, in-flight requests drain on shutdown, and outbound calls
  retry behind a per-host circuit breaker.
- **Your schema can't drift** — the test schema is built from your
  migrations, so a model change without a matching migration fails the
  gate before merge.
- **Great DX with modern tooling** — uv, ruff, ty, just, and prek, where
  `just dev` starts the stack, `just new` scaffolds a module, and
  `just check` runs the same gate as CI.
- **AI-ready** — 12 Claude Code skills, 2 subagents, and 6 hooks ship
  pre-wired so an assistant follows your conventions and can't edit
  files it shouldn't.

## Start a New Project

You need [`uv`](https://docs.astral.sh/uv/),
[`just`](https://github.com/casey/just), and
[Docker](https://www.docker.com/). `uvx` runs Copier without installing
it:

```bash
uvx copier copy --trust gh:balakmran/quoin-api my-api
```

Copier asks for your project name, folder slug, environment-variable
prefix, description, and author details, then rewrites the project to
match: the `QUOIN_` prefix becomes yours, `QuoinAPI` becomes your
project name, and template-only pages such as the roadmap and changelog
are left out. The generated project gets its own starter README.

`--trust` is required because the template runs a post-generation
script. Read
[`scripts/copier_setup.py.jinja`](scripts/copier_setup.py.jinja) first
if you want to see what it does.

### Run it

```bash
cd my-api
git init                # the commit hooks need a repository
cp .env.example .env
just setup              # install dependencies and the prek hooks
just dev                # start Postgres + mock OAuth, migrate, serve
```

The API is at [http://localhost:8000](http://localhost:8000), with
interactive docs at [/docs](http://localhost:8000/docs).

| Service          | Port |
| ---------------- | ---- |
| API              | 8000 |
| PostgreSQL       | 5432 |
| Mock OAuth2/OIDC | 8080 |

### Make an authenticated request

Every `/api/v1/` endpoint needs a bearer token. In a second terminal,
mint one from the mock OAuth server and call a protected endpoint:

```bash
TOKEN=$(just token --roles="users.read,users.write")
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/users/
```

### Make it yours

- `just new <module>` scaffolds a complete feature module. Mirror
  `app/modules/user/`, the worked example, then delete it once you have
  modules of your own.
- `just check` runs format, lint, typecheck, migration check, and tests
  — the same gate CI runs. The pre-push hook runs the tests, so
  Postgres must be up (`just db`) when you push.

### Take template updates

Your project records the template release it came from, so a later
release is a three-way merge rather than a re-copy. Commit your work,
then:

```bash
uvx copier update --trust --conflict rej
```

Read [Staying Current](docs/guides/staying-current.md) before your
first update, and the
[API Stability & SemVer](docs/guides/api-stability.md) policy for what
counts as a breaking change.

## What You Get

```plaintext
├── app/
│   ├── core/          # Config, security, errors, logging, telemetry, middleware
│   ├── db/            # Async engine and session dependency
│   ├── http/          # Shared outbound HTTP client
│   ├── modules/
│   │   ├── system/    # Health, readiness & home-page routes
│   │   └── user/      # Example domain module to mirror
│   ├── static/        # Landing-page assets
│   ├── templates/     # Jinja2 templates (landing page)
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
- [Staying Current](docs/guides/staying-current.md) — take template
  updates
- [AI-Assisted Development](docs/guides/ai-setup.md) — Claude Code
  skills, hooks, and subagents

Browse the full set under [`docs/guides/`](docs/guides/).

## Project

- [Roadmap](ROADMAP.md) — planned features and milestones
- [Changelog](CHANGELOG.md) — version history
- [Security Policy](SECURITY.md) — how to report a vulnerability
- [Contributing](CONTRIBUTING.md) — working on QuoinAPI itself
- [License](LICENSE) — MIT
