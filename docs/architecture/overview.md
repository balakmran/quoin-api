# Overview

Component structure, data flow, and integration patterns of the
QuoinAPI.

---

## High-Level Architecture

```mermaid
graph TB
    Client[Client/Browser] -->|HTTP/JSON| API[FastAPI App]
    API --> MW[Middleware Layer]
    MW --> Routes[API Routes]
    Routes --> Services[Service Layer]
    Services --> Repos[Repository Layer]
    Repos --> DB[(PostgreSQL)]

    API --> Static[Static Files]
    API --> OTEL[OpenTelemetry]
    Services --> Logger[Structlog]

    OTEL -.->|Traces| Collector[OTEL Collector]
    Logger -.->|Logs| Aggregator[Log Aggregator]
```

---

## Component Layers

### 1. Application Layer (`app/main.py`)

The application factory creates and configures the FastAPI application:

```python
def create_app() -> FastAPI:
    setup_logging()
    validate_production_settings()  # crash-loop a bad production config

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup: DB engine, session factory, shared HTTP client
        yield
        # Shutdown: flip /ready to 503, drain in-flight requests, then
        # close the HTTP client and dispose the engine

    app = FastAPI(lifespan=lifespan, **OPENAPI_PARAMETERS)
    add_exception_handlers(app)
    configure_middlewares(app)
    setup_opentelemetry(app)
    app.mount("/static", StaticFiles(directory=...), name="static")
    app.include_router(api_router)  # everything under /api/v1
    app.include_router(system_router_root)  # /, /health, /ready
    return app
```

**Responsibilities:**

- Manage application lifecycle (startup, graceful shutdown)
- Fail fast on an incomplete production configuration
- Configure middlewares and exception handlers
- Set up observability (OTEL, logging)
- Mount static files
- Include API and system routes

---

### 2. Core Infrastructure (`app/core/`)

Shared infrastructure components used across the application.

#### Configuration (`config.py`)

```python
class Settings(BaseSettings):
    # Environment
    ENV: Environment = Environment.development
    LOG_LEVEL: LogLevel = "INFO"  # DEBUG | INFO | WARNING | ERROR
    OTEL_ENABLED: bool = True

    # Database
    POSTGRES_DRIVER: str = "postgresql+asyncpg"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_PASSWORD: SecretStr = SecretStr("postgres")
    POSTGRES_DB: str = "app_db"
    # ...

    # A plain @property, not a @computed_field: the credential-bearing
    # URL stays out of model_dump() and the OpenAPI schema.
    @property
    def DATABASE_URL(self) -> PostgresDsn:
        return MultiHostUrl.build(...)
```

Loads settings from `.env` file using Pydantic Settings.

#### Exceptions (`exceptions.py`)

```python
class QuoinError(Exception):
    def __init__(
        self,
        message: str,
        status_code: int = 500,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.headers = headers


class NotFoundError(QuoinError):
    def __init__(self, message: str = "Not Found"):
        super().__init__(message, status_code=404)
```

Domain exception hierarchy for business logic errors.

#### Logging (`logging.py`)

Configures **Structlog** for structured, machine-readable logs:

```python
def setup_logging() -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),  # dev
            # structlog.processors.JSONRenderer()  # prod
        ],
    )
```

#### Telemetry (`telemetry.py`)

Sets up **OpenTelemetry** for distributed tracing:

```python
def setup_opentelemetry(app: FastAPI) -> None:
    if not settings.OTEL_ENABLED:
        return

    resource = Resource.create(
        {
            SERVICE_NAME: metadata.APP_NAME,
            "service.version": metadata.VERSION,
            "deployment.environment.name": settings.ENV.value,
            # Deprecated key, kept for one release.
            "deployment.environment": settings.ENV.value,
        }
    )
    provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(provider)
    # OTLP exporter if endpoint set; otherwise console in development
    # and test, or nothing (with a startup warning) in production.
    provider.add_span_processor(BatchSpanProcessor(exporter))
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
```

Auto-instruments FastAPI HTTP requests. Exports via OTLP when
`OTEL_EXPORTER_OTLP_ENDPOINT` is set. Without it, development and test
print spans to the console; production instead logs one
`otel_enabled_without_exporter` warning and exports nothing, so
`QUOIN_OTEL_ENABLED=true` without a collector configured doesn't
silently interleave every span into the JSON log stream.
`Resource.create` also honours the standard `OTEL_RESOURCE_ATTRIBUTES`
and `OTEL_SERVICE_NAME` environment variables for any attribute not set
explicitly above.

#### Middlewares (`middlewares.py`)

Registers the whole stack. `add_middleware` is LIFO, so the first
registered is innermost and the last is outermost:

```python
def configure_middlewares(app: FastAPI) -> None:
    app.add_middleware(UnhandledErrorMiddleware)  # innermost of all
    app.add_middleware(InFlightRequestMiddleware)
    app.add_middleware(RequestSizeLimitMiddleware)
    app.add_middleware(TimeoutMiddleware)
    configure_cors(app)  # CORS from settings.BACKEND_CORS_ORIGINS
    configure_trusted_hosts(app)  # TrustedHostMiddleware
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)  # outermost
```

