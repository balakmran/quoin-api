from collections.abc import Sequence
from typing import Any, LiteralString, NotRequired, TypedDict

from pydantic_core import ErrorDetails, InitErrorDetails, PydanticCustomError
from pydantic_core import ValidationError as PydanticValidationError


class QuoinError(Exception):
    """Base exception for all Quoin application errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize QuoinError."""
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

    Note: TimeoutMiddleware builds the 504 RFC 9457 response directly
    rather than raising this exception, because BaseHTTPMiddleware runs
    outside the ExceptionMiddleware layer where registered handlers live.
    This class exists for use in service/route code and for type-safe
    construction of timeout error details.
    """

    def __init__(
        self,
        message: str = "Request timed out",
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize GatewayTimeoutError."""
        super().__init__(message, status_code=504, headers=headers)
