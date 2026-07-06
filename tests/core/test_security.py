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
from app.core.exceptions import (
    BadGatewayError,
    ForbiddenError,
    UnauthorizedError,
)
from app.core.security import (
    JWKSCache,
    ServicePrincipal,
    extract_roles,
    get_current_caller,
    require_roles,
    validate_token,
)
from app.http.client import ResilientHTTPClient


def _fake_http_client(
    *, response: Any = None, side_effect: Exception | None = None
) -> Any:
    """Build a fake resilient HTTP client whose ``get`` returns/raises."""
    client = MagicMock(spec=ResilientHTTPClient)
    client.get = (
        AsyncMock(side_effect=side_effect)
        if side_effect is not None
        else AsyncMock(return_value=response)
    )
    return client


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
    await cache._refresh(_fake_http_client(response=mock_response))

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
    await cache._refresh(_fake_http_client(response=mock_response))

    assert "ec-key-1" in cache._keys


async def test_jwks_cache_refresh_skips_non_sig_keys() -> None:
    """_refresh ignores keys whose 'use' is not 'sig' or absent."""
    jwks_payload = {"keys": [{"kid": "enc-key", "kty": "RSA", "use": "enc"}]}

    mock_response = MagicMock(spec=Response)
    mock_response.json.return_value = jwks_payload
    mock_response.raise_for_status.return_value = None

    cache = JWKSCache("http://example.com/jwks")
    await cache._refresh(_fake_http_client(response=mock_response))

    assert cache._keys == {}


async def test_jwks_cache_refresh_skips_unknown_kty_keys() -> None:
    """_refresh ignores keys with an unrecognised kty (e.g. OKP)."""
    jwks_payload = {"keys": [{"kid": "okp-key", "kty": "OKP", "use": "sig"}]}

    mock_response = MagicMock(spec=Response)
    mock_response.json.return_value = jwks_payload
    mock_response.raise_for_status.return_value = None

    cache = JWKSCache("http://example.com/jwks")
    await cache._refresh(_fake_http_client(response=mock_response))

    assert cache._keys == {}


async def test_jwks_cache_refresh_propagates_transport_failure() -> None:
    """A transport failure surfaces as a 5xx domain error, not a 401.

    The shared client already translates connection failures into
    Bad/Gateway/ServiceUnavailable — a down IdP is our upstream failing,
    so it must not be relabelled as an auth (401) problem.
    """
    cache = JWKSCache("http://example.com/jwks")
    client = _fake_http_client(
        side_effect=BadGatewayError("Upstream request failed")
    )

    with pytest.raises(BadGatewayError):
        await cache._refresh(client)


async def test_jwks_cache_refresh_raises_on_http_error() -> None:
    """A JWKS HTTP error *response* (e.g. 404) maps to UnauthorizedError."""
    mock_response = MagicMock(spec=Response)
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "404 Not Found", request=MagicMock(), response=MagicMock()
    )
    cache = JWKSCache("http://example.com/jwks")

    with pytest.raises(
        UnauthorizedError, match="Unable to fetch OAuth signing keys"
    ):
        await cache._refresh(_fake_http_client(response=mock_response))


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
    key = await cache.get_signing_key(
        "key-abc", _fake_http_client(response=mock_response)
    )

    assert key is not None


async def test_jwks_cache_get_signing_key_not_found() -> None:
    """get_signing_key raises UnauthorizedError when kid is unknown."""
    mock_response = MagicMock(spec=Response)
    mock_response.json.return_value = {"keys": []}
    mock_response.raise_for_status.return_value = None

    cache = JWKSCache("http://example.com/jwks")

    with pytest.raises(UnauthorizedError, match="signing key not found"):
        await cache.get_signing_key(
            "missing-kid", _fake_http_client(response=mock_response)
        )


async def test_jwks_cache_get_signing_key_cache_hit(
    rsa_public_key: rsa.RSAPublicKey,
) -> None:
    """get_signing_key returns a key from cache without re-fetching."""
    cache = JWKSCache("http://example.com/jwks")
    # Pre-populate the cache and mark it as fresh
    cache._keys = {"cached-kid": rsa_public_key}
    cache._fetched_at = time.monotonic()

    # No outbound call should be made — the client's get must stay unused.
    client = _fake_http_client(response=MagicMock())
    key = await cache.get_signing_key("cached-kid", client)
    client.get.assert_not_awaited()

    assert key is rsa_public_key


