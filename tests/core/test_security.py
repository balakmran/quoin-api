"""Unit tests for app/core/security.py."""

import json
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from httpx import Response
from jwt.algorithms import ECAlgorithm, RSAAlgorithm

from app.core import security as security_module
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import (
    JWKSCache,
    ServicePrincipal,
    extract_roles,
    get_current_caller,
    require_roles,
    validate_token,
)


@pytest.fixture(scope="session")
def rsa_private_key() -> rsa.RSAPrivateKey:
    """Generate a test RSA private key."""
    return rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )


@pytest.fixture(scope="session")
def rsa_public_key(
    rsa_private_key: rsa.RSAPrivateKey,
) -> rsa.RSAPublicKey:
    """Return the public key for the test RSA key pair."""
    return rsa_private_key.public_key()


def _make_token(
    private_key: rsa.RSAPrivateKey,
    claims: dict[str, Any],
    kid: str = "test-kid",
    algorithm: str = "RS256",
) -> str:
    """Sign a JWT with the given private key and claims."""
    return jwt.encode(
        claims,
        private_key,
        algorithm=algorithm,
        headers={"kid": kid},
    )


def _make_claims(
    *,
    sub: str = "svc-001",
    aud: str = "quoin-api",
    iss: str = "http://mock-issuer",
    exp_offset: int = 3600,
    roles: list[str] | None = None,
) -> dict[str, Any]:
    """Build a minimal claims dict for test tokens."""
    now = int(time.time())
    claims: dict[str, Any] = {
        "sub": sub,
        "aud": aud,
        "iss": iss,
        "iat": now,
        "exp": now + exp_offset,
    }
    if roles is not None:
        claims["roles"] = roles
    return claims


_TEST_TTL_SECONDS = 60


def test_jwks_cache_init() -> None:
    """JWKSCache initialises with correct default state."""
    cache = JWKSCache("http://example.com/jwks", ttl_seconds=_TEST_TTL_SECONDS)
    assert cache._uri == "http://example.com/jwks"
    assert cache._ttl == _TEST_TTL_SECONDS
    assert cache._keys == {}
    assert cache._fetched_at == float("-inf")


def test_jwks_cache_is_stale_initially() -> None:
    """A freshly created cache reports as stale."""
    cache = JWKSCache("http://example.com/jwks")
    assert cache._is_stale() is True


def test_jwks_cache_is_not_stale_after_fetch() -> None:
    """Cache is not stale immediately after _fetched_at is set."""
    cache = JWKSCache("http://example.com/jwks", ttl_seconds=3600)
    cache._fetched_at = time.monotonic()
    assert cache._is_stale() is False


async def test_jwks_cache_refresh_parses_rsa_keys(
    rsa_private_key: rsa.RSAPrivateKey,
    rsa_public_key: rsa.RSAPublicKey,
) -> None:
    """_refresh fetches JWKS and populates _keys with RSA public keys."""
    jwk_public = RSAAlgorithm.to_jwk(rsa_public_key)
    jwk_dict = json.loads(jwk_public)
    jwk_dict["kid"] = "key-1"
    jwk_dict["use"] = "sig"
    jwks_payload = {"keys": [jwk_dict]}

    mock_response = MagicMock(spec=Response)
    mock_response.json.return_value = jwks_payload
    mock_response.raise_for_status.return_value = None

    cache = JWKSCache("http://example.com/jwks")

    with patch(
        "app.core.security.AsyncClient",
        return_value=AsyncMock(
            __aenter__=AsyncMock(
                return_value=AsyncMock(
                    get=AsyncMock(return_value=mock_response)
                )
            ),
            __aexit__=AsyncMock(return_value=False),
        ),
    ):
        await cache._refresh()

    assert "key-1" in cache._keys
    assert cache._fetched_at > 0


async def test_jwks_cache_refresh_parses_ec_keys() -> None:
    """_refresh populates _keys with EC public keys (ES256 support)."""
    ec_private_key = ec.generate_private_key(ec.SECP256R1())
    ec_public_key = ec_private_key.public_key()
    jwk_dict = json.loads(ECAlgorithm.to_jwk(ec_public_key))
    jwk_dict["kid"] = "ec-key-1"
    jwk_dict["use"] = "sig"
    jwks_payload = {"keys": [jwk_dict]}

    mock_response = MagicMock(spec=Response)
    mock_response.json.return_value = jwks_payload
    mock_response.raise_for_status.return_value = None

    cache = JWKSCache("http://example.com/jwks")

    with patch(
        "app.core.security.AsyncClient",
        return_value=AsyncMock(
            __aenter__=AsyncMock(
                return_value=AsyncMock(
                    get=AsyncMock(return_value=mock_response)
                )
            ),
            __aexit__=AsyncMock(return_value=False),
        ),
    ):
        await cache._refresh()

    assert "ec-key-1" in cache._keys


