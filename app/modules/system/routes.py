from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core import metadata
from app.db.session import get_session

router = APIRouter()
templates = Jinja2Templates(
    directory=Path(__file__).resolve().parent.parent.parent / "templates"
)


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root(request: Request) -> HTMLResponse:
    """Root endpoint to verify the application is running."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "app_name": metadata.APP_NAME,
            "app_version": metadata.VERSION,
            "app_description": metadata.APP_DESCRIPTION,
            "repository_url": metadata.REPOSITORY_URL,
            "copyright_owner": metadata.COPYRIGHT_OWNER,
            "copyright_year": datetime.now(UTC).year,
        },
    )


@router.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


@router.get("/ready", include_in_schema=False)
async def ready(session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    """Readiness probe endpoint."""
    try:
        await session.exec(text("SELECT 1"))  # type: ignore
        return {"status": "ready"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        ) from e