SecurityHeaders and RequestID sit outermost so every manufactured error
— 504, 413, 400, 500 — still carries security headers and an
`X-Request-ID`. See the [security guide](../guides/security.md#middleware-ordering)
for the full rationale.

---

### 3. Database Layer (`app/db/`)

#### Engine Creation (`session.py`)

```python
def create_db_engine(url: str | None = None) -> AsyncEngine:
    return create_async_engine(
        url or str(settings.DATABASE_URL),
        echo=False,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT,
        pool_recycle=settings.DB_POOL_RECYCLE,
        pool_pre_ping=settings.DB_POOL_PRE_PING,
    )
```

Every pool knob is a `QUOIN_DB_POOL_*` setting — see the
[configuration guide](../guides/configuration.md#key-settings).

Stored on `app.state.engine` during application lifespan.

#### Session Injection

```python
async def get_session(request: Request) -> AsyncSession:
    engine = request.app.state.engine
    async_session = async_sessionmaker(engine, ...)
    async with async_session() as session:
        yield session
        await session.commit()  # or rollback() on error
```

Routes depend on `SessionDep` (an `Annotated[AsyncSession,
Depends(get_session, scope="function")]` alias), not on `get_session`
directly. The explicit `scope="function"` matters: it's what makes
FastAPI close this generator — running the commit above — *before* the
response is sent, rather than after. Depending on `get_session` without
that scope commits the transaction after the client has already
received the response.

---

### 4. Feature Modules (`app/modules/`)

Each module follows **Domain-Driven Design** principles:

```
app/modules/user/
├── __init__.py       # Export router
├── models.py         # SQLModel tables
├── schemas.py        # Pydantic request/response
├── exceptions.py     # Domain-specific exceptions
├── repository.py     # Database operations (CRUD)
├── service.py        # Business logic
└── routes.py         # FastAPI endpoints
```

#### Data Flow

```mermaid
sequenceDiagram
    participant Client
    participant Route
    participant Service
    participant Repo
    participant DB

    Client->>Route: POST /api/v1/users/
    Route->>Service: create_user(user_create)
    Service->>Repo: get_by_email(email)
    Repo->>DB: SELECT * FROM users WHERE...
    DB-->>Repo: None
    Repo-->>Service: None
    Service->>Repo: create(user_create)
    Repo->>DB: INSERT INTO users...
    DB-->>Repo: User
    Repo-->>Service: User
    Service-->>Route: User
    Route-->>Client: 201 Created
```

#### Layer Responsibilities

| Layer            | Responsibility                | Example                              |
| :--------------- | :---------------------------- | :----------------------------------- |
| **Routes**       | HTTP handling, validation     | `@router.post("/users/")`            |
| **Services**     | Business logic, orchestration | `if existing: raise ConflictError()` |
| **Repositories** | Database operations           | `session.execute(select(User))`      |
| **Models**       | Database schema               | `class User(SQLModel, table=True)`   |
| **Schemas**      | API contracts                 | `class UserCreate(BaseModel)`        |

---

## Template-Owned vs. User-Owned Files

QuoinAPI is also a Copier template, so every file falls on one side of a
line: **template-owned** files ship improvements to you on
`copier update`; **user-owned** files are yours and are never rewritten.

| Ownership | Files | On `copier update` |
| :--- | :--- | :--- |
| Template | `app/core/`, `app/db/`, `app/main.py`, `app/api.py`, `alembic/env.py`, `justfile`, `pyproject.toml`, `Dockerfile`, `.github/`, `.claude/`, `docs/guides/` | Updated; edits here are what produce merge conflicts |
| User | your `app/modules/<feature>/`, their tests, the migrations you generate, `.env`, your own docs | Left alone |
| Example | `app/modules/user/` and its tests | Template-owned, but meant to be deleted or rewritten once you have real modules |

Keeping your code in `app/modules/` is what keeps `copier update` diffs
small. See the [API stability guide](../guides/api-stability.md) for what
counts as a breaking template change.

---

## Request Lifecycle

1. **Client Request** → FastAPI receives HTTP request
2. **Middleware** → CORS, logging, tracing
3. **Router** → Matches URL pattern, validates input (Pydantic)
4. **Service** → Executes business logic, may raise domain exceptions
5. **Repository** → Queries/updates database via SQLModel
6. **Database** → PostgreSQL with asyncpg driver
7. **Response** → Service returns data, router serializes to JSON
8. **Exception Handling** → Global handlers catch `QuoinError` exceptions
9. **Logging & Tracing** → OTEL spans, structured logs emitted

---

## Database Schema

**Current Tables** (simplified; the migrations are the source of truth):

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    is_active BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ  -- soft-delete tombstone
);

-- Case-insensitive uniqueness among live rows only
CREATE UNIQUE INDEX ix_users_email_lower
    ON users (lower(email)) WHERE deleted_at IS NULL;
```

See [Soft Delete](../guides/soft-delete.md) for why the unique index is
partial. Managed via **Alembic** migrations. Schema changes are versioned
and tracked in `alembic/versions/`.

---

## Static Files & Templates

```python
app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).parent / "static"),
    name="static",
)
```

Serves:

- `app/static/css/` — Stylesheets
- `app/static/img/` — Images and icons
- `app/static/js/` — The home page's script, kept out of the HTML so the
  default CSP needs no `'unsafe-inline'` in `script-src`
- `app/templates/` — Jinja2 templates (root page)

---

## API Versioning

All API routes are versioned. The prefix is applied once, in
`app/api.py`; each module router declares only its own prefix
(`APIRouter(prefix="/users")`):

```python
v1_router = APIRouter()
v1_router.include_router(user_router)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(v1_router)
```

**URL Structure:** `/api/v{version}/{module}/{resource}`

Example: `/api/v1/users/` → User CRUD operations

---

## Deployment Architecture

```mermaid
graph LR
    LB[Load Balancer] --> App1[App Instance 1]
    LB --> App2[App Instance 2]
    LB --> AppN[App Instance N]

    App1 --> PG[(PostgreSQL)]
    App2 --> PG
    AppN --> PG

    App1 -.-> OTEL[OTEL Collector]
    App2 -.-> OTEL
    AppN -.-> OTEL