async def test_jwks_cache_refresh_skips_non_sig_keys() -> None:
    """_refresh ignores keys whose 'use' is not 'sig' or absent."""
    jwks_payload = {"keys": [{"kid": "enc-key", "kty": "RSA", "use": "enc"}]}

    mock_response = MagicMock(spec=Response)
    mock_response.json.return_value = jwks_payload
    mock_response.raise_for_status.return_value = None

    cache = JWKSCache("http://example.com/jwks")

    with patch(
        "app.core.security.AsyncClient",
        return_value=AsyncMock(
            __aenter__=AsyncMock(
                return_value=AsyncMock(
                    get=AsyncMock(return_value=mock_response)
                )
            ),
            __aexit__=AsyncMock(return_value=False),
        ),
    ):
        await cache._refresh()

    assert cache._keys == {}


async def test_jwks_cache_refresh_skips_unknown_kty_keys() -> None:
    """_refresh ignores keys with an unrecognised kty (e.g. OKP)."""
    jwks_payload = {"keys": [{"kid": "okp-key", "kty": "OKP", "use": "sig"}]}

    mock_response = MagicMock(spec=Response)
    mock_response.json.return_value = jwks_payload
    mock_response.raise_for_status.return_value = None

    cache = JWKSCache("http://example.com/jwks")

    with patch(
        "app.core.security.AsyncClient",
        return_value=AsyncMock(
            __aenter__=AsyncMock(
                return_value=AsyncMock(
                    get=AsyncMock(return_value=mock_response)
                )
            ),
            __aexit__=AsyncMock(return_value=False),
        ),
    ):
        await cache._refresh()

    assert cache._keys == {}


async def test_jwks_cache_refresh_raises_on_http_error() -> None:
    """_refresh raises UnauthorizedError when the JWKS endpoint is down."""
    cache = JWKSCache("http://example.com/jwks")

    with patch(
        "app.core.security.AsyncClient",
        return_value=AsyncMock(
            __aenter__=AsyncMock(
                return_value=AsyncMock(
                    get=AsyncMock(
                        side_effect=httpx.ConnectError("connection refused")
                    )
                )
            ),
            __aexit__=AsyncMock(return_value=False),
        ),
    ):
        with pytest.raises(
            UnauthorizedError, match="Unable to fetch OAuth signing keys"
        ):
            await cache._refresh()


async def test_jwks_cache_get_signing_key_found(
    rsa_private_key: rsa.RSAPrivateKey,
    rsa_public_key: rsa.RSAPublicKey,
) -> None:
    """get_signing_key returns the public key for a known kid."""
    jwk_public = RSAAlgorithm.to_jwk(rsa_public_key)
    jwk_dict = json.loads(jwk_public)
    jwk_dict["kid"] = "key-abc"
    jwk_dict["use"] = "sig"
    jwks_payload = {"keys": [jwk_dict]}

    mock_response = MagicMock(spec=Response)
    mock_response.json.return_value = jwks_payload
    mock_response.raise_for_status.return_value = None

    cache = JWKSCache("http://example.com/jwks")

    with patch(
        "app.core.security.AsyncClient",
        return_value=AsyncMock(
            __aenter__=AsyncMock(
                return_value=AsyncMock(
                    get=AsyncMock(return_value=mock_response)
                )
            ),
            __aexit__=AsyncMock(return_value=False),
        ),
    ):
        key = await cache.get_signing_key("key-abc")

    assert key is not None


async def test_jwks_cache_get_signing_key_not_found() -> None:
    """get_signing_key raises UnauthorizedError when kid is unknown."""
    mock_response = MagicMock(spec=Response)
    mock_response.json.return_value = {"keys": []}
    mock_response.raise_for_status.return_value = None

    cache = JWKSCache("http://example.com/jwks")

    with patch(
        "app.core.security.AsyncClient",
        return_value=AsyncMock(
            __aenter__=AsyncMock(
                return_value=AsyncMock(
                    get=AsyncMock(return_value=mock_response)
                )
            ),
            __aexit__=AsyncMock(return_value=False),
        ),
    ):
        with pytest.raises(UnauthorizedError, match="signing key not found"):
            await cache.get_signing_key("missing-kid")


async def test_jwks_cache_get_signing_key_cache_hit(
    rsa_public_key: rsa.RSAPublicKey,
) -> None:
    """get_signing_key returns a key from cache without re-fetching."""
    cache = JWKSCache("http://example.com/jwks")
    # Pre-populate the cache and mark it as fresh
    cache._keys = {"cached-kid": rsa_public_key}
    cache._fetched_at = time.monotonic()

    # No HTTP call should be made — if AsyncClient is invoked this test fails
    with patch("app.core.security.AsyncClient") as mock_client:
        key = await cache.get_signing_key("cached-kid")
        mock_client.assert_not_called()

    assert key is rsa_public_key


