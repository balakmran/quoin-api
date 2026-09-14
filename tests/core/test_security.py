"""Unit tests for app/core/security.py."""

import asyncio
import base64
import json
import time
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx2
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from httpx2 import Response
from jwt.algorithms import ECAlgorithm, RSAAlgorithm
from structlog.contextvars import get_contextvars, unbind_contextvars
from structlog.testing import capture_logs

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
    get_jwks_cache,
    require_roles,
    validate_token,
)
from app.http.client import ResilientHTTPClient, create_http_client


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


async def test_jwks_cache_refresh_skips_malformed_key(
    rsa_public_key: rsa.RSAPublicKey,
) -> None:
    """A key the algorithm cannot parse is skipped, not fatal (S4).

    One bad entry in the IdP's document used to raise out of _refresh
    as a 500 — and because _fetched_at stayed unset, every request for
    the whole backoff window re-raised it.
    """
    good = json.loads(RSAAlgorithm.to_jwk(rsa_public_key))
    good["kid"] = "good-key"
    good["use"] = "sig"
    bad = {"kid": "bad-key", "kty": "RSA", "use": "sig", "n": "!!!"}
    jwks_payload = {"keys": [bad, good]}

    mock_response = MagicMock(spec=Response)
    mock_response.json.return_value = jwks_payload
    mock_response.raise_for_status.return_value = None

    cache = JWKSCache("http://example.com/jwks")
    with capture_logs() as cap_logs:
        await cache._refresh(_fake_http_client(response=mock_response))

    assert set(cache._keys) == {"good-key"}
    assert cache._fetched_at != float("-inf")
    assert [log["kid"] for log in cap_logs] == ["bad-key"]


async def test_jwks_cache_all_keys_malformed_yields_401() -> None:
    """A document with no usable key is a 401, not a 500 loop (S4)."""
    jwks_payload = {
        "keys": [{"kid": "bad-key", "kty": "RSA", "use": "sig", "n": "!!!"}]
    }

    mock_response = MagicMock(spec=Response)
    mock_response.json.return_value = jwks_payload
    mock_response.raise_for_status.return_value = None

    cache = JWKSCache("http://example.com/jwks")
    with pytest.raises(UnauthorizedError, match="signing key not found"):
        await cache.get_signing_key(
            "bad-key", _fake_http_client(response=mock_response)
        )


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
    mock_response.raise_for_status.side_effect = httpx2.HTTPStatusError(
        "404 Not Found", request=MagicMock(), response=MagicMock()
    )
    cache = JWKSCache("http://example.com/jwks")

    with pytest.raises(
        UnauthorizedError, match="Unable to fetch OAuth signing keys"
    ):
        await cache._refresh(_fake_http_client(response=mock_response))


@pytest.mark.parametrize(
    "payload",
    [["not", "an", "object"], "just a string", {"keys": "not-a-list"}],
    ids=["array", "string", "keys-not-a-list"],
)
async def test_jwks_cache_refresh_rejects_json_that_is_not_jwks(
    payload: object,
) -> None:
    """JSON that is not a JWKS document is a 401, not a repeating 500."""
    mock_response = MagicMock(spec=Response)
    mock_response.json.return_value = payload
    mock_response.raise_for_status.return_value = None
    cache = JWKSCache("http://example.com/jwks")

    with pytest.raises(
        UnauthorizedError, match="Unable to fetch OAuth signing keys"
    ):
        await cache._refresh(_fake_http_client(response=mock_response))


async def test_jwks_cache_refresh_skips_non_object_key(
    rsa_public_key: rsa.RSAPublicKey,
) -> None:
    """A `keys` entry that is not an object is skipped like a malformed key."""
    good = json.loads(RSAAlgorithm.to_jwk(rsa_public_key))
    good["kid"] = "good-key"
    mock_response = MagicMock(spec=Response)
    mock_response.json.return_value = {"keys": ["not-a-key", good]}
    mock_response.raise_for_status.return_value = None

    cache = JWKSCache("http://example.com/jwks")
    with capture_logs() as cap_logs:
        await cache._refresh(_fake_http_client(response=mock_response))

    assert set(cache._keys) == {"good-key"}
    assert [log["event"] for log in cap_logs] == ["jwks_key_unparseable"]


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


