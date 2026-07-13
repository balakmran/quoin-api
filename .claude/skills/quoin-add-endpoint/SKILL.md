---
name: quoin-add-endpoint
description: Use this skill whenever the user wants to add a single new endpoint (route) to an existing QuoinAPI module — a new operation on a resource that already has its own `app/modules/<name>/` package. Triggers include phrases like "add an endpoint to the user module", "add a GET /users/by-email route", "expose a search endpoint on products", "add a deactivate action to users", "add a bulk-create route", or any request to add one route plus the service/repository/schema plumbing behind it. Do NOT use for: scaffolding a brand-new module whose directory doesn't exist yet (that is `quoin-new-module`), changing only the auth/`require_roles` on an existing route (that is `quoin-auth-route`), or altering the DB schema/columns (that is `quoin-db-migration`).
allowed-tools: Read, Edit, Write, Grep, Glob, Bash
---

# Adding an Endpoint to an Existing QuoinAPI Module

This is the common case: a module already exists, and you need one more
operation on it. The work flows **up** the layers — schema → repository →
service → route — so each layer is in place before the one above calls it.
The reference module to mirror is
[app/modules/user/](../../../app/modules/user/); read the matching file
there before writing each layer.

Unlike `quoin-new-module`, you are editing files that already exist. Match
the surrounding code's shape exactly — naming, docstring style, the
`Annotated[X, Depends(...)]` syntax — rather than inventing a new pattern.

## Before you start

- Confirm the endpoint belongs in an **existing** module. If the directory
  doesn't exist yet, stop and use `quoin-new-module` instead.
- Decide whether the operation needs a DB schema change (a new column, a new
  index to support a query). If it does, that is a separate
  `quoin-db-migration` task — do it first, then come back here.
- Make sure the DB is up (`just db`) so tests can run.

## Workflow

Work bottom-to-top. Don't skip a layer, and don't let a route call a service
method that doesn't exist yet.

### 1. Schemas (`schemas.py`)

Add request/response models only if the existing ones don't fit. Reuse
`XxxRead` for responses where you can. For a new input shape, add a focused
schema with `model_config = ConfigDict(extra="forbid")` (see
[app/modules/user/schemas.py](../../../app/modules/user/schemas.py)). Keep
schemas separate from the DB model — the schema is the public contract.

### 2. Repository (`repository.py`)

If the endpoint needs a query the repository doesn't already expose, add an
`async def` method. Repository methods are CRUD/query only — they take the
session, return models or `None`/`list`, and contain **no business logic and
no exception raising** beyond what the DB itself raises. Mirror the existing
`select(...)` query style in
[app/modules/user/repository.py](../../../app/modules/user/repository.py),
including the bare `# type: ignore` on the statements (never a tagged ignore).

### 3. Service (`service.py`)

Add the business-logic method here. This is the **only** layer that raises
domain exceptions —`NotFoundError`, `ConflictError`, `BadRequestError`,
`ForbiddenError`, `InternalServerError` from `app/core/exceptions`, or the
module's own subclasses in `exceptions.py`. Never raise `HTTPException` from
the service; the global handler can only standardize domain exceptions.

If you need a new error condition, add a subclass in the module's
`exceptions.py` following the existing pattern (a tight `__init__` that builds
the message and calls `super().__init__(message=...)`).

### 4. Route (`routes.py`)

Add the route function to the existing `router`. It should be thin: parse
input, call one service method, return the result. Keep these rules:

- **Reuse the module's `get_<module>_service` dependency** — don't construct
  the service inline.
- **Protect it with `require_roles("<domain>.<action>")`** unless it is
  deliberately public. Pick the role string per `quoin-auth-route` (read and
  write are not hierarchical; require both if the route does both).
- **Declare the extra error responses** in the per-route `responses=` block
  (e.g. `404`, `409`) so OpenAPI stays accurate. The router already declares
  `401`/`403`/`500` at the router level — don't repeat those.
- Type the return as the **DB model** (e.g. `-> User`) and set
  `response_model=` to the **read schema** (e.g. `UserRead`), matching the
  existing routes.

No new wiring is needed in `app/api.py` — the module's router is already
registered there; a new route on the same `router` mounts automatically.

### 5. Tests (`tests/modules/<module>/`)

Add tests to the module's existing test file. Use the fixtures from
`tests/conftest.py` (`client`, `read_client`, `admin_client`, `db_session`,
`caller_read`, `caller_admin`). For a protected route write at minimum:

1. **Happy path** — a client whose roles satisfy the requirement; expect 2xx.
2. **Forbidden** — a client lacking the role; expect 403.
3. **Unauthenticated** — the bare `client`; expect 401.
4. **Domain error paths** the route can produce (404, 409, 400, …).

Tests are integration tests against the real DB with per-test SAVEPOINT
rollback — prefer them over mocks. See `quoin-write-tests` for fixture detail.

### 6. Docs

Per the CLAUDE.md docs-coverage rule, a new user-visible endpoint is a
feature change: update the relevant guide in `docs/guides/` in the same turn,
then run `just docb` to verify the build. Don't leave docs as a follow-up.

### 7. Run the full check suite

```bash
just check
```

Format → lint → typecheck → test must all pass before you report done.

## Conventions to keep in mind

- **100% type hints**; suppress with a bare `# type: ignore` only — never a
  MyPy-style tag like `# type: ignore[arg-type]` (the project uses `ty`).
- **80-char line limit** for Python and Markdown (tables/code blocks exempt).
- **Async-first** — every repository and service method is `async def`.
- **Google-style docstrings** on the new public functions.
- **No raw `HTTPException`** in service or repository code.

## Things that bite

- **Adding the route but forgetting `require_roles()`** — the route then
  returns 200 to anyone. Auth is opt-in, not default-deny.
- **Putting business logic or exception raising in the repository** — keep
  that in the service; the repository only talks to the DB.
- **A query that needs a column or index you haven't added** — that's a
  schema change; do the `quoin-db-migration` flow first, don't hand-edit the
  schema.
- **Returning the DB model directly without a `response_model`** — leaks
  storage fields into the API contract. Always set `response_model=` to the
  read schema.
