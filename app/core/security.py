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
import structlog
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.algorithms import ECAlgorithm, RSAAlgorithm
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import settings
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.http.client import ResilientHTTPClient, get_http_client

logger = structlog.get_logger(__name__)

#: Claims a token must carry, not merely satisfy when present. PyJWT
#: only verifies claims that exist, so without ``require`` a token with
#: no ``exp`` never expires and one with no ``sub`` yields an anonymous
#: principal.
_REQUIRED_CLAIMS = ["exp", "iat", "sub", "aud", "iss"]

#: Seconds of clock skew tolerated on ``exp``/``iat``/``nbf``. Small
#: enough that an expired token is not usefully extended, large enough
#: that an IdP a few seconds ahead of this host does not mint tokens
#: that fail on arrival.
_CLOCK_SKEW_LEEWAY_SECONDS = 10

#: Per-attempt timeout for a JWKS fetch, shorter than the general
#: outbound timeout so a slow IdP cannot outlast the request timeout.
_JWKS_FETCH_TIMEOUT_SECONDS = 3.0


def _not_configured(setting: str) -> UnauthorizedError:
    """Log which OAuth setting is missing; return a generic 401.

    Args:
        setting: The unset ``QUOIN_*`` variable, for the log line only.

    Returns:
        An error whose body does not name the setting.
    """
    logger.error("oauth_not_configured", setting=setting)
    return UnauthorizedError("Authentication is not configured")


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

    def __init__(
        self,
        uri: str,
        ttl_seconds: int = 3600,
        min_refresh_seconds: float = 30.0,
    ) -> None:
        """Initialize JWKSCache.

        Args:
            uri: The JWKS endpoint URL.
            ttl_seconds: Cache TTL in seconds (default 1 hour).
            min_refresh_seconds: Minimum seconds between refetches
                triggered by an unknown kid. Bounds outbound calls
                when tokens carrying garbage kids are sprayed.
        """
        self._uri = uri
        self._ttl = ttl_seconds
        self._min_refresh = min_refresh_seconds
        self._keys: dict[str, Any] = {}
        self._fetched_at: float = float("-inf")
        self._last_attempt: float = float("-inf")
        self._lock = asyncio.Lock()
        self._refresh_task: asyncio.Task[None] | None = None

    def _is_stale(self) -> bool:
        """Return True if the cache has expired."""
        return (time.monotonic() - self._fetched_at) > self._ttl

    def _may_refetch(self) -> bool:
        """Return True if enough time has passed to attempt a refetch.

        Backs off after the last fetch *attempt* (success or failure)
        so a spray of unknown-kid tokens — or a persistently failing
        JWKS endpoint — triggers at most one outbound call per
        ``min_refresh`` window.
        """
        return (time.monotonic() - self._last_attempt) > self._min_refresh

    async def _refresh(self, client: ResilientHTTPClient) -> None:
        """Fetch fresh keys from the JWKS URI via the shared HTTP client.

        Transport-level failures (connection refused, timeout, open
        circuit) propagate as the client's 5xx domain exceptions —
        a down IdP is our upstream failing, not a bad caller token.
        Only a genuine HTTP error *response* (e.g. 404 JWKS), an
        unparseable body, or JSON that is not a JWKS document maps back
        to ``UnauthorizedError``.

        Args:
            client: The shared resilient HTTP client (retries, per-host
                circuit breaker, shared timeout, OTel instrumentation).
        """
        # Record the attempt up-front so a *failed* fetch also backs
        # off, not just a successful one.
        self._last_attempt = time.monotonic()
        response = await client.get(
            self._uri,
            retry_on_status=True,
            timeout=_JWKS_FETCH_TIMEOUT_SECONDS,
        )
        try:
            response.raise_for_status()
            jwks = response.json()
        except Exception as exc:
            raise UnauthorizedError(
                "Unable to fetch OAuth signing keys"
            ) from exc

        # Valid JSON is not necessarily a JWKS document. An array or a
        # string here would otherwise raise AttributeError as a 500.
        key_list = jwks.get("keys", []) if isinstance(jwks, dict) else None
        if not isinstance(key_list, list):
            raise UnauthorizedError("Unable to fetch OAuth signing keys")

        keys: dict[str, Any] = {}
        for key_data in key_list:
            if not isinstance(key_data, dict):
                logger.warning(
                    "jwks_key_unparseable",
                    kid=None,
                    kty=None,
                    error=f"expected an object, got {type(key_data).__name__}",
                )
                continue
            if key_data.get("use") not in ("sig", None):
                continue
            kid = key_data.get("kid", "")
            kty = key_data.get("kty")
            if kty not in ("RSA", "EC"):
                continue
            # Parse per key: one malformed entry in the IdP's document
            # must not take down every other key in it. Raising here
            # would escape as a 500 *and* leave ``_fetched_at`` unset,
            # so every request for the next backoff window would re-raise.
            try:
                if kty == "RSA":
                    keys[kid] = RSAAlgorithm.from_jwk(key_data)
                else:
                    keys[kid] = ECAlgorithm.from_jwk(key_data)
            except Exception as exc:
                logger.warning(
                    "jwks_key_unparseable",
                    kid=kid,
                    kty=kty,
                    error=repr(exc),
                )
        self._keys = keys
        self._fetched_at = time.monotonic()

    async def _background_refresh(self, client: ResilientHTTPClient) -> None:
        """Refresh a stale key set without failing any request."""
        try:
            async with self._lock:
                if self._is_stale() and self._may_refetch():
                    await self._refresh(client)
        except Exception as exc:
            logger.warning("jwks_background_refresh_failed", error=repr(exc))

    async def get_signing_key(
        self, kid: str, client: ResilientHTTPClient
    ) -> Any:
        """Return the public key for the given kid.

        A known kid is served from the cache without waiting on the
        lock; if the set is stale, it is refreshed in the background
        (stale-while-revalidate). Only an unknown kid waits for a fetch.

        Args:
            kid: The key ID from the JWT header.
            client: The shared resilient HTTP client used for any refresh.

        Returns:
            The RSA public key object.

        Raises:
            UnauthorizedError: If the kid is not found after a fresh fetch.
        """
        key = self._keys.get(kid)
        if key is not None:
            if (
                self._is_stale()
                and self._may_refetch()
                and (self._refresh_task is None or self._refresh_task.done())
            ):
                self._refresh_task = asyncio.create_task(
                    self._background_refresh(client)
                )
            return key

        async with self._lock:
            # A request queued behind this lock may find the kid fetched.
            if kid not in self._keys and self._may_refetch():
                await self._refresh(client)
        if kid not in self._keys:
            raise UnauthorizedError("Token signing key not found")
        return self._keys[kid]


