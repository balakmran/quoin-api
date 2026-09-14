from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import structlog
from fastapi import FastAPI, status
from httpx2 import ASGITransport, AsyncClient
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError
from structlog.testing import capture_logs

from app.core.config import Environment
from app.core.exception_handlers import validation_exception_handler
from app.core.exceptions import QuoinError
from app.core.logging import _add_otel_context, setup_logging
from app.main import create_app


def test_setup_logging() -> None:
    """Test setup_logging configuration."""
    with patch("structlog.configure") as mock_configure:
        setup_logging()

        # Verify structlog.configure was called
        mock_configure.assert_called_once()

        # Verify basic logging config
        # We can check if basicConfig was called or if the handler is set
        # But since setup_logging modifies global state, we should be careful.
        # The function sets logging.basicConfig.

        # Let's verify that we can get a logger and it works
        logger = structlog.get_logger()
        assert logger is not None


def test_setup_logging_prod() -> None:
    """Test setup_logging configuration in production."""
    with (
        patch("app.core.logging.settings.ENV", Environment.production),
        patch("structlog.configure") as mock_configure,
    ):
        setup_logging()

        mock_configure.assert_called_once()
        # Verify JSONRenderer is in processors
        call_args = mock_configure.call_args
        processors = call_args.kwargs["processors"]
        assert any(
            isinstance(p, structlog.processors.JSONRenderer) for p in processors
        )


def test_setup_logging_not_dev() -> None:
    """Test setup_logging stdlib configuration in non-dev environment."""
    with (
        patch("app.core.logging.settings.ENV", Environment.production),
        patch("app.core.logging.settings.LOG_LEVEL", "WARNING"),
        patch("logging.getLogger") as mock_get_logger,
        patch("logging.StreamHandler"),
    ):
        mock_root_logger = MagicMock()
        mock_get_logger.return_value = mock_root_logger

        setup_logging()

        # Verify root logger handlers were cleared and new handler added
        mock_root_logger.handlers.clear.assert_called_once()
        mock_root_logger.addHandler.assert_called_once()
        # B4 regression: the level follows QUOIN_LOG_LEVEL.
        mock_root_logger.setLevel.assert_called_with("WARNING")


@pytest.mark.parametrize("env", [Environment.development, Environment.test])
def test_setup_logging_console_leaves_stdlib_logging_alone(
    env: Environment,
) -> None:
    """Console profiles skip the stdlib handler wiring entirely.

    The mirror of ``test_setup_logging_not_dev``. Patched explicitly so
    the branch is covered whatever ``QUOIN_ENV`` the runner has.
    """
    with (
        patch("app.core.logging.settings.ENV", env),
        patch("logging.getLogger") as mock_get_logger,
    ):
        mock_root_logger = MagicMock()
        mock_get_logger.return_value = mock_root_logger

        setup_logging()

        # ConsoleRenderer handles dev output; the stdlib root logger is
        # left untouched.
        mock_root_logger.handlers.clear.assert_not_called()
        mock_root_logger.addHandler.assert_not_called()


def test_test_profile_emits_one_plain_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The ``test`` profile prints console lines, not JSON-wrapped ones."""
    try:
        with patch("app.core.logging.settings.ENV", Environment.test):
            setup_logging()
            structlog.get_logger().warning("plain_line_check", k="v")
    finally:
        setup_logging()

    lines = [ln for ln in capsys.readouterr().out.splitlines() if ln]
    assert len(lines) == 1
    assert "plain_line_check" in lines[0]
    assert not lines[0].lstrip().startswith("{")


def test_log_level_filters_below_threshold() -> None:
    """B4 regression: QUOIN_LOG_LEVEL suppresses logs below itself."""
    try:
        with patch("app.core.logging.settings.LOG_LEVEL", "WARNING"):
            setup_logging()
            logger = structlog.get_logger()
            with capture_logs() as cap_logs:
                logger.info("suppressed")
                logger.warning("emitted")
    finally:
        # Restore the suite's normal configuration for later tests.
        setup_logging()

    events = [entry["event"] for entry in cap_logs]
    assert "emitted" in events
    assert "suppressed" not in events


async def _log_quoin_error_through(app: FastAPI) -> None:
    """Hit a route that logs once via exception_handlers' module logger."""

    @app.get("/test-logging-generations")
    async def _raise() -> None:
        raise QuoinError(
            message="boom", status_code=status.HTTP_400_BAD_REQUEST
        )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        await ac.get("/test-logging-generations")