def _jwks_response(public_key: rsa.RSAPublicKey, kid: str) -> Any:
    """Build a mock JWKS response carrying one RSA key."""
    jwk_dict = json.loads(RSAAlgorithm.to_jwk(public_key))
    jwk_dict["kid"] = kid
    response = MagicMock(spec=Response)
    response.json.return_value = {"keys": [jwk_dict]}
    response.raise_for_status.return_value = None
    return response


async def test_jwks_cache_stale_key_served_while_refresh_is_slow(
    rsa_public_key: rsa.RSAPublicKey,
) -> None:
    """A slow IdP does not delay requests whose kid is cached."""
    release = asyncio.Event()

    async def handler(request: httpx2.Request) -> httpx2.Response:
        await release.wait()
        return httpx2.Response(200, json={"keys": []})

    client = create_http_client(transport=httpx2.MockTransport(handler))
    cache = JWKSCache("http://example.com/jwks", ttl_seconds=60)
    cache._keys = {"kid": rsa_public_key}
    cache._fetched_at = time.monotonic() - 120

    try:
        for _ in range(2):
            key = await asyncio.wait_for(
                cache.get_signing_key("kid", client), timeout=0.5
            )
            assert key is rsa_public_key
        assert cache._refresh_task is not None
        assert not cache._refresh_task.done()
    finally:
        release.set()
        if cache._refresh_task is not None:
            await cache._refresh_task
        await client.aclose()


async def test_jwks_cache_hit_does_not_wait_on_unknown_kid_fetch(
    rsa_public_key: rsa.RSAPublicKey,
) -> None:
    """A fetch for an unknown kid holds the lock; cache hits skip it."""
    release = asyncio.Event()

    async def slow_get(*args: Any, **kwargs: Any) -> Any:
        await release.wait()
        raise BadGatewayError("boom")

    cache = JWKSCache("http://example.com/jwks")
    cache._keys = {"known": rsa_public_key}
    cache._fetched_at = time.monotonic()
    client = _client_with_get(AsyncMock(side_effect=slow_get))

    pending = asyncio.create_task(cache.get_signing_key("unknown", client))
    await asyncio.sleep(0)
    assert cache._lock.locked()
    key = await asyncio.wait_for(
        cache.get_signing_key("known", client), timeout=0.5
    )
    assert key is rsa_public_key

    release.set()
    with pytest.raises(BadGatewayError):
        await pending


async def test_jwks_cache_queued_unknown_kid_reuses_fetch(
    rsa_public_key: rsa.RSAPublicKey,
) -> None:
    """Concurrent requests for a new kid share one short-timeout fetch."""
    get_mock = AsyncMock(return_value=_jwks_response(rsa_public_key, "new"))
    cache = JWKSCache("http://example.com/jwks", min_refresh_seconds=0)
    client = _client_with_get(get_mock)

    keys = await asyncio.gather(
        cache.get_signing_key("new", client),
        cache.get_signing_key("new", client),
    )

    assert len(keys) == 2  # noqa: PLR2004
    get_mock.assert_awaited_once_with(
        "http://example.com/jwks",
        retry_on_status=True,
        timeout=security_module._JWKS_FETCH_TIMEOUT_SECONDS,
    )


async def test_jwks_cache_background_refresh_failure_is_logged(
    rsa_public_key: rsa.RSAPublicKey,
) -> None:
    """A failed background refresh is logged and the cached key served."""
    cache = JWKSCache("http://example.com/jwks", ttl_seconds=60)
    cache._keys = {"kid": rsa_public_key}
    cache._fetched_at = time.monotonic() - 120
    client = _fake_http_client(side_effect=BadGatewayError("boom"))

    with capture_logs() as cap_logs:
        key = await cache.get_signing_key("kid", client)
        assert cache._refresh_task is not None
        await cache._refresh_task

    assert key is rsa_public_key
    assert [log["event"] for log in cap_logs] == [
        "jwks_background_refresh_failed"
    ]


