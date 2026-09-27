# Testing

Tests run against a real Postgres, through the real routes, with every
test rolled back afterwards. Coverage is 100% and enforced. Use the
fixtures in [`tests/conftest.py`](https://github.com/balakmran/quoin-api/blob/main/tests/conftest.py)
and you get a clean database and an authenticated client for free.

Don't mock the database. The schema is built from the Alembic
migrations, so a model/migration mismatch fails the suite instead of
shipping.

## Test Layout

Tests mirror `app/`:

```
tests/
├── conftest.py                  # Shared fixtures
├── test_*.py                    # App factory, DB, migration guard,
│                                # docs coverage, template tooling, ...
├── core/                        # config, security, middlewares, ...
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

The `user` module has no `test_service.py` or `test_repository.py`. Both
layers are covered through `test_routes.py`; split them out when a layer
grows logic worth testing on its own.

`pytest-asyncio` runs in `auto` mode on one session-scoped event loop.
Write tests and fixtures as plain `async def`, with no
`@pytest.mark.asyncio`.

## Fixtures

| Fixture | Gives you |
| :--- | :--- |
| `initialize_db` | Session-wide, automatic. Runs `alembic upgrade head` before the suite and `downgrade base` after, so down-migrations are exercised too |
| `db_session` | An `AsyncSession` inside a transaction that rolls back after the test. `session.commit()` only releases a SAVEPOINT |
| `client` | An `httpx.AsyncClient` over the app, sharing `db_session`. No credentials |
| `anonymous_client` | `client` with the outbound HTTP client stubbed, so an unauthenticated request reaches the `401` path |
| `read_client` | `client` authenticated as a service with `users.read` |
| `admin_client` | `client` authenticated with `users.read` and `users.write` |

The auth clients inject a `ServicePrincipal` through
`dependency_overrides`, so no JWT is minted or validated.

!!! warning "Every error response is checked"
    A `response` hook on `client` (and every client built on it) fails
    the test if any 4xx or 5xx response is not
    `application/problem+json`, lacks `X-Request-ID`, or has a body that
    doesn't parse as `ProblemDetail` with matching `status` and
    `instance`. This runs even if the test never looks at the response.
    If it fires, fix the handler, not the test: raise a domain exception
    and let the global handlers render it.

## Writing Tests

Drive the API through the role-scoped client and assert on the problem
details body for failures:

```python
# tests/modules/user/test_routes.py
async def test_create_user_duplicate_email(admin_client: AsyncClient):
    payload = {"email": "duplicate@example.com", "full_name": "User"}
    await admin_client.post("/api/v1/users/", json=payload)

    response = await admin_client.post("/api/v1/users/", json=payload)

    assert response.status_code == 409
    assert response.json()["type"] == "urn:quoin:error:duplicate_email_error"


async def test_create_user_requires_a_token(anonymous_client: AsyncClient):
    response = await anonymous_client.post(
        "/api/v1/users/", json={"email": "anon@example.com"}
    )
    assert response.status_code == 401
```

Test a service or repository directly when it has logic the routes
can't reach. Assert on the domain exception, not an HTTP status:

```python
async def test_get_user_not_found(db_session: AsyncSession):
    service = UserService(UserRepository(db_session))
    with pytest.raises(UserNotFoundError):
        await service.get_user(uuid.uuid4())
```

Give generated data unique values (`f"user{uuid.uuid4()}@example.com"`)
rather than hard-coded IDs, so tests never depend on each other.

### External calls

Patch outbound calls with `unittest.mock.AsyncMock`. For the shared HTTP
client, see [Outbound HTTP](outbound-http.md#testing).

### Settings

Build a fresh `Settings` from the environment. Pass `_env_file=None` so a
local `.env` can't leak in:

```python
def test_log_level(monkeypatch):
    monkeypatch.setenv("QUOIN_LOG_LEVEL", "WARNING")
    assert Settings(_env_file=None).LOG_LEVEL == "WARNING"
```

Avoid `importlib.reload(config)`; it rebinds the `settings` the rest of
the suite already imported.

## Coverage

`fail_under = 100` with branch coverage on, so `just check` and CI fail
on any untested line or branch. If a line truly can't be covered, mark
it `# pragma: no cover` with a reason rather than lowering the gate.
`TYPE_CHECKING` blocks, `__repr__`, and `raise NotImplementedError` are
excluded already.

## Debugging Failed Tests

Run pytest through `uv run`, with Postgres up (`just db`; `just test`
starts it for you):

```bash
uv run pytest -vv          # verbose
uv run pytest -s           # show print output
uv run pytest --pdb        # drop into the debugger on failure
uv run pytest --lf         # re-run only the last failures
```

### Common failures

- **`Event loop is closed`** — an async resource was built at module
  level or in a sync fixture, so it sits on another loop. Declare tests
  and fixtures as plain `async def` and take the shared fixtures instead
  of building your own engine.
- **`fixture '...' not found`** — the shared fixtures are listed above;
  define anything else in the nearest `conftest.py`.
- **State leaks between tests** — the test wrote through a session other
  than `db_session`, so its SAVEPOINT rollback didn't cover it.

## See Also

- [Quality Checks](quality-checks.md) — the gate that runs this suite
  locally and in CI
- [Pytest Documentation](https://docs.pytest.org/)
- [httpx: calling into Python web apps](https://www.python-httpx.org/async/#calling-into-python-web-apps)
