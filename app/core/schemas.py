"""The response body every error is rendered into.

``ProblemDetail`` is the RFC 9457 document the exception handlers return
for every failure, so a client parses one shape whether it met a
validation error, a 404, or an uncaught 500.

``errors`` is an RFC 9457 extension carrying per-field validation
failures. It is omitted on every status but 422.
"""

from typing import Any

from pydantic import BaseModel, Field


class ProblemDetail(BaseModel):
    """RFC 9457 Problem Details response body.

    Returned for all error responses with Content-Type
    application/problem+json.
    """

    type: str = Field(
        default="about:blank",
        description="URI identifying the problem type.",
    )
    title: str = Field(..., description="Short, human-readable summary.")
    status: int = Field(..., description="HTTP status code.")
    detail: str = Field(..., description="Human-readable explanation.")
    instance: str = Field(
        ..., description="URI of the specific occurrence (request path)."
    )
    errors: list[dict[str, Any]] | None = Field(
        default=None,
        description=(
            "Per-field validation errors (RFC 9457 extension). "
            "Only present on 422 responses."
        ),
    )