async def test_jwks_cache_background_refresh_skips_fresh_set(
    rsa_public_key: rsa.RSAPublicKey,
) -> None:
    """A background refresh that finds the set already fresh does nothing."""
    cache = JWKSCache("http://example.com/jwks", ttl_seconds=60)
    cache._keys = {"kid": rsa_public_key}
    cache._fetched_at = time.monotonic() - 120
    client = _fake_http_client(response=MagicMock())

    await cache.get_signing_key("kid", client)
    # Another refresh lands before the scheduled task runs.
    cache._fetched_at = time.monotonic()
    assert cache._refresh_task is not None
    await cache._refresh_task

    client.get.assert_not_awaited()


def test_jwks_cache_init_records_min_refresh() -> None:
    """min_refresh_seconds is stored on the cache (S2)."""
    cache = JWKSCache("http://example.com/jwks", min_refresh_seconds=15.0)
    assert cache._min_refresh == 15.0  # noqa: PLR2004
    assert cache._last_attempt == float("-inf")


async def test_get_jwks_cache_no_uri_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """get_jwks_cache raises UnauthorizedError when no JWKS URI is set."""
    monkeypatch.setattr(
        security_module,
        "settings",
        MagicMock(OAUTH_JWKS_URI=None),
    )
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))

    with pytest.raises(
        UnauthorizedError, match=r"^Authentication is not configured$"
    ):
        await get_jwks_cache(request)  # type: ignore


async def test_get_jwks_cache_creates_and_stores_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """get_jwks_cache creates a JWKSCache and stores it on app.state."""
    monkeypatch.setattr(
        security_module,
        "settings",
        MagicMock(
            OAUTH_JWKS_URI="http://example.com/jwks",
            OAUTH_JWKS_MIN_REFRESH_SECONDS=30.0,
            OAUTH_JWKS_TTL_SECONDS=_TEST_TTL_SECONDS,
        ),
    )
    state = SimpleNamespace()
    request = SimpleNamespace(app=SimpleNamespace(state=state))

    cache = await get_jwks_cache(request)  # type: ignore

    assert isinstance(cache, JWKSCache)
    assert cache._uri == "http://example.com/jwks"
    assert cache._ttl == _TEST_TTL_SECONDS
    # Stored on app.state so the next call reuses the same instance
    # rather than dropping and refetching the keys (S2/Improvement 6).
    assert state.jwks_cache is cache
    assert await get_jwks_cache(request) is cache  # type: ignore


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

    token = _make_token(rsa_private_key, _make_claims())
    claims = await validate_token(token, _fake_http_client(), cache)
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

    # Beyond the clock-skew leeway validate_token now allows.
    token = _make_token(rsa_private_key, _make_claims(exp_offset=-3600))
    with pytest.raises(UnauthorizedError, match="expired"):
        await validate_token(token, _fake_http_client(), cache)