def _client_with_get(get_mock: AsyncMock) -> Any:
    """Build a fake resilient HTTP client whose get uses ``get_mock``."""
    client = MagicMock(spec=ResilientHTTPClient)
    client.get = get_mock
    return client


async def test_jwks_cache_unknown_kid_backoff() -> None:
    """Repeated unknown kids inside the window trigger one fetch (S2)."""
    mock_response = MagicMock(spec=Response)
    mock_response.json.return_value = {"keys": []}
    mock_response.raise_for_status.return_value = None
    get_mock = AsyncMock(return_value=mock_response)

    # A large min_refresh keeps both sprays inside the backoff window.
    cache = JWKSCache("http://example.com/jwks", min_refresh_seconds=1000)
    client = _client_with_get(get_mock)

    with pytest.raises(UnauthorizedError, match="signing key not found"):
        await cache.get_signing_key("spray-1", client)
    with pytest.raises(UnauthorizedError, match="signing key not found"):
        await cache.get_signing_key("spray-2", client)

    # The second unknown kid is served from cache — no outbound call.
    assert get_mock.await_count == 1


async def test_jwks_cache_failed_fetch_backs_off() -> None:
    """A failing JWKS endpoint is retried at most once per window (S2)."""
    get_mock = AsyncMock(side_effect=BadGatewayError("boom"))

    cache = JWKSCache("http://example.com/jwks", min_refresh_seconds=1000)
    client = _client_with_get(get_mock)

    # First attempt propagates the upstream failure (5xx, not a 401)...
    with pytest.raises(BadGatewayError):
        await cache.get_signing_key("any-kid", client)
    # ...and even though the cache is still empty/stale, the backoff timer
    # (set before the failed fetch) suppresses the second call, so the
    # kid is simply reported missing.
    with pytest.raises(UnauthorizedError, match="signing key not found"):
        await cache.get_signing_key("any-kid", client)

    assert get_mock.await_count == 1


def test_jwks_cache_init_records_min_refresh() -> None:
    """min_refresh_seconds is stored on the cache (S2)."""
    cache = JWKSCache("http://example.com/jwks", min_refresh_seconds=15.0)
    assert cache._min_refresh == 15.0  # noqa: PLR2004
    assert cache._last_attempt == float("-inf")


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
    claims = await validate_token(token, _fake_http_client())
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
        await validate_token(token, _fake_http_client())


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
        await validate_token(token, _fake_http_client())


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
        await validate_token(token, _fake_http_client())


async def test_validate_token_no_uri(
    mock_settings: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """validate_token raises UnauthorizedError if no JWKS URI is set."""
    mock_settings.OAUTH_JWKS_URI = ""
    with pytest.raises(UnauthorizedError, match="not configured"):
        await validate_token("header.payload.signature", _fake_http_client())


async def test_validate_token_no_audience(
    mock_settings: MagicMock,
) -> None:
    """validate_token raises UnauthorizedError if audience is not set."""
    mock_settings.OAUTH_AUDIENCE = ""
    with pytest.raises(UnauthorizedError, match="QUOIN_OAUTH_AUDIENCE"):
        await validate_token("header.payload.signature", _fake_http_client())


async def test_validate_token_no_issuer(
    mock_settings: MagicMock,
) -> None:
    """validate_token raises UnauthorizedError if issuer is not set (S1).

    Guards the PyJWT hole where ``issuer=None`` skips ``iss`` checks.
    """
    mock_settings.OAUTH_ISSUER = ""
    with pytest.raises(UnauthorizedError, match="QUOIN_OAUTH_ISSUER"):
        await validate_token("header.payload.signature", _fake_http_client())


async def test_validate_token_malformed(
    mock_settings: MagicMock,
) -> None:
    """Malformed token string raises UnauthorizedError."""
    with pytest.raises(UnauthorizedError, match="Invalid token format"):
        await validate_token("not.a.jwt", _fake_http_client())


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
            await validate_token(token, _fake_http_client())


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
    http_client = _fake_http_client()

    result = await security_module.get_token_claims(
        credentials=credentials, http_client=http_client
    )

    mock_validate.assert_awaited_once_with("raw.jwt.token", http_client)
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
