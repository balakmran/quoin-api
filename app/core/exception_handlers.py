import re
from http import HTTPStatus
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import Response

from app.core.exceptions import QuoinError, QuoinRequestValidationError
from app.core.schemas import ProblemDetail

logger = structlog.get_logger(__name__)

_PROBLEM_MEDIA_TYPE = "application/problem+json"

# CPython's HTTPStatus.phrase wording tracks RFC updates (e.g. 422's
# phrase changed from "Unprocessable Entity" to "Unprocessable Content"),
# so deriving titles from it would make the response body depend on
# which Python version is running the server. Pin the phrases QuoinAPI
# actually raises so the RFC 9457 `title` field is stable across the
# supported interpreter range.
_PROBLEM_TITLES = {
    HTTPStatus.UNPROCESSABLE_ENTITY: "Unprocessable Content",
}


def _problem_type(exc: Exception) -> str:
    """Derive a URN problem type from the exception class name."""
    name = type(exc).__name__
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
    return f"urn:quoin:error:{snake}"


def _problem_title(status_code: int) -> str:
    """Return the standard HTTP reason phrase for a status code."""
    try:
        status = HTTPStatus(status_code)
    except ValueError:
        return "Error"
    return _PROBLEM_TITLES.get(status, status.phrase)


def _problem_response(
    problem: ProblemDetail,
    status_code: int,
    headers: dict[str, str] | None = None,
) -> Response:
    """Serialize a ProblemDetail into an application/problem+json response."""
    return Response(
        content=problem.model_dump_json(exclude_none=True),
        status_code=status_code,
        media_type=_PROBLEM_MEDIA_TYPE,
        headers=headers,
    )


async def quoin_exception_handler(request: Request, exc: Any) -> Response:
    """Handle QuoinError exceptions."""
    quoin_exc: QuoinError = exc
    logger.warning(
        "quoin_error",
        status_code=quoin_exc.status_code,
        message=quoin_exc.message,
        path=request.url.path,
    )
    problem = ProblemDetail(
        type=_problem_type(quoin_exc),
        title=_problem_title(quoin_exc.status_code),
        status=quoin_exc.status_code,
        detail=quoin_exc.message,
        instance=request.url.path,
    )
    return _problem_response(problem, quoin_exc.status_code, quoin_exc.headers)


async def unhandled_exception_handler(request: Request, exc: Any) -> Response:
    """Handle any exception not caught by a more specific handler.

    Guarantees that even bare ``KeyError``s or non-transport ``httpx``
    errors surface as RFC 9457 ``application/problem+json`` responses
    rather than Starlette's default ``text/plain`` 500. The internal
    exception message and traceback are logged but never leaked to the
    client.
    """
    logger.exception(
        "unhandled_exception",
        exc_type=type(exc).__name__,
        path=request.url.path,
    )
    problem = ProblemDetail(
        type="urn:quoin:error:internal_server_error",
        title=_problem_title(500),
        status=500,
        detail="Internal Server Error",
        instance=request.url.path,
    )
    return _problem_response(problem, 500)


async def validation_exception_handler(request: Request, exc: Any) -> Response:
    """Handle Pydantic and FastAPI request validation errors."""
    errors: list[dict[str, Any]] = exc.errors()
    problem = ProblemDetail(
        type="urn:quoin:error:validation_error",
        title=_problem_title(422),
        status=422,
        detail="Request validation failed",
        instance=request.url.path,
        errors=errors,
    )
    return _problem_response(problem, 422)


def add_exception_handlers(app: FastAPI) -> None:
    """Add exception handlers to the application."""
    app.add_exception_handler(
        QuoinRequestValidationError, validation_exception_handler
    )
    app.add_exception_handler(QuoinError, quoin_exception_handler)
    app.add_exception_handler(
        RequestValidationError, validation_exception_handler
    )
    app.add_exception_handler(Exception, unhandled_exception_handler)
