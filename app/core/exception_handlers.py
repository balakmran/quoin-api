"""Renders exceptions as RFC 9457 ``application/problem+json``.

``add_exception_handlers`` registers the whole set with the application
at startup: ``QuoinError``, request validation failures, Starlette's
``HTTPException`` (404, 405, ...), and anything that escapes uncaught.
Between them they cover every way a request can fail, so no response
falls back to FastAPI's default ``{"detail": ...}`` shape.

The 500 handler never puts the exception message in the response. It is
logged instead, with the request ID to join on.
"""

import json
import re
from http import HTTPStatus
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import Response
from fastapi.utils import is_body_allowed_for_status_code
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import QuoinError, QuoinRequestValidationError
from app.core.schemas import ProblemDetail

logger = structlog.get_logger(__name__)

_PROBLEM_MEDIA_TYPE = "application/problem+json"

# Cap on a reflected `input` value in a 422 body, so a validation error
# never echoes an unbounded amount of client data back to the client.
_MAX_INPUT_CHARS = 200

#: Signals that `input` should be dropped rather than reflected.
_OMIT_INPUT = object()

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


def _detail_text(detail: Any) -> str:
    """Render an ``HTTPException.detail`` as an RFC 9457 ``detail`` string.

    RFC 9457 types ``detail`` as a string, but FastAPI allows any
    JSON-serializable value there (``detail={"code": ...}`` is a common
    idiom) and its own handler passes that through as real JSON. A bare
    ``str()`` would emit a Python ``repr`` — single-quoted and not
    parseable by a client — so a non-string detail is JSON-encoded
    instead, and anything that still cannot be encoded falls back to
    ``str()``.
    """
    if isinstance(detail, str):
        return detail
    try:
        return json.dumps(jsonable_encoder(detail))
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return str(detail)


def _problem_type_from_status(status_code: int) -> str:
    """Derive a URN problem type from a status code's reason phrase.

    Used for :class:`~starlette.exceptions.HTTPException`, which (unlike
    a :class:`~app.core.exceptions.QuoinError` subclass) has no
    exception-class name worth encoding — every status raises the same
    class, so ``_problem_type`` would collapse a 404 and a 405 into the
    same generic ``urn:quoin:error:http_exception``.
    """
    phrase = _problem_title(status_code)
    snake = re.sub(r"[^a-zA-Z0-9]+", "_", phrase).strip("_").lower()
    return f"urn:quoin:error:{snake}"


def _problem_response(
    problem: ProblemDetail,
    status_code: int,
    headers: dict[str, str] | None = None,
) -> Response:
    """Serialize a ProblemDetail into an application/problem+json response.

    Statuses that forbid a body (1xx, 204, 205, 304) get a bodyless
    response instead: sending one anyway is a protocol violation that
    ASGI servers reject outright — uvicorn raises "Response content
    longer than Content-Length" mid-send, after the headers are already
    on the wire, leaving the client with a truncated response. Starlette
    and FastAPI both special-case these statuses in their own handlers
    for the same reason.
    """
    if not is_body_allowed_for_status_code(status_code):
        return Response(status_code=status_code, headers=headers)
    return Response(
        content=problem.model_dump_json(exclude_none=True),
        status_code=status_code,
        media_type=_PROBLEM_MEDIA_TYPE,
        headers=headers,
    )


def _log_error_response(
    event: str, status_code: int, exc: BaseException, **fields: Any
) -> None:
    """Log an error response at the level matching who has to act on it.

    A 5xx is the server's fault: ERROR, with the traceback an operator
    needs. 401/403 stay at WARNING, where repeated denials are worth
    watching. Any other 4xx -- including every scanner's 404 -- is the
    client's mistake and routine: INFO.
    """
    if status_code >= 500:  # noqa: PLR2004
        logger.error(event, status_code=status_code, exc_info=exc, **fields)
    elif status_code in (401, 403):
        logger.warning(event, status_code=status_code, **fields)
    else:
        logger.info(event, status_code=status_code, **fields)


