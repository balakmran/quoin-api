import asyncio
from logging.config import fileConfig
from typing import Any, Literal

from alembic.autogenerate.api import AutogenContext
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.core.config import settings
from app.db.base import SQLModel

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# set the sqlalchemy.url from settings
config.set_main_option("sqlalchemy.url", str(settings.DATABASE_URL))

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = SQLModel.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def render_item(
    type_: str, obj: Any, autogen_context: AutogenContext
) -> Literal[False]:
    """Ensure ``import sqlmodel`` is emitted for sqlmodel column types.

    Alembic autogenerate renders SQLModel string columns as
    ``sqlmodel.sql.sqltypes.AutoString(...)`` but does not add the
    corresponding import, so generated migrations would fail at runtime
    with ``NameError: name 'sqlmodel' is not defined``. Registering the
    needed import here populates the template's ``${imports}`` block only
    when a sqlmodel type is actually used.

    Args:
        type_: The kind of object being rendered (e.g. ``"type"``).
        obj: The object being rendered.
        autogen_context: The active autogenerate context.

    Returns:
        ``False`` to fall back to Alembic's default rendering.

    """
    module = obj.__class__.__module__
    if type_ == "type" and module.startswith("sqlmodel"):
        # Import the concrete submodule (e.g. ``sqlmodel.sql.sqltypes``)
        # so the rendered ``sqlmodel.sql.sqltypes.AutoString(...)``
        # reference resolves cleanly for both runtime and type checking.
        autogen_context.imports.add(f"import {module}")
    return False


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    # Replace async driver with sync equivalent for offline SQL generation
    if url:
        url = url.replace("postgresql+asyncpg", "postgresql+psycopg")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_item=render_item,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations using the connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_item=render_item,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'async' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    When a caller injects a live connection via
    ``config.attributes["connection"]`` — as the test session fixture
    does to build its schema from the migration chain — reuse it and
    run migrations synchronously against it. Reusing the caller's
    connection avoids nesting ``asyncio.run`` inside an already-running
    event loop. Otherwise, build a fresh async engine from the
    configured URL.

    """
    connectable = config.attributes.get("connection")
    if connectable is None:
        asyncio.run(run_async_migrations())
    else:
        do_run_migrations(connectable)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
