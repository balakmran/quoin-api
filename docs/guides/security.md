# Security

QuoinAPI ships several middleware layers that cover the most common
production security hardening steps out of the box. All of them are
configurable via `QUOIN_*` environment variables and safe to run in
development with their default values.

---

## CORS Hardening

Cross-Origin Resource Sharing is controlled by `CORSMiddleware`,
configured in `app/core/middlewares.py`.

### Configuration

| Variable | Default | Notes |
| :--- | :--- | :--- |
| `QUOIN_BACKEND_CORS_ORIGINS` | `["http://localhost:3000", "http://localhost:8000"]` | Empty list disables CORS entirely |
| `QUOIN_BACKEND_CORS_ALLOW_METHODS` | `["GET","POST","PUT","PATCH","DELETE","OPTIONS"]` | |
| `QUOIN_BACKEND_CORS_ALLOW_HEADERS` | `["Authorization","Content-Type","X-Request-ID"]` | |
| `QUOIN_BACKEND_CORS_ALLOW_CREDENTIALS` | `true` | See warning below |

### Wildcard footgun protection

Browsers silently refuse credentialed CORS responses when the server
responds with `Access-Control-Allow-Methods: *` or
`Access-Control-Allow-Headers: *`. QuoinAPI detects this at startup and
**raises a `RuntimeError`** if you combine wildcards with
`allow_credentials=True` outside `development`:

```
RuntimeError: CORS misconfiguration: allow_credentials=True with wildcard
allow_methods/allow_headers is rejected outside development.
```

This is intentional — a silent browser refusal is harder to debug than
a startup crash.

In development the guard is skipped so you can use loose settings
during local work.

### Production example

```bash
# .env.production
QUOIN_BACKEND_CORS_ORIGINS=["https://app.example.com"]
QUOIN_BACKEND_CORS_ALLOW_METHODS=["GET","POST","PUT","DELETE","OPTIONS"]
QUOIN_BACKEND_CORS_ALLOW_HEADERS=["Authorization","Content-Type"]
QUOIN_BACKEND_CORS_ALLOW_CREDENTIALS=true
```

---

## Security Headers

`SecurityHeadersMiddleware` adds a standard set of defensive response
headers. It is enabled by default and runs on every HTTP response.

Toggle via `QUOIN_SECURITY_HEADERS_ENABLED=false` if your reverse proxy
(NGINX, Caddy, Cloudflare) manages headers instead.

### Headers emitted

| Header | Default value | Purpose |
| :--- | :--- | :--- |
| `X-Content-Type-Options` | `nosniff` | Prevents MIME-type sniffing |
| `X-Frame-Options` | `DENY` | Blocks framing / clickjacking |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Limits referrer leakage |
| `Permissions-Policy` | `geolocation=(), camera=(), microphone=()` | Disables unused browser APIs |
| `Content-Security-Policy` | See below | Restricts resource loading |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | Forces HTTPS (browsers only honour over HTTPS) |

### Content-Security-Policy

The default CSP accommodates the built-in homepage (Google Fonts,
simpleicons CDN, and inline styles/scripts):

```
default-src 'self';
style-src  'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net;
font-src   'self' https://fonts.gstatic.com;
img-src    'self' https://cdn.simpleicons.org https://fastapi.tiangolo.com;
script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net;
frame-ancestors 'none';
base-uri 'self'
```

The default covers two built-in UIs:

- **Homepage** — Google Fonts (`fonts.googleapis.com` / `fonts.gstatic.com`)
  and tech-logo icons (`cdn.simpleicons.org`).
- **Swagger UI** (`/docs`) — FastAPI loads its UI assets and favicon from
  `cdn.jsdelivr.net` and `fastapi.tiangolo.com`.

!!! note "unsafe-inline"
    Both `style-src` and `script-src` include `'unsafe-inline'` because
    the homepage uses inline `<style>` and `<script>` blocks. Moving those
    to static files would let you drop `'unsafe-inline'` for a stricter
    policy.

Override it for your own frontend:

```bash
QUOIN_SECURITY_CSP=default-src 'self'; img-src 'self' data:; \
  frame-ancestors 'none'; base-uri 'self'
```

### HSTS tuning

HSTS is emitted by default. Browsers only honour it over HTTPS — over
HTTP it is silently ignored. Set `max-age=0` to suppress the header
entirely (e.g. behind a TLS-terminating proxy that sets it itself):

```bash
QUOIN_SECURITY_HSTS_MAX_AGE=0
```

Enable the `preload` directive only once your domain is submitted to
the HSTS preload list — it is hard to reverse:

```bash
QUOIN_SECURITY_HSTS_PRELOAD=true
```

---

## Request Size Limit

`RequestSizeLimitMiddleware` rejects requests whose `Content-Length`
exceeds the configured cap before the route handler reads the body. It
returns a `413 Content Too Large` RFC 9457 Problem Details response:

```json
{
  "type": "urn:quoin:error:payload_too_large",
  "title": "Content Too Large",
  "status": 413,
  "detail": "Request body exceeds 1048576 bytes",
  "instance": "/api/v1/users"
}
```

| Variable | Default | Notes |
| :--- | :--- | :--- |
| `QUOIN_MAX_REQUEST_BODY_BYTES` | `1048576` (1 MiB) | `<=0` disables the cap |

