# User

Documentation for the User module.

---

## Models

Database model for users.

### User Model

```python
import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Index, func, literal_column, text
from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    """User model."""

    __tablename__ = "users"
    __table_args__ = (
        Index(
            "ix_users_email_lower",
            func.lower(literal_column("email")),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: str = Field(index=True, max_length=255)
    full_name: str | None = Field(default=None, max_length=255)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
            onupdate=lambda: datetime.now(UTC),
        ),
    )
    # Soft-delete tombstone: NULL means live, a timestamp means deleted.
    deleted_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
```

**Table:** `users`

**Indexes:**

- `ix_users_email` — plain index on `email`, from `index=True`
- `ix_users_email_lower` — case-insensitive **partial** unique index on
  `lower(email)` `WHERE deleted_at IS NULL` (so a soft-deleted user's
  email frees up for reuse)

**Source:** [app/modules/user/models.py](https://github.com/balakmran/quoin-api/blob/main/app/modules/user/models.py)

---

## Schemas

Pydantic schemas for request/response validation.

### UserBase

```python
class UserBase(BaseModel):
    """Base user schema."""

    email: EmailStr = Field(max_length=255)
    full_name: str | None = Field(default=None, max_length=255)
    is_active: bool = True

    model_config = ConfigDict(extra="forbid")
```

The email is validated as an address and lower-cased, so uniqueness
checks are case-insensitive. Unknown fields are rejected with a `422`.

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
    """Schema for partially updating a user."""

    email: EmailStr | SkipJsonSchema[None] = None
    full_name: str | None = Field(default=None, max_length=255)
    is_active: bool | SkipJsonSchema[None] = None

    model_config = ConfigDict(extra="forbid")
```

Omit a field to leave it unchanged. Only `full_name` accepts `null`,
which clears it; `null` for `email` or `is_active` is a 422, because
those columns cannot store it.

### UserRead

```python
class UserRead(BaseModel):
    """Schema for reading a user."""

    id: uuid.UUID
    email: EmailStr
    full_name: str | None = None
    is_active: bool = True
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

Database operations (CRUD). Repositories `flush()` rather than commit;
the request's unit of work commits (see
[Creating a Module](../guides/creating-a-module.md)). Every read excludes
soft-deleted rows.

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
        self,
        params: PageParams,
        *,
        sort: str | None = None,
        is_active: bool | None = None,
        q: str | None = None,
    ) -> tuple[list[User], int]:
        """List a filtered, sorted page of users and the total count."""
        ...

    async def update(self, user: User, user_update: UserUpdate) -> User:
        """Update a user."""
        ...

    async def delete(self, user: User) -> None:
        """Soft-delete a user (stamp the deleted_at tombstone)."""
        ...
```

**Source:** [app/modules/user/repository.py](https://github.com/balakmran/quoin-api/blob/main/app/modules/user/repository.py)

---

## Service

Business logic layer.

### UserService

```python
class UserService:
    """Business-logic layer for User operations."""

    async def create_user(self, user_create: UserCreate) -> User:
        """Create a new user, enforcing email uniqueness.

        Raises:
            DuplicateEmailError: If the email is already registered.
        """
        existing_user = await self.repository.get_by_email(user_create.email)
        if existing_user:
            raise DuplicateEmailError(email=user_create.email)
        return await self.repository.create(user_create)

    async def get_user(self, user_id: uuid.UUID) -> User:
        """Retrieve a user by ID, raising if absent.

        Raises:
            UserNotFoundError: If no user with user_id exists.
        """
        user = await self.repository.get(user_id)
        if not user:
            raise UserNotFoundError(user_id=str(user_id))
        return user

    async def list_users(
        self,
        params: PageParams,
        *,
        sort: str | None = None,
        is_active: bool | None = None,
        q: str | None = None,
    ) -> tuple[list[User], int]:
        """Return a filtered, sorted page of users and the total count."""
        return await self.repository.list(
            params, sort=sort, is_active=is_active, q=q
        )

    async def update_user(
        self, user_id: uuid.UUID, user_update: UserUpdate
    ) -> User:
        """Apply a partial update.

        Raises:
            UserNotFoundError: If no user with user_id exists.
            DuplicateEmailError: If the new email belongs to another user.
        """
        ...

    async def delete_user(self, user_id: uuid.UUID) -> None:
        """Soft-delete a user by ID."""
        user = await self.get_user(user_id)  # UserNotFoundError if absent
        await self.repository.delete(user)
