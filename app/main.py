from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import api_router, system_router_root
from app.core.config import settings
from app.core.exception_handlers import add_exception_handlers
from app.core.lifecycle import Lifecycle
from app.core.logging import setup_logging
from app.core.middlewares import configure_middlewares
from app.core.openapi import OPENAPI_PARAMETERS, set_openapi_generator
from app.core.telemetry import setup_opentelemetry
from app.db.session import create_db_engine, create_session_factory

logger = structlog.get_logger(__name__)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    setup_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        """Manage the engine, session factory, and graceful shutdown.

        On startup the DB engine and session factory are created. On
        shutdown the readiness probe is flipped to 503, in-flight
        requests are drained (bounded by
        ``QUOIN_SHUTDOWN_DRAIN_TIMEOUT``), and only then is the engine
        disposed so no in-flight request loses its connection.

        Args:
            app: The FastAPI application instance.
        """
        engine = create_db_engine()
        app.state.engine = engine
        app.state.session_factory = create_session_factory(engine)
        yield
        lifecycle: Lifecycle = app.state.lifecycle
        lifecycle.begin_shutdown()
        timeout = settings.SHUTDOWN_DRAIN_TIMEOUT
        try:
            if await lifecycle.drain(timeout):
                logger.info("shutdown_drained")
            else:
                logger.warning(
                    "shutdown_drain_timeout",
                    timeout=timeout,
                    in_flight=lifecycle.in_flight,
                )
        except BaseException as exc:
            # Catch BaseException so an unexpected drain failure — most
            # importantly CancelledError when the server's own graceful
            # timeout fires — never skips engine disposal. Re-raise to
            # preserve the server's cancellation protocol.
            logger.error(
                "shutdown_drain_error",
                error=repr(exc),
                in_flight=lifecycle.in_flight,
            )
            raise
        finally:
            await app.state.engine.dispose()

    app = FastAPI(lifespan=lifespan, **OPENAPI_PARAMETERS)
    app.state.lifecycle = Lifecycle()
    set_openapi_generator(app)
    add_exception_handlers(app)
    configure_middlewares(app)

    # Setup Observability
    setup_opentelemetry(app)

    # Mount static files (use absolute path)
    base_dir = Path(__file__).resolve().parent
    app.mount(
        "/static", StaticFiles(directory=base_dir / "static"), name="static"
    )

    app.include_router(api_router)
    app.include_router(system_router_root)

    return app


app = create_app()