async def get_jwks_cache(request: Request) -> JWKSCache:
    """Return (or lazily create) this application's JWKS cache.

    Stored on ``app.state`` — mirroring ``get_http_client`` — rather than
    a module-level global, so each application instance (real or test)
    gets its own cache instead of sharing one process-wide singleton, and
    a future multi-issuer setup has somewhere per-app to keep more than
    one.

    Declared ``async`` deliberately: it sits on the authenticated
    request path, and a plain ``def`` dependency would make FastAPI hop
    to a threadpool worker on every request just to read an attribute.
    Running on the event loop also makes the check-then-set below atomic,
    so a cold-start burst cannot build (and discard) several caches.

    Args:
        request: The current FastAPI request (used to access app.state).

    Returns:
        The application's :class:`JWKSCache`.

    Raises:
        UnauthorizedError: If ``QUOIN_OAUTH_JWKS_URI`` is not set.
    """
    cache = getattr(request.app.state, "jwks_cache", None)
    if cache is None:
        if not settings.OAUTH_JWKS_URI:
            raise _not_configured("QUOIN_OAUTH_JWKS_URI")
        cache = JWKSCache(
            settings.OAUTH_JWKS_URI,
            ttl_seconds=settings.OAUTH_JWKS_TTL_SECONDS,
            min_refresh_seconds=settings.OAUTH_JWKS_MIN_REFRESH_SECONDS,
        )
        request.app.state.jwks_cache = cache
    return cache


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


