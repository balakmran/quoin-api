"""OAuth 2.0 / OIDC security infrastructure.

This module provides stateless JWT validation against any OIDC-compliant
authorization server, plus FastAPI dependencies for protecting routes.

No routes, no models, no database access.
"""

import asyncio
import time
from collections.abc import Callable
from typing import Any

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from httpx import AsyncClient
from jwt.algorithms import RSAAlgorithm
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import settings
from app.core.exceptions import ForbiddenError, UnauthorizedError

# ---------------------------------------------------------------------------
# JWKS Cache
# ---------------------------------------------------------------------------

_http_bearer = HTTPBearer(
    auto_error=False,
    description="OAuth 2.0 Bearer token from your authorization server.",
)


class JWKSCache:
    """Fetches and caches JWKS from the configured OAuth server.

    Refreshes automatically on TTL expiry or when a token references
    an unknown kid (handles provider-side key rotation transparently).
    """

    def __init__(self, uri: str, ttl_seconds: int = 3600) -> None:
        """Initialize JWKSCache.

        Args:
            uri: The JWKS endpoint URL.
            ttl_seconds: Cache TTL in seconds (default 1 hour).
        """
        self._uri = uri
        self._ttl = ttl_seconds
        self._keys: dict[str, Any] = {}
        self._fetched_at: float = 0.0
        self._lock = asyncio.Lock()

    def _is_stale(self) -> bool:
        """Return True if the cache has expired."""
        return (time.monotonic() - self._fetched_at) > self._ttl

    async def _refresh(self) -> None:
        """Fetch fresh keys from the JWKS URI."""
        async with AsyncClient() as client:
            response = await client.get(self._uri, timeout=10.0)
            response.raise_for_status()
            jwks = response.json()

        self._keys = {
            key_data["kid"]: RSAAlgorithm.from_jwk(key_data)
            for key_data in jwks.get("keys", [])
            if key_data.get("use") in ("sig", None)
            and key_data.get("kty") == "RSA"
        }
        self._fetched_at = time.monotonic()

    async def get_signing_key(self, kid: str) -> Any:
        """Return the public key for the given kid.

        Fetches from JWKS URI if the cache is stale or the kid is unknown.

        Args:
            kid: The key ID from the JWT header.

        Returns:
            The RSA public key object.

        Raises:
            UnauthorizedError: If the kid is not found after a fresh fetch.
        """
        async with self._lock:
            if self._is_stale() or kid not in self._keys:
                await self._refresh()
            if kid not in self._keys:
                raise UnauthorizedError("Token signing key not found")
            return self._keys[kid]


# Module-level cache instance (initialised lazily on first request)
_jwks_cache: JWKSCache | None = None


def _get_jwks_cache() -> JWKSCache:
    """Return (or create) the module-level JWKS cache."""
    global _jwks_cache  # noqa: PLW0603
    if _jwks_cache is None:
        if not settings.OAUTH_JWKS_URI:
            raise UnauthorizedError(
                "OAuth not configured — QUOIN_OAUTH_JWKS_URI is not set"
            )
        _jwks_cache = JWKSCache(settings.OAUTH_JWKS_URI)
    return _jwks_cache


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def extract_roles(claims: dict[str, Any]) -> list[str]:
    """Normalize app roles from JWT claims.

    Handles both:
    - Array format (Azure AD / app roles): ``["api.read", "api.admin"]``
    - Space-separated string (OAuth 2.0 scope): ``"api.read api.admin"``

    Args:
        claims: Decoded JWT claims dict.

    Returns:
        List of role strings.
    """
    raw = claims.get(settings.OAUTH_ROLES_CLAIM, [])
    if isinstance(raw, str):
        return raw.split()
    if isinstance(raw, list):
        return [str(r) for r in raw]
    return []


# ---------------------------------------------------------------------------
# ServicePrincipal
# ---------------------------------------------------------------------------


