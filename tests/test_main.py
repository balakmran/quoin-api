from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import create_app


@pytest.fixture(autouse=True)
def mock_db_lifecycle():
    """Mock database lifecycle events to avoid connection attempts."""
    mock_engine = MagicMock()
    mock_engine.dispose = AsyncMock()

    with patch("app.db.session.create_db_engine", return_value=mock_engine):
        yield


def test_lifespan():
    """Test lifespan events (startup/shutdown)."""
    app = create_app()

    # TestClient triggers lifespan events on enter/exit
    with TestClient(app, base_url="http://test") as client:
        response = client.get("/health")
        assert response.status_code == status.HTTP_200_OK


def test_lifespan_shutdown_drain_timeout(monkeypatch: pytest.MonkeyPatch):
    """Shutdown takes the timeout branch when a request stays in flight."""
    monkeypatch.setattr(settings, "SHUTDOWN_DRAIN_TIMEOUT", 0.01)
    app = create_app()

    with TestClient(app, base_url="http://test") as client:
        client.get("/health")
        # Leave a request in flight so the drain cannot reach idle and
        # the lifespan takes the shutdown_drain_timeout branch on exit.
        app.state.lifecycle.acquire()

    assert app.state.lifecycle.is_shutting_down is True
