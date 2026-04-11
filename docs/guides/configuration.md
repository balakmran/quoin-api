# Configuration

The application is configured using **environment variables** and **[Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)**. This ensures strict type validation for all configuration options.

## Environment-Based Configuration

The application supports three environments with automatic `.env` file selection based on the `ENV` variable:

| Environment | ENV Value               | Config File       | Use Case              |
| :---------- | :---------------------- | :---------------- | :-------------------- |
| Development | `development` (default) | `.env`            | Local development     |
| Test        | `test`                  | `.env.test`       | Test suite, CI/CD     |
| Production  | `production`            | `.env.production` | Production deployment |

The environment is determined at startup from the `QUOIN_ENV` environment
variable, with `ENV` as a fallback for backward compatibility.

## Environment Variable Prefix

All application settings use the `QUOIN_` prefix for namespacing. This prevents conflicts with system or other application variables.

```bash
# Example: setting log level
export QUOIN_LOG_LEVEL=DEBUG

# Without prefix (won't work)
export LOG_LEVEL=DEBUG  # ❌ Ignored
```

## Setup

Copy the example configuration to create your local `.env` file:

```bash
cp .env.example .env
```

The template contains these defaults — ready for local development
with Docker:

```bash
# Application
# Environment: development, test, production
QUOIN_ENV=development
QUOIN_LOG_LEVEL=INFO
QUOIN_OTEL_ENABLED=True

# Database
QUOIN_POSTGRES_DRIVER=postgresql+asyncpg
QUOIN_POSTGRES_HOST=localhost
QUOIN_POSTGRES_PORT=5432
QUOIN_POSTGRES_USER=postgres
QUOIN_POSTGRES_PASSWORD=postgres
QUOIN_POSTGRES_DB=app_db
```

> [!NOTE]
> The defaults work out of the box with `just db`. For production,
> override `QUOIN_POSTGRES_HOST`, `QUOIN_POSTGRES_PASSWORD`, and set
> `QUOIN_ENV=production`.

### Creating Environment-Specific Files

Create `.env.test` for test-specific settings:

```bash
# .env.test
QUOIN_ENV=test
QUOIN_LOG_LEVEL=DEBUG
QUOIN_OTEL_ENABLED=False
QUOIN_POSTGRES_DB=test_db
```

Create `.env.production` for production settings (never commit this):

```bash
# .env.production
QUOIN_ENV=production
QUOIN_LOG_LEVEL=WARNING
QUOIN_OTEL_ENABLED=True
QUOIN_POSTGRES_HOST=your-prod-db-host
# ... other production settings
```

## Key Settings

| Variable                     | Description                                         | Default                                              |
| :--------------------------- | :-------------------------------------------------- | :--------------------------------------------------- |
| `QUOIN_ENV`                  | Environment (`development`, `test`, `production`)   | `development`                                        |
| `QUOIN_LOG_LEVEL`            | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `INFO`                                               |
| `QUOIN_OTEL_ENABLED`         | Enable OpenTelemetry tracing                        | `true`                                               |
| `QUOIN_POSTGRES_DRIVER`      | Database driver                                     | `postgresql+asyncpg`                                 |
| `QUOIN_POSTGRES_HOST`        | PostgreSQL host                                     | `localhost`                                          |
| `QUOIN_POSTGRES_PORT`        | PostgreSQL port                                     | `5432`                                               |
| `QUOIN_POSTGRES_USER`        | PostgreSQL username                                 | `postgres`                                           |
| `QUOIN_POSTGRES_PASSWORD`    | PostgreSQL password                                 | `postgres`                                           |
| `QUOIN_POSTGRES_DB`          | PostgreSQL database name                            | `app_db`                                             |
| `QUOIN_ALLOWED_HOSTS`        | Trusted host list                                   | `["localhost", "127.0.0.1", "test", "*.orb.local"]`  |
| `QUOIN_BACKEND_CORS_ORIGINS` | CORS allowed origins                                | `["http://localhost:3000", "http://localhost:8000"]` |

## Core Settings Module

All settings are defined in [`app/core/config.py`](../../app/core/config.py). The `Settings` class defines the schema and validation rules.

```python
from enum import StrEnum
from pydantic import PostgresDsn, computed_field
from pydantic_settings import BaseSettings

class Environment(StrEnum):
    """Application environment."""
    development = "development"
    test = "test"
    production = "production"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="quoin_",
        case_sensitive=False,
        env_file=env_file,  # Automatically selected
    )

    ENV: Environment = Environment.development
    LOG_LEVEL: str = "INFO"
    OTEL_ENABLED: bool = True

    # Database - constructed from individual POSTGRES_* vars
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    # ... other POSTGRES_* fields

    @computed_field
    @property
    def DATABASE_URL(self) -> PostgresDsn:
        \"\"\"Assemble the database URL.\"\"\"
        # Constructed from POSTGRES_* fields
```

## Database Configuration

The database connection is managed in [`app/db/session.py`](../../app/db/session.py). The async engine is created via `create_db_engine()` and stored on `app.state.engine` during the application lifespan. It uses `SQLModel` (a wrapper around SQLAlchemy) with the async `asyncpg` driver for high performance.

- **Changes**: Never modify the database schema manually. Always change the `SQLModel` definition in Python.
- **Migrations**: Use `just migrate-gen \"message\"` to generate migration scripts.

---

## See Also

- [Database Migrations Guide](database-migrations.md) — Managing schema changes
- [.env.example](https://github.com/balakmran/quoin-api/blob/main/.env.example) — Environment variables template
- [app/core/config.py](https://github.com/balakmran/quoin-api/blob/main/app/core/config.py) — Settings module
