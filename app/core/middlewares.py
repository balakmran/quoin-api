from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.core.config import settings


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


__all__ = ["configure_cors", "configure_middlewares", "configure_trusted_hosts"]
