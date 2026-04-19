# Authentication

This guide covers QuoinAPI's OAuth 2.0 / 2.1 authentication system for
service-to-service API access.

---

## Overview

QuoinAPI uses **Bearer token authentication** based on the OAuth 2.0 Client
Credentials grant. There are no user sessions, cookies, or passwords. Every
API call is authenticated by validating a signed JWT issued by your
authorization server.

The security core is **provider-agnostic**: it works with any OIDC-compliant
server (Azure AD, Okta, Auth0, Keycloak) via standard JWKS discovery.

---

## Concepts

### NUID (Non-User ID)

A **NUID** is the unique identity of a **calling service** — not a human user.
When Service A calls QuoinAPI, it authenticates using its own service identity.

This maps to the standard OAuth 2.0 `sub` (subject) claim in the JWT, which
is stable, unique per service, and provider-agnostic.

```json
{
  "sub": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "roles": ["users.read"],
  "iss": "https://login.microsoftonline.com/{tenant}/v2.0",
  "aud": "api://your-app-client-id",
  "exp": 1713484800
}
```

### App Roles (Domain Scoped)

Authorization is enforced via **app roles** embedded in the token.

QuoinAPI enforces **Domain-Scoped Permissions** rather than global read/write
permissions. Scopes should target specific resource bounded contexts formatted as `[domain].[action]`
to adhere to the Principle of Least Privilege.

| Role | Description | Protects |
| :--- | :--- | :--- |
| `users.read` | Read access to a domain | `GET /api/v1/users/` |
| `users.write` | Mutation access to a domain | `POST /api/v1/users/` |
| `api.superuser` | **Global Bypass** | *Local testing and master scripts* |

Routes explicitly declare which role they require via `require_roles(...)`. There is no hidden baseline
role — every route is perfectly self-documenting.

### Token Validation

Every request to a protected endpoint runs the following checks natively:

| Check | Source |
| :--- | :--- |
| Signature | JWKS from your OAuth server (cached with auto-rotation) |
| Expiry | `exp` claim |
| Audience | `aud` == `QUOIN_OAUTH_AUDIENCE` |
| Issuer | `iss` == `QUOIN_OAUTH_ISSUER` |
| Role | `roles` contains the specifically requested `[domain].[action]` |

---

## Flow

```
Calling Service              OAuth Server              QuoinAPI
      │                           │                        │
      ├─ client_credentials ─────>│                        │
      │<─ JWT (sub, roles) ───────│                        │
      │                           │                        │
      ├─ Bearer <JWT> ────────────────────────────────────->
      │                           │<─ GET /jwks (cached) ──│
      │                           │─ public keys ─────────>│
      │                           │  validate sig/exp/aud  │
      │                           │  check roles claim     │
      │<─ 200 OK ───────────────────────────────────────────
```

---

## Configuration

Add the following to your `.env` file:

```bash
# OAuth 2.0 — required for authentication
QUOIN_OAUTH_JWKS_URI=https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys
QUOIN_OAUTH_ISSUER=https://login.microsoftonline.com/{tenant}/v2.0
QUOIN_OAUTH_AUDIENCE=api://{your-app-client-id}

# Claim key — defaults work for Azure AD; adjust for other providers
QUOIN_OAUTH_ROLES_CLAIM=roles
```

> [!NOTE]
> If your provider uses scopes instead of roles (e.g. Okta, Auth0 M2M),
> set `QUOIN_OAUTH_ROLES_CLAIM=scope`. The validator handles both array
> (`["users.read"]`) and space-separated string (`"users.read users.write"`)
> formats automatically.

> [!TIP]
> The local `mock-oauth2-server` places roles in the `aud` claim, so the
> development `.env` uses `QUOIN_OAUTH_ROLES_CLAIM=aud`. Production IdPs
> (Azure AD, Auth0, Keycloak) use `roles` — the default value.

---

## Protecting Routes

Routes declare their own required roles explicitly using `require_roles()`.
There is no implicit baseline — every route self-documents its access
requirement.

### General Usage

