import uuid
from collections.abc import Awaitable, Callable

import anyio
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings
from app.core.exception_handlers import _problem_response
from app.core.schemas import ProblemDetail

logger = structlog.get_logger(__name__)


class TimeoutMiddleware(BaseHTTPMiddleware):
    """Enforce a per-request wall-clock timeout using anyio cancel scopes."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Cancel the request and return 504 if it exceeds the timeout.

        Args:
            request: The incoming request.
            call_next: The next middleware or route handler.

        Returns:
            The response from the downstream handler, or a 504 Problem
            Details response if the deadline is exceeded.
        """
        timeout = settings.REQUEST_TIMEOUT_SECONDS
        try:
            with anyio.fail_after(timeout):
                return await call_next(request)
        except TimeoutError:
            logger.warning(
                "request_timeout",
                path=request.url.path,
                timeout=timeout,
            )
            problem = ProblemDetail(
                type="urn:quoin:error:gateway_timeout_error",
                title="Gateway Timeout",
                status=504,
                detail=f"Request exceeded {timeout}s timeout",
                instance=request.url.path,
            )
            return _problem_response(problem, 504)


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
    app.add_middleware(TimeoutMiddleware)


__all__ = [
    "RequestIDMiddleware",
    "TimeoutMiddleware",
    "configure_cors",
    "configure_middlewares",
    "configure_trusted_hosts",
]
