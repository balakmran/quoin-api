# Troubleshooting

Common issues and their solutions for the QuoinAPI project.

---

## Application Startup

### "Database engine is not initialized"

```
RuntimeError: Database engine is not initialized
```

**Cause**: The database engine wasn't created during app lifespan.

**Solution**: Ensure `create_app()` is used and the lifespan context
manager runs:

```python
# Correct
from app.main import app  # Uses create_app()

# Incorrect
app = FastAPI()  # Missing lifespan
```

### "FAILED: Target database is not up to date"

```
alembic.util.exc.CommandError: Target database is not up to date.
```

**Cause**: Database schema is behind the code.

**Solution**: Run pending migrations:

```bash
just migrate-up
```

---

## Database Issues

### Connection Refused

```
psycopg.OperationalError: connection failed: connection to server at
"127.0.0.1", port 5432 failed: Connection refused
```

The migration commands connect with `psycopg`; the running app uses
`asyncpg`, which reports the same problem as
`ConnectionRefusedError: [Errno 61] Connect call failed`.

**Check:**

1. Is PostgreSQL running?

   ```bash
   just db  # Start database
   ```

2. Are `QUOIN_POSTGRES_*` env vars correct?

   ```bash
   cat .env | grep QUOIN_POSTGRES
   ```

3. Is the port already in use?

   ```bash
   lsof -i :5432
   ```

4. Did the container start but then fail? Check what it logged:

   ```bash
   just logs
   ```

### "Async driver Required for Async Operations"

```
sqlalchemy.exc.InvalidRequestError: The asyncio extension requires an
async driver to be used.
```

**Cause**: Using `postgresql://` instead of `postgresql+asyncpg://`.

**Solution**: Check `QUOIN_POSTGRES_DRIVER` in `.env`:

```bash
# .env
QUOIN_POSTGRES_DRIVER=postgresql+asyncpg
```

### Migration Conflicts

```
FAILED: Can't locate revision identified by 'abc123'
ERROR: Multiple head revisions are present
```

**Cause**: Two branches each added a migration off the same parent, or
the database was stamped with a revision this checkout doesn't have.

**Solution**:

1. Compare the history with the database:

   ```bash
   uv run alembic heads      # more than one line means two heads
   uv run alembic current
   ```

2. For two heads, rebase one branch's migration onto the other (edit its
   `down_revision`) if it hasn't been applied anywhere; otherwise join
   them with `uv run alembic merge -m "merge heads" <rev1> <rev2>`.

3. Never delete a migration that has been applied to a shared
   database. See [Database Migrations](database-migrations.md).

---

## Testing Issues

### "Fixture not found"

```
pytest.fixture.FixtureNotFound: fixture 'app' not found
```

**Cause**: The fixture name is misspelled or defined outside the test's
scope. The shared fixtures live in `tests/conftest.py`: `db_session`,
`client`, `read_client`, and `admin_client`.

**Solution**: Use one of those, or define the fixture in the nearest
`conftest.py`. See the [Testing guide](testing.md).

### Tests Fail with "Event loop is closed"

```
RuntimeError: Event loop is closed
```

**Cause**: An async resource (engine, client, session) created outside
the shared event loop, or a sync fixture holding onto one.

**Solution**: The suite runs `pytest-asyncio` in `auto` mode on one
session-scoped loop, so declare tests and fixtures as plain
`async def` — no `@pytest.mark.asyncio` — and take the shared fixtures
rather than building your own engine:

```python
async def test_user_creation(client: AsyncClient):
    response = await client.post("/api/v1/users/", ...)
```

### Database State Leaks Between Tests

**Cause**: The test wrote through a session other than `db_session`, or
committed on a connection outside its SAVEPOINT.

**Solution**: Take the `db_session` fixture (or a client built on it,
such as `client`), which rolls back after each test. See
[Testing](testing.md).

---

## Development Server

### Auto-reload Not Working

**Cause**: The server was started with `fastapi run`, or another way
that doesn't watch files.

**Solution**: Use the `just dev` command (or `just run` if the database
is already up):

```bash
just dev  # Runs `fastapi dev`, which reloads on change
```

### Port Already in Use

```
OSError: [Errno 48] Address already in use
```

**Solution**: Kill the process using port 8000:

```bash
lsof -ti:8000 | xargs kill -9
```

Or change the port:

```bash
uv run fastapi dev app/main.py --port 8001
```

---

## Documentation Build

### "mkdocstrings plugin is enabled but not installed"

A docs build fails on a missing module such as `zensical` or
`mkdocstrings`.

**Solution**: Install the docs dependencies:

```bash
uv sync --group docs
```

### Page Not Found in Navigation

