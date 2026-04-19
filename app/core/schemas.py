from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Standard error response model used across the application.

    This schema ensures OpenAPI documentation correctly maps the
    error JSON payloads emitted by the global exception handlers.
    """

    detail: str = Field(..., description="A human-readable error description.")
