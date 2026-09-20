# Core

Core infrastructure modules shared across the entire application.

---

## Configuration

Application settings loaded from environment variables via Pydantic
Settings.

### Settings Class

```python
from pydantic import SecretStr
from pydantic_settings import BaseSettings
from pydantic_core import MultiHostUrl


class Settings(BaseSettings):
    # Environment
    ENV: Environment = (
        Environment.development
    )  # development | test | production
    LOG_LEVEL: LogLevel = "INFO"  # DEBUG | INFO | WARNING | ERROR

    # Database
    POSTGRES_DRIVER: str = "postgresql+asyncpg"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: SecretStr = SecretStr("postgres")
    POSTGRES_DB: str = "app_db"

    # A plain @property, not a @computed_field: the credential-bearing
    # URL stays out of model_dump() and the OpenAPI schema, and the
    # password is a SecretStr, redacted in dumps.
    @property
    def DATABASE_URL(self) -> PostgresDsn:
        # Constructs database URL from POSTGRES_* components
        ...

    # Observability
    OTEL_ENABLED: bool = True

    # Networking
    ALLOWED_HOSTS: list[str] = ["localhost", "127.0.0.1", "test", "*.orb.local"]
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
    ]
    # ... plus the CORS, security-header, pool, timeout, OAuth, and
    # outbound HTTP settings
```

