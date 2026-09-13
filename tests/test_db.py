from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from httpx2 import ASGITransport, AsyncClient
from sqlmodel import select
from starlette.types import Message, Receive, Scope, Send

from app.core.config import settings
from app.core.exceptions import InternalServerError
from app.db.session import (
    SessionDep,
    create_db_engine,
    create_session_factory,
    get_session,
)
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

    # 3. Re-initialize the DB (restore state for other tests/teardown).
    # Build the URL from parts (override only the db name) rather than
    # string-replacing inside an assembled URL.
    test_url = str(
        settings.model_copy(update={"POSTGRES_DB": "postgres"}).DATABASE_URL
    )
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


@pytest.mark.asyncio
async def test_session_dep_commits_before_response_is_sent() -> None:
    """B1 regression: SessionDep commits before the response is sent."""
    events: list[str] = []

    mock_session = AsyncMock()

    async def fake_commit() -> None:
        events.append("commit")

    mock_session.commit = fake_commit
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = False

    app = FastAPI()
    app.state.session_factory = Mock(return_value=mock_session)

    @app.get("/probe")
    async def probe(session: SessionDep) -> dict[str, bool]:
        assert session is mock_session
        events.append("handler")
        return {"ok": True}

    async def tracking_app(
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        async def tracking_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                events.append("response-start")
            await send(message)

        await app(scope, receive, tracking_send)

    transport = ASGITransport(app=tracking_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/probe")

    assert response.status_code == 200  # noqa: PLR2004
    assert events == ["handler", "commit", "response-start"]
