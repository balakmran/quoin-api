from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from alembic import command
from app.core.config import settings
from app.core.security import ServicePrincipal, get_current_caller
from app.db.session import create_db_engine, create_session_factory, get_session
from app.main import app as fastapi_app

_ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def _test_database_url() -> str:
    """Build the test connection URL from settings parts.

    Overrides only the database name (to the maintenance ``postgres``
    database, so the suite never touches a real ``app_db``) and
    reassembles the URL from its components. Building from parts avoids
    the brittleness of string-replacing the db name inside an assembled
    URL, where a name colliding with the user or host would corrupt it.
    """
    return str(
        settings.model_copy(update={"POSTGRES_DB": "postgres"}).DATABASE_URL
    )


def _alembic_config(connection: Connection) -> Config:
    """Build an Alembic Config bound to an existing DB connection."""
    config = Config(str(_ALEMBIC_INI))
    config.attributes["connection"] = connection
    return config


def _reset_schema(connection: Connection) -> None:
    """Drop every app table plus Alembic's version table.

    Guarantees a clean slate before the migration chain runs, so a
    crashed prior session — or a database still holding ``create_all``
    tables from before the migration-backed switch — can't wedge
    ``alembic upgrade``.
    """
    SQLModel.metadata.drop_all(connection, checkfirst=True)
    connection.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")


def _upgrade_to_head(connection: Connection) -> None:
    """Apply the full migration chain against ``connection``."""
    command.upgrade(_alembic_config(connection), "head")


def _downgrade_to_base(connection: Connection) -> None:
    """Reverse the full migration chain against ``connection``."""
    command.downgrade(_alembic_config(connection), "base")


@pytest.fixture(scope="session", autouse=True)
async def initialize_db() -> AsyncGenerator[None]:
    """Initialize the test database engine and schema for the session.

    Builds the schema by running the Alembic migration chain rather
    than ``SQLModel.metadata.create_all``, so model/migration drift
    fails the suite instead of shipping silently. Teardown reverses the
    chain to ``base``, exercising the down-migrations and leaving the
    database clean.
    """
    engine = create_db_engine(url=_test_database_url())
    fastapi_app.state.engine = engine
    fastapi_app.state.session_factory = create_session_factory(engine)

    # Reset any leftover state, then build the schema from migrations.
    async with engine.connect() as conn:
        await conn.run_sync(_reset_schema)
        await conn.commit()
    async with engine.connect() as conn:
        await conn.run_sync(_upgrade_to_head)

    yield

    async with engine.connect() as conn:
        await conn.run_sync(_downgrade_to_base)

    await engine.dispose()
    fastapi_app.state.engine = None


@pytest.fixture
async def db_session(initialize_db: None) -> AsyncGenerator[AsyncSession]:
    """Fixture that returns a SQLAlchemy session with a SAVEPOINT.

    The rollback happens after the test completes. This guarantees that the
    database is cleaned up after each test.
    """
    if not fastapi_app.state.engine:
        raise RuntimeError("Database engine is not initialized")

    connection = await fastapi_app.state.engine.connect()
    trans = await connection.begin()

    # join_transaction_mode="create_savepoint" makes every
    # session.commit() release a SAVEPOINT rather than a real
    # transaction commit. Tests that seed data via db_session.commit()
    # stay isolated inside the outer transaction rolled back in
    # teardown. HTTP tests override get_session entirely, so the UoW
    # commit in get_session is bypassed; flush() visibility within the
    # session is sufficient for test assertions.
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


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    """Fixture that returns an HTTP client for the application.

    It overrides the get_session dependency to use the test session.
    """
    # Override the get_session dependency to use the test session
    fastapi_app.dependency_overrides[get_session] = lambda: db_session

    async with AsyncClient(
        transport=ASGITransport(app=fastapi_app), base_url="http://test"
    ) as c:
        yield c

    # Remove only the override this fixture added, so nested fixtures'
    # overrides (e.g. get_current_caller) survive independent teardown.
    fastapi_app.dependency_overrides.pop(get_session, None)


@pytest.fixture
def caller_read() -> ServicePrincipal:
    """ServicePrincipal with users.read role only."""
    return ServicePrincipal(
        subject="test-service-read",
        roles=["users.read"],
        claims={},
    )


@pytest.fixture
def caller_admin() -> ServicePrincipal:
    """ServicePrincipal with users.read + users.write roles."""
    return ServicePrincipal(
        subject="test-service-admin",
        roles=["users.read", "users.write"],
        claims={},
    )


@pytest.fixture
async def read_client(
    client: AsyncClient,
    caller_read: ServicePrincipal,
) -> AsyncGenerator[AsyncClient]:
    """HTTP client authenticated as a service with users.read role."""
    fastapi_app.dependency_overrides[get_current_caller] = lambda: caller_read
    yield client
    fastapi_app.dependency_overrides.pop(get_current_caller, None)


@pytest.fixture
async def admin_client(
    client: AsyncClient,
    caller_admin: ServicePrincipal,
) -> AsyncGenerator[AsyncClient]:
    """HTTP client authenticated as a service with users.read + users.write."""
    fastapi_app.dependency_overrides[get_current_caller] = lambda: caller_admin
    yield client
    fastapi_app.dependency_overrides.pop(get_current_caller, None)
