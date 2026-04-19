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
    """Create and return a new async database engine."""
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
    """Create a reusable async session factory bound to the given engine."""
    return async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )


async def get_session(
    request: Request,
) -> AsyncGenerator[AsyncSession, None]:
    """Get a database session from app.state.session_factory."""
    session_factory = getattr(request.app.state, "session_factory", None)
    if not session_factory:
        raise InternalServerError("Database session factory is not initialized")
    async with session_factory() as session:
        yield session
