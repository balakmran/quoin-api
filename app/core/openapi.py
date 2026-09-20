"""Schema generation, route tags, and shared error declarations.

``DEFAULT_ERROR_RESPONSES`` covers what any authenticated endpoint can
return (401, 403, 422, 500) and belongs on the router;
``error_responses(*codes)`` declares what a single route adds on top.
Requesting an undocumented code raises ``KeyError``, and a
``descriptions`` key matching none of the requested codes raises
``ValueError``, so a typo fails loudly instead of silently documenting
nothing.

``OPENAPI_PARAMETERS`` is the ``FastAPI(...)`` keyword set. Its
``docs_url``, ``redoc_url``, and ``openapi_url`` are all ``None`` in
production, so the schema and both UIs are unavailable there.
``set_openapi_generator`` post-processes the generated schema to label
error responses ``application/problem+json``, matching what the
handlers actually send.

Usage:
    router = APIRouter(prefix="/users", responses=DEFAULT_ERROR_RESPONSES)

    @router.get(
        "/{user_id}",
        responses=error_responses(404, descriptions={404: "User not found"}),
    )
    async def get_user(...) -> ...: ...
"""

import inspect
from collections.abc import Mapping
from enum import StrEnum
from typing import Any, NotRequired, TypedDict

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.core import metadata
from app.core.config import Environment, settings
from app.core.schemas import ProblemDetail

PROBLEM_MEDIA_TYPE = "application/problem+json"

_ERROR_DESCRIPTIONS: dict[int, str] = {
    400: "Bad Request",
    401: "Unauthorized - Missing or invalid token",
    403: "Forbidden - Token lacks the required role",
    404: "Not Found",
    409: "Conflict",
    422: "Validation Error",
    500: "Internal Server Error",
}


def error_responses(
    *codes: int,
    descriptions: Mapping[int, str] | None = None,
) -> dict[int | str, dict[str, Any]]:
    """Build an OpenAPI ``responses`` mapping of RFC 9457 error models.

    Use this for the error codes a specific route can raise. Every
    module router should additionally carry
    ``DEFAULT_ERROR_RESPONSES``, which covers the codes any
    authenticated endpoint can return.

    Args:
        codes: HTTP status codes to document.
        descriptions: Optional per-code overrides, for routes that can
            say something more useful than the generic reason phrase.

    Returns:
        A mapping suitable for the ``responses`` argument of an
        ``APIRouter`` or a route decorator.

    Raises:
        KeyError: If a code has no entry in ``_ERROR_DESCRIPTIONS``.
        ValueError: If ``descriptions`` carries a key that is not in
            ``codes``. Silently dropping it would ship the generic
            reason phrase for a route the caller meant to describe.
    """
    overrides = descriptions or {}
    unmatched = sorted(set(overrides) - set(codes))
    if unmatched:
        raise ValueError(
            f"descriptions keys not in codes: {unmatched}. "
            f"Documented codes are {sorted(codes)}."
        )
    return {
        code: {
            "model": ProblemDetail,
            "description": overrides.get(code, _ERROR_DESCRIPTIONS[code]),
        }
        for code in codes
    }


DEFAULT_ERROR_RESPONSES = error_responses(401, 403, 422, 500)


class OpenAPIExternalDoc(TypedDict):
    """External documentation link for an OpenAPI tag."""

    description: NotRequired[str]
    url: str


class OpenAPITag(TypedDict):
    """OpenAPI tag entry grouping related endpoints."""

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
    openapi_url: str | None
    openapi_tags: list[dict[str, Any]]
    servers: list[dict[str, Any]] | None
    swagger_ui_parameters: dict[str, Any]
    swagger_ui_oauth2_redirect_url: str | None


#: Swagger UI path. Named so `SecurityHeadersMiddleware` can scope the
#: relaxed docs CSP to exactly this route.
DOCS_URL = "/docs"

#: ReDoc path. Listed for symmetry; ReDoc needs no inline script and so
#: is served under the default policy.
REDOC_URL = "/redoc"

OPENAPI_PARAMETERS: OpenAPIParameters = {
    "title": metadata.APP_NAME,
    "summary": metadata.APP_DESCRIPTION,
    "version": metadata.VERSION,
    "description": inspect.cleandoc(metadata.APP_LONG_DESCRIPTION),
    "docs_url": DOCS_URL if settings.ENV != Environment.production else None,
    "redoc_url": (
        REDOC_URL if settings.ENV != Environment.production else None
    ),
    "openapi_url": (
        "/openapi.json" if settings.ENV != Environment.production else None
    ),
    "openapi_tags": APITag.metadata(),  # type: ignore
    "servers": None,
    "swagger_ui_parameters": {"defaultModelsExpandDepth": -1},
    # Its page is an inline script the /docs-only CSP does not cover,
    # and nothing under HTTPBearer uses the OAuth2 redirect flow.
    "swagger_ui_oauth2_redirect_url": None,
}


_OPENAPI_METHODS = frozenset(
    {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
)

_PROBLEM_DETAIL_REF = "#/components/schemas/ProblemDetail"


def _use_problem_media_type(schema: dict[str, Any]) -> None:
    """Relabel RFC 9457 error bodies as ``application/problem+json``.

    FastAPI always files a ``responses`` model under
    ``application/json``, and the declarative ``content`` override
    emits a broken duplicate entry rather than replacing that key. So
    the media type is corrected after generation instead, to match what
    ``app.core.exception_handlers`` actually sends on the wire.

    Only responses whose schema references ``ProblemDetail`` are
    touched, so a non-problem error body is never mislabelled.

    Args:
        schema: Generated OpenAPI schema, modified in place.
    """
    for path_item in schema.get("paths", {}).values():
        for method, operation in path_item.items():
            if method not in _OPENAPI_METHODS:
                continue
            for response in operation.get("responses", {}).values():
                content = response.get("content", {})
                media = content.get("application/json")
                if media is None:
                    continue
                if media.get("schema", {}).get("$ref") == _PROBLEM_DETAIL_REF:
                    content[PROBLEM_MEDIA_TYPE] = content.pop(
                        "application/json"
                    )


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

        _use_problem_media_type(openapi_schema)

        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = _openapi_generator  # type: ignore


__all__ = [
    "DEFAULT_ERROR_RESPONSES",
    "DOCS_URL",
    "OPENAPI_PARAMETERS",
    "PROBLEM_MEDIA_TYPE",
    "REDOC_URL",
    "APITag",
    "error_responses",
    "set_openapi_generator",
]
