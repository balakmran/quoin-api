# Testing

This guide explains the testing philosophy, patterns, and best practices
for the QuoinAPI project.

---

## Philosophy

The project follows these testing principles:

1. **Integration over Unit**: Prioritize integration tests that exercise
   the full stack (routes → services → repositories → database)
2. **Real Database**: Use a real PostgreSQL database for repository tests,
   not mocks
3. **Full Coverage**: 100% line and branch coverage, enforced
4. **Fast Feedback**: Tests should run in <10 seconds

---

## Test Structure

Tests mirror the `app/` structure:

```
tests/
├── conftest.py                  # Shared fixtures
├── test_main.py                 # App factory tests
├── test_db.py                   # Session and engine tests
├── test_migration_guard.py      # Migration safety checks
├── test_scaffold_module.py      # `just new` output
├── test_problem_details_hook.py # Error-contract hook on every response
├── test_template_substitution.py # Copier substitution and headroom
├── test_tool_pins.py            # Tool versions agree across files
├── test_bump_version.py         # `just bump`
├── test_tag_release.py          # `just tag`
├── test_copier_update_workflow.py # Update-check workflow
├── core/                        # config, security, middlewares,
│   └── ...                      # logging, telemetry, pagination, ...
├── http/
│   └── test_client.py           # Outbound client (retries, breaker)
└── modules/
    ├── system/
    │   └── test_routes.py       # Health and readiness endpoints
    └── user/
        ├── test_models.py       # Model validation
        ├── test_routes.py       # API endpoints
        ├── test_exceptions.py   # Module exception classes
        └── test_concurrency.py  # Cross-transaction races
```

The `user` module has no `test_service.py` or `test_repository.py`: both
layers are covered through `test_routes.py`, which drives them through
the API against a real database and calls the repository directly for
edge cases. Split them out when a layer grows logic worth testing on its
own.

---

## Pytest Configuration

Pytest is configured in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"   # All async tests run without @pytest.mark.asyncio
asyncio_default_fixture_loop_scope = "session"
asyncio_default_test_loop_scope = "session"
testpaths = ["tests"]
pythonpath = ["."]
python_files = ["test_*.py"]

[tool.coverage.run]
source = ["app"]
branch = true
concurrency = ["thread", "greenlet"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "if __name__ == .__main__.:",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
]
show_missing = true
fail_under = 100
```

!!! warning
    `asyncio_mode = "auto"` means all `async def test_*` functions run
    automatically as async. Do **not** add `@pytest.mark.asyncio` —
    it's redundant and causes a warning. Tests and fixtures share one
    session-scoped event loop, so an async resource built at module
    level or in a sync fixture can end up on a different loop.

---

## Fixtures

Shared fixtures are defined in
[`tests/conftest.py`](https://github.com/balakmran/quoin-api/blob/main/tests/conftest.py).

### `initialize_db` — Database Setup

Runs automatically before the test session begins. It builds the schema
by **running the Alembic migration chain** (`alembic upgrade head`),
yields, then reverses the chain (`alembic downgrade base`) and disposes
the engine at the end of the session. Building from migrations — rather
than `SQLModel.metadata.create_all` — means model/migration drift fails
the suite instead of shipping silently, and running the down-migrations
at teardown exercises them too.

The connection URL is assembled from settings parts (overriding only the
database name to the maintenance `postgres` database) rather than
string-replacing the name inside an assembled URL:

```python
@pytest.fixture(scope="session", autouse=True)
async def initialize_db() -> AsyncGenerator[None, None]:
    engine = create_db_engine(url=_test_database_url())
    fastapi_app.state.engine = engine
    fastapi_app.state.session_factory = create_session_factory(engine)

    # Reset any leftover state, then build the schema from migrations.
    async with engine.connect() as conn:
        await conn.run_sync(_reset_schema)
        await conn.commit()
    async with engine.connect() as conn:
        await conn.run_sync(_upgrade_to_head)  # alembic upgrade head

    yield

    async with engine.connect() as conn:
        await conn.run_sync(_downgrade_to_base)  # alembic downgrade base

    await engine.dispose()
    fastapi_app.state.engine = None
