"""The async database engine and the per-request session.

``create_app()`` builds one engine and session factory at startup and
keeps them on ``app.state``. Routes depend on ``SessionDep``, which
opens a session for the request, commits it before the response is
sent, and rolls it back if the handler raises, so a whole request is
one transaction.

Pool sizing and recycling come from the ``DB_POOL_*`` settings; the
Configuration guide lists them.

Usage:
    from app.db.session import SessionDep


    def get_widget_service(session: SessionDep) -> WidgetService:
        return WidgetService(WidgetRepository(session))
"""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Request
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
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT,
        pool_recycle=settings.DB_POOL_RECYCLE,
        pool_pre_ping=settings.DB_POOL_PRE_PING,
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
) -> AsyncGenerator[AsyncSession]:
    """Yield a unit-of-work session scoped to one HTTP request.

    Commits on clean exit; rolls back if the handler raises. This
    makes the entire request handler atomic — repositories only need
    to flush to detect constraint violations early; the actual
    transaction commit is deferred to here.

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
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ``scope="function"`` runs the commit/rollback above before the response
# is sent; FastAPI's default defers it until after. Without it a client
# can receive a 2xx for a write whose COMMIT has not happened yet — or
# ever will, if it fails. Depend on ``SessionDep`` rather than
# ``Depends(get_session)`` so that decision lives in one place.
SessionDep = Annotated[AsyncSession, Depends(get_session, scope="function")]