All settings use the `QUOIN_` prefix (e.g., `QUOIN_POSTGRES_HOST`). The
[Configuration guide](../guides/configuration.md#key-settings) lists
every setting and its default.

**Usage:**

```python
from app.core.config import settings

database_url = settings.DATABASE_URL
is_production = settings.ENV == "production"
```

**Source:** [app/core/config.py](https://github.com/balakmran/quoin-api/blob/main/app/core/config.py)

---

## Metadata

Static application identity used in OpenAPI parameters and the root
page template.

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

## Logging

Structured logging configuration powered by Structlog. Initialized
first during application startup.

### setup_logging

Configures Structlog and the standard library to share one pipeline:
context variables (request ID, caller), log level, timestamp, and trace
correlation. `production` renders JSON in UTC; development and test
render human-readable console lines. `QUOIN_LOG_LEVEL` sets the
verbosity.

```python
def setup_logging() -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            # ... trace correlation, then JSONRenderer in production or
            # ConsoleRenderer otherwise
        ],
    )
```

See the [Observability guide](../guides/observability.md).

**Source:** [app/core/logging.py](https://github.com/balakmran/quoin-api/blob/main/app/core/logging.py)

---

## Exceptions

Domain exception classes that map business errors to HTTP status codes.
All inherit from `QuoinError`.

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

### Subclasses

| Class | Status | Default Message |
| :---- | :----: | :-------------- |
| `BadRequestError` | 400 | `"Bad Request"` |
| `UnauthorizedError` | 401 | `"Unauthorized"` |
| `ForbiddenError` | 403 | `"Forbidden"` |
| `NotFoundError` | 404 | `"Not Found"` |
| `ConflictError` | 409 | `"Conflict"` |
| `QuoinRequestValidationError` | 422 | _(Pydantic errors, internal)_ |
| `InternalServerError` | 500 | `"Internal Server Error"` |
| `BadGatewayError` | 502 | `"Bad Gateway"` |
| `ServiceUnavailableError` | 503 | `"Service Unavailable"` |
| `GatewayTimeoutError` | 504 | `"Gateway Timeout"` |

See the [Error Handling guide](../guides/error-handling.md) for when to
use each.

**Usage:**

```python
from app.core.exceptions import NotFoundError, ConflictError

raise NotFoundError(message="User not found")
raise ConflictError(message="Email already registered")
```

**Source:** [app/core/exceptions.py](https://github.com/balakmran/quoin-api/blob/main/app/core/exceptions.py)

---

## Schemas

The response body every error is rendered into.

### ProblemDetail

```python
class ProblemDetail(BaseModel):
    """RFC 9457 Problem Details response body."""

    type: str = "about:blank"  # urn:quoin:error:<snake_case_name>
    title: str  # HTTP reason phrase
    status: int  # mirrors the response status
    detail: str  # explanation of this occurrence
    instance: str  # request path
    errors: list[dict[str, Any]] | None = None  # 422 only
```

`errors` is an RFC 9457 extension carrying per-field validation
failures, and is omitted on every other status.

**Source:** [app/core/schemas.py](https://github.com/balakmran/quoin-api/blob/main/app/core/schemas.py)

---

## Exception Handlers

Converts exceptions to [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457)
`application/problem+json` responses. Registered with the FastAPI app
during startup.

### quoin_exception_handler

Renders a `QuoinError` as a `ProblemDetail` body (`type`, `title`,
`status`, `detail`, `instance`) with the exception's status code and
headers, and logs it at a level matching the status.

```python
async def quoin_exception_handler(request: Request, exc: Any) -> Response:
    problem = ProblemDetail(
        type=_problem_type(exc),  # urn:quoin:error:<snake_case_name>
        title=_problem_title(exc.status_code),
        status=exc.status_code,
        detail=exc.message,
        instance=request.url.path,
    )
    ...
```

### validation_exception_handler

Renders request validation failures as a 422 problem document with an
`errors` array. Handles `RequestValidationError` and
`QuoinRequestValidationError`.

### http_exception_handler and unhandled_exception_handler

Render Starlette `HTTPException`s (404, 405, ...) and any uncaught
exception (500) in the same problem-details shape. The 500 never carries
the exception message.

### add_exception_handlers

Registers all of the above with the application.

```python
def add_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(QuoinError, quoin_exception_handler)
    app.add_exception_handler(
        RequestValidationError, validation_exception_handler
    )
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    # ... plus QuoinRequestValidationError -> validation_exception_handler
```

**Source:** [app/core/exception_handlers.py](https://github.com/balakmran/quoin-api/blob/main/app/core/exception_handlers.py)

---

## Middlewares

Request-level processing applied before routes are hit.

### configure_middlewares

Registers the whole stack in one call. From outermost to innermost:

| Middleware | Role |
| :--- | :--- |
| `SecurityHeadersMiddleware` | Security response headers on every response |
| `RequestIDMiddleware` | Validates and echoes the request ID header |
| `AccessLogMiddleware` | One structured log line per request |
| `TrustedHostMiddleware` | Rejects an unlisted `Host` with problem+json |
| `CORSMiddleware` | Explicit-allowlist CORS (`configure_cors`) |
| `TimeoutMiddleware` | Per-request wall-clock timeout (`504`) |
| `RequestSizeLimitMiddleware` | Rejects oversize bodies (`413`) |
| `InFlightRequestMiddleware` | Tracks requests for graceful shutdown |
| `UnhandledErrorMiddleware` | Turns an escaping exception into a `500` |

Most layers are tunable through a `QUOIN_` setting; see
[Configuration](../guides/configuration.md#key-settings). The ordering
rationale is in the [Security guide](../guides/security.md#middleware-ordering).

**Source:** [app/core/middlewares.py](https://github.com/balakmran/quoin-api/blob/main/app/core/middlewares.py)

---

## Security

OAuth 2.0 / OIDC bearer-token validation and role-based access control.

### ServicePrincipal

The authenticated caller, injected into every protected route.

```python
class ServicePrincipal(BaseModel):
    subject: str  # JWT `sub`
    roles: list[str]  # normalized app roles
    claims: dict[str, Any]  # full decoded payload
```

### require_roles

```python
from app.core.security import ServicePrincipal, require_roles


@router.get("/")
async def list_users(
    caller: Annotated[ServicePrincipal, Depends(require_roles("users.read"))],
) -> ...: ...
```

Returns a dependency that validates the token and requires **any** of
the named roles, plus the configurable superuser bypass. A missing or
invalid token is a `401`; a valid token without the role is a `403`.

### Other entry points

| Name | Role |
| :--- | :--- |
| `validate_token` | Verifies signature, required claims, `exp`, `aud`, and `iss` |
| `get_token_claims` | Bearer extraction, returning the raw claims |
| `get_current_caller` | Builds the `ServicePrincipal` and binds `caller` to the log context |
| `extract_roles` | Reads the roles claim, accepting an array or a space-separated string |
| `JWKSCache` | Caches signing keys, refreshing stale sets in the background with backoff on an unknown `kid` |

**Usage:** see the [Authentication guide](../guides/authentication.md).

**Source:** [app/core/security.py](https://github.com/balakmran/quoin-api/blob/main/app/core/security.py)

---

## Lifecycle

Tracks in-flight requests so shutdown can drain them.

### Lifecycle

One instance lives on `app.state.lifecycle`.
`InFlightRequestMiddleware` maintains the counter; the lifespan handler
drives the drain.

| Member | Role |
| :--- | :--- |
| `in_flight` | Requests currently being processed |
| `is_shutting_down` | Once true, `/ready` answers `503` |
| `acquire` / `release` | Enter and leave the in-flight set |
| `begin_shutdown` | Flip readiness so traffic drains away |
| `drain(timeout)` | Await an idle server; `True` if it settled in time |

**Usage:** see
[Graceful Shutdown](../guides/deployment.md#graceful-shutdown).

**Source:** [app/core/lifecycle.py](https://github.com/balakmran/quoin-api/blob/main/app/core/lifecycle.py)

---

## Telemetry

OpenTelemetry instrumentation for distributed tracing. Added last
during application startup.

### setup_opentelemetry

```python
def setup_opentelemetry(app: FastAPI) -> None:
    if not settings.OTEL_ENABLED:
        return

    # Tracer provider and exporter: OTLP when OTEL_EXPORTER_OTLP_ENDPOINT
    # is set, console in development/test, none in production.
    ...
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
```

The database engine (`instrument_sqlalchemy_engine`) and the shared
outbound HTTP client (`instrument_http_client`) are instrumented
separately, in the application lifespan, once they exist.

Disable with `QUOIN_OTEL_ENABLED=False` in `.env`. See the
[Observability guide](../guides/observability.md).

**Source:** [app/core/telemetry.py](https://github.com/balakmran/quoin-api/blob/main/app/core/telemetry.py)

---

## Pagination

Shared list-response envelope and query-parameter conventions used by
every module's list endpoint.

### Page

```python
from app.core.pagination import Page, PageParams, parse_sort


class Page[T](BaseModel):
    items: list[T]
    total: int  # rows matching the query, ignoring pagination
    limit: int
    offset: int
```

`PageParams` is a FastAPI dependency exposing `limit` (1..100) and
`offset` (>= 0). `parse_sort` turns a `?sort=-created_at,email` value
into SQLAlchemy order-by terms, validating each field against a
per-module whitelist and raising `BadRequestError` for anything else.

**Usage:** see the [Pagination guide](../guides/pagination.md).

**Source:** [app/core/pagination.py](https://github.com/balakmran/quoin-api/blob/main/app/core/pagination.py)

---

## Versioning

Endpoint deprecation signalling via the RFC 8594 `Deprecation`,
`Sunset`, and `Link` headers.

### deprecated

```python
from datetime import date
from app.core.versioning import deprecated


@router.get(
    "/legacy",
    dependencies=[Depends(deprecated(sunset=date(2027, 1, 1), link="..."))],
)
async def legacy() -> ...: ...
```

Returns a dependency that stamps `Deprecation: true` (plus `Sunset` and
`Link` when configured) on every response, without changing the
handler's return value.

**Source:** [app/core/versioning.py](https://github.com/balakmran/quoin-api/blob/main/app/core/versioning.py)

---

## OpenAPI

Schema generation, route tags, and the shared error-response
declarations.

### error_responses and DEFAULT_ERROR_RESPONSES

```python
from app.core.openapi import DEFAULT_ERROR_RESPONSES, error_responses

router = APIRouter(prefix="/users", responses=DEFAULT_ERROR_RESPONSES)


@router.get(
    "/{user_id}",
    responses=error_responses(404, descriptions={404: "User not found"}),
)
async def get_user(...) -> ...: ...
```

`DEFAULT_ERROR_RESPONSES` covers what any authenticated endpoint can
return (401, 403, 422, 500) and belongs on the router;
`error_responses(*codes)` declares what one route adds. Requesting an
undocumented code raises `KeyError`, and a `descriptions` key matching
none of the requested codes raises `ValueError`, so a typo fails loudly.

### APITag

The tag enum backing the grouping in Swagger UI. A new module's tag is
added here so its description travels with it.

### OPENAPI_PARAMETERS and set_openapi_generator

`OPENAPI_PARAMETERS` is the `FastAPI(...)` keyword set: title, version,
and long description from
[Metadata](#metadata), plus the docs routes — `docs_url`, `redoc_url`,
and `openapi_url` are all `None` in production, so the schema and both
UIs are unavailable there.

`set_openapi_generator(app)` post-processes the generated schema to
label error responses `application/problem+json`, matching what the
handlers actually send.

**Usage:** see
[OpenAPI Documentation](../guides/error-handling.md#openapi-documentation).

**Source:** [app/core/openapi.py](https://github.com/balakmran/quoin-api/blob/main/app/core/openapi.py)

**Usage:** see the
[Deprecating Endpoints guide](../guides/deprecating-endpoints.md).

**Source:** [app/core/versioning.py](https://github.com/balakmran/quoin-api/blob/main/app/core/versioning.py)

---

## See Also

- [Configuration Guide](../guides/configuration.md) — Environment setup
- [Error Handling Guide](../guides/error-handling.md) — Exception patterns
- [Observability Guide](../guides/observability.md) — Logging and tracing
