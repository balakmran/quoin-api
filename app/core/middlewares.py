import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings

logger = structlog.get_logger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Generate or propagate X-Request-ID and bind it to the log context."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Assign a request ID, bind it to structlog, echo it in response."""
        header = settings.REQUEST_ID_HEADER
        request_id = request.headers.get(header, str(uuid.uuid4()))
        structlog.contextvars.bind_contextvars(request_id=request_id)
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.unbind_contextvars("request_id")
        response.headers[header] = request_id
        return response


def configure_cors(app: FastAPI) -> None:
    """Configure CORS middleware."""
    if settings.BACKEND_CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[
                str(origin) for origin in settings.BACKEND_CORS_ORIGINS
            ],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )


def configure_trusted_hosts(app: FastAPI) -> None:
    """Configure TrustedHost middleware."""
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.ALLOWED_HOSTS,
    )


def configure_middlewares(app: FastAPI) -> None:
    """Configure all application middlewares."""
    configure_cors(app)
    configure_trusted_hosts(app)
    app.add_middleware(RequestIDMiddleware)


__all__ = [
    "RequestIDMiddleware",
    "configure_cors",
    "configure_middlewares",
    "configure_trusted_hosts",
]
