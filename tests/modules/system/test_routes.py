import re
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, status
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.db.session import (
    create_db_engine,
    create_session_factory,
    get_session,
)
from app.main import create_app


@pytest.fixture
def app() -> FastAPI:
    """Create a FastAPI app for testing."""
    return create_app()


@pytest.mark.asyncio
async def test_root(app: FastAPI):
    """Test the root endpoint."""
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/")

    assert response.status_code == status.HTTP_200_OK
    assert "text/html" in response.headers["content-type"]
    assert "INITIALIZING" in response.text


async def _landing_page(app: FastAPI) -> str:
    """Render the landing page and return its HTML."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/")
    assert response.status_code == status.HTTP_200_OK
    return response.text


@pytest.mark.asyncio
async def test_root_has_no_inline_script(app: FastAPI):
    """The CSP blocks inline handlers and scripts; the page must use none."""
    html = await _landing_page(app)

    assert re.findall(r"<[^>]*\son[a-z]+\s*=", html) == []
    assert re.findall(r"<script(?![^>]*\bsrc=)[^>]*>", html) == []


@pytest.mark.asyncio
async def test_root_links_docs_only_when_enabled(app: FastAPI):
    """The Swagger link is omitted when the docs route is not registered."""
    assert 'href="/docs"' in await _landing_page(app)

    app.docs_url = None
    assert 'href="/docs"' not in await _landing_page(app)


def test_no_oauth2_redirect_route(app: FastAPI):
    """Swagger's OAuth2 redirect page, an inline script, is not served."""
    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/docs/oauth2-redirect" not in paths


@pytest.mark.asyncio
async def test_health(app: FastAPI):
    """Test the health endpoint."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/health")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "healthy"}


@pytest.mark.asyncio
async def test_ready_success(app: FastAPI):
    """Test the readiness endpoint when DB is available."""

    # Mock the session dependency
    async def mock_get_session():
        mock_session = AsyncMock()
        mock_session.exec = AsyncMock(return_value=True)
        yield mock_session

    app.dependency_overrides[get_session] = mock_get_session

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/ready")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ready"}


@pytest.mark.asyncio
async def test_ready_failure(app: FastAPI):
    """Test the readiness endpoint when DB is unavailable."""

    # Mock the session dependency to raise exception
    async def mock_get_session():
        mock_session = AsyncMock()
        mock_session.exec = AsyncMock(
            side_effect=SQLAlchemyError("DB Connection Error")
        )
        yield mock_session

    app.dependency_overrides[get_session] = mock_get_session

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/ready")

    body = response.json()
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.headers["content-type"] == "application/problem+json"
    assert body["type"] == "urn:quoin:error:service_unavailable_error"
    assert body["status"] == status.HTTP_503_SERVICE_UNAVAILABLE
    assert body["detail"] == "Database connection failed"
    assert body["instance"] == "/ready"


@pytest.mark.asyncio
async def test_ready_database_unreachable(app: FastAPI):
    """A refused connection is a 503: asyncpg raises a bare OSError."""
    url = settings.model_copy(update={"POSTGRES_PORT": 1}).DATABASE_URL
    engine = create_db_engine(url=str(url))
    app.state.session_factory = create_session_factory(engine)

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/ready")
    finally:
        await engine.dispose()

    body = response.json()
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert body["detail"] == "Database connection failed"


@pytest.mark.asyncio
async def test_ready_reports_503_during_shutdown(app: FastAPI):
    """Readiness flips to 503 once graceful shutdown has begun."""

    # The engine is still alive while draining, so the session resolves;
    # the shutdown flag is what trips the 503.
    async def mock_get_session():
        yield AsyncMock()

    app.dependency_overrides[get_session] = mock_get_session
    app.state.lifecycle.begin_shutdown()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/ready")

    body = response.json()
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert body["type"] == "urn:quoin:error:service_unavailable_error"
    assert body["detail"] == "Service is shutting down"


@pytest.mark.asyncio
async def test_ready_misconfigured_without_lifecycle(app: FastAPI):
    """Readiness returns 500 if app.state.lifecycle is missing."""

    async def mock_get_session():
        yield AsyncMock()

    app.dependency_overrides[get_session] = mock_get_session
    del app.state.lifecycle

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/ready")

    body = response.json()
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert body["type"] == "urn:quoin:error:internal_server_error"
