# Core API

Documentation for core infrastructure modules.

---

## Exceptions

Core exception classes for domain error handling.

### QuoinError

Base class for all application exceptions.

```python
from app.core.exceptions import QuoinError

class QuoinError(Exception):
    """Base class for application exceptions."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.headers = headers
```

**Usage:**

```python
raise QuoinError(message="Something went wrong", status_code=500)
```

### NotFoundError

Resource not found (404).

```python
raise NotFoundError(message="User not found")
```

### ConflictError

Resource conflict (409).

```python
raise ConflictError(message="Email already exists")
```

### BadRequestError

Invalid request (400).

```python
raise BadRequestError(message="Invalid request parameters")
```

### InternalServerError

Internal server error (500).

```python
raise InternalServerError(message="Something went wrong")
```

### ForbiddenError

Insufficient permissions (403).

```python
raise ForbiddenError(message="Admin access required")
```

### QuoinRequestValidationError

Wraps Pydantic validation errors with the `QuoinError` format (422).
Used internally by the exception handler infrastructure.

**Source:** [app/core/exceptions.py](https://github.com/balakmran/quoin-api/blob/main/app/core/exceptions.py)

---

## Configuration

Application settings loaded from environment variables.

### Settings Class

```python
from pydantic_settings import BaseSettings
from pydantic import computed_field
from pydantic_core import MultiHostUrl

class Settings(BaseSettings):
    # Environment
    ENV: Environment = Environment.development  # development | test | production
    LOG_LEVEL: str = "INFO"

    # Database
    POSTGRES_DRIVER: str = "postgresql+asyncpg"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "app_db"

    @computed_field
    @property
    def DATABASE_URL(self) -> PostgresDsn:
        # Constructs database URL from POSTGRES_* components
        ...

    # Observability
    OTEL_ENABLED: bool = True

    # Networking
    ALLOWED_HOSTS: list[str] = ["localhost", "127.0.0.1", "test"]
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
    ]
```

All settings use the `QUOIN_` prefix (e.g., `QUOIN_POSTGRES_HOST`).

**Usage:**

```python
from app.core.config import settings

# Access configuration
database_url = settings.DATABASE_URL
is_production = settings.ENV == "production"
```

**Source:** [app/core/config.py](https://github.com/balakmran/quoin-api/blob/main/app/core/config.py)

---

## Exception Handlers

Global exception handlers for converting domain exceptions to HTTP responses.

### quoin_exception_handler

Converts `QuoinError` exceptions to JSON responses.

```python
async def quoin_exception_handler(
    request: Request, exc: QuoinError
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
        headers=exc.headers,
    )
```

### validation_exception_handler

Converts Pydantic `ValidationError` exceptions to 422 JSON responses.

```python
async def validation_exception_handler(
    request: Request, exc: ValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )
```

### add_exception_handlers

Registers all exception handlers with the FastAPI app.

```python
def add_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(QuoinError, quoin_exception_handler)
    app.add_exception_handler(ValidationError, validation_exception_handler)
```

**Source:** [app/core/exception_handlers.py](https://github.com/balakmran/quoin-api/blob/main/app/core/exception_handlers.py)

---

## Middlewares

CORS and other middleware configuration.

### configure_middlewares

```python
def configure_middlewares(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )
```

Allowed origins are configured via `QUOIN_BACKEND_CORS_ORIGINS` (defaults to
`localhost:3000` and `localhost:8000`).

**Source:** [app/core/middlewares.py](https://github.com/balakmran/quoin-api/blob/main/app/core/middlewares.py)

---

## Logging

Structured logging configuration with Structlog.

### setup_logging

```python
def setup_logging() -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer()  # dev
        ],
    )
```

**Source:** [app/core/logging.py](https://github.com/balakmran/quoin-api/blob/main/app/core/logging.py)

---

## Telemetry

OpenTelemetry configuration for distributed tracing.

### setup_opentelemetry

```python
def setup_opentelemetry(app: FastAPI) -> None:
    if not settings.OTEL_ENABLED:
        return

    FastAPIInstrumentor.instrument_app(app)
    SQLAlchemyInstrumentor().instrument()
```

**Source:** [app/core/telemetry.py](https://github.com/balakmran/quoin-api/blob/main/app/core/telemetry.py)

---

## Metadata

Application metadata and OpenAPI parameters.

```python
from app.core.metadata import (
    APP_NAME,
    APP_DESCRIPTION,
    VERSION,
    REPOSITORY_URL,
    COPYRIGHT_OWNER,
)
```

**Source:** [app/core/metadata.py](https://github.com/balakmran/quoin-api/blob/main/app/core/metadata.py)

---

## See Also

- [Error Handling Guide](../guides/error-handling.md) — Detailed exception patterns
- [Configuration Guide](../guides/configuration.md) — Environment setup
- [Observability Guide](../guides/observability.md) — Logging and tracing
