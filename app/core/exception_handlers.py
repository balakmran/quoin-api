import re
from http import HTTPStatus
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import Response
from pydantic import ValidationError

from app.core.exceptions import QuoinError, QuoinRequestValidationError
from app.core.schemas import ProblemDetail

logger = structlog.get_logger(__name__)

_PROBLEM_MEDIA_TYPE = "application/problem+json"


def _problem_type(exc: Exception) -> str:
    """Derive a URN problem type from the exception class name."""
    name = type(exc).__name__
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
    return f"urn:quoin:error:{snake}"


def _problem_title(status_code: int) -> str:
    """Return the standard HTTP reason phrase for a status code."""
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return "Error"


def _problem_response(
    problem: ProblemDetail,
    status_code: int,
    headers: dict[str, str] | None = None,
) -> Response:
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
    app.add_exception_handler(ValidationError, validation_exception_handler)