**Cause**: File exists but not in `zensical.toml` nav.

**Solution**: Add page to navigation:

```toml
# zensical.toml
nav = [
    { "Guides" = [
        { "My New Page" = "guides/my-new-page.md" },
    ]},
]
```

---

## Dependency Management

### "Package not found"

```
error: Failed to download package
```

**Solution**: Clear cache and retry:

```bash
uv cache clean
uv sync
```

### Lock File Out of Sync

```
error: The lockfile is out of sync with pyproject.toml
```

**Solution**: Re-resolve the lockfile against `pyproject.toml`:

```bash
uv lock
```

Don't add `--upgrade`; that also bumps every dependency, which belongs
in its own change.

---

## Docker Issues

### Build Fails: "No module named 'app'"

**Cause**: Source files not copied into the image.

**Solution**: Check `Dockerfile` has `COPY` commands:

```dockerfile
COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini .
```

### Container Exits Immediately

**Check logs**:

```bash
docker logs <container-id>
```

**Common causes:**

1. Database not accessible (check the `QUOIN_POSTGRES_*` variables)
2. Production config incomplete: the app exits at startup if
   `QUOIN_ALLOWED_HOSTS` or an OAuth trust anchor is missing; the log
   names it (see [Deployment](deployment.md#environment-variables))
3. Migrations not applied (the image doesn't run them; see
   [Database Migrations](database-migrations.md#production-deployments))

---

## Type Checking

### "Incompatible types in assignment"

```
error[invalid-return-type]: Return type does not match returned value
  expected `User`, found `User | None`
```

**Cause**: Function can return `None` but type hint doesn't allow it.

**Solution**: Add `| None` to return type:

```python
async def get_user(user_id: UUID) -> User | None:  # Allow None
    return await self.session.get(User, user_id)
```

### "Missing type parameters"

The project requires 100% type hints, and a bare `list` or `dict` is
rejected in review.

**Solution**: Add type parameters:

```python
# Wrong
def get_users() -> list: ...


# Correct
def get_users() -> list[User]: ...
```

---

## Performance

### Slow Queries

**Enable SQL echo** to see queries:

```python
# app/db/session.py, in create_db_engine()
return create_async_engine(
    url or str(settings.DATABASE_URL),
    echo=True,  # Print all SQL; revert before committing
    ...
)
```

**Common fixes:**

1. Add database indexes
2. Load related rows in one query (`selectinload` / `joinedload`)
   instead of one query per row
3. Paginate large result sets

### High Memory Usage

**Check:**

1. Connection pool size (default: 20), per process:

   ```bash
   QUOIN_DB_POOL_SIZE=10
   QUOIN_DB_MAX_OVERFLOW=5
   ```

2. Leaked sessions (use `async with` context manager)

3. Large result sets (add pagination)

---

## Production Issues

### Unexpected 500 Errors

An exception no handler maps comes back as a generic `500`
`application/problem+json` response and is logged as
`unhandled_exception` with the exception type and path. The response
never carries the message; find it in the log by the request ID.

**Solution**: Raise a domain exception (a `QuoinError` subclass from
`app/core/exceptions.py`) so the caller gets a meaningful status. If a
third-party exception needs its own mapping, register a handler in
`add_exception_handlers()` in `app/core/exception_handlers.py`, typing
`exc` as `Any`:

```python
async def vendor_exception_handler(request: Request, exc: Any) -> Response:
    logger.error("vendor_error", detail=str(exc))
    ...


app.add_exception_handler(VendorError, vendor_exception_handler)
```

See [Error Handling](error-handling.md).

### OTEL Slowing Down Requests

**Solution**: Disable tracing in development:

```bash
# .env
QUOIN_OTEL_ENABLED=False  # Disable tracing
```

In production, a slow or unreachable OTLP collector is the usual
cause; see [Observability](observability.md).

---

## Getting Help

If you're still stuck:

1. **Check logs**: `just logs` or `just dev` output
2. **Search docs**: Use the search bar in the documentation site
3. **Check GitHub Issues**: Look for similar problems
4. **Review tests**: See how the feature is tested in `tests/`

---

## Common Commands Reference

| Issue                 | Command                  |
| :-------------------- | :----------------------- |
| Start database        | `just db`                |
| Run migrations        | `just migrate-up`        |
| Run all checks        | `just check`             |
| Rebuild docs          | `just docb`              |
| View logs             | `just logs`              |
| Reset database        | `just reset-db`          |
| Clean build artifacts | `just clean`             |

## See Also

- [Getting Started](getting-started.md) — the setup these failures
  interrupt
- [Configuration](configuration.md) — every setting named above
- [Observability](observability.md) — reading the logs and traces that
  explain a failure
