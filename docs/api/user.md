# User

Documentation for the User module.

---

## Models

Database model for users.

### User Model

```python
import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    """User model."""

    __tablename__ = "users"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: str = Field(unique=True, index=True, max_length=255)
    full_name: str | None = Field(default=None, max_length=255)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            onupdate=lambda: datetime.now(UTC),
        ),
    )
```

**Table:** `users`

**Indexes:**

- `email` (unique, indexed)

**Source:** [app/modules/user/models.py](https://github.com/balakmran/quoin-api/blob/main/app/modules/user/models.py)

---

## Schemas

Pydantic schemas for request/response validation.

### UserBase

```python
class UserBase(BaseModel):
    """Base schema for user data."""

    email: str
    full_name: str | None = None
```

### UserCreate

```python
class UserCreate(UserBase):
    """Schema for creating a user."""
    pass
```

**Example:**

```json
{
  "email": "user@example.com",
  "full_name": "John Doe"
}
```

### UserUpdate

```python
class UserUpdate(BaseModel):
    """Schema for updating a user."""

    email: str | None = None
    full_name: str | None = None
    is_active: bool | None = None
```

### UserRead

```python
class UserRead(BaseModel):
    """Schema for reading a user."""

    id: uuid.UUID
    email: str
    full_name: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
```

**Example:**

```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "email": "user@example.com",
  "full_name": "John Doe",
  "is_active": true,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

**Source:** [app/modules/user/schemas.py](https://github.com/balakmran/quoin-api/blob/main/app/modules/user/schemas.py)

---

## Repository

Database operations (CRUD).

### UserRepository

```python
class UserRepository:
    """Repository for user database operations."""

    async def create(self, user_create: UserCreate) -> User:
        """Create a new user."""
        ...

    async def get(self, user_id: uuid.UUID) -> User | None:
        """Get user by ID."""
        ...

    async def get_by_email(self, email: str) -> User | None:
        """Get user by email."""
        ...

    async def list(
        self, skip: int = 0, limit: int = 100
    ) -> list[User]:
        """List users with pagination."""
        ...

    async def update(
        self, user: User, user_update: UserUpdate
    ) -> User:
        """Update a user."""
        ...

    async def delete(self, user: User) -> None:
        """Delete a user."""
        ...
```

**Source:** [app/modules/user/repository.py](https://github.com/balakmran/quoin-api/blob/main/app/modules/user/repository.py)

---

## Service

Business logic layer.

### UserService

```python
class UserService:
    """Service for user business logic."""

    async def create_user(self, user_create: UserCreate) -> User:
        """
        Create a new user.

        Raises:
            ConflictError: If email already exists
        """
        existing = await self.repository.get_by_email(user_create.email)
        if existing:
            raise ConflictError(message="Email already registered")

        return await self.repository.create(user_create)

    async def get_user(self, user_id: uuid.UUID) -> User:
        """
        Get user by ID.

        Raises:
            NotFoundError: If user not found
        """
        user = await self.repository.get(user_id)
        if not user:
            raise NotFoundError(message="User not found")
        return user

    async def list_users(
        self, skip: int = 0, limit: int = 100
    ) -> list[User]:
        """List all users with pagination."""
        return await self.repository.list(skip=skip, limit=limit)

    async def update_user(
        self, user_id: uuid.UUID, user_update: UserUpdate
    ) -> User:
        """Update a user."""
        user = await self.get_user(user_id)  # Raises NotFoundError if not found
        return await self.repository.update(user, user_update)

    async def delete_user(self, user_id: uuid.UUID) -> None:
        """Delete a user."""
        user = await self.get_user(user_id)  # Raises NotFoundError if not found
        await self.repository.delete(user)
```

**Source:** [app/modules/user/service.py](https://github.com/balakmran/quoin-api/blob/main/app/modules/user/service.py)

---

## Routes

FastAPI endpoint definitions.

### Endpoints

#### POST /api/v1/users/

Create a new user.

**Request Body:** `UserCreate`

**Response:** `UserRead` (201 Created)

**Errors:**

- `409 Conflict` — Email already exists

**Example:**

```bash
curl -X POST http://localhost:8000/api/v1/users/ \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "full_name": "John Doe"}'
```

#### GET /api/v1/users/

List all users.

**Query Parameters:**

- `skip` (int, default: 0) — Pagination offset
- `limit` (int, default: 100) — Pagination limit

**Response:** `list[UserRead]` (200 OK)

**Example:**

```bash
curl http://localhost:8000/api/v1/users/?skip=0&limit=10
```

#### GET /api/v1/users/{user_id}

Get user by ID.

**Path Parameters:**

- `user_id` (UUID) — User ID

**Response:** `UserRead` (200 OK)

**Errors:**

- `404 Not Found` — User not found

**Example:**

```bash
curl http://localhost:8000/api/v1/users/123e4567-e89b-12d3-a456-426614174000
```

#### PATCH /api/v1/users/{user_id}

Update a user.

**Path Parameters:**

- `user_id` (UUID) — User ID

**Request Body:** `UserUpdate`

**Response:** `UserRead` (200 OK)

**Errors:**

- `404 Not Found` — User not found

**Example:**

```bash
curl -X PATCH http://localhost:8000/api/v1/users/123e4567-e89b-12d3-a456-426614174000 \
  -H "Content-Type: application/json" \
  -d '{"full_name": "Jane Doe"}'
```

#### DELETE /api/v1/users/{user_id}

Delete a user.

**Path Parameters:**

- `user_id` (UUID) — User ID

**Response:** `204 No Content`

**Errors:**

- `404 Not Found` — User not found

**Example:**

```bash
curl -X DELETE http://localhost:8000/api/v1/users/123e4567-e89b-12d3-a456-426614174000
```

**Source:** [app/modules/user/routes.py](https://github.com/balakmran/quoin-api/blob/main/app/modules/user/routes.py)

---

## See Also

- [Error Handling Guide](../guides/error-handling.md) — Exception patterns
- [Testing Guide](../guides/testing.md) — How to test the user module
- [Database Migrations](../guides/database-migrations.md) — Schema management
