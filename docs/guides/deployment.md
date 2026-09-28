# Deployment

Build one image, give it production settings, run migrations as a
separate job, and put it behind a proxy that rate-limits. This page
covers each step and how the app drains on shutdown.

## Local Docker Stack

`just up` builds the image and starts the app, Postgres, and the mock
OAuth server; `just down` stops them. The app is at
[http://localhost:8000](http://localhost:8000) (or
`http://api.quoin-api.orb.local` under OrbStack).

!!! warning "Compose is a development stack"
    It runs `fastapi dev` with the source mounted, and sets
    `QUOIN_OAUTH_ROLES_CLAIM=aud` and
    `QUOIN_OAUTH_SUPERUSER_ENABLED=true` for the mock OAuth server.
    Don't deploy it; production must not inherit those values.

## Production Image

```bash
docker build -t quoin-api:latest .
```

The [`Dockerfile`](https://github.com/balakmran/quoin-api/blob/main/Dockerfile)
is a two-stage build: `uv sync --no-dev --frozen` in a builder, then a
slim final image with the virtualenv, `app/`, and the Alembic files. It
runs as the non-root `appuser` (uid 1001), starts with `fastapi run`, and
has a `HEALTHCHECK` that polls `/health`.

The image ships no `.env`; settings come from the container
environment:

```bash
docker run -d --name quoin-api -p 8000:8000 \
  --env-file production.env quoin-api:latest
```

**Apply migrations before the new version takes traffic.** The image
doesn't run them on start; run them as a one-off job, as described in
[Database Migrations](database-migrations.md#production-deployments).

## Environment Variables

Every setting is listed in the [Configuration guide](configuration.md).
The production essentials:

```bash
QUOIN_ENV=production
QUOIN_ALLOWED_HOSTS=["api.example.com"]   # required; default is rejected
QUOIN_BACKEND_CORS_ORIGINS=["https://app.example.com"]

# OAuth trust anchors: all three required; the JWKS URI must be https
QUOIN_OAUTH_JWKS_URI=https://idp.example.com/.well-known/jwks.json
QUOIN_OAUTH_ISSUER=https://idp.example.com/
QUOIN_OAUTH_AUDIENCE=api://your-api

QUOIN_POSTGRES_HOST=db
QUOIN_POSTGRES_USER=postgres
QUOIN_POSTGRES_PASSWORD=<strong-password>
QUOIN_POSTGRES_DB=app_db
```

If `QUOIN_ALLOWED_HOSTS` or a trust anchor is missing, the app exits at
startup naming it. See
[Security](security.md#what-else-production-refuses-to-boot-without).

**Don't start from `.env.example`.** Two of its values exist only for
the mock OAuth server. Leave both unset in production so the defaults
apply:

| Setting | Development | Production default |
| :--- | :--- | :--- |
| `QUOIN_OAUTH_ROLES_CLAIM` | `aud` (where the mock puts roles) | `roles` |
| `QUOIN_OAUTH_SUPERUSER_ENABLED` | `true` (one token for every endpoint) | `false` |

A production boot with the bypass on logs
`production_superuser_bypass_enabled`.

## Behind a load balancer or reverse proxy

Behind a proxy, the TCP peer is the proxy, so the real client IP,
scheme, and host arrive in `X-Forwarded-*` headers, which any client can
forge. Trust them **only from the proxy**. It's off by default; turn it
on with uvicorn's `--proxy-headers` and scope it with
`FORWARDED_ALLOW_IPS`:

```bash
docker run -d --name quoin-api -p 8000:8000 \
  -e FORWARDED_ALLOW_IPS=10.0.0.0/8 \
  quoin-api:latest \
  fastapi run app/main.py --host 0.0.0.0 --port 8000 --proxy-headers
```

Never set `FORWARDED_ALLOW_IPS=*` on a socket the internet can reach;
any caller could then spoof their IP in your logs. If TLS ends at the
proxy, make it send `X-Forwarded-Proto: https`.

## Health Checks

| Endpoint | Returns 200 when | Returns 503 when |
| :--- | :--- | :--- |
| `/health` | The process is up: `{"status": "healthy"}` | — |
| `/ready` | The database answers: `{"status": "ready"}` | The database is down, or shutdown has begun |

Point liveness probes at `/health` and readiness probes at `/ready`.

!!! warning "Keep probes off the public internet"
    `/ready` runs an unauthenticated `SELECT 1` on every hit. Exposed
    publicly, that's free database load for anyone. Restrict both
    probes to the internal network.

## Edge rate limiting

QuoinAPI has no in-process rate limiter. It assumes your API gateway,
ingress, CDN, or WAF limits requests, which is more robust and
consistent across replicas than a per-process counter. Without one, the
API has no protection against request floods.

## Graceful Shutdown

On shutdown the lifespan handler:

1. flips `/ready` to **503**, so load balancers stop sending traffic;
2. waits for in-flight requests to finish, up to
   `QUOIN_SHUTDOWN_DRAIN_TIMEOUT` (default `30.0`; `0` or less skips it),
   logging `shutdown_drained` or `shutdown_drain_timeout`;
3. disposes the database engine, only after the drain.

`InFlightRequestMiddleware` counts requests, skipping the probe paths.
WebSockets aren't counted or drained.

`fastapi run` (uvicorn) already waits for open connections before the
lifespan shutdown, so this drain is mostly a safety net. It still gives
the same behaviour under any ASGI server, one timeout setting, and the
readiness flip that actually takes the instance out of rotation.

### Kubernetes wiring

- Set `terminationGracePeriodSeconds` to at least
  `QUOIN_SHUTDOWN_DRAIN_TIMEOUT` plus the readiness probe's reaction
  time. With default probes (every 10s, 3 failures), traffic can arrive
  for about 30s after `/ready` starts failing.
- Keep uvicorn's `--timeout-graceful-shutdown` at least
  `QUOIN_SHUTDOWN_DRAIN_TIMEOUT`. If it's shorter, uvicorn cancels the
  requests first and the drain reports success over requests that were
  killed.

## See Also

- [Database Migrations](database-migrations.md) — rolling out schema
  changes without downtime
- [Security](security.md) — what production refuses to boot without
- [Observability](observability.md) — logs and traces in production