```

**Characteristics:**

- **Stateless** application instances (horizontal scaling)
- **Shared** PostgreSQL database (connection pooling)
- **Centralized** observability (OTEL → Jaeger/Tempo)

---

## Concurrency Model

- **Async/Await** throughout the stack
- **asyncpg** for database I/O
- **AsyncSession** for SQLAlchemy operations
- **ResilientHTTPClient** (`httpx2`) for external API calls, with retries
  and a circuit breaker; see [Outbound HTTP](../guides/outbound-http.md)

```python
async def create_user(self, user_create: UserCreate) -> User:
    # Non-blocking database operations
    existing = await self.repository.get_by_email(user_create.email)
    if existing:
        raise ConflictError(message="Email already registered")
    return await self.repository.create(user_create)
```

Enables handling thousands of concurrent requests with minimal
resource usage.

---

## Error Handling Flow

```mermaid
graph TD
    Service[Service Layer] -->|raises| Exception[QuoinError]
    Exception --> Handler[Global Exception Handler]
    Handler --> Response[JSON Response]

    Response --> Client[Client]
```

All business logic errors are converted to HTTP responses
automatically. See [Error Handling Guide](../guides/error-handling.md)
for details.

---

## Testing Architecture

```
tests/
├── conftest.py           # Shared fixtures
├── core/                 # Settings, security, middleware, ...
└── modules/
    └── user/
        ├── test_routes.py       # Integration tests (routes → DB)
        └── test_concurrency.py  # Cross-transaction races
```

**Strategy:**

- **Integration tests** drive the full stack against a real PostgreSQL;
  each test rolls back to a SAVEPOINT
- **Focused tests** for models, exceptions, and core infrastructure
- Split out service or repository tests when a layer grows logic worth
  testing on its own

See [Testing Guide](../guides/testing.md) for patterns.

---

## Security Considerations

### Current Measures

1. **Input Validation** — Pydantic schema validation on all inputs
2. **SQL Injection Protection** — SQLAlchemy parameterized queries
3. **OAuth 2.0 / 2.1 Authentication** — JWT validation via JWKS with
   `require_roles()` per-route; `ServicePrincipal` identity injection
4. **CORS Configuration** — Allowlist-driven; no wildcard in production
5. **Trusted Hosts** — `Host` header allowlist; required in production
6. **Security Headers** — CSP, HSTS, `X-Frame-Options`, and friends on
   every response
7. **Request Limits** — Body-size cap (413) and per-request timeout (504)
8. **Environment Variables** — Secrets loaded from the environment or
   `.env` (not committed); the database password is a `SecretStr`
9. **Fail-fast Production Config** — the app refuses to boot without
   OAuth trust anchors and an explicit host allowlist

See the [Security guide](../guides/security.md) for each measure.

---

## Performance Optimizations

1. **Connection Pooling** — PostgreSQL connection pool (default size
   20, tunable with `QUOIN_DB_POOL_*`)
2. **Async I/O** — Non-blocking database and HTTP operations
3. **Database Indexes** — Indexed `users.email` for fast lookups
4. **Bounded Pagination** — list endpoints cap `limit` at 100

---

## See Also

- [Decision Log](decision-log.md) — Why we chose these technologies
- [Error Handling](../guides/error-handling.md) — Exception architecture
- [Database Migrations](../guides/database-migrations.md) — Schema management
- [Observability](../guides/observability.md) — Logging and tracing
