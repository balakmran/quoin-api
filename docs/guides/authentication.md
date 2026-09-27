# Authentication

Every API call carries a Bearer JWT from your OAuth server, obtained with
the Client Credentials grant; there are no sessions, cookies, or
passwords. QuoinAPI validates the token against the server's JWKS, then
checks the route's required role. Any OIDC-compliant provider works
(Azure AD, Okta, Auth0, Keycloak), under OAuth 2.0 or 2.1 alike: 2.1's
changes apply to authorization servers, not to an API like this one.

## Concepts

### ServicePrincipal

`ServicePrincipal` is the resolved identity of an authenticated calling
service — not a human user. It is built from validated JWT claims and
injected into every protected route by `require_roles()`.

```python
class ServicePrincipal(BaseModel):
    subject: str  # JWT `sub` — stable, unique service identifier
    roles: list[str]  # Normalized app roles from the token
    claims: dict[str, Any]  # Full decoded JWT payload (for advanced use)
```

`subject` maps to the OAuth 2.0 `sub` claim, which is stable and
provider-agnostic across Azure AD, Auth0, Okta, and Keycloak:

```json
{
  "sub": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "roles": ["users.read"],
  "iss": "https://login.microsoftonline.com/{tenant}/v2.0",
  "aud": "api://your-app-client-id",
  "exp": 1713484800
}
```

Use `caller.subject` in structured logs for audit trails:

```python
logger.info(
    "resource.deleted",
    actor=caller.subject,
    resource_id=resource_id,
)
```

### App Roles (Domain Scoped)

Authorization is enforced via **app roles** embedded in the token.

QuoinAPI enforces **domain-scoped permissions** rather than global
read/write permissions. Scopes name a resource's bounded context, formatted
`[domain].[action]`, to follow the principle of least privilege.

| Role | Description | Protects |
| :--- | :--- | :--- |
| `users.read` | Read access to a domain | `GET /api/v1/users/` |
| `users.write` | Mutation access to a domain | `POST /api/v1/users/` |
| `api.superuser` | **Global Bypass** (opt-in) | *Local testing and master scripts* |

Routes declare which role they require via `require_roles(...)`. There is
no hidden baseline role, so every route documents its own access
requirement.

The bypass is **off by default**. `QUOIN_OAUTH_SUPERUSER_ENABLED=true`
turns it on, and the generated `.env` does so for local development.
Enabled in production, it logs `production_superuser_bypass_enabled`
at startup. The role name is a setting, `QUOIN_OAUTH_SUPERUSER_ROLE`:
if you enable the bypass and your IdP could issue a role literally
named `api.superuser` to callers who should not hold global authority,
rename it.

### Token Validation

Every request to a protected endpoint runs the following checks natively:

| Check | Source |
| :--- | :--- |
| Signature | JWKS from your OAuth server (cached with auto-rotation) |
| Required claims | `exp`, `iat`, `sub`, `aud`, `iss` must all be **present** |
| Expiry | `exp` claim, with 10 s of clock-skew leeway |
| Audience | `aud` == `QUOIN_OAUTH_AUDIENCE` |
| Issuer | `iss` == `QUOIN_OAUTH_ISSUER` |
| Subject | `sub` is non-empty after trimming |
| Role | `roles` contains the specifically requested `[domain].[action]` |

!!! warning "Presence is checked, not just validity"
    PyJWT verifies only the claims a token actually carries. Without
    `options["require"]`, a token minted with **no `exp`** would be
    accepted forever, and one with no `sub` would resolve to a
    `ServicePrincipal` with an empty subject. QuoinAPI therefore
    requires all five claims explicitly; a token missing any of them is
    a `401` naming the claim.

    If your IdP genuinely omits one — some legacy servers skip `iat` —
    adjust `_REQUIRED_CLAIMS` in `app/core/security.py`. Do not remove
    `exp`.

## Flow

```mermaid
sequenceDiagram
    participant CS as Calling Service
    participant OS as OAuth Server
    participant QA as QuoinAPI

    CS->>OS: client_credentials grant
    OS-->>CS: JWT (sub, roles)
    CS->>QA: Bearer <JWT>
    QA->>OS: GET /jwks (cached)
    OS-->>QA: public keys
    Note over QA: validate sig / required claims<br/>exp / aud / iss, then roles
    QA-->>CS: 200 OK
```

## Configuration

| Variable | Description | Default |
| :--- | :--- | :--- |
| `QUOIN_OAUTH_JWKS_URI` | JWKS endpoint (public signing keys) | `None` |
| `QUOIN_OAUTH_ISSUER` | Expected `iss` claim | `None` |
| `QUOIN_OAUTH_AUDIENCE` | Expected `aud` claim | `None` |
| `QUOIN_OAUTH_ROLES_CLAIM` | Claim key holding app roles | `roles` |
| `QUOIN_OAUTH_SUPERUSER_ROLE` | Role that bypasses every `require_roles()` check | `api.superuser` |
| `QUOIN_OAUTH_SUPERUSER_ENABLED` | Whether the bypass applies at all | `false` |
| `QUOIN_OAUTH_JWKS_MIN_REFRESH_SECONDS` | Min seconds between JWKS refetches triggered by an unknown `kid` | `30.0` |
| `QUOIN_OAUTH_JWKS_TTL_SECONDS` | Seconds a fetched key set is fresh; a stale set is still served while it refreshes in the background | `3600` |

