"""Genuine multi-connection concurrency tests for the user module.

Unlike the sequential B2 regression tests in ``test_routes.py`` (which
race two inserts inside a single SAVEPOINT-wrapped session), these use
independent sessions that really commit, so the email-uniqueness race
is exercised across separate transactions the way it happens in
production. Rows created here escape the per-test rollback, so each
test cleans up after itself.
"""

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app.main import app as fastapi_app
from app.modules.user.exceptions import DuplicateEmailError
from app.modules.user.models import User
from app.modules.user.repository import UserRepository
from app.modules.user.schemas import UserCreate

_RACE_EMAIL = "concurrent-create@example.com"


async def _attempt_create(
    session_factory: async_sessionmaker[AsyncSession],
) -> User:
    """Insert and commit the racing email in an independent session."""
    async with session_factory() as session:
        user = await UserRepository(session).create(
            UserCreate(email=_RACE_EMAIL)
        )
        await session.commit()
        return user


async def _delete_race_user(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Remove the committed race row so it can't leak into other tests."""
    async with session_factory() as session:
        existing = await UserRepository(session).get_by_email(_RACE_EMAIL)
        if existing is not None:
            await session.delete(existing)
            await session.commit()


async def test_concurrent_create_same_email_one_conflict(
    initialize_db: None,
) -> None:
    """B2 across transactions: exactly one create wins, one raises 409.

    Two real, concurrently-running sessions insert the same email. The
    service-layer pre-check can't prevent the race, so the loser must
    surface a ``DuplicateEmailError`` (→ 409) rather than an unhandled
    ``IntegrityError`` (→ 500).
    """
    session_factory: async_sessionmaker[AsyncSession] = (
        fastapi_app.state.session_factory
    )
    try:
        results = await asyncio.gather(
            _attempt_create(session_factory),
            _attempt_create(session_factory),
            return_exceptions=True,
        )
    finally:
        await _delete_race_user(session_factory)

    winners = [r for r in results if isinstance(r, User)]
    conflicts = [r for r in results if isinstance(r, DuplicateEmailError)]
    unexpected = [
        r
        for r in results
        if isinstance(r, BaseException)
        and not isinstance(r, DuplicateEmailError)
    ]

    assert not unexpected, f"unexpected errors from race: {unexpected}"
    assert len(winners) == 1
    assert len(conflicts) == 1
