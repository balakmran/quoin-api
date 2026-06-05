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

    # Patch the name bound in app.main (it imports create_db_engine
    # directly), so the lifespan actually uses the mock engine.
    with patch("app.main.create_db_engine", return_value=mock_engine):
        yield


def test_lifespan():
    """Test lifespan events (startup/shutdown)."""
    app = create_app()

    # TestClient triggers lifespan events on enter/exit
    with TestClient(app, base_url="http://test") as client:
        response = client.get("/health")
        assert response.status_code == status.HTTP_200_OK

    # Shutdown ran the clean-drain path and disposed the engine.
    assert app.state.lifecycle.is_shutting_down is True
    assert app.state.engine.dispose.called


def test_lifespan_shutdown_drain_timeout(monkeypatch: pytest.MonkeyPatch):
    """Shutdown takes the timeout branch when a request stays in flight."""
    monkeypatch.setattr(settings, "SHUTDOWN_DRAIN_TIMEOUT", 0.01)
    app = create_app()

    with TestClient(app, base_url="http://test") as client:
        client.get("/health")
        # Leave a request in flight so the drain cannot reach idle and
        # the lifespan takes the shutdown_drain_timeout branch on exit.
        app.state.lifecycle.acquire()

    # The drain timed out with the request still counted, yet the engine
    # was disposed anyway.
    assert app.state.lifecycle.is_shutting_down is True
    assert app.state.lifecycle.in_flight == 1
    assert app.state.engine.dispose.called


def test_lifespan_disposes_engine_when_drain_errors(
    monkeypatch: pytest.MonkeyPatch,
):
    """Engine is disposed even if drain raises (e.g. cancellation)."""
    app = create_app()

    with pytest.raises(RuntimeError, match="boom"):
        with TestClient(app, base_url="http://test") as client:
            client.get("/health")
            # Force the drain to raise on shutdown; the lifespan must
            # still dispose the engine and re-raise.
            monkeypatch.setattr(
                app.state.lifecycle,
                "drain",
                AsyncMock(side_effect=RuntimeError("boom")),
            )

    assert app.state.engine.dispose.called
