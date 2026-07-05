from unittest.mock import AsyncMock, Mock

import pytest
from sqlmodel import select

from app.core.config import settings
from app.core.exceptions import InternalServerError
from app.db.session import create_db_engine, create_session_factory, get_session
from app.main import app as fastapi_app
from app.modules.user.models import User


@pytest.mark.asyncio
async def test_get_session():
    """Test the get_session dependency directly to ensure coverage."""
    mock_request = Mock()
    mock_request.app.state = fastapi_app.state

    async for session in get_session(mock_request):
        assert session is not None
        await session.exec(select(User).limit(1))


@pytest.mark.asyncio
async def test_db_lifecycle_and_error_handling():
    """Test database initialization, closing, and error handling."""
    # 1. Close the DB (simulating shutdown or uninitialized state)
    if fastapi_app.state.engine:
        await fastapi_app.state.engine.dispose()
        fastapi_app.state.engine = None
        fastapi_app.state.session_factory = None
    assert fastapi_app.state.engine is None

    # 2. Verify get_session raises InternalServerError when not initialized
    mock_request = Mock()
    mock_request.app.state.session_factory = None
    with pytest.raises(
        InternalServerError, match="session factory is not initialized"
    ):
        async for _ in get_session(mock_request):
            pass

    # 3. Re-initialize the DB (restore state for other tests/teardown)
    base_url = str(settings.DATABASE_URL)
    test_url = base_url.replace(f"/{settings.POSTGRES_DB}", "/postgres")
    engine = create_db_engine(url=test_url)
    fastapi_app.state.engine = engine
    fastapi_app.state.session_factory = create_session_factory(engine)
    assert fastapi_app.state.engine is not None


def _mock_request_with_session(mock_session: AsyncMock) -> Mock:
    """Build a fake Request whose session_factory yields mock_session."""
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = False
    mock_request = Mock()
    mock_request.app.state.session_factory = Mock(return_value=mock_session)
    return mock_request


@pytest.mark.asyncio
async def test_get_session_commits_on_success():
    """get_session commits the session when the caller exits cleanly."""
    mock_session = AsyncMock()
    mock_request = _mock_request_with_session(mock_session)

    async for session in get_session(mock_request):
        assert session is mock_session

    mock_session.commit.assert_awaited_once()
    mock_session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_session_rolls_back_and_reraises_on_error():
    """get_session rolls back and re-raises when the caller errors."""
    mock_session = AsyncMock()
    mock_request = _mock_request_with_session(mock_session)

    class HandlerError(Exception):
        """Stand-in for an exception raised by a request handler."""

    generator = get_session(mock_request)
    session = await generator.__anext__()
    assert session is mock_session

    with pytest.raises(HandlerError):
        await generator.athrow(HandlerError("handler failed"))

    mock_session.rollback.assert_awaited_once()
    mock_session.commit.assert_not_awaited()