def test_get_jwks_cache_no_uri_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_get_jwks_cache raises UnauthorizedError when no JWKS URI is set."""
    monkeypatch.setattr(
        security_module,
        "settings",
        MagicMock(OAUTH_JWKS_URI=None),
    )
    monkeypatch.setattr(security_module, "_jwks_cache", None)

    with pytest.raises(UnauthorizedError, match="QUOIN_OAUTH_JWKS_URI"):
        security_module._get_jwks_cache()


def test_get_jwks_cache_creates_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_get_jwks_cache creates and stores a JWKSCache when one doesn't exist."""
    monkeypatch.setattr(
        security_module,
        "settings",
        MagicMock(OAUTH_JWKS_URI="http://example.com/jwks"),
    )
    monkeypatch.setattr(security_module, "_jwks_cache", None)

    cache = security_module._get_jwks_cache()

    assert isinstance(cache, JWKSCache)
    assert cache._uri == "http://example.com/jwks"


def test_extract_roles_array(monkeypatch: pytest.MonkeyPatch) -> None:
    """Array-format roles claim is parsed correctly."""
    monkeypatch.setattr(
        security_module,
        "settings",
        MagicMock(OAUTH_ROLES_CLAIM="roles"),
    )
    assert extract_roles({"roles": ["api.read", "api.admin"]}) == [
        "api.read",
        "api.admin",
    ]


def test_extract_roles_scope_string(monkeypatch: pytest.MonkeyPatch) -> None:
    """Space-separated scope string is parsed correctly."""
    monkeypatch.setattr(
        security_module,
        "settings",
        MagicMock(OAUTH_ROLES_CLAIM="scope"),
    )
    assert extract_roles({"scope": "api.read api.admin"}) == [
        "api.read",
        "api.admin",
    ]


