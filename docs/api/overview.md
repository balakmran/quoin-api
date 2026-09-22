# Overview

A high-level summary of all API modules, available endpoints, and
their responsibilities.

---

## Modules

### Core

The [`app/core/`](core.md) package contains shared infrastructure used
by all feature modules:

- **[Configuration](core.md#configuration)** — Application settings
- **[Metadata](core.md#metadata)** — App name, version, OpenAPI info
- **[Logging](core.md#logging)** — Structured logging setup
- **[Exceptions](core.md#exceptions)** — Domain exception classes
- **[Schemas](core.md#schemas)** — The `ProblemDetail` error body
- **[Exception Handlers](core.md#exception-handlers)** — Global error
  handling
- **[Middlewares](core.md#middlewares)** — Security headers, request
  ID, CORS, timeouts, and size limits
- **[Security](core.md#security)** — Token validation, `ServicePrincipal`,
  and `require_roles`
- **[Lifecycle](core.md#lifecycle)** — In-flight tracking and the
  shutdown drain
- **[Telemetry](core.md#telemetry)** — OpenTelemetry tracing
- **[Pagination](core.md#pagination)** — `Page` and `PageParams`
- **[Versioning](core.md#versioning)** — Endpoint deprecation signalling
- **[OpenAPI](core.md#openapi)** — Schema generation, tags, and shared
  error responses
- **[Database Session](core.md#database-session)** — The engine and
  the per-request `SessionDep` (`app/db/`)
- **[Outbound HTTP Client](core.md#outbound-http-client)** — The shared
  `ResilientHTTPClient` (`app/http/`)

### Feature Modules

#### User

The [`app/modules/user/`](user.md) package provides user management:

- **[Models](user.md#models)** — Database table (SQLModel)
- **[Schemas](user.md#schemas)** — Request/Response shapes (Pydantic)
- **[Repository](user.md#repository)** — Database CRUD operations
- **[Service](user.md#service)** — Business logic
- **[Routes](user.md#routes)** — FastAPI endpoints

#### System

The [`app/modules/system/`](system.md) package serves the operational
endpoints that sit outside `/api/v1/`:

- **[`GET /`](system.md#landing-page-get)** — Landing page
- **[`GET /health`](system.md#liveness-probe-get-health)** — Liveness
  probe
- **[`GET /ready`](system.md#readiness-probe-get-ready)** — Readiness
  probe, `503` while draining or when the database is unreachable

None of the three is in the OpenAPI document, and none requires a token.

---

## Endpoints

### Base URL

```
http://localhost:8000/api/v1
```

### User Endpoints

Every user endpoint requires a bearer token: `users.read` for the
`GET` routes, `users.write` for the rest. Mint one locally with
`just token --roles="users.read,users.write"`.

| Method   | Endpoint              | Description     | Status |
| :------- | :-------------------- | :-------------- | :----- |
| `POST`   | `/api/v1/users/`      | Create user     | 201    |
| `GET`    | `/api/v1/users/`      | List users      | 200    |
| `GET`    | `/api/v1/users/{id}`  | Get user by ID  | 200    |
| `PATCH`  | `/api/v1/users/{id}`  | Update user     | 200    |
| `DELETE` | `/api/v1/users/{id}`  | Delete user     | 204    |

### System Endpoints (Root Level)

No token required; none appears in the OpenAPI document. See
[System](system.md).

| Method | Endpoint  | Description      | Status   |
| :----- | :-------- | :--------------- | :------- |
| `GET`  | `/`       | Landing page     | 200      |
| `GET`  | `/health` | Liveness probe   | 200      |
| `GET`  | `/ready`  | Readiness probe  | 200, 503 |

---

## Interactive Docs

Available in non-production environments:

- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **OpenAPI JSON**: [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

---

## Module Index

| Module                     | Description          | Reference                         |
| :------------------------- | :------------------- | :-------------------------------- |
| `app.core.config`           | Application settings | [Core](core.md#configuration)     |
| `app.core.exceptions`       | Domain exceptions    | [Core](core.md#exceptions)        |
| `app.core.security`         | Auth and RBAC        | [Core](core.md#security)          |
| `app.core.middlewares`      | Middleware stack     | [Core](core.md#middlewares)       |
| `app.core.lifecycle`        | Shutdown drain       | [Core](core.md#lifecycle)         |
| `app.core.pagination`       | Page and PageParams  | [Core](core.md#pagination)        |
| `app.core.versioning`       | Deprecation helper   | [Core](core.md#versioning)        |
| `app.core.openapi`          | Schema and tags      | [Core](core.md#openapi)           |
| `app.modules.user.models`   | User database model  | [User](user.md#models)            |
| `app.modules.user.schemas`  | User API schemas     | [User](user.md#schemas)           |
| `app.modules.user.service`  | User business logic  | [User](user.md#service)           |
| `app.modules.user.routes`   | User endpoints       | [User](user.md#routes)            |
| `app.modules.system.routes` | Probes, landing page | [System](system.md#routes)        |

---

## Usage Examples

### Create a User

The examples assume a token minted with
`just token --roles="users.read,users.write"`.

```python
import httpx

headers = {"Authorization": f"Bearer {token}"}

async with httpx.AsyncClient(headers=headers) as client:
    response = await client.post(
        "http://localhost:8000/api/v1/users/",
        json={"email": "user@example.com", "full_name": "John Doe"},
    )
    user = response.json()
```

### List Users

```python
async with httpx.AsyncClient(headers=headers) as client:
    response = await client.get("http://localhost:8000/api/v1/users/")
    page = response.json()  # {"items": [...], "total": ..., ...}
```

---

## See Also

- [Architecture Overview](../architecture/overview.md) — How components
  fit together
- [Conventions](conventions.md) — Routing and versioning rules
- [Error Handling](../guides/error-handling.md) — Exception patterns
- [Testing](../guides/testing.md) — How to test the API
