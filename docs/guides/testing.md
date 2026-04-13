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
3. **High Coverage**: Maintain >95% code coverage
4. **Fast Feedback**: Tests should run in <10 seconds

---

## Test Structure

Tests mirror the `app/` structure:

```
tests/
├── conftest.py                  # Shared fixtures
├── test_main.py                 # App factory tests
├── test_db.py                   # Database setup tests
├── core/
│   ├── test_exceptions.py       # Exception classes
│   └── test_exception_handlers.py
├── modules/
│   ├── system/
│   │   └── test_routes.py       # Integration tests
│   └── user/
│       ├── test_models.py       # Model validation
│       ├── test_repository.py   # Database operations
│       ├── test_service.py      # Business logic
│       └── test_routes.py       # API endpoints
```

---

## Pytest Configuration

Pytest is configured in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"   # All async tests run without @pytest.mark.asyncio
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
    "if __name__ == .__main__.:",
    "if TYPE_CHECKING:",
]
show_missing = true
```

> [!IMPORTANT]
> `asyncio_mode = "auto"` means all `async def test_*` functions run
> automatically as async. Do **not** add `@pytest.mark.asyncio` —
> it's redundant and causes a warning.

---

## Fixtures

Shared fixtures are defined in
[`tests/conftest.py`](https://github.com/balakmran/quoin-api/blob/main/tests/conftest.py).

### `initialize_db` — Database Setup

Runs automatically before the test session begins. Creates all tables once, yields,
then drops all tables and disposes the engine at the end of the session, drastically improving test speeds:

```python
@pytest.fixture(scope="session", autouse=True)
async def initialize_db() -> AsyncGenerator[None, None]:
    original_db = settings.POSTGRES_DB
    settings.POSTGRES_DB = "postgres"

    fastapi_app.state.engine = create_db_engine()

    async with fastapi_app.state.engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    yield

    async with fastapi_app.state.engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)

    await fastapi_app.state.engine.dispose()
    fastapi_app.state.engine = None
    settings.POSTGRES_DB = original_db
```

### `db_session` — Isolated Database Session

Provides a session bound to a transaction that is rolled back after
each test — guaranteeing a clean slate:

```python
@pytest.fixture
async def db_session(
    initialize_db: None,
) -> AsyncGenerator[AsyncSession, None]:
    connection = await fastapi_app.state.engine.connect()
    trans = await connection.begin()
    session_maker = async_sessionmaker(
        bind=connection,
        class_=AsyncSession,
        expire_on_commit=False,
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

Overrides the `get_session` dependency to inject the test session,
so HTTP requests use the same rolled-back transaction:

```python
@pytest.fixture
async def client(
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    fastapi_app.dependency_overrides[get_session] = lambda: db_session
    async with AsyncClient(
        transport=ASGITransport(app=fastapi_app),
        base_url="http://test",
    ) as c:
        yield c
    fastapi_app.dependency_overrides.clear()
```

> [!TIP]
> The `client` → `db_session` → `initialize_db` fixture chain means
> requesting `client` in a test automatically sets up a fresh, isolated
> database transaction. You never need to call `initialize_db` manually.

---

## Testing Patterns

### Integration Tests (Routes)

Test the full request-response cycle:

```python
# tests/modules/user/test_routes.py
import pytest

async def test_create_user(client: AsyncClient):
    response = await client.post("/api/v1/users/", json={
        "email": "test@example.com",
        "full_name": "Test User",
    })

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert "id" in data
    assert "created_at" in data

async def test_create_user_duplicate_email(client: AsyncClient):
    # First user succeeds
    await client.post("/api/v1/users/", json={
        "email": "duplicate@example.com",
        "full_name": "First User",
    })

    # Second user with same email fails
    response = await client.post("/api/v1/users/", json={
        "email": "duplicate@example.com",
        "full_name": "Second User",
    })

    assert response.status_code == 409
    assert response.json() == {"detail": "Email already registered"}
```

### Service Tests

Test business logic in isolation:

```python
# tests/modules/user/test_service.py
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
# tests/modules/user/test_repository.py
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
# tests/modules/user/conftest.py
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

async def test_list_users(client: AsyncClient):
    # Create multiple users
    for _ in range(5):
        await client.post("/api/v1/users/", json=create_user_data())

    response = await client.get("/api/v1/users/")
    assert len(response.json()) == 5
```

---

## Mocking External Dependencies

For external APIs, use `pytest-mock` or `unittest.mock`:

```python
from unittest.mock import AsyncMock, patch

async def test_send_email_notification(mocker):
    # Mock the email service
    mock_send = mocker.patch(
        "app.services.email.send_email",
        new=AsyncMock(return_value=True)
    )

    await user_service.create_user_with_welcome_email(user_create)

    # Verify email was sent
    mock_send.assert_called_once()
    call_args = mock_send.call_args[1]
    assert call_args["to"] == user_create.email
```

---

## Testing Configuration

Use `monkeypatch` to override settings:

```python
async def test_with_custom_config(monkeypatch, app):
    # Override settings
    monkeypatch.setenv("QUOIN_ENV", "test")
    monkeypatch.setenv("QUOIN_OTEL_ENABLED", "false")

    # Re-import to pick up new settings
    from importlib import reload
    from app.core import config
    reload(config)

    assert config.settings.ENV == "test"
```

---

## Coverage Requirements

The project maintains high coverage standards:

- **Overall**: >95%
- **Services**: 100% (business logic must be fully tested)
- **Routes**: >90% (integration tests)
- **Models**: >90% (validation tests)

Excluded from coverage:

- `if __name__ == "__main__"` blocks
- Type checking code
- Debug-only code paths

---

## CI Integration

Tests run automatically on every push via GitHub Actions:

```yaml
# .github/workflows/ci.yml
- name: Run tests
  run: just test

- name: Check coverage
  run: coverage report --fail-under=95
```

---

## Best Practices

### ✅ Do

- Use descriptive test names: `test_create_user_duplicate_email_returns_409`
- Test both success and failure paths
- Use fixtures for repeated setup
- Clean up resources (database handles itself via transactions)
- Test edge cases (empty lists, None values, boundary conditions)

### ❌ Don't

- Mock the database (use a real test DB)
- Write tests that depend on execution order
- Use hard-coded IDs or timestamps
- Test implementation details (test behavior, not internals)
- Skip cleanup (rely on automatic transaction rollback)

---

## Debugging Failed Tests

### Verbose Output

```bash
pytest -vv
```

### Show Print Statements

```bash
pytest -s
```

### Drop into Debugger

```bash
pytest --pdb
```

### Re-run Failed Tests

```bash
pytest --lf  # last failed
pytest --ff  # failed first
```

---

## See Also

- [Pytest Documentation](https://docs.pytest.org/)
- [httpx Testing Guide](https://www.python-httpx.org/async/#calling-into-python-web-apps)
- [tests/conftest.py](https://github.com/balakmran/quoin-api/blob/main/tests/conftest.py) — Shared fixtures