### Tuning for file uploads

If a route accepts file uploads, raise the cap or disable it for that
deployment:

```bash
# Allow up to 10 MiB globally
QUOIN_MAX_REQUEST_BODY_BYTES=10485760
```

!!! note "Chunked transfers"
    The middleware only checks the advertised `Content-Length`.
    Conforming HTTP clients always send it. The underlying uvicorn/h11
    layer caps raw protocol buffers for the rare chunked case.

---

## Request ID validation

`RequestIDMiddleware` propagates an inbound `X-Request-ID` into the log
context and echoes it in the response. To stop a client from injecting
newlines or control characters into logs (log injection) or reflecting
attacker-controlled content in the response header, the inbound value is
accepted only if it matches `^[A-Za-z0-9._-]{1,64}$`. Anything longer or
containing other characters is discarded and a fresh UUID is generated
instead.

---

## OAuth trust anchors & fail-fast

Token validation (see the [Authentication guide](authentication.md))
requires **all three** trust anchors — `QUOIN_OAUTH_JWKS_URI`,
`QUOIN_OAUTH_ISSUER`, and `QUOIN_OAUTH_AUDIENCE`. Issuer is enforced
explicitly: PyJWT silently skips `iss` verification when the expected
issuer is `None`, so an unset issuer would let any token signed by a
JWKS key through regardless of `iss`.

In `production` these are validated at **app startup**
(`validate_production_oauth()` is called from `create_app()`), and the
JWKS URI must be `https://` — an `http://` endpoint would let an
on-path attacker substitute signing keys. A misconfigured production
deployment therefore crash-loops rather than serving 401s while
appearing healthy. The check lives in `create_app()` rather than on
config import so data-plane tooling that only imports settings —
Alembic migrations, scripts — stays decoupled from OAuth. Development
and test skip the check.

### JWKS refresh backoff

A token carrying an unknown `kid` normally triggers a JWKS refetch to
pick up rotated keys. Left unbounded, an attacker spraying garbage-`kid`
tokens could force an outbound HTTP call on every request. `JWKSCache`
caps unknown-`kid` refetches to at most one per
`QUOIN_OAUTH_JWKS_MIN_REFRESH_SECONDS` (default `30`), and the backoff
timer is set before the fetch so a *failed* fetch backs off too. Tokens
inside the window are rejected from cache with no outbound call.

The refresh itself goes through the shared
[resilient HTTP client](outbound-http.md) — retries with backoff, a
per-host circuit breaker, and the shared `QUOIN_HTTP_TIMEOUT_SECONDS` —
rather than a bare per-refresh client. A hard-down authorization server
therefore trips the breaker and fails fast instead of serialising every
auth attempt behind a doomed fetch. A transport-level JWKS failure (a
down IdP, a timeout, or an open circuit) surfaces as a `502`/`503`/`504`
rather than a mislabeled `401`, since the outage is our upstream
failing and not the caller's token; a genuine JWKS HTTP error response
(such as a `404`) still maps to `401`.

---

## Database credential redaction

`QUOIN_POSTGRES_PASSWORD` is a `SecretStr`, and the assembled
`DATABASE_URL` is a plain `@property` (not a `@computed_field`), so
neither the password nor the credential-bearing URL is emitted by
`settings.model_dump()`, the OpenAPI schema, or a future config-dump
endpoint.

---

## Middleware ordering

Middleware is registered in LIFO order via `add_middleware`, so the
execution order from outermost to innermost is:

```
SecurityHeadersMiddleware  ← outermost: every response gets these headers
RequestIDMiddleware
TrustedHostMiddleware      ← validates Host before CORS can short-circuit
CORSMiddleware
TimeoutMiddleware          ← reject oversize before the timeout clock ticks
RequestSizeLimitMiddleware
InFlightRequestMiddleware  ← innermost, closest to the router
```

SecurityHeaders and RequestID sit outermost so that error responses
manufactured by inner layers — 504s from `TimeoutMiddleware`, 413s from
`RequestSizeLimitMiddleware`, 400s from `TrustedHostMiddleware` — still
bubble back through them and carry security headers and an
`X-Request-ID` echo instead of arriving at the client bare.

`TrustedHostMiddleware` sits outside `CORSMiddleware` deliberately:
Starlette's `CORSMiddleware` answers a CORS preflight (`OPTIONS`)
request itself, without ever calling the wrapped app. If CORS were
outer, a forged `Host` header on a preflight request would never reach
`TrustedHostMiddleware` at all. With `TrustedHostMiddleware` outer,
Host validation applies to every request, preflight included; a
rejected (400) request never reaches CORS and so doesn't carry CORS
headers, but it does get the outer SecurityHeaders/RequestID treatment.
`CORSMiddleware` still wraps `TimeoutMiddleware`/`RequestSizeLimitMiddleware`,
so their 504/413 responses do carry CORS headers.

---

## See Also

- [Configuration reference](configuration.md) — all `QUOIN_SECURITY_*` variables
- [Dependency Scanning](dependency-scanning.md) — Dependabot + secret scanning
- [Deployment guide](deployment.md) — production environment setup
- [`app/core/middlewares.py`](../../app/core/middlewares.py) — implementation
