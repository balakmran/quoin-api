from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError

from app.core.exceptions import QuoinError


async def quoin_exception_handler(
    request: Request, exc: QuoinError
) -> Response:
    """Handle QuoinError exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
        headers=exc.headers,
    )


async def validation_exception_handler(
    request: Request, exc: ValidationError
) -> Response:
    """Handle Pydantic ValidationError exceptions."""
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )


def add_exception_handlers(app: FastAPI) -> None:
    """Add exception handlers to the application."""
    app.add_exception_handler(QuoinError, quoin_exception_handler)  # type: ignore
    app.add_exception_handler(ValidationError, validation_exception_handler)  # type: ignore