async def validate_token(
    token: str, client: ResilientHTTPClient, cache: JWKSCache
) -> dict[str, Any]:
    """Validate a Bearer JWT against the configured OAuth server.

    Checks the signature (via JWKS) and requires — not merely
    verifies-if-present — ``exp``, ``iat``, ``sub``, ``aud``, and
    ``iss``.

    Args:
        token: Raw JWT string (without "Bearer " prefix).
        client: The shared resilient HTTP client used to fetch JWKS.
        cache: The application's JWKS cache (see ``get_jwks_cache``).

    Returns:
        Decoded claims dict.

    Raises:
        UnauthorizedError: On any validation failure.
    """
    if not settings.OAUTH_JWKS_URI:
        raise _not_configured("QUOIN_OAUTH_JWKS_URI")
    if not settings.OAUTH_AUDIENCE:
        raise _not_configured("QUOIN_OAUTH_AUDIENCE")
    # PyJWT silently skips issuer verification when ``issuer`` is None,
    # so an unset issuer would let any token signed by a JWKS key pass
    # regardless of ``iss``. Require it explicitly.
    if not settings.OAUTH_ISSUER:
        raise _not_configured("QUOIN_OAUTH_ISSUER")

    # InvalidTokenError, not DecodeError: PyJWT 2.10+ also validates the
    # header here (a non-string ``kid``, an unsupported ``crit``).
    try:
        header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError("Invalid token format") from exc

    kid = header.get("kid", "")
    public_key = await cache.get_signing_key(kid, client)

    decode_options: dict[str, Any] = {
        "verify_exp": True,
        "verify_aud": True,
        "require": _REQUIRED_CLAIMS,
    }

    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            public_key,
            algorithms=["RS256", "ES256"],
            audience=settings.OAUTH_AUDIENCE,
            issuer=settings.OAUTH_ISSUER,
            leeway=_CLOCK_SKEW_LEEWAY_SECONDS,
            options=decode_options,  # type: ignore
        )
    except jwt.MissingRequiredClaimError as exc:
        raise UnauthorizedError(
            f"Token is missing the required claim: {exc.claim}"
        ) from exc
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
    http_client: ResilientHTTPClient = Depends(get_http_client),
    cache: JWKSCache = Depends(get_jwks_cache),
) -> dict[str, Any]:
    """Extract and validate the Bearer token from the request.

    Args:
        credentials: HTTP Bearer credentials from the Authorization header.
        http_client: The shared resilient HTTP client (for JWKS fetches).
        cache: The application's JWKS cache.

    Returns:
        Decoded JWT claims dict.

    Raises:
        UnauthorizedError: If no token is provided or validation fails.
    """
    if credentials is None:
        raise UnauthorizedError("Authorization header is required")
    return await validate_token(credentials.credentials, http_client, cache)


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

    Raises:
        UnauthorizedError: If ``sub`` is present but empty — an
            identity that would authorize as the empty string.
    """
    subject = str(claims.get("sub", "")).strip()
    if not subject:
        raise UnauthorizedError("Token subject is empty")
    roles = extract_roles(claims)
    # Later log lines in this request say who the caller was;
    # RequestIDMiddleware unbinds it when the request ends.
    structlog.contextvars.bind_contextvars(caller=subject)
    return ServicePrincipal(subject=subject, roles=roles, claims=claims)


def _is_superuser(caller: ServicePrincipal) -> bool:
    """Return whether the caller holds the configured bypass role.

    Args:
        caller: The resolved calling principal.

    Returns:
        True if the bypass is enabled, named, and held by the caller.
    """
    superuser = settings.OAUTH_SUPERUSER_ROLE
    return bool(
        settings.OAUTH_SUPERUSER_ENABLED
        and superuser
        and superuser in caller.roles
    )


def require_roles(*roles: str) -> Callable[..., Any]:
    """Dependency factory for role-based authorization.

    Usage:

        @router.delete("/{id}", status_code=204)
        async def delete_resource(
            id: str,
            _: Annotated[
                ServicePrincipal,
                Depends(require_roles("resource.write")),
            ],
        ) -> None: ...

    A caller holding ``QUOIN_OAUTH_SUPERUSER_ROLE`` (default
    ``api.superuser``) bypasses every check. Set
    ``QUOIN_OAUTH_SUPERUSER_ENABLED=false`` to remove the bypass
    entirely — worth doing if the IdP is shared and could issue a role
    by that name to callers that should not hold global authority.

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
        if _is_superuser(caller):
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
    "get_jwks_cache",
    "get_token_claims",
    "require_roles",
    "validate_token",
]