async def quoin_exception_handler(request: Request, exc: Any) -> Response:
    """Handle QuoinError exceptions."""
    error: QuoinError = exc
    _log_error_response(
        "quoin_error",
        error.status_code,
        error,
        message=error.message,
        path=request.url.path,
    )
    problem = ProblemDetail(
        type=_problem_type(error),
        title=_problem_title(error.status_code),
        status=error.status_code,
        detail=error.message,
        instance=request.url.path,
    )
    return _problem_response(problem, error.status_code, error.headers)


async def http_exception_handler(request: Request, exc: Any) -> Response:
    """Handle Starlette's own ``HTTPException``.

    FastAPI/Starlette raise this internally for cases no domain
    exception ever covers — no route matched (404), a route matched but
    not for this method (405) — and register a default handler for it
    that returns a bare ``{"detail": ...}`` JSON body. Left unregistered
    here, that default would be the one gap in the "every error response
    is ``application/problem+json``" contract the rest of the app
    upholds (the same class of gap B3 was for the 500 path).

    Registering against the Starlette base class (rather than
    ``fastapi.HTTPException``) also catches ``fastapi.HTTPException`` —
    still occasionally the more convenient choice in third-party
    dependencies — since it is a subclass.
    """
    http_exc: StarletteHTTPException = exc
    _log_error_response(
        "http_exception",
        http_exc.status_code,
        http_exc,
        detail=http_exc.detail,
        path=request.url.path,
    )
    problem = ProblemDetail(
        type=_problem_type_from_status(http_exc.status_code),
        title=_problem_title(http_exc.status_code),
        status=http_exc.status_code,
        detail=_detail_text(http_exc.detail),
        instance=request.url.path,
    )
    headers = dict(http_exc.headers) if http_exc.headers else None
    return _problem_response(problem, http_exc.status_code, headers)


async def unhandled_exception_handler(request: Request, exc: Any) -> Response:
    """Handle any exception not caught by a more specific handler.

    Guarantees that even bare ``KeyError``s or non-transport ``httpx2``
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


def _truncate_input(value: Any) -> Any:
    """Cap the serialised length of a reflected validation `input` value.

    Never changes the value's JSON type: a string is shortened, but an
    over-long object or array is dropped rather than replaced by a
    truncated stand-in, which would make the type of ``errors[].input``
    depend on the value's size — and a cut-off Python ``repr`` isn't
    valid JSON for a client to parse anyway.

    Args:
        value: A JSON-safe value (already through ``jsonable_encoder``).

    Returns:
        ``value`` if it fits, a truncated string if it is an over-long
        string, else ``_OMIT_INPUT``.
    """
    if isinstance(value, str):
        if len(value) <= _MAX_INPUT_CHARS:
            return value
        return value[:_MAX_INPUT_CHARS] + "…"
    if len(repr(value)) <= _MAX_INPUT_CHARS:
        return value
    return _OMIT_INPUT


def _sanitize_validation_errors(
    errors: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Make validation errors JSON-safe and trim what they reveal.

    A ``field_validator`` raising ``ValueError`` — Pydantic's documented
    idiom — puts the exception object itself under ``ctx.error``, which
    is not JSON-serializable, so serialising it directly would turn this
    422 into a 500. ``jsonable_encoder`` stringifies whatever it cannot
    otherwise encode.

    Also drops ``url`` (a link into Pydantic's docs) and bounds ``input``
    (see ``_truncate_input``), so an error never echoes an unbounded
    amount of client data — or a secret pasted into the wrong field.

    Args:
        errors: Raw error dicts from ``exc.errors()``.

    Returns:
        JSON-safe error dicts with `url` removed and `input` bounded.
    """
    sanitized: list[dict[str, Any]] = []
    for error in jsonable_encoder(errors):
        error.pop("url", None)
        if "input" in error:
            truncated = _truncate_input(error["input"])
            if truncated is _OMIT_INPUT:
                del error["input"]
            else:
                error["input"] = truncated
        sanitized.append(error)
    return sanitized


async def validation_exception_handler(request: Request, exc: Any) -> Response:
    """Handle Pydantic and FastAPI request validation errors."""
    errors = _sanitize_validation_errors(exc.errors())
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
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
