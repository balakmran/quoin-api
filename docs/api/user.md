# User

Documentation for the User module.

---

## Models

::: app.modules.user.models

## Schemas

::: app.modules.user.schemas

## Repository

::: app.modules.user.repository

## Service

::: app.modules.user.service

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
