from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, status
from httpx import ASGITransport, AsyncClient

from app.db.session import get_session
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
            side_effect=Exception("DB Connection Error")
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
