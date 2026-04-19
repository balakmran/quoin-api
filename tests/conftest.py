from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.security import ServicePrincipal, get_current_caller
from app.db.session import create_db_engine, create_session_factory, get_session
from app.main import app as fastapi_app


@pytest.fixture(scope="session", autouse=True)
async def initialize_db() -> AsyncGenerator[None, None]:
    """Initialize the database engine for the test session."""
    # Connect to the default 'postgres' database safely to avoid dropping
    # tables from the main development 'app_db' database.
    base_url = str(settings.DATABASE_URL)
    test_url = base_url.replace(f"/{settings.POSTGRES_DB}", "/postgres")

    engine = create_db_engine(url=test_url)
    fastapi_app.state.engine = engine
    fastapi_app.state.session_factory = create_session_factory(engine)

    # Create tables
    async with fastapi_app.state.engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    yield

    # Drop tables (optional, but good for cleanup)
    async with fastapi_app.state.engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)

    await fastapi_app.state.engine.dispose()
    fastapi_app.state.engine = None


@pytest.fixture
async def db_session(initialize_db: None) -> AsyncGenerator[AsyncSession, None]:
    """Fixture that returns a SQLAlchemy session with a SAVEPOINT.

    The rollback happens after the test completes. This guarantees that the
    database is cleaned up after each test.
    """
    if not fastapi_app.state.engine:
        raise RuntimeError("Database engine is not initialized")

    connection = await fastapi_app.state.engine.connect()
    trans = await connection.begin()

    # Create a session bound to the connection
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


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Fixture that returns an HTTP client for the application.

    It overrides the get_session dependency to use the test session.
    """
    # Override the get_session dependency to use the test session
    fastapi_app.dependency_overrides[get_session] = lambda: db_session

    async with AsyncClient(
        transport=ASGITransport(app=fastapi_app), base_url="http://test"
    ) as c:
        yield c

    # Clear overrides after test
    fastapi_app.dependency_overrides.clear()


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
) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client authenticated as a service with users.read role."""
    fastapi_app.dependency_overrides[get_current_caller] = lambda: caller_read
    yield client
    fastapi_app.dependency_overrides.clear()


@pytest.fixture
async def admin_client(
    client: AsyncClient,
    caller_admin: ServicePrincipal,
) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client authenticated as a service with users.read + users.write."""
    fastapi_app.dependency_overrides[get_current_caller] = lambda: caller_admin
    yield client
    fastapi_app.dependency_overrides.clear()
