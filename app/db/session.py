from collections.abc import AsyncGenerator

from fastapi import Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.exceptions import InternalServerError


def create_db_engine(url: str | None = None) -> AsyncEngine:
    """Create a configured async SQLAlchemy engine.

    Args:
        url: Optional connection URL; defaults to settings.DATABASE_URL.

    Returns:
        A new AsyncEngine with connection pooling pre-configured.
    """
    return create_async_engine(
        url or str(settings.DATABASE_URL),
        echo=False,
        future=True,
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True,
    )


def create_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory bound to the given engine.

    Args:
        engine: The AsyncEngine the factory will use for connections.

    Returns:
        A reusable async_sessionmaker that yields AsyncSession objects.
    """
    return async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )


async def get_session(
    request: Request,
) -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session for the duration of the request.

    Reads the session factory from app.state, which is initialised
    during application startup.

    Args:
        request: The current FastAPI request (used to access app.state).

    Yields:
        An AsyncSession scoped to this request.

    Raises:
        InternalServerError: If the session factory is not initialised.
    """
    session_factory = getattr(request.app.state, "session_factory", None)
    if not session_factory:
        raise InternalServerError("Database session factory is not initialized")
    async with session_factory() as session:
        yield session