!!! warning "All three trust anchors are required"
    `validate_token` rejects every request unless
    `QUOIN_OAUTH_JWKS_URI`, `QUOIN_OAUTH_ISSUER`, **and**
    `QUOIN_OAUTH_AUDIENCE` are set. Issuer is enforced explicitly
    because PyJWT silently skips `iss` verification when the expected
    issuer is `None`. In `production` these are validated at **startup**
    — a deployment missing any of them (or using a non-`https://` JWKS
    URI) crash-loops rather than serving 401s while looking healthy.

!!! note
    If your provider uses scopes instead of roles (e.g. Okta, Auth0
    M2M), set `QUOIN_OAUTH_ROLES_CLAIM=scope`. The validator handles
    both array (`["users.read"]`) and space-separated string
    (`"users.read users.write"`) formats automatically.

!!! tip
    The local `mock-oauth2-server` places roles in the `aud` claim, so
    the development `.env` uses `QUOIN_OAUTH_ROLES_CLAIM=aud`.
    Production IdPs (Azure AD, Auth0, Keycloak) use `roles` — the
    default value.

## Protecting Routes

Every route names its own required role with `require_roles()`; there is
no implicit baseline, so a route without it is open to any caller.

```python
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.security import ServicePrincipal, require_roles

router = APIRouter()


@router.get("/")
async def list_users(
    caller: Annotated[ServicePrincipal, Depends(require_roles("users.read"))],
): ...
```

The dependency chain is `HTTPBearer` → `get_token_claims` (validates the
JWT) → `get_current_caller` (builds the `ServicePrincipal`) →
`require_roles` (checks the role). Depend on `get_current_caller`
directly when a route needs the caller but no role.

## Local Testing & Tokens

`just dev` starts `mock-oauth2-server` beside the database. It issues
real RS256 JWTs from a real JWKS endpoint, and `just token` mints them,
so no real SSO is needed. The local `.env` enables the superuser bypass,
so one token reaches every endpoint:

```bash
just token --roles="api.superuser"
```

To check a role is refused, mint a narrower token and try a write:

```bash
TOKEN=$(just token --roles="users.read")
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/users/   # 200
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"email":"bad@caller.com"}' http://localhost:8000/api/v1/users/        # 403
```

The test suite skips tokens entirely; see [Testing](#testing).

## Error Responses

All error responses use `Content-Type: application/problem+json`
(RFC 9457). The `401` includes `WWW-Authenticate: Bearer` per RFC 6750.

| Status | When |
| :--- | :--- |
| `401 Unauthorized` | No token, malformed token or header, expired token, invalid signature |
| `403 Forbidden` | Valid token, but missing required role |

## Testing

Route tests don't mint real tokens. `read_client` and `admin_client`
override the `get_current_caller` dependency with a fixed
`ServicePrincipal`, so a test exercises *your* authorization rules
without a JWKS round trip:

```python
async def test_create_user(admin_client: AsyncClient) -> None:
    """A caller holding users.write may create."""
    response = await admin_client.post(
        "/api/v1/users/", json={"email": "new@example.com"}
    )
    assert response.status_code == 201
```

The negative cases are the ones worth writing, and they're the ones
people skip. An authenticated caller without the role gets `403`, and
`anonymous_client` — a client carrying no credentials at all — gets
`401`:

```python
async def test_create_user_requires_write(read_client: AsyncClient) -> None:
    """A caller holding only users.read cannot create."""
    response = await read_client.post(
        "/api/v1/users/", json={"email": "denied@example.com"}
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


async def test_create_user_requires_a_token(
    anonymous_client: AsyncClient,
) -> None:
    """A missing token is 401, not 403."""
    response = await anonymous_client.post(
        "/api/v1/users/", json={"email": "anon@example.com"}
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
```

`anonymous_client` exists because the plain `client` fixture cannot
reach the 401 path. `get_token_claims` rejects a missing header before
it touches the HTTP client, but FastAPI resolves every dependency in
the signature first — and `get_http_client` raises unless the lifespan
ran, which it does not under `ASGITransport`. The fixture overrides
that one dependency so the rejection happens where it should.

Every protected route deserves all three: the allowed caller, the
under-privileged caller, and no caller at all. Distinguishing 401 from
403 matters — collapsing them tells an authenticated client to go and
re-authenticate, which will not help.

Token validation itself — JWKS fetching, key selection, malformed keys,
expiry — is already covered in `tests/core/test_security.py`. Don't
re-test it per route; test your role checks.

## See Also

- [Configuration Guide](configuration.md)
- [Error Handling Guide](error-handling.md)
- [app/core/security.py](https://github.com/balakmran/quoin-api/blob/main/app/core/security.py)