def test_extract_roles_missing_claim(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing roles claim returns empty list."""
    monkeypatch.setattr(
        security_module,
        "settings",
        MagicMock(OAUTH_ROLES_CLAIM="roles"),
    )
    assert extract_roles({}) == []


def test_extract_roles_invalid_type(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-string, non-list roles claim returns empty list (fallback branch)."""
    monkeypatch.setattr(
        security_module,
        "settings",
        MagicMock(OAUTH_ROLES_CLAIM="roles"),
    )
    # Pass an integer — neither str nor list
    assert extract_roles({"roles": 42}) == []


@pytest.fixture
def mock_settings(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Patch settings with valid OAuth config."""
    s = MagicMock(
        OAUTH_JWKS_URI="http://mock-issuer/jwks",
        OAUTH_ISSUER="http://mock-issuer",
        OAUTH_AUDIENCE="quoin-api",
        OAUTH_ROLES_CLAIM="roles",
        OAUTH_READ_ROLE="api.read",
        OAUTH_ADMIN_ROLE="api.admin",
    )
    monkeypatch.setattr(security_module, "settings", s)
    monkeypatch.setattr(security_module, "_jwks_cache", None)
    return s


async def test_validate_token_success(
    rsa_private_key: rsa.RSAPrivateKey,
    rsa_public_key: rsa.RSAPublicKey,
    mock_settings: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Valid token returns decoded claims."""
    cache = MagicMock(spec=JWKSCache)
    cache.get_signing_key = AsyncMock(return_value=rsa_public_key)
    monkeypatch.setattr(security_module, "_jwks_cache", cache)

    token = _make_token(rsa_private_key, _make_claims())
    claims = await validate_token(token)
    assert claims["sub"] == "svc-001"


async def test_validate_token_expired(
    rsa_private_key: rsa.RSAPrivateKey,
    rsa_public_key: rsa.RSAPublicKey,
    mock_settings: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Expired token raises UnauthorizedError."""
    cache = MagicMock(spec=JWKSCache)
    cache.get_signing_key = AsyncMock(return_value=rsa_public_key)
    monkeypatch.setattr(security_module, "_jwks_cache", cache)

    token = _make_token(rsa_private_key, _make_claims(exp_offset=-1))
    with pytest.raises(UnauthorizedError, match="expired"):
        await validate_token(token)


async def test_validate_token_wrong_audience(
    rsa_private_key: rsa.RSAPrivateKey,
    rsa_public_key: rsa.RSAPublicKey,
    mock_settings: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Token with wrong audience raises UnauthorizedError."""
    cache = MagicMock(spec=JWKSCache)
    cache.get_signing_key = AsyncMock(return_value=rsa_public_key)
    monkeypatch.setattr(security_module, "_jwks_cache", cache)

    token = _make_token(rsa_private_key, _make_claims(aud="wrong-audience"))
    with pytest.raises(UnauthorizedError, match="audience"):
        await validate_token(token)


async def test_validate_token_wrong_issuer(
    rsa_private_key: rsa.RSAPrivateKey,
    rsa_public_key: rsa.RSAPublicKey,
    mock_settings: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Token with wrong issuer raises UnauthorizedError."""
    cache = MagicMock(spec=JWKSCache)
    cache.get_signing_key = AsyncMock(return_value=rsa_public_key)
    monkeypatch.setattr(security_module, "_jwks_cache", cache)

    token = _make_token(rsa_private_key, _make_claims(iss="http://evil-issuer"))
    with pytest.raises(UnauthorizedError, match="issuer"):
        await validate_token(token)


async def test_validate_token_no_uri(
    mock_settings: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """validate_token raises UnauthorizedError if no JWKS URI is set."""
    mock_settings.OAUTH_JWKS_URI = ""
    with pytest.raises(UnauthorizedError, match="not configured"):
        await validate_token("header.payload.signature")


async def test_validate_token_no_audience(
    mock_settings: MagicMock,
) -> None:
    """validate_token raises UnauthorizedError if audience is not set."""
    mock_settings.OAUTH_AUDIENCE = ""
    with pytest.raises(UnauthorizedError, match="QUOIN_OAUTH_AUDIENCE"):
        await validate_token("header.payload.signature")


async def test_validate_token_malformed(
    mock_settings: MagicMock,
) -> None:
    """Malformed token string raises UnauthorizedError."""
    with pytest.raises(UnauthorizedError, match="Invalid token format"):
        await validate_token("not.a.jwt")


async def test_validate_token_generic_pyjwt_error(
    rsa_private_key: rsa.RSAPrivateKey,
    rsa_public_key: rsa.RSAPublicKey,
    mock_settings: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Generic PyJWTError is caught and raised as UnauthorizedError."""
    cache = MagicMock(spec=JWKSCache)
    cache.get_signing_key = AsyncMock(return_value=rsa_public_key)
    monkeypatch.setattr(security_module, "_jwks_cache", cache)

    token = _make_token(rsa_private_key, _make_claims())
    with patch.object(
        jwt,
        "decode",
        side_effect=jwt.PyJWTError("unexpected error"),
    ):
        with pytest.raises(UnauthorizedError, match="Token validation failed"):
            await validate_token(token)


async def test_get_current_caller_resolves_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """get_current_caller resolves subject and roles from token claims."""
    monkeypatch.setattr(
        security_module,
        "settings",
        MagicMock(OAUTH_ROLES_CLAIM="roles"),
    )

    claims = {"sub": "svc-xyz", "roles": ["api.read"]}
    caller = await get_current_caller(claims=claims)
    assert caller.subject == "svc-xyz"
    assert caller.roles == ["api.read"]
    assert caller.claims == claims


async def test_get_token_claims_no_credentials() -> None:
    """get_token_claims raises UnauthorizedError if credentials are missing."""
    with pytest.raises(UnauthorizedError, match="Authorization header"):
        await security_module.get_token_claims(credentials=None)


async def test_get_token_claims_delegates_to_validate_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """get_token_claims forwards valid credentials to validate_token."""
    expected = {"sub": "svc", "roles": ["api.read"]}
    mock_validate = AsyncMock(return_value=expected)
    monkeypatch.setattr(security_module, "validate_token", mock_validate)

    credentials = MagicMock()
    credentials.credentials = "raw.jwt.token"

    result = await security_module.get_token_claims(credentials=credentials)

    mock_validate.assert_awaited_once_with("raw.jwt.token")
    assert result == expected


async def test_require_roles_read_pass() -> None:
    """Caller with api.read passes a read-role check."""
    caller = ServicePrincipal(subject="svc", roles=["api.read"], claims={})
    check = require_roles("api.read")
    result = await check(caller=caller)
    assert result.subject == "svc"


async def test_require_roles_admin_pass() -> None:
    """Caller with api.admin passes an admin-role check."""
    caller = ServicePrincipal(
        subject="svc", roles=["api.read", "api.admin"], claims={}
    )
    check = require_roles("api.admin")
    result = await check(caller=caller)
    assert result is caller


async def test_require_roles_admin_fail() -> None:
    """Caller with only api.read fails an admin-role check."""
    caller = ServicePrincipal(subject="svc", roles=["api.read"], claims={})
    check = require_roles("api.admin")
    with pytest.raises(ForbiddenError, match=r"api\.admin"):
        await check(caller=caller)


async def test_require_roles_superuser_bypass() -> None:
    """Caller with api.superuser bypasses all specific role checks."""
    caller = ServicePrincipal(subject="svc", roles=["api.superuser"], claims={})
    check = require_roles("very.specific.role")
    result = await check(caller=caller)  # Should bypass and not raise
    assert result is caller
