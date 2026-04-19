# Conventions

Routing conventions, URL versioning strategy, and endpoint patterns
used across the QuoinAPI.

## Router Structure

The API is organized hierarchically in [`app/api.py`](https://github.com/balakmran/quoin-api/blob/main/app/api.py):

```python
from fastapi import APIRouter
from app.modules.user import router as user_router
from app.modules.system import router as system_router_root

# Versioned API router
v1_router = APIRouter()
v1_router.include_router(user_router)

# Top-level API router with version prefix
api_router = APIRouter(prefix="/api/v1")
api_router.include_router(v1_router)

# System router (no prefix)
# Included separately at root level in main.py
```

## API Versioning

The API uses **URL-based versioning** with the following structure:

```
/api/v{version}/{module}/{resource}
```

### Current Version: v1

All user-facing endpoints are prefixed with `/api/v1/`:

| Endpoint             | Method | Description       |
| :------------------- | :----- | :---------------- |
| `/api/v1/users/`     | POST   | Create a new user |
| `/api/v1/users/{id}` | GET    | Get user by ID    |
| `/api/v1/users/`     | GET    | List all users    |
| `/api/v1/users/{id}` | PATCH  | Update user       |
| `/api/v1/users/{id}` | DELETE | Delete user       |

### System Endpoints (No Version Prefix)

Health and system status endpoints remain at the root level:

| Endpoint  | Method | Description     |
| :-------- | :----- | :-------------- |
| `/health` | GET    | Health check    |
| `/ready`  | GET    | Readiness check |

### API Documentation

Interactive API documentation is available (development only):

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

!!! note
    API documentation endpoints (`/docs`, `/redoc`) are only available
    in non-production environments for security.

---

## Versioning Strategy

### When to Create a New Version

Create a new API version (e.g., `/api/v2/`) when making **breaking changes**:

- Removing or renaming fields
- Changing response structure
- Modifying endpoint URLs
- Changing authentication methods

### Non-Breaking Changes

The following changes **do not** require a new version:

- Adding new optional fields
- Adding new endpoints
- Adding new query parameters (with defaults)
- Improving error messages
- Performance improvements

---

## Example Requests

### Create User

```bash
POST /api/v1/users/
Content-Type: application/json

{
  "email": "user@example.com",
  "full_name": "John Doe"
}

# Response: 201 Created
{
  "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "email": "user@example.com",
  "full_name": "John Doe",
  "created_at": "2026-02-16T15:30:00.000000"
}
```

### Get User

```bash
GET /api/v1/users/f47ac10b-58cc-4372-a567-0e02b2c3d479

# Response: 200 OK
{
  "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "email": "user@example.com",
  "full_name": "John Doe",
  "created_at": "2026-02-16T15:30:00.000000"
}
```

### Health Check

```bash
GET /health

# Response: 200 OK
{
  "status": "healthy"
}
```

---

## See Also

- [app/api.py](https://github.com/balakmran/quoin-api/blob/main/app/api.py) — API router configuration
- [app/main.py](https://github.com/balakmran/quoin-api/blob/main/app/main.py) — Application entry point
- [Error Handling](error-handling.md) — API error responses
- [Testing Guide](testing.md) — API integration tests
