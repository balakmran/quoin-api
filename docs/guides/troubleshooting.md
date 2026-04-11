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
psycopg.OperationalError: connection refused
```

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
```

**Cause**: Git merge created conflicting migration files.

**Solution**:

1. Check migration history:

   ```bash
   ls alembic/versions/
   ```

2. Delete conflicting migrations (keep the correct one)

3. Regenerate if needed:
   ```bash
   just migrate-gen "merge migrations"
   ```

---

## Testing Issues

### "Fixture not found"

```
pytest.fixture.FixtureNotFound: fixture 'app' not found
```

**Cause**: Missing import or fixture not in visible scope.

**Solution**: Check fixture is defined in `conftest.py`:

```python
# tests/conftest.py
@pytest.fixture
def app() -> FastAPI:
    return create_app()
```

### Tests Fail with "Event loop is closed"

```
RuntimeError: Event loop is closed
```

**Cause**: Mixing sync and async test fixtures.

**Solution**: Use `pytest-asyncio` and mark tests async:

```python
import pytest

@pytest.mark.asyncio
async def test_user_creation(client: AsyncClient):
    response = await client.post("/api/v1/users/", ...)
```

### Database State Leaks Between Tests

**Cause**: Transactions not rolled back.

**Solution**: Use session fixture that auto-rolls back:

```python
@pytest.fixture
async def session(app) -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        async with session.begin():
            yield session
            await session.rollback()
```

---

## Development Server

### Auto-reload Not Working

**Cause**: Running without `--reload` flag.

**Solution**: Use the `just dev` command:

```bash
just dev  # Uses uvicorn with --reload
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

```
Error: mkdocstrings plugin is enabled, but mkdocstrings is not
installed.
```

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

**Solution**: Regenerate the lockfile:

```bash
uv lock --upgrade
```

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

1. Database not accessible (check `DATABASE_URL`)
2. Missing environment variables
3. Migrations failed (run migrations manually)

---

## Type Checking

### "Incompatible types in assignment"

```
error: Incompatible types in assignment (expression has type "None",
variable has type "User")
```

**Cause**: Function can return `None` but type hint doesn't allow it.

**Solution**: Add `| None` to return type:

```python
async def get_user(user_id: UUID) -> User | None:  # Allow None
    return await self.session.get(User, user_id)
```

### "Missing type parameters"

```
error: Missing type parameters for generic type "list"
```

**Solution**: Add type parameters:

```python
# Wrong
def get_users() -> list:
    ...

# Correct
def get_users() -> list[User]:
    ...
```

---

## Performance

### Slow Queries

**Enable SQL echo** to see queries:

```python
# app/db/session.py
engine = create_async_engine(
    str(settings.DATABASE_URL),
    echo=True,  # Print all SQL
)
```

**Common fixes:**

1. Add database indexes
2. Use `select_related` for joins
3. Paginate large result sets

### High Memory Usage

**Check:**

1. Connection pool size (default: 20):

   ```python
   engine = create_async_engine(..., pool_size=10)
   ```

2. Leaked sessions (use `async with` context manager)

3. Large result sets (add pagination)

---

## Production Issues

### 500 Errors with No Logs

**Cause**: Exception not caught by app error handler.

**Solution**: Check exception type and add handler:

```python
from fastapi import HTTPException

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    logger.error("http_error", status=exc.status_code, detail=exc.detail)
    return JSONResponse(...)
```

### OTEL Slowing Down Requests

**Solution**: Disable in development or reduce sampling:

```bash
# .env
QUOIN_OTEL_ENABLED=False  # Disable tracing
```

---

## Getting Help

If you're still stuck:

1. **Check logs**: `docker-compose logs` or `just dev` output
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
| View logs             | `docker-compose logs -f` |
| Reset database        | `docker-compose down -v` |
| Clean build artifacts | `just clean`             |
