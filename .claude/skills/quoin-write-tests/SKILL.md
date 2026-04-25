---
name: quoin-write-tests
description: Use this skill whenever the user wants to write, add, or modify tests in the QuoinAPI codebase — for routes, services, repositories, or any other module-level code. Triggers include phrases like "write tests for", "add a test", "test this endpoint", "I need coverage for", "write a unit test", "write an integration test", "test the create_user flow", or any request that involves creating files under `tests/`. Also use when the user asks how to mock the database, how to inject an authenticated caller, or why their test is leaking state — those are questions about the project's specific test fixtures. Do NOT use for: configuring pytest itself, debugging the test runner, or running the existing suite without writing new tests.
---

# Writing Tests for QuoinAPI

QuoinAPI's test infrastructure is **integration-first against a real Postgres**, with fixtures in [tests/conftest.py](../../../tests/conftest.py) that handle the parts most people get wrong (DB isolation, auth injection, session lifecycle). If you're tempted to mock the database, stop and use the fixtures instead — the project's bug history includes mocked tests that passed while real migrations failed. The long-form reference is [docs/guides/testing.md](../../../docs/guides/testing.md).

## Prerequisites

- **Postgres must be running** (`just db`). Tests connect to a real DB.
- **Tests live in `tests/modules/<module>/`**, mirroring the `app/modules/<module>/` layout.
- **All endpoints are under `/api/v1/`** — write paths as `/api/v1/users/`, not `/users/`.

## The fixture toolkit

These come from `tests/conftest.py`. Use them — don't roll your own.

| Fixture | What it gives you | Use when |
|---|---|---|
| `db_session` | An `AsyncSession` wrapped in a SAVEPOINT that rolls back after the test | Direct DB setup or assertions outside HTTP |
| `client` | `httpx.AsyncClient` with `get_session` overridden to use `db_session`; **no auth** | Testing 401 behavior or public routes |
| `read_client` | Same as `client` but with `caller_read` injected via `dependency_overrides` | Routes requiring `users.read` |
| `admin_client` | Same but with `caller_admin` (`users.read` + `users.write`) | Routes requiring `users.write` |
| `caller_read` / `caller_admin` | The bare `ServicePrincipal` for those roles | Calling service-layer code directly |

The SAVEPOINT pattern means **state from one test never leaks into another** — every test starts fresh, every change rolls back. You can `INSERT` freely without cleaning up.

## A typical test file

```python
import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.modules.product.models import Product


@pytest.mark.asyncio
async def test_create_product_happy_path(admin_client: AsyncClient):
    response = await admin_client.post(
        "/api/v1/products/",
        json={"name": "widget", "price": 999},
    )
    assert response.status_code == 201
    assert response.json()["name"] == "widget"


@pytest.mark.asyncio
async def test_create_product_forbidden_for_read_only(read_client: AsyncClient):
    response = await read_client.post(
        "/api/v1/products/",
        json={"name": "widget", "price": 999},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_product_unauthenticated(client: AsyncClient):
    response = await client.post(
        "/api/v1/products/",
        json={"name": "widget", "price": 999},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_product_returns_404_for_missing(read_client: AsyncClient):
    response = await read_client.get("/api/v1/products/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
```

Notice the auth triple — happy path, forbidden, unauthenticated. Every protected route should have these three.

## Adding callers for a new domain

The shared `caller_read` / `caller_admin` only carry `users.*` roles. If your module uses different scopes (e.g. `products.read`, `products.write`), add domain-specific fixtures to your test file:

```python
import pytest
from app.core.security import ServicePrincipal, get_current_caller
from app.main import app as fastapi_app


@pytest.fixture
def caller_products_admin() -> ServicePrincipal:
    return ServicePrincipal(
        subject="test-products-admin",
        roles=["products.read", "products.write"],
        claims={},
    )


@pytest.fixture
async def products_admin_client(client, caller_products_admin):
    fastapi_app.dependency_overrides[get_current_caller] = lambda: caller_products_admin
    yield client
    fastapi_app.dependency_overrides.pop(get_current_caller, None)
```

**Don't** mutate the shared fixtures — they're used across many tests.

## What to test

For a new module, aim for **≥95% coverage** with these cases:

| Layer | What to cover |
|---|---|
| Routes | happy path, 401 (unauth), 403 (wrong role), 404 (missing), 409 (conflict if applicable), 422 (bad input) |
| Service | each method's happy path + each domain exception path it raises |
| Repository | rarely tested directly; covered transitively by service tests unless there's tricky SQL |

Use `db_session` directly when you need to seed data that the route doesn't expose, or to assert state that isn't in the response (e.g. an audit log row, a soft-deleted flag).

## Running

```bash
just test                                                # full suite, with coverage
uv run pytest tests/modules/product/ -v                  # one module
uv run pytest tests/modules/product/test_routes.py::test_create -v  # one test
```

## Things that bite

- **Mocking `AsyncSession`.** Resist it. The project's session fixture is exactly what production uses; mocking it usually hides the bug you'd catch otherwise. Mock external HTTP only (Stripe, etc.).
- **Forgetting `@pytest.mark.asyncio`.** The test will be collected but never awaited — appears to "pass" while testing nothing. Easy to miss.
- **Asserting on raw SQL ordering.** Postgres does not guarantee row order without `ORDER BY`. If you compare lists, sort them or assert as sets.
- **Reusing one `db_session` across multiple "phases".** The SAVEPOINT covers the whole test; if you commit inside the test, you defeat the rollback. Call `await db_session.flush()` (not `.commit()`) when you need an INSERT to be visible to a subsequent query in the same test.
- **Hitting `/users/` instead of `/api/v1/users/`.** The prefix is applied centrally; routes in modules declare only `/users`. The HTTP path includes `/api/v1`.
