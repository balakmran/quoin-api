import inspect
from enum import StrEnum
from typing import Any, NotRequired, TypedDict

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.core import metadata
from app.core.config import Environment, settings


class OpenAPIExternalDoc(TypedDict):
    description: NotRequired[str]
    url: str


class OpenAPITag(TypedDict):
    name: str
    description: NotRequired[str]
    externalDocs: NotRequired[dict[str, str]]


class APITag(StrEnum):
    """Tags used by our documentation to better organize the endpoints.

    New route tags should be defined here and imported in
    `module_name/routes.py`.
    """

    users = "users"

    @classmethod
    def metadata(cls) -> list[OpenAPITag]:
        """Get the metadata for the tags."""
        return [
            {
                "name": cls.users,
                "description": "Operations with users.",
            },
        ]


class OpenAPIParameters(TypedDict):
    """Parameters for the OpenAPI schema."""

    title: str
    summary: str
    version: str
    description: str
    docs_url: str | None
    redoc_url: str | None
    openapi_tags: list[dict[str, Any]]
    servers: list[dict[str, Any]] | None
    swagger_ui_parameters: dict[str, Any]


OPENAPI_PARAMETERS: OpenAPIParameters = {
    "title": metadata.APP_NAME,
    "summary": metadata.APP_DESCRIPTION,
    "version": metadata.VERSION,
    "description": inspect.cleandoc(metadata.APP_LONG_DESCRIPTION),
    "docs_url": "/docs" if settings.ENV != Environment.production else None,
    "redoc_url": "/redoc" if settings.ENV != Environment.production else None,
    "openapi_tags": APITag.metadata(),  # type: ignore
    "servers": None,
    "swagger_ui_parameters": {"defaultModelsExpandDepth": -1},
}


def set_openapi_generator(app: FastAPI) -> None:
    """Set the custom OpenAPI generator for the application."""

    def _openapi_generator() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema

        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            openapi_version=app.openapi_version,
            summary=app.summary,
            description=app.description,
            terms_of_service=app.terms_of_service,
            contact=app.contact,
            license_info=app.license_info,
            routes=app.routes,
            webhooks=app.webhooks.routes,
            tags=app.openapi_tags,
            servers=app.servers,
            separate_input_output_schemas=app.separate_input_output_schemas,
        )

        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = _openapi_generator  # type: ignore


__all__ = [
    "OPENAPI_PARAMETERS",
    "APITag",
    "set_openapi_generator",
]
