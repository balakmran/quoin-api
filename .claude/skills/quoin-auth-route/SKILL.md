---
name: quoin-auth-route
description: Use this skill whenever the user wants to add authentication or role-based access control to a QuoinAPI endpoint, change which roles are required for an endpoint, protect a new route, expose a route as public, or generally touch the auth surface of routes in `app/modules/*/routes.py`. Triggers include phrases like "protect this endpoint", "add RBAC", "require the X role", "this endpoint should be admin-only", "let read-only users hit this", "make this route public", "who is the caller in this endpoint", or any request that implies a `require_roles(...)` change. Do NOT use for: changing the authentication mechanism itself (JWKS, token validation), adding new core security primitives (`app/core/security.py`), or OAuth provider configuration.
---

# Adding RBAC to a QuoinAPI Route

QuoinAPI uses **DDD-scoped role strings** (`<domain>.<action>`, e.g. `users.read`, `users.write`) declared per route via the `require_roles()` dependency. There is no global "admin" role and no role hierarchy — `users.write` does not imply `users.read`. The long-form reference is [docs/guides/authentication.md](../../../docs/guides/authentication.md); this skill is the in-the-moment cheat sheet. The reference module to mirror is [app/modules/user/routes.py](../../../app/modules/user/routes.py).

## The pattern

Every protected route looks like this:

```python
from typing import Annotated
from fastapi import Depends
from app.core.security import ServicePrincipal, require_roles

@router.post("/")
async def create_thing(
    payload: ThingCreate,
    service: Annotated[ThingService, Depends(get_thing_service)],
    caller: Annotated[ServicePrincipal, Depends(require_roles("things.write"))],
) -> Thing:
    ...
```

Three things to notice:

1. **`require_roles("things.write")`** is the only thing that protects the route. No middleware, no decorator, no class-based auth — it's all explicit per route.
2. **`caller: ServicePrincipal`** is the resolved identity (`subject`, `roles`, `claims`). Pass it to the service if business logic needs to know *who* is acting (e.g. to record `created_by`). If the service doesn't need it, you can drop the `caller` parameter — `require_roles` still runs as a side-effect dependency, but it's clearer to keep it visible.
3. **`Annotated[X, Depends(...)]`** is the project's chosen syntax — match it for consistency with the user module.

## Choosing the role string

Roles follow `<domain>.<action>`:

- Domain matches the module name in plural form: `users`, `products`, `orders`.
- Action is one of: `read`, `write`, `delete` (or other verbs if the domain has a meaningful one — e.g. `payments.refund`).
- **Read and write are not hierarchical.** A caller with `users.write` cannot read users unless they also have `users.read`. If an endpoint conceptually requires both (e.g. PUT that returns the updated record), require both: `require_roles("users.read", "users.write")`.

The bypass: any caller with `api.superuser` in their roles passes every `require_roles()` check. This is for local dev convenience and break-glass, not for production traffic — don't hand out `api.superuser` casually.

## The `responses=` block on the router or route

The user module's `APIRouter` declares `401`, `403`, `500` at the router level (so every route inherits them) and per-route extras like `409`. Mirror this — it's how OpenAPI ends up accurate:

```python
router = APIRouter(
    prefix="/things",
    tags=[APITag.things],  # add to app/core/openapi.py if new
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized — missing or invalid token"},
        403: {"model": ErrorResponse, "description": "Forbidden — token lacks the required scope"},
        500: {"model": ErrorResponse, "description": "Internal Server Error"},
    },
)
```

## Public (unauthenticated) routes

Health checks, the root page, and similar routes live in `app/modules/system/` and simply omit the `require_roles` dependency. If you're adding a public endpoint, ask first whether it really should be public — the project's stance is "auth by default, public by exception."

## Testing the new auth

Use the pre-built fixtures from `tests/conftest.py`:

| Fixture | Token has roles |
|---|---|
| `client` | none (unauthenticated) |
| `read_client` | `users.read` |
| `admin_client` | `users.read` + `users.write` |
| `caller_read` / `caller_admin` | the matching `ServicePrincipal` |

For each new protected route, write at least three tests:
1. **Happy path** — call with a client whose roles satisfy the requirement; expect 2xx.
2. **Forbidden** — call with a client whose roles don't satisfy the requirement; expect 403.
3. **Unauthenticated** — call with the bare `client`; expect 401.

If you add a new domain (e.g. `things`), the existing `caller_read` / `caller_admin` fixtures only carry `users.*` roles. Add module-specific caller fixtures to your test file rather than mutating the shared ones — see the `quoin-write-tests` skill for the pattern.

## Things that bite

- **Forgetting `require_roles()` entirely.** The route compiles, runs, and returns 200 to anyone. There is no "default-deny" for routes — auth is opt-in. Always declare it explicitly.
- **Listing roles as a single string.** `require_roles("users.read users.write")` is one bizarre role name, not two. Pass them as separate args: `require_roles("users.read", "users.write")`.
- **Coupling business logic to roles.** Don't write `if "api.superuser" in caller.roles: ...` in a service — that re-implements RBAC outside the dependency system and gets out of sync. If the service needs different behavior per role, take that as a signal to split the route or push the decision back to `require_roles`.
