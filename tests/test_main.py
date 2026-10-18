import contextlib
import logging
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import structlog
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from app.core.config import Environment, settings
from app.core.telemetry import FASTAPI_TELEMETRY
from app.main import create_app


@contextlib.contextmanager
def _preserved_logging_config() -> Generator[None]:
    """Restore global logging state on exit.

    ``create_app()`` calls ``setup_logging()``, which reconfigures
    structlog process-wide and clears the stdlib root logger's handlers
    — including the ones pytest installs for ``caplog`` and live
    logging. Neither is undone by ``monkeypatch``, so a test that boots
    an app under a different ``ENV`` would otherwise leave every later
    test in the session running against the wrong logging profile.

    structlog's processor *list object* is restored by identity, not
    just by value: ``capture_logs()`` works by mutating that list in
    place, and loggers cached before the swap hold a reference to it.
    """
    config = structlog.get_config().copy()
    root = logging.getLogger()
    handlers = root.handlers[:]
    level = root.level
    try:
        yield
    finally:
        structlog.configure(**config)
        root.handlers[:] = handlers
        root.setLevel(level)


def test_create_app_calls_validate_production_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """create_app() itself calls validate_production_settings() (Imp. 11).

    Every other boot-validation test calls the helper function directly
    — none of them would notice a refactor of create_app() that
    accidentally dropped the call. Test settings otherwise leave the
    OAuth trust anchor unset, so flipping ENV to production is enough to
    prove create_app() itself performs the check, crash-loop and all.
    """
    monkeypatch.setattr(settings, "ENV", Environment.production)

    with _preserved_logging_config():
        with pytest.raises(RuntimeError, match="QUOIN_OAUTH_JWKS_URI"):
            create_app()


def test_create_app_turns_off_fastapi_builtin_telemetry() -> None:
    """create_app() passes FASTAPI_TELEMETRY to the FastAPI constructor."""
    with (
        _preserved_logging_config(),
        patch("app.main.FastAPI", wraps=FastAPI) as fastapi_cls,
    ):
        create_app()

    assert fastapi_cls.call_args.kwargs["telemetry"] is FASTAPI_TELEMETRY


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

    # Shutdown ran the clean-drain path and disposed the engine, and the
    # shared HTTP client was created on startup and closed on shutdown.
    assert app.state.lifecycle.is_shutting_down is True
    assert app.state.engine.dispose.called
    assert app.state.http_client.is_closed


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


def test_lifespan_disposes_engine_when_http_close_errors(
    monkeypatch: pytest.MonkeyPatch,
):
    """Engine is disposed even if closing the HTTP client raises."""
    app = create_app()

    with pytest.raises(RuntimeError, match="close boom"):
        with TestClient(app, base_url="http://test") as client:
            client.get("/health")
            # Force aclose() to raise on shutdown; the independently
            # guarded finally must still dispose the engine.
            monkeypatch.setattr(
                app.state.http_client,
                "aclose",
                AsyncMock(side_effect=RuntimeError("close boom")),
            )

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
