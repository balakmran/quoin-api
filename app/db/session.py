from collections.abc import AsyncGenerator

from fastapi import Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings


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


async def get_session(
    request: Request,
) -> AsyncGenerator[AsyncSession, None]:
    """Get a database session from app.state.engine."""
    engine: AsyncEngine | None = getattr(request.app.state, "engine", None)
    if not engine:
        raise RuntimeError("Database engine is not initialized")

    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session