@pytest.mark.asyncio
async def test_capture_logs_survives_repeated_create_app_calls() -> None:
    """Regression: capture_logs() must see logs across setup_logging() runs.

    ``create_app()`` calls ``setup_logging()`` on every invocation, not
    just once at process start. With ``cache_logger_on_first_use=True``,
    a module-level logger (e.g. ``app.core.exception_handlers.logger``)
    caches a bound logger the first time it actually logs, capturing a
    reference to whichever processors list was live at that moment. If
    ``setup_logging()`` swapped in a brand-new list object on a later
    call (a later "generation"), that cached logger would keep pointing
    at the old, abandoned list -- and ``capture_logs()``, which only
    ever mutates the *current* list in place, would silently stop
    seeing that logger's output. See ``structlog.testing.capture_logs``'s
    docstring: "keep the list instance intact to not break references
    held by bound loggers."
    """
    # First generation: create_app() re-runs setup_logging(), and the
    # shared exception_handlers logger logs (and may get cached here).
    await _log_quoin_error_through(create_app())

    # Second generation: another setup_logging() call. Without the fix
    # this rebinds structlog's processors to a brand-new list, orphaning
    # any logger already cached against the previous one.
    app = create_app()
    await _log_quoin_error_through(app)

    # capture_logs() mutates whatever list is *currently* configured;
    # the module logger must still be wired to it.
    with capture_logs() as cap_logs:
        await _log_quoin_error_through(app)

    events = [log for log in cap_logs if log["event"] == "quoin_error"]
    assert len(events) == 1
    assert events[0]["log_level"] == "info"  # a 400 is routine client error


def test_add_otel_context_injects_fields_when_span_valid() -> None:
    """Test trace_id and span_id are added when an active span exists."""
    mock_ctx = MagicMock()
    mock_ctx.is_valid = True
    mock_ctx.trace_id = 0x4BF92F3577B34DA6A3CE929D0E0E4736
    mock_ctx.span_id = 0x00F067AA0BA902B7

    mock_span = MagicMock()
    mock_span.get_span_context.return_value = mock_ctx

    with patch(
        "app.core.logging.trace.get_current_span", return_value=mock_span
    ):
        result: dict[str, Any] = {}
        _add_otel_context(None, "info", result)

    assert result["trace_id"] == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert result["span_id"] == "00f067aa0ba902b7"


def test_add_otel_context_omits_fields_when_span_invalid() -> None:
    """Test no fields are added when there is no active span."""
    mock_ctx = MagicMock()
    mock_ctx.is_valid = False

    mock_span = MagicMock()
    mock_span.get_span_context.return_value = mock_ctx

    with patch(
        "app.core.logging.trace.get_current_span", return_value=mock_span
    ):
        result: dict[str, Any] = {}
        _add_otel_context(None, "info", result)

    assert "trace_id" not in result
    assert "span_id" not in result


@pytest.mark.asyncio
async def test_validation_exception_handler() -> None:
    """Test validation_exception_handler handles Pydantic errors."""
    # Create a mock request
    request = MagicMock()
    request.url.path = "/test"

    # Create a ValidationError
    try:

        class TestModel(BaseModel):
            value: int

        TestModel(value="not_an_int")
    except PydanticValidationError as exc:
        response = await validation_exception_handler(request, exc)
        assert response.status_code == 422  # noqa: PLR2004
        body = response.body.decode()  # type: ignore
        assert "detail" in body