```

Running Alembic against a live connection requires `alembic/env.py`'s
`run_migrations_online()` to reuse a connection injected via
`config.attributes["connection"]`; the test helpers set that attribute
before calling `command.upgrade` / `command.downgrade`.

### `db_session` — Isolated Database Session

Provides a session bound to an outer transaction that is rolled back
after each test — guaranteeing a clean slate. With
`join_transaction_mode="create_savepoint"`, a `session.commit()` inside
a test releases a SAVEPOINT instead of committing for real, so tests
that commit still stay isolated:

```python
@pytest.fixture
async def db_session(
    initialize_db: None,
) -> AsyncGenerator[AsyncSession]:
    connection = await fastapi_app.state.engine.connect()
    trans = await connection.begin()
    session_maker = async_sessionmaker(
        bind=connection,
        class_=AsyncSession,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    session = session_maker()
    try:
        yield session
    finally:
        await session.close()
        await trans.rollback()
        await connection.close()
```

### `client` — Async HTTP Client

Overrides the `get_session` dependency to inject the test session, so
HTTP requests use the same rolled-back transaction. It also attaches the
problem-details contract hook to every response:

```python
@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    fastapi_app.dependency_overrides[get_session] = lambda: db_session
    async with AsyncClient(
        transport=ASGITransport(app=fastapi_app),
        base_url="http://test",
        event_hooks={"response": [_assert_problem_details_contract]},
    ) as c:
        yield c
    # Pop only the override this fixture added — clearing everything
    # would wipe overrides owned by nested fixtures (e.g. the caller
    # override in read_client / admin_client) during independent teardown.
    fastapi_app.dependency_overrides.pop(get_session, None)
```

!!! tip
    The `client` → `db_session` → `initialize_db` fixture chain means
    requesting `client` in a test automatically sets up a fresh,
    isolated database transaction. You never need to call
    `initialize_db` manually.

!!! warning "Every error response is checked"
    The `response` event hook runs on every response a test makes
    through `client`, including `read_client` and `admin_client`, which
    yield the same client. The test fails if any 4xx or 5xx response:

    - is not `application/problem+json`,
    - lacks `X-Request-ID`, or
    - has a body that does not parse as `ProblemDetail`, or whose
      `status` differs from the response status or whose `instance`
      differs from the request path. (`HEAD` responses have no body,
      so only their headers are checked.)

    This happens even if the test never asserts on that response. If a
    new error path makes a test fail with that message, fix the handler,
    not the test: raise a domain exception so the global handlers render
    it. A test that builds its own `AsyncClient` does not get the hook.

### Pre-built Auth Clients

For tests that hit authenticated endpoints, use the role-scoped client fixtures
instead of `client`:

| Fixture | Roles | Use for |
| :--- | :--- | :--- |
| `client` | none (no auth override) | Unauthenticated requests, testing 401 responses |
| `read_client` | `users.read` | Read-only endpoints (`GET`) |
| `admin_client` | `users.read`, `users.write` | Write endpoints (`POST`, `PATCH`, `DELETE`) |

These fixtures inject a `ServicePrincipal` with the appropriate roles via
`dependency_overrides`, bypassing actual JWT validation in tests.

---

## Testing Patterns

The service, repository, and fixture snippets below are illustrative
patterns, not files in this repo — their fixtures (`user_service`,
`user_repository`, `user_create`) come with them. Only the route and
model examples mirror real files.

### Integration Tests (Routes)

Test the full request-response cycle:

```python
# tests/modules/user/test_routes.py
import pytest


async def test_create_user(admin_client: AsyncClient):
    response = await admin_client.post(
        "/api/v1/users/",
        json={
            "email": "test@example.com",
            "full_name": "Test User",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert "id" in data
    assert "created_at" in data


async def test_create_user_duplicate_email(admin_client: AsyncClient):
    # First user succeeds
    await admin_client.post(
        "/api/v1/users/",
        json={
            "email": "duplicate@example.com",
            "full_name": "First User",
        },
    )

    # Second user with same email fails
    response = await admin_client.post(
        "/api/v1/users/",
        json={
            "email": "duplicate@example.com",
            "full_name": "Second User",
        },
    )

    assert response.status_code == 409
    assert "already registered" in response.json()["detail"]
```

### Service Tests

Test business logic in isolation:

```python
# tests/modules/user/test_service.py (example)
import pytest
from app.core.exceptions import ConflictError, NotFoundError


async def test_create_user_duplicate_email_raises(
    user_service: UserService,
    user_create: UserCreate,
):
    # Create first user
    await user_service.create_user(user_create)

    # Try to create duplicate
    with pytest.raises(ConflictError) as exc_info:
        await user_service.create_user(user_create)

    assert exc_info.value.message == "Email already registered"
    assert exc_info.value.status_code == 409


async def test_get_user_not_found_raises(user_service: UserService):
    with pytest.raises(NotFoundError):
        await user_service.get_user(uuid.uuid4())
```

### Repository Tests

Test database operations:

```python
# tests/modules/user/test_repository.py (example)
async def test_create_user(
    user_repository: UserRepository,
    user_create: UserCreate,
):
    user = await user_repository.create(user_create)

    assert user.id is not None
    assert user.email == user_create.email
    assert user.created_at is not None


async def test_get_by_email(
    user_repository: UserRepository,
    user_create: UserCreate,
):
    created_user = await user_repository.create(user_create)
    found_user = await user_repository.get_by_email(user_create.email)

    assert found_user is not None
    assert found_user.id == created_user.id
```

### Model Tests

Test Pydantic validation:

```python
# tests/modules/user/test_models.py
import pytest
from pydantic import ValidationError


def test_user_create_valid():
    user = UserCreate(email="test@example.com", full_name="Test User")
    assert user.email == "test@example.com"
    assert user.is_active is True  # default


def test_user_create_invalid_email():
    with pytest.raises(ValidationError) as exc_info:
        UserCreate(email="not-an-email", full_name="Test")

    errors = exc_info.value.errors()
    assert "email" in str(errors[0]["loc"])
```

---

## Test Data Management

### Using Fixtures for Test Data

Create reusable data fixtures:

```python
# tests/modules/user/conftest.py (example)
@pytest.fixture
def user_create() -> UserCreate:
    return UserCreate(
        email="testuser@example.com",
        full_name="Test User",
    )


@pytest.fixture
async def sample_user(
    user_repository: UserRepository,
    user_create: UserCreate,
) -> User:
    return await user_repository.create(user_create)
```

### Factories for Multiple Objects

Use factory pattern for generating test data:

```python
def create_user_data(email: str | None = None) -> dict:
    return {
        "email": email or f"user{uuid.uuid4()}@example.com",
        "full_name": "Test User",
    }


async def test_list_users(admin_client: AsyncClient):
    # Create multiple users
    for _ in range(5):
        await admin_client.post("/api/v1/users/", json=create_user_data())

    response = await admin_client.get("/api/v1/users/")
    assert response.json()["total"] == 5
```

---

## Mocking External Dependencies

For external APIs, patch the call with `unittest.mock`. The
`app.services.email` target below is a stand-in for your own integration:

```python
from unittest.mock import AsyncMock, patch


async def test_send_email_notification(
    user_service: UserService, user_create: UserCreate
):
    with patch(
        "app.services.email.send_email", new=AsyncMock(return_value=True)
    ) as mock_send:
        await user_service.create_user_with_welcome_email(user_create)

    # Verify email was sent
    mock_send.assert_called_once()
    call_args = mock_send.call_args[1]
    assert call_args["to"] == user_create.email
```

---

## Testing Configuration

To test how code reacts to a setting, build a fresh `Settings` from
environment variables. Pass `_env_file=None` so a developer's local
`.env` can't leak into the assertion:

```python
from app.core.config import Settings


def test_with_custom_config(monkeypatch):
    monkeypatch.setenv("QUOIN_LOG_LEVEL", "WARNING")

    settings = Settings(_env_file=None)

    assert settings.LOG_LEVEL == "WARNING"
```

Avoid `importlib.reload(config)`: it rebinds the module-level
`settings` that the rest of the suite already imported.

---

## Coverage Requirements

Coverage is **100%, enforced** — `fail_under = 100` in
`[tool.coverage.report]` fails the run below it, so a change that adds
an untested branch fails `just check` rather than quietly lowering the
number. Branch coverage is on, so both sides of every conditional must
be exercised, not just every line.

If a line genuinely cannot be covered, mark it `# pragma: no cover`
with a reason rather than lowering the gate.

Excluded from coverage:

- `if __name__ == "__main__"` blocks
- `if TYPE_CHECKING:` blocks
- `__repr__` methods and `raise NotImplementedError` lines
- Anything marked `# pragma: no cover`

---

## CI Integration

Tests run automatically on every push via GitHub Actions, as part of
the single `just check` step:

```yaml
# .github/workflows/ci.yml
- name: Run quality checks
  run: just check
```

Coverage is not a separate CI step — `fail_under = 100` in
`[tool.coverage.report]` ([`pyproject.toml`](../../pyproject.toml))
fails the run wherever coverage is measured, so CI and `just check`
enforce the identical gate.

---

## Best Practices

### Do

- Use descriptive test names: `test_create_user_duplicate_email_returns_409`
- Test both success and failure paths
- Use fixtures for repeated setup
- Clean up resources (database handles itself via transactions)
- Test edge cases (empty lists, None values, boundary conditions)

### Don't

- Mock the database (use a real test DB)
- Write tests that depend on execution order
- Use hard-coded IDs or timestamps
- Test implementation details (test behavior, not internals)
- Skip cleanup (rely on automatic transaction rollback)

---

## Debugging Failed Tests

Run pytest through `uv run` so it uses the project environment. Start
the database first with `just db`; `just test` does it for you.

### Verbose Output

```bash
uv run pytest -vv
```

### Show Print Statements

```bash
uv run pytest -s
```

### Drop into Debugger

```bash
uv run pytest --pdb
```

### Re-run Failed Tests

```bash
uv run pytest --lf  # last failed
uv run pytest --ff  # failed first
```

---

## See Also

- [Pytest Documentation](https://docs.pytest.org/)
- [httpx Testing Guide](https://www.python-httpx.org/async/#calling-into-python-web-apps)
- [tests/conftest.py](https://github.com/balakmran/quoin-api/blob/main/tests/conftest.py) — Shared fixtures
