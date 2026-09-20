"""Domain exceptions that map business failures to HTTP status codes.

Service and repository code raises these rather than ``HTTPException``,
and the global handlers render them as RFC 9457 problem documents. That
keeps transport concerns out of the domain layers and gives every
failure the same response shape.

Every class below inherits ``QuoinError``, which carries a message, a
status code, and optional response headers.

| Class | Status |
| :---- | :----: |
| `BadRequestError` | 400 |
| `UnauthorizedError` | 401 |
| `ForbiddenError` | 403 |
| `NotFoundError` | 404 |
| `ConflictError` | 409 |
| `QuoinRequestValidationError` | 422 |
| `InternalServerError` | 500 |
| `BadGatewayError` | 502 |
| `ServiceUnavailableError` | 503 |
| `GatewayTimeoutError` | 504 |

Usage:
    from app.core.exceptions import ConflictError, NotFoundError

    raise NotFoundError("User not found")
    raise ConflictError("Email already registered")
"""

from collections.abc import Sequence
from typing import Any, LiteralString, NotRequired, TypedDict

from pydantic_core import ErrorDetails, InitErrorDetails, PydanticCustomError
from pydantic_core import ValidationError as PydanticValidationError


class QuoinError(Exception):
    """Base exception for all application errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize QuoinError.

        Args:
            message: Human-readable error detail, surfaced in the
                response body.
            status_code: HTTP status code for the response.
            headers: Optional extra response headers (e.g.
                ``WWW-Authenticate``).
        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.headers = headers


class ValidationError(TypedDict):
    """Pydantic validation error shape."""

    loc: tuple[int | str, ...]
    msg: LiteralString
    type: LiteralString
    input: Any
    ctx: NotRequired[dict[str, Any]]
    url: NotRequired[str]


class QuoinRequestValidationError(QuoinError):
    """Request validation error (wraps Pydantic ValidationError)."""

    def __init__(self, errors: Sequence[ValidationError]) -> None:
        """Initialize QuoinRequestValidationError."""
        super().__init__("Request validation failed", status_code=422)
        self._errors = errors

    def errors(self) -> list[ErrorDetails]:
        """Convert to Pydantic error format."""
        pydantic_errors: list[InitErrorDetails] = []
        for error in self._errors:
            pydantic_errors.append(
                {
                    "type": PydanticCustomError(error["type"], error["msg"]),
                    "loc": error["loc"],
                    "input": error["input"],
                }
            )
        pydantic_error = PydanticValidationError.from_exception_data(
            self.__class__.__name__, pydantic_errors
        )
        return pydantic_error.errors()


class InternalServerError(QuoinError):
    """Internal Server Error."""

    def __init__(
        self,
        message: str = "Internal Server Error",
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize InternalServerError."""
        super().__init__(message, status_code=500, headers=headers)


class NotFoundError(QuoinError):
    """Resource Not Found."""

    def __init__(
        self,
        message: str = "Not Found",
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize NotFoundError."""
        super().__init__(message, status_code=404, headers=headers)


class ConflictError(QuoinError):
    """Resource Conflict."""

    def __init__(
        self,
        message: str = "Conflict",
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize ConflictError."""
        super().__init__(message, status_code=409, headers=headers)


class BadRequestError(QuoinError):
    """Bad Request."""

    def __init__(
        self,
        message: str = "Bad Request",
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize BadRequestError."""
        super().__init__(message, status_code=400, headers=headers)


class ForbiddenError(QuoinError):
    """Forbidden."""

    def __init__(
        self,
        message: str = "Forbidden",
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize ForbiddenError."""
        super().__init__(message, status_code=403, headers=headers)


class UnauthorizedError(QuoinError):
    """Unauthorized — missing, expired, or invalid Bearer token."""

    def __init__(
        self,
        message: str = "Unauthorized",
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize UnauthorizedError.

        Includes WWW-Authenticate: Bearer header per RFC 6750 §3.1.
        """
        default_headers = {"WWW-Authenticate": "Bearer"}
        super().__init__(
            message,
            status_code=401,
            headers=headers or default_headers,
        )


class BadGatewayError(QuoinError):
    """Bad Gateway — an upstream dependency returned an invalid response."""

    def __init__(
        self,
        message: str = "Bad Gateway",
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize BadGatewayError."""
        super().__init__(message, status_code=502, headers=headers)


class ServiceUnavailableError(QuoinError):
    """Service Unavailable — a required dependency is unreachable."""

    def __init__(
        self,
        message: str = "Service Unavailable",
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize ServiceUnavailableError."""
        super().__init__(message, status_code=503, headers=headers)


class GatewayTimeoutError(QuoinError):
    """Gateway Timeout — request exceeded the configured wall-clock limit.

    Note: ``TimeoutMiddleware`` builds the 504 RFC 9457 response
    directly via raw ASGI rather than raising this exception, because
    the timeout fires from an ``anyio`` cancel scope wrapping the whole
    middleware/router call — there is no request context left in which
    to raise an exception for a handler to catch. This class exists for
    use in service/route code (e.g. an outbound call that times out)
    and for type-safe construction of timeout error details.
    """

    def __init__(
        self,
        message: str = "Request timed out",
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize GatewayTimeoutError."""
        super().__init__(message, status_code=504, headers=headers)
