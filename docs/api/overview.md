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
- **[Exception Handlers](core.md#exception-handlers)** — Global error
  handling
- **[Middlewares](core.md#middlewares)** — CORS configuration
- **[Telemetry](core.md#telemetry)** — OpenTelemetry tracing

### Feature Modules

#### User

The [`app/modules/user/`](user.md) package provides user management:

- **[Models](user.md#models)** — Database table (SQLModel)
- **[Schemas](user.md#schemas)** — Request/Response shapes (Pydantic)
- **[Repository](user.md#repository)** — Database CRUD operations
- **[Service](user.md#service)** — Business logic
- **[Routes](user.md#routes)** — FastAPI endpoints

---

## Endpoints

### Base URL

```
http://localhost:8000/api/v1
```

### User Endpoints

| Method   | Endpoint              | Description     | Status |
| :------- | :-------------------- | :-------------- | :----- |
| `POST`   | `/api/v1/users/`      | Create user     | 201    |
| `GET`    | `/api/v1/users/`      | List users      | 200    |
| `GET`    | `/api/v1/users/{id}`  | Get user by ID  | 200    |
| `PATCH`  | `/api/v1/users/{id}`  | Update user     | 200    |
| `DELETE` | `/api/v1/users/{id}`  | Delete user     | 204    |

### System Endpoints (Root Level)

| Method | Endpoint  | Description      | Status |
| :----- | :-------- | :--------------- | :----- |
| `GET`  | `/health` | Health check     | 200    |
| `GET`  | `/ready`  | Readiness probe  | 200    |


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
| `app.core.config`          | Application settings | [Core](core.md#configuration)     |
| `app.core.exceptions`      | Domain exceptions    | [Core](core.md#exceptions)        |
| `app.modules.user.models`  | User database model  | [User](user.md#models)            |
| `app.modules.user.schemas` | User API schemas     | [User](user.md#schemas)           |
| `app.modules.user.service` | User business logic  | [User](user.md#service)           |
| `app.modules.user.routes`  | User endpoints       | [User](user.md#routes)            |

---

## Usage Examples

### Create a User

```python
import httpx

async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://localhost:8000/api/v1/users/",
        json={"email": "user@example.com", "full_name": "John Doe"},
    )
    user = response.json()
```

### List Users

```python
async with httpx.AsyncClient() as client:
    response = await client.get("http://localhost:8000/api/v1/users/")
    users = response.json()
```

---

## See Also

- [Architecture Overview](../architecture/overview.md) — How components
  fit together
- [Conventions](conventions.md) — Routing and versioning rules
- [Error Handling](../guides/error-handling.md) — Exception patterns
- [Testing](../guides/testing.md) — How to test the API