async def test_validate_token_wrong_audience(
    rsa_private_key: rsa.RSAPrivateKey,
    rsa_public_key: rsa.RSAPublicKey,
    mock_settings: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Token with wrong audience raises UnauthorizedError."""
    cache = MagicMock(spec=JWKSCache)
    cache.get_signing_key = AsyncMock(return_value=rsa_public_key)

    token = _make_token(rsa_private_key, _make_claims(aud="wrong-audience"))
    with pytest.raises(UnauthorizedError, match="audience"):
        await validate_token(token, _fake_http_client(), cache)


async def test_validate_token_wrong_issuer(
    rsa_private_key: rsa.RSAPrivateKey,
    rsa_public_key: rsa.RSAPublicKey,
    mock_settings: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Token with wrong issuer raises UnauthorizedError."""
    cache = MagicMock(spec=JWKSCache)
    cache.get_signing_key = AsyncMock(return_value=rsa_public_key)

    token = _make_token(rsa_private_key, _make_claims(iss="http://evil-issuer"))
    with pytest.raises(UnauthorizedError, match="issuer"):
        await validate_token(token, _fake_http_client(), cache)


async def test_validate_token_no_uri(
    mock_settings: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """validate_token raises UnauthorizedError if no JWKS URI is set."""
    mock_settings.OAUTH_JWKS_URI = ""
    await _assert_not_configured("QUOIN_OAUTH_JWKS_URI")


async def _assert_not_configured(setting: str) -> None:
    """Assert the 401 body is generic and only the log names ``setting``."""
    with capture_logs() as cap_logs:
        with pytest.raises(UnauthorizedError) as exc_info:
            await validate_token(
                "header.payload.signature",
                _fake_http_client(),
                MagicMock(spec=JWKSCache),
            )
    assert exc_info.value.message == "Authentication is not configured"
    assert cap_logs == [
        {
            "event": "oauth_not_configured",
            "setting": setting,
            "log_level": "error",
        }
    ]


async def test_validate_token_no_audience(
    mock_settings: MagicMock,
) -> None:
    """validate_token raises UnauthorizedError if audience is not set."""
    mock_settings.OAUTH_AUDIENCE = ""
    await _assert_not_configured("QUOIN_OAUTH_AUDIENCE")


async def test_validate_token_no_issuer(
    mock_settings: MagicMock,
) -> None:
    """validate_token raises UnauthorizedError if issuer is not set (S1).

    Guards the PyJWT hole where ``issuer=None`` skips ``iss`` checks.
    """
    mock_settings.OAUTH_ISSUER = ""
    await _assert_not_configured("QUOIN_OAUTH_ISSUER")


async def test_validate_token_malformed(
    mock_settings: MagicMock,
) -> None:
    """Malformed token string raises UnauthorizedError."""
    with pytest.raises(UnauthorizedError, match="Invalid token format"):
        await validate_token(
            "not.a.jwt", _fake_http_client(), MagicMock(spec=JWKSCache)
        )


def _unsigned_token(header: dict[str, Any]) -> str:
    """Build a token with an arbitrary header and no valid signature."""

    def b64(data: dict[str, Any]) -> str:
        raw = json.dumps(data).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    return f"{b64(header)}.{b64({'sub': 'x'})}.c2ln"


@pytest.mark.parametrize(
    "header",
    [
        {"alg": "RS256", "kid": 123},
        {"alg": "RS256", "kid": {"a": 1}},
        {"alg": "RS256", "kid": "k", "crit": ["foo"]},
    ],
)
async def test_validate_token_invalid_header(
    header: dict[str, Any],
    mock_settings: MagicMock,
) -> None:
    """A header PyJWT rejects is a 401, not an unhandled 500."""
    cache = MagicMock(spec=JWKSCache)
    with pytest.raises(UnauthorizedError, match="Invalid token format"):
        await validate_token(
            _unsigned_token(header), _fake_http_client(), cache
        )
    cache.get_signing_key.assert_not_called()


async def test_validate_token_generic_pyjwt_error(
    rsa_private_key: rsa.RSAPrivateKey,
    rsa_public_key: rsa.RSAPublicKey,
    mock_settings: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Generic PyJWTError is caught and raised as UnauthorizedError."""
    cache = MagicMock(spec=JWKSCache)
    cache.get_signing_key = AsyncMock(return_value=rsa_public_key)

    token = _make_token(rsa_private_key, _make_claims())
    with patch.object(
        jwt,
        "decode",
        side_effect=jwt.PyJWTError("unexpected error"),
    ):
        with pytest.raises(UnauthorizedError, match="Token validation failed"):
            await validate_token(token, _fake_http_client(), cache)


@pytest.mark.parametrize("claim", ["exp", "iat", "sub", "aud", "iss"])
async def test_validate_token_requires_claim(
    claim: str,
    rsa_private_key: rsa.RSAPrivateKey,
    rsa_public_key: rsa.RSAPublicKey,
    mock_settings: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A token omitting any required claim is rejected (S1).

    PyJWT verifies only the claims a token carries, so without
    ``options["require"]`` a token with no ``exp`` never expires.
    """
    cache = MagicMock(spec=JWKSCache)
    cache.get_signing_key = AsyncMock(return_value=rsa_public_key)

    claims = _make_claims()
    del claims[claim]
    token = _make_token(rsa_private_key, claims)
    with pytest.raises(UnauthorizedError, match=f"required claim: {claim}"):
        await validate_token(token, _fake_http_client(), cache)


async def test_validate_token_allows_small_clock_skew(
    rsa_private_key: rsa.RSAPrivateKey,
    rsa_public_key: rsa.RSAPublicKey,
    mock_settings: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A token expired within the leeway still validates (S1)."""
    cache = MagicMock(spec=JWKSCache)
    cache.get_signing_key = AsyncMock(return_value=rsa_public_key)

    token = _make_token(rsa_private_key, _make_claims(exp_offset=-1))
    claims = await validate_token(token, _fake_http_client(), cache)
    assert claims["sub"] == "svc-001"


async def test_get_current_caller_rejects_empty_subject(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty sub is refused rather than authorizing as "" (S1)."""
    monkeypatch.setattr(
        security_module,
        "settings",
        MagicMock(OAUTH_ROLES_CLAIM="roles"),
    )

    with pytest.raises(UnauthorizedError, match="subject is empty"):
        await get_current_caller(claims={"sub": "   ", "roles": []})


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
    try:
        caller = await get_current_caller(claims=claims)
        bound = get_contextvars()
    finally:
        unbind_contextvars("caller")

    assert caller.subject == "svc-xyz"
    assert caller.roles == ["api.read"]
    assert caller.claims == claims
    # Binds the subject so later log lines in the request name the caller.
    assert bound["caller"] == "svc-xyz"


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
    cache = MagicMock(spec=JWKSCache)

    result = await security_module.get_token_claims(
        credentials=credentials, http_client=http_client, cache=cache
    )

    mock_validate.assert_awaited_once_with("raw.jwt.token", http_client, cache)
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


async def test_require_roles_superuser_role_is_configurable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The bypass follows QUOIN_OAUTH_SUPERUSER_ROLE (S3)."""
    monkeypatch.setattr(
        security_module,
        "settings",
        MagicMock(
            OAUTH_SUPERUSER_ROLE="ops.break_glass",
            OAUTH_SUPERUSER_ENABLED=True,
        ),
    )
    caller = ServicePrincipal(
        subject="svc", roles=["ops.break_glass"], claims={}
    )
    assert await require_roles("very.specific.role")(caller=caller) is caller


async def test_require_roles_superuser_bypass_can_be_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """QUOIN_OAUTH_SUPERUSER_ENABLED=false removes the bypass (S3)."""
    monkeypatch.setattr(
        security_module,
        "settings",
        MagicMock(
            OAUTH_SUPERUSER_ROLE="api.superuser",
            OAUTH_SUPERUSER_ENABLED=False,
        ),
    )
    caller = ServicePrincipal(subject="svc", roles=["api.superuser"], claims={})
    with pytest.raises(ForbiddenError, match=r"very\.specific\.role"):
        await require_roles("very.specific.role")(caller=caller)


async def test_require_roles_ignores_an_unnamed_superuser_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty role name never matches, even when enabled (S3)."""
    monkeypatch.setattr(
        security_module,
        "settings",
        MagicMock(OAUTH_SUPERUSER_ROLE="", OAUTH_SUPERUSER_ENABLED=True),
    )
    caller = ServicePrincipal(subject="svc", roles=[""], claims={})
    with pytest.raises(ForbiddenError, match=r"very\.specific\.role"):
        await require_roles("very.specific.role")(caller=caller)