class ServicePrincipal(BaseModel):
    """Resolved identity of an authenticated calling service.

    Attributes:
        subject: The ``sub`` claim — stable service identifier.
        roles: Normalized app roles from the token.
        claims: Full decoded JWT payload for advanced use.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    subject: str
    roles: list[str] = Field(default_factory=list)
    claims: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Token validation
# ---------------------------------------------------------------------------


async def validate_token(token: str) -> dict[str, Any]:
    """Validate a Bearer JWT against the configured OAuth server.

    Checks signature (via JWKS), expiry, audience, and issuer.

    Args:
        token: Raw JWT string (without "Bearer " prefix).

    Returns:
        Decoded claims dict.

    Raises:
        UnauthorizedError: On any validation failure.
    """
    if not settings.OAUTH_JWKS_URI:
        raise UnauthorizedError(
            "OAuth not configured — QUOIN_OAUTH_JWKS_URI is not set"
        )

    try:
        header = jwt.get_unverified_header(token)
    except jwt.DecodeError as exc:
        raise UnauthorizedError("Invalid token format") from exc

    kid = header.get("kid", "")
    cache = _get_jwks_cache()
    public_key = await cache.get_signing_key(kid)

    decode_options: dict[str, Any] = {
        "verify_exp": True,
        "verify_aud": bool(settings.OAUTH_AUDIENCE),
    }

    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            public_key,
            algorithms=["RS256", "ES256"],
            audience=settings.OAUTH_AUDIENCE or None,
            issuer=settings.OAUTH_ISSUER,
            options=decode_options,  # type: ignore
        )
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("Token has expired") from exc
    except jwt.InvalidAudienceError as exc:
        raise UnauthorizedError("Invalid token audience") from exc
    except jwt.InvalidIssuerError as exc:
        raise UnauthorizedError("Invalid token issuer") from exc
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("Token validation failed") from exc

    return claims


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------


async def get_token_claims(
    credentials: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
) -> dict[str, Any]:
    """Extract and validate the Bearer token from the request.

    Args:
        credentials: HTTP Bearer credentials from the Authorization header.

    Returns:
        Decoded JWT claims dict.

    Raises:
        UnauthorizedError: If no token is provided or validation fails.
    """
    if credentials is None:
        raise UnauthorizedError("Authorization header is required")
    return await validate_token(credentials.credentials)


async def get_current_caller(
    claims: dict[str, Any] = Depends(get_token_claims),
) -> ServicePrincipal:
    """Resolve ServicePrincipal from validated token claims.

    Does not enforce any specific role — routes declare their own
    requirements via ``require_roles()``.

    Args:
        claims: Decoded JWT claims from ``get_token_claims``.

    Returns:
        ServicePrincipal with subject, roles, and claims.
    """
    subject = claims.get("sub", "")
    roles = extract_roles(claims)
    return ServicePrincipal(subject=subject, roles=roles, claims=claims)


def require_roles(*roles: str) -> Callable[..., Any]:
    """Dependency factory for role-based authorization.

    Usage::

        @router.delete("/{id}", status_code=204)
        async def delete_resource(
            id: str,
            _: Annotated[
                ServicePrincipal,
                Depends(require_roles("resource.write")),
            ],
        ) -> None: ...

    Args:
        *roles: One or more role names that the caller must hold.

    Returns:
        A FastAPI dependency that returns ServicePrincipal or raises
        ForbiddenError.
    """

    async def _check(
        caller: ServicePrincipal = Depends(get_current_caller),
    ) -> ServicePrincipal:
        """Check that the caller holds all required roles."""
        if "api.superuser" in caller.roles:
            return caller

        missing = [r for r in roles if r not in caller.roles]
        if missing:
            raise ForbiddenError(
                f"Missing required role(s): {', '.join(missing)}"
            )
        return caller

    return _check


__all__ = [
    "JWKSCache",
    "ServicePrincipal",
    "extract_roles",
    "get_current_caller",
    "get_token_claims",
    "require_roles",
    "validate_token",
]
