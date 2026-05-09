# Getting Started

## Start a new project

Use QuoinAPI as a [Copier](https://copier.readthedocs.io/) template to
scaffold a production-ready API. Only `uv` needs to be installed — `uvx`
runs Copier without a separate install step:

```bash
uvx copier copy --trust gh:balakmran/quoin-api my-api
cd my-api
cp .env.example .env
just setup
just dev
```

Visit [http://localhost:8000](http://localhost:8000) once the server is up.

---

## Develop QuoinAPI itself

The rest of this guide covers working on QuoinAPI directly — cloning the
repo, running the test suite, and contributing changes.

## Prerequisites

Ensure you have the following tools installed:

- **[Git](https://git-scm.com/)**: Version control system.
- **[Python 3.12+](https://www.python.org/downloads/)**: The programming language used.
- **[uv](https://github.com/astral-sh/uv)**: A fast Python package installer and manager.
- **[just](https://github.com/casey/just)**: A handy command runner for project tasks.
- **[Docker](https://www.docker.com/)**: Required for running the database and services.

## Quick Start

Follow these steps to get up and running in minutes.

```bash
# 1. Clone the Repository
git clone https://github.com/balakmran/quoin-api.git
cd quoin-api

# 2. Configure Environment
cp .env.example .env

# 3. Setup Project (installs deps & git hooks)
just setup

# 4. Start DB, Apply Migrations, and Run the Server
just dev
```

Visit [http://localhost:8000](http://localhost:8000) — the home page confirms
the app is up. API docs are at [/docs](http://localhost:8000/docs) (Swagger UI)
and [/redoc](http://localhost:8000/redoc).

![QuoinAPI Home Page](../assets/images/quoin-api-homepage.png)

## Project Structure

Understanding the project layout will help you navigate the codebase.

```plaintext
.
├── app/
│   ├── core/                   # Core configuration (settings, logging, exceptions)
│   ├── db/                     # Database session and base models
│   ├── modules/                # Domain-specific feature modules (e.g., user)
│   │   └── user/               # Example module
│   │       ├── exceptions.py   # Domain-specific exceptions
│   │       ├── models.py       # database tables
│   │       ├── schemas.py      # Pydantic models
│   │       ├── repository.py   # CRUD operations
│   │       ├── routes.py       # API endpoints
│   │       └── service.py      # Business logic
│   └── main.py                 # Application entry point
├── tests/                      # Test suite
├── alembic/                    # Database migrations
├── docker-compose.yml          # Local development services
├── justfile                    # Task runner configuration
└── pyproject.toml              # Project dependencies and tool config
```

## What's Next?

Now that the app is running, here are the logical next steps:

| Task | Guide |
| :--- | :---- |
| Add a new feature module | [Creating a Module](creating-a-module.md) |
| Change environment settings | [Configuration](configuration.md) |
| Add a database column | [Database Migrations](database-migrations.md) |
| Write tests | [Testing](testing.md) |
| Explore the live API | [localhost:8000/docs](http://localhost:8000/docs) |

---

## Troubleshooting

### Port Conflicts

If `just dev` fails, check if port **8000** is already in use.

```bash
# check the process
lsof -i :8000

# kill the process
kill -9 $(lsof -ti:8000)
```

### Database Connection

If the app cannot connect to the database:

1. Ensure the Docker container is running: `docker ps`
2. Check logs: `docker compose logs db`
3. Restart the database: `just db`