```

**Source:** [app/modules/user/service.py](https://github.com/balakmran/quoin-api/blob/main/app/modules/user/service.py)

---

## Routes

FastAPI endpoint definitions.

Every endpoint requires a bearer token carrying the role named in its
heading: `users.read` for reads, `users.write` for writes. Without one
the API answers `401`; with a valid token that lacks the role, `403`.
The examples assume a local token:

```bash
TOKEN=$(just token --roles="users.read,users.write")
```

See the [Authentication guide](../guides/authentication.md) for how
tokens are validated.

### Endpoints

#### POST /api/v1/users/

Create a new user. Requires `users.write`.

**Request Body:** `UserCreate`

**Response:** `UserRead` (201 Created)

**Errors:**

- `409 Conflict` — Email already exists

**Example:**

```bash
curl -X POST http://localhost:8000/api/v1/users/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "full_name": "John Doe"}'
```

#### GET /api/v1/users/

List users, paginated, sorted, and filtered. Soft-deleted users are
excluded. Requires `users.read`.

**Query Parameters:**

- `limit` (int, default: 100, 1..100) — Page size
- `offset` (int, default: 0) — Rows to skip
- `sort` (str, optional) — Comma-separated fields, `-` prefix for
  descending (e.g. `-created_at,email`). Sortable: `created_at`,
  `updated_at`, `email`, `full_name`.
- `is_active` (bool, optional) — Filter by active flag
- `q` (str, optional) — Case-insensitive search on email/full name

**Response:** `Page[UserRead]` (200 OK) — `{ items, total, limit, offset }`

**Errors:**

- `400 Bad Request` — `sort` names a non-sortable field

**Example:**

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/users/?limit=10&offset=0&sort=-created_at&q=alice"
```

#### GET /api/v1/users/{user_id}

Get user by ID. Requires `users.read`.

**Path Parameters:**

- `user_id` (UUID) — User ID

**Response:** `UserRead` (200 OK)

**Errors:**

- `404 Not Found` — User not found

**Example:**

```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/users/123e4567-e89b-12d3-a456-426614174000
```

#### PATCH /api/v1/users/{user_id}

Update a user. Requires `users.write`.

**Path Parameters:**

- `user_id` (UUID) — User ID

**Request Body:** `UserUpdate`

**Response:** `UserRead` (200 OK)

**Errors:**

- `404 Not Found` — User not found
- `409 Conflict` — Email already registered to another user

**Example:**

```bash
curl -X PATCH \
  http://localhost:8000/api/v1/users/123e4567-e89b-12d3-a456-426614174000 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"full_name": "Jane Doe"}'
```

#### DELETE /api/v1/users/{user_id}

Soft-delete a user (sets the `deleted_at` tombstone). The row is
retained but excluded from all subsequent reads. Requires
`users.write`.

**Path Parameters:**

- `user_id` (UUID) — User ID

**Response:** `204 No Content`

**Errors:**

- `404 Not Found` — User not found (or already soft-deleted)

**Example:**

```bash
curl -X DELETE \
  http://localhost:8000/api/v1/users/123e4567-e89b-12d3-a456-426614174000 \
  -H "Authorization: Bearer $TOKEN"
```

**Source:** [app/modules/user/routes.py](https://github.com/balakmran/quoin-api/blob/main/app/modules/user/routes.py)

---

## See Also

- [Error Handling Guide](../guides/error-handling.md) — Exception patterns
- [Testing Guide](../guides/testing.md) — How to test the user module
- [Database Migrations](../guides/database-migrations.md) — Schema management