```python
from typing import Annotated
from fastapi import APIRouter, Depends
from app.core.security import ServicePrincipal, require_roles

router = APIRouter()

# Read — any caller with users.read OR api.superuser
@router.get("/")
async def list_users(
    caller: Annotated[ServicePrincipal, Depends(require_roles("users.read"))]
): ...

# Write — any caller with users.write OR api.superuser
@router.post("/")
async def create_user(
    caller: Annotated[ServicePrincipal, Depends(require_roles("users.write"))]
): ...
```

### Accessing the caller identity

The `ServicePrincipal` object is safely extracted and available in any
protected route:

```python
class ServicePrincipal(BaseModel):
    subject: str         # JWT `sub` claim — stable service identifier
    roles: list[str]     # App roles from the token
    claims: dict         # Full decoded JWT payload (for advanced use)
```

Use `caller.subject` in structured logs for deep audit trails:

```python
logger.info(
    "resource.deleted",
    actor=caller.subject,
    resource_id=resource_id,
)
```

---

## Dependency Graph

```
HTTPBearer()
    └── get_token_claims()        # Validates JWT, returns raw claims
            └── get_current_caller()  # Parses ServicePrincipal (no role check)
                    └── require_roles("users.read")   # Domain checks
```

---

## OAuth 2.1 Compatibility

QuoinAPI is compatible with both OAuth 2.0 and OAuth 2.1 for
service-to-service calls. The Client Credentials grant is **unchanged**
between the two specifications.

The key differences in OAuth 2.1 (implicit grant removal, PKCE requirement,
refresh token rotation) apply to **authorization servers** — not resource
servers like QuoinAPI. Your token validation code does not change.

---

## Local Testing & Tokens

For testing and rapid development locally, QuoinAPI leverages two frameworks flawlessly.

### Layer 1 — The `mock-oauth2-server` stack

The integration testing layer. `mock-oauth2-server` runs as a Docker service
alongside the database, issuing real RS256 JWTs from a real JWKS endpoint.

```bash
just dev   # Starts DB + mock OAuth server + API natively
```

The script `scripts/gen_token.py` (wired simply as `just token`) allows you to generate completely signed and valid tokens bypassing real SSO networks instantly.

**Testing Everything Instantly (The Bypass Token)**:
Because QuoinAPI supports the `api.superuser` bypass flag natively in the `require_roles` validator, you can test every single endpoint seamlessly simply by requesting one token:

```bash
# Generate a master bypass token
just token roles="api.superuser"
```

**Testing Explicit Constraints**:
If you want to ensure your `users.read` role is getting blocked on the `/delete` endpoints appropriately:

```bash
# 1. Get a standard token strictly limited to `users.read`
TOKEN=$(just token roles="users.read")

# 2. Call a protected Read endpoint (e.g. fetching users) -> 200 OK
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/users/

# 3. Attempt to mutate (which requires `users.write`) -> 403 Forbidden
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"email":"bad@caller.com", "full_name": "Eve"}' \
  http://localhost:8000/api/v1/users/
```

### Layer 2 — `dependency_overrides` natively in tests

The unit/fast testing layer used by the automated test suite. No containers,
no tokens, instant evaluating. Pytest scripts inject a pre-built `ServicePrincipal`
directly via standard FastAPI dependency injection mocks:

```python
# tests/conftest.py — shared fixtures (already configured)
@pytest.fixture
def caller_read() -> ServicePrincipal:
    return ServicePrincipal(
        subject="test-service-read",
        roles=["users.read"],
        claims={},
    )
```

Use in tests:

```python
async def test_get_resource(read_client: AsyncClient) -> None:
    response = await read_client.get("/api/v1/users/")
    assert response.status_code == 200
```

---

## Error Responses

| Status | When | Response |
| :--- | :--- | :--- |
| `401 Unauthorized` | No token, expired token, invalid signature | `{"detail": "Unauthorized"}` |
| `403 Forbidden` | Valid token, but missing required role | `{"detail": "Forbidden"}` |

The `401` response includes a `WWW-Authenticate: Bearer` header per RFC 6750.

---

## See Also

- [Configuration Guide](configuration.md)
- [Error Handling Guide](error-handling.md)
- [app/core/security.py](https://github.com/balakmran/quoin-api/blob/main/app/core/security.py)
