# Deployment

This guide covers how to deploy the QuoinAPI application using Docker.

## Docker Deployment

The project includes a production-ready `Dockerfile` and `docker-compose.yml`
for containerized deployment.

---

## Local Docker Development

Run the entire stack (Application + PostgreSQL Database) locally using Docker
Compose:

```bash
just up
```

This command:

- Builds the application Docker image
- Starts PostgreSQL container
- Starts the application container
- Configures networking between containers

Access the application at [http://localhost:8000](http://localhost:8000) (or via `http://api.quoin-api.orb.local` if using OrbStack).

### Stop Containers

To stop and remove all containers:

```bash
just down
```

---

## Production Deployment

### Building the Production Image

Build the Docker image manually for production:

```bash
docker build -t quoin-api:latest .
```

The `Dockerfile` uses a **multi-stage build**:

```dockerfile
# Stage 1: Builder — install dependencies only
FROM python:3.14-slim-bookworm AS builder
# uv pinned by version tag AND manifest digest for reproducible builds
COPY --from=ghcr.io/astral-sh/uv:0.11.26@sha256:3d868e... /uv /bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock* README.md ./
RUN uv sync --no-dev --frozen

# Stage 2: Final — lean production image
FROM python:3.14-slim-bookworm
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini .
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"
# Non-root user for security
RUN addgroup --system --gid 1001 quoin && \
    adduser --system --uid 1001 --ingroup quoin quoin
RUN chown -R quoin:quoin /app
USER quoin
# Liveness probe hitting /health via the stdlib (no curl in slim)
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=2).status == 200 else 1)"]
CMD ["fastapi", "run", "app/main.py", "--host", "0.0.0.0", "--port", "8000"]
```

The `HEALTHCHECK` lets Docker/Compose report container health (and
orchestrators gate traffic on it). Inspect it with:

```bash
docker inspect --format '{{.State.Health.Status}}' quoin-api
```

### Running in Production

**With Docker Compose:**

```bash
docker-compose up -d
```

**With Docker CLI:**

```bash
# Run PostgreSQL
docker run -d \
  --name postgres \
  -e QUOIN_POSTGRES_USER=postgres \
  -e QUOIN_POSTGRES_PASSWORD=postgres \
  -e QUOIN_POSTGRES_DB=app_db \
  -p 5432:5432 \
  postgres:17-alpine

# Run Application
docker run -d \
  --name quoin-api \
  --link postgres:db \
  -p 8000:8000 \
  -e QUOIN_POSTGRES_HOST=db \
  quoin-api:latest
```

---

## Behind a load balancer or reverse proxy

When the service runs behind a load balancer, ingress, or reverse proxy
(the usual production topology), the TCP peer is the proxy, not the
client. To recover the real client IP, scheme, and host, the app must
trust the `X-Forwarded-*` / `Forwarded` headers the proxy sets — but
**only from the proxy**, because any client can forge those headers.

Proxy-header trust is therefore **off by default**. Enable it
explicitly for the deployment, scoping trust to the proxy's address:

```bash
# Trust forwarded headers only from the proxy's IP(s). Never use "*"
# unless the app is unreachable except through the proxy.
docker run -d \
  --name quoin-api \
  -p 8000:8000 \
  -e FORWARDED_ALLOW_IPS=10.0.0.0/8 \
  quoin-api:latest \
  fastapi run app/main.py --host 0.0.0.0 --port 8000 --proxy-headers
```

- `--proxy-headers` tells the underlying uvicorn server to honour the
  forwarded headers.
- `FORWARDED_ALLOW_IPS` (a uvicorn environment variable) restricts
  which source addresses are trusted; set it to the proxy's IP or CIDR,
  never a blanket `*` on an internet-reachable socket — that lets any
  caller spoof their apparent client IP (and thus your access logs and
  any IP-based logic).

If you terminate TLS at the edge, also ensure the proxy forwards
`X-Forwarded-Proto: https` so the app builds correct absolute URLs.

---

## Environment Variables

Configure the application using environment variables. See
[Configuration Guide](configuration.md) for all available options.

**Production Essentials:**

```bash
# Application
QUOIN_ENV=production
QUOIN_OTEL_ENABLED=true

# Database
QUOIN_POSTGRES_HOST=db
QUOIN_POSTGRES_PORT=5432
QUOIN_POSTGRES_USER=postgres
QUOIN_POSTGRES_PASSWORD=<strong-password>
QUOIN_POSTGRES_DB=app_db
```

> **Security Warning**: Never commit `.env` files with production credentials to
> version control!

---

## Health Checks

The application includes dedicated endpoints for health and readiness monitoring:

### Health Probe

The `/health` endpoint checks if the application process is running:

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{
  "status": "healthy"
}
```

### Readiness Probe

The `/ready` endpoint checks if the application is ready to accept traffic (e.g., database is connected):

```bash
curl http://localhost:8000/ready
```

Expected response (HTTP 200 OK):

```json
{
  "status": "ready"
}
```

It returns an HTTP 503 error if the database is unavailable, or once
graceful shutdown has begun (see below) so orchestrators stop routing
new traffic to the draining instance.

Use these endpoints for:

- **Docker health checks** - the image ships a `HEALTHCHECK` directive
  that polls `/health` (see the Dockerfile above)
- **Load balancer probes** - Kubernetes liveness/readiness
- **Monitoring systems** - Uptime tracking

!!! warning "Keep probes off the public internet"
    `/ready` runs an unauthenticated `SELECT 1` against the database on
    every hit. That is harmless from an in-cluster orchestrator, but if
    the endpoint is internet-routable it becomes a free DB-load
    amplification lever. Restrict `/health` and `/ready` to the internal
    network (ingress allowlist, separate probe port, or a
    `NetworkPolicy`) rather than exposing them publicly.

---

## Edge rate limiting

QuoinAPI does **not** ship an in-process rate limiter — the template
*assumes rate limiting is enforced at the edge* (API gateway, ingress,
CDN, or WAF) in front of the service. Budget for this in your
deployment: without an upstream limiter, the API has no protection
against request floods. This is a deliberate design choice — edge
limiting is more robust and horizontally consistent than a per-process
counter.

---

## Graceful Shutdown

On shutdown the application drains in-flight requests before releasing
resources. The sequence in the lifespan handler is:

1. The readiness probe flips to **503** (`is_shutting_down`), so load
   balancers and Kubernetes stop routing new traffic to the instance.
2. In-flight requests are awaited until the in-flight counter reaches
   zero, bounded by `QUOIN_SHUTDOWN_DRAIN_TIMEOUT` (default `30.0`
   seconds; `<=0` skips the wait). A clean drain logs `shutdown_drained`;
   a timeout logs `shutdown_drain_timeout` with the residual count.
3. The database engine is disposed — only after the drain — so no
   in-flight request loses its connection mid-query.

The in-flight gauge is maintained by `InFlightRequestMiddleware`, which
brackets every HTTP request that reaches a handler. The `/health` and
`/ready` probe paths are excluded so orchestrator polling never keeps
the gauge from reaching zero. WebSocket connections are outside the
gauge and are not drained.

### Relationship to the uvicorn server

The server matters here. `fastapi run` (uvicorn) **already drains
connection-level in-flight requests before it runs the lifespan
shutdown**: on `SIGTERM` it stops accepting new connections, waits for
open connections to finish their responses (bounded by
`--timeout-graceful-shutdown`), and only then triggers the lifespan
shutdown where the steps above execute. In that default setup the
application-level drain is largely a **safety net** rather than the
primary drain mechanism.

The application-level drain still earns its place:

- **Server-agnostic behaviour** — the same drain semantics hold under
  uvicorn, Gunicorn with uvicorn workers, Hypercorn, or any ASGI
  server, without per-launcher graceful-timeout flags.
- **Safe engine disposal ordering** — the engine is guaranteed disposed
  *after* in-flight work completes, so a request never has its database
  connection torn out from under it.
- **A single, app-controlled timeout** — `QUOIN_SHUTDOWN_DRAIN_TIMEOUT`
  is the one knob, with structured `shutdown_drained` /
  `shutdown_drain_timeout` logs for observability.
- **Explicit readiness signalling** — the 503 flip is what actually
  removes the instance from a load balancer's rotation; uvicorn's
  connection drain does not change what `/ready` reports.

### Kubernetes wiring

For zero-downtime rollouts, give the orchestrator room to react to the
readiness flip and the drain:

- Set `terminationGracePeriodSeconds` greater than or equal to
  `QUOIN_SHUTDOWN_DRAIN_TIMEOUT` so the pod is not force-killed
  mid-drain.
- Keep the server's `--timeout-graceful-shutdown` greater than or equal
  to `QUOIN_SHUTDOWN_DRAIN_TIMEOUT`. If it is shorter, uvicorn cancels
  in-flight tasks before the lifespan drain runs; cancellation still
  releases the in-flight counter (via the `finally` in
  `InFlightRequestMiddleware`), so the drain reports immediate success —
  but those requests were terminated, not gracefully finished.
- Point the readiness probe at `/ready`; once it returns 503 the
  Endpoints controller removes the pod from Service rotation. Readiness
  probes poll at `periodSeconds` and need `failureThreshold` consecutive
  failures first, so with the Kubernetes defaults (10s x 3) new traffic
  can still arrive for up to ~30s after `/ready` begins failing. Size
  `terminationGracePeriodSeconds` to cover both this probe delay and the
  drain timeout.

---

## See Also

- [Release Workflow](release-workflow.md) — Version management and tagging
- [Observability](observability.md) — Setting up logs and traces
- [Troubleshooting](troubleshooting.md) — Common deployment issues
- [Dockerfile](https://github.com/balakmran/quoin-api/blob/main/Dockerfile) — Production image configuration
