---
name: quoin-new-module
description: Use this skill whenever the user wants to add a new feature module, domain, or resource to the QuoinAPI codebase. Triggers include phrases like "add a product module", "scaffold an orders feature", "create a new resource for X", "set up a payments module", "I want to add a new domain for Y", or any request that implies creating a fresh `app/modules/<name>/` package with its own model, schemas, service, repository, routes, and tests. Do NOT use for adding fields/columns to an existing model (that is a migration task), editing an existing module, or adding a single new endpoint to a module that already exists — only for greenfield modules where the directory doesn't yet exist.
---

# Creating a New QuoinAPI Module

A QuoinAPI feature is a self-contained DDD module under `app/modules/<name>/` with seven files in a strict layered structure: routes → service → repository → DB. This skill is a checklist; the long-form prose lives in [docs/guides/creating-a-module.md](../../../docs/guides/creating-a-module.md), and [app/modules/user/](../../../app/modules/user/) is the working reference to mirror.

## Before you start

- Confirm the module name with the user if it's ambiguous. Use a singular, snake_case noun (e.g. `product`, `order_item`, not `Products`).
- Check the directory doesn't already exist — if it does, this is an edit task, not a scaffold task.
- Make sure the DB is up (`just db`) so migrations and tests can run.

## Workflow

Work top-to-bottom. Each step has a reason — don't skip layers, and don't leave a step half-done before moving on.

### 1. Scaffold the skeleton

```bash
just new <module>
```

This creates `app/modules/<module>/{__init__,models,schemas,repository,service,routes,exceptions}.py` and `tests/modules/<module>/test_routes.py`. The files start empty — you fill them in.

### 2. Define the model (`models.py`)

A SQLModel table class. Use `EmailStr` for any email field. Read [app/modules/user/models.py](../../../app/modules/user/models.py) and copy the shape (table config, primary key, timestamps).

### 3. Define schemas (`schemas.py`)

Pydantic request and response models. Keep them separate from the DB model — the schema is the public contract, the model is storage. Use `EmailStr` here too for emails.

### 4. Domain exceptions (`exceptions.py`)

Module-specific errors that extend `QuoinError` (or one of its subclasses in `app/core/exceptions.py`). Example: `ProductNotFoundError(NotFoundError)`. The framework's exception handlers will map these to clean JSON responses automatically — but only if you raise the domain type, never `HTTPException`.

### 5. Repository (`repository.py`)

Async CRUD only. No business logic, no orchestration, no exception raising beyond what the DB itself raises. Takes a session, returns models or `None`.

### 6. Service (`service.py`)

Async business logic. This is where you raise `NotFoundError`, `ConflictError`, `BadRequestError`, `ForbiddenError`, `InternalServerError` from `app/core/exceptions` (or your module's own subclasses). Never raise `HTTPException` from service code — the global handler can't standardize what it doesn't recognize.

### 7. Routes (`routes.py`)

- All paths must end up under `/api/v1/` (the prefix is applied centrally in `app/api.py`, so just declare `APIRouter(prefix="/<module>", tags=["<Module>"])`).
- Protect every endpoint with `require_roles("scope.action")` from `app/core/security`. Read an existing route in `app/modules/user/routes.py` to match the dependency pattern.
- Routes should be thin: parse input, call service, return response. No business logic here.

### 8. Expose the router (`__init__.py`)

```python
from app.modules.<module>.routes import router

__all__ = ["router"]
```

### 9. Register in `app/api.py`

Add the import and `v1_router.include_router(<module>_router)` next to the existing modules. Without this step the routes don't actually mount — easy to forget.

### 10. Generate and apply the migration

```bash
just migrate-gen "add <module> model"
```

**Open the generated file in `alembic/versions/` and read it before applying.** Autogenerate is good but not infallible — check that it picked up exactly the columns you defined and didn't drop anything unrelated. Then:

```bash
just migrate-up
```

### 11. Write tests

Tests go in `tests/modules/<module>/`. Prefer integration tests against the real DB over mocks — the project's test infrastructure already gives you per-test SAVEPOINT rollback, so pollution isn't a concern.

Use the pre-built fixtures from `tests/conftest.py`:

| Fixture | Use for |
|---|---|
| `client` | Unauthenticated requests |
| `read_client` | Requests as a read-scoped caller |
| `admin_client` | Requests as an admin-scoped caller |
| `db_session` | Direct DB setup/assertions |
| `caller_read` / `caller_admin` | The `ServicePrincipal` for those clients |

Aim for **≥95% coverage** on the new module. Cover the happy path, the auth-denied path, and the domain error paths (404, 409, 400 etc.).

### 12. Run the full check suite

```bash
just check
```

This runs format → lint → typecheck → test. Fix anything that fails before reporting the task complete. Don't skip this — the project's contract is that `just check` is green at every commit.

## Conventions to keep in mind throughout

These bite people often enough that they're worth restating here rather than buried in docs:

- **100% type hints.** When you need to suppress a type error, write the bare `# type: ignore` — never `# type: ignore[arg-type]` or any other MyPy-style tag. The project uses `ty` (Pyright engine), which rejects unrecognized tag names.
- **80-character line limit** for both Python and Markdown. Tables and code blocks are exempt.
- **Async-first.** Every DB call, repository method, and service method is `async def`. If you find yourself writing a sync function in a module, stop and reconsider.
- **Google-style docstrings** on public functions and classes. The Ruff config enforces this.
- **No raw `HTTPException`** in service or repository code — raise a domain exception and let the global handler translate it.

## When something doesn't fit the template

The seven-file structure handles 95% of features. If your module genuinely needs more (e.g. a `tasks.py` for background jobs, a `events.py` for domain events), add the file alongside the others — don't fight the template. But check first whether the work actually belongs in an existing layer; "I need a helpers file" is usually a sign the service is doing too much.

If the user's feature is more like a cross-cutting concern (middleware, a new auth strategy, a telemetry exporter), it probably belongs in `app/core/`, not `app/modules/`. Flag this and ask before scaffolding.
