# Troubleshooting

Find the symptom, follow the fix. A fix that belongs to a topic lives in
that topic's guide; this page links to it.

!!! tip "First check the logs"
    `just logs` shows the containers, and the `just dev` output shows the
    app. Every error response carries a request ID; search the logs for
    it.

## Startup and database

- **`connection refused` on port 5432** (`psycopg.OperationalError`
  from migrations, `ConnectionRefusedError` from the app) — Postgres
  isn't up. Run `just db`, check the `QUOIN_POSTGRES_*` values in
  `.env`, and read `just logs` if the container started and then died.
- **`Database session factory is not initialized`** — the app was built
  without its lifespan. Import `app` from `app.main` (built by
  `create_app()`) rather than constructing a bare `FastAPI()`.
- **`The asyncio extension requires an async driver`** —
  `QUOIN_POSTGRES_DRIVER` must be `postgresql+asyncpg` (the default).
- **`Target database is not up to date`**, **`Can't locate revision`**,
  or **multiple heads** — see
  [Database Migrations](database-migrations.md#troubleshooting).
- **Autogenerate finds no changes** — see
  [Database Migrations](database-migrations.md#autogenerate-doesnt-detect-changes).

## Tests and checks

- **`Event loop is closed`**, **fixture not found**, or **state leaking
  between tests** — see [Testing](testing.md#common-failures).
- **Format, type, or coverage failures in `just check`** — see
  [Quality Checks](quality-checks.md#troubleshooting).

## Dependencies and docs

- **`The lockfile is out of sync`** — run `uv lock`. Don't add
  `--upgrade`; that bumps every dependency.
- **Docs build can't find `zensical` or `mkdocstrings`** — run
  `uv sync --group docs`.
- **A new page is missing from the docs site** — add it to `nav` in
  `zensical.toml`.

## Production

- **Container exits at startup** — production refuses to boot without
  `QUOIN_ALLOWED_HOSTS` or an OAuth trust anchor, and the log names the
  missing one. See
  [Deployment](deployment.md#environment-variables). The image doesn't
  run migrations; see
  [Database Migrations](database-migrations.md#production-deployments).
- **Unexpected `500` responses** — an exception no handler maps. See
  [Error Handling](error-handling.md#catch-all-for-uncaught-exceptions).
- **Logs or traces missing, or tracing slowing requests** — see
  [Observability](observability.md#troubleshooting).
- **Slow queries** — set `echo=True` in `create_db_engine()`
  (`app/db/session.py`) locally to print SQL, then add an index, load
  related rows with `selectinload`, or paginate.

## See Also

- [Getting Started](getting-started.md) — the setup these failures
  interrupt
- [Configuration](configuration.md) — every setting named above
