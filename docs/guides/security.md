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
| `QUOIN_BACKEND_CORS_ALLOW_HEADERS` | `["Authorization","Content-Type"]` | The request-ID header is always added |
| `QUOIN_BACKEND_CORS_EXPOSE_HEADERS` | `["Deprecation","Sunset","Link"]` | The request-ID header is always added |
| `QUOIN_BACKEND_CORS_ALLOW_CREDENTIALS` | `true` | See warning below |

### Headers a browser can read

A cross-origin script sees only the CORS-safelisted response headers
unless the server exposes more. The API exposes the request-ID header
(`QUOIN_REQUEST_ID_HEADER`, `X-Request-ID` by default), so a front end
can quote it in a bug report. It also exposes the `Deprecation`,
`Sunset`, and `Link` headers that
[deprecated endpoints](deprecating-endpoints.md) set, so their clients can see
the warning.

The request-ID header is added to both the allowed and exposed lists
from `QUOIN_REQUEST_ID_HEADER` itself. Renaming it, for example to
`X-Correlation-ID`, needs no CORS change. Add your own response headers
to `QUOIN_BACKEND_CORS_EXPOSE_HEADERS`.

### Wildcard footgun protection

Browsers silently refuse credentialed CORS responses when the server
responds with `Access-Control-Allow-Methods: *` or
`Access-Control-Allow-Headers: *`. They also ignore
`Access-Control-Expose-Headers: *` for credentialed requests. A `*` in
`QUOIN_BACKEND_CORS_ORIGINS` is worse: Starlette answers it with
credentials by reflecting whatever `Origin` the caller sent, so every
site becomes a trusted origin. QuoinAPI detects all four at startup and
**raises a `RuntimeError`** if you combine a wildcard with
`allow_credentials=True` outside `development`:

```
RuntimeError: CORS misconfiguration: allow_credentials=True with a wildcard
in origins, allow_methods, allow_headers, or expose_headers is rejected
outside development.
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

The default CSP (`QUOIN_SECURITY_CSP`) allows only same-origin
resources and no third-party host:

```
default-src 'self';
script-src 'self';
frame-ancestors 'none';
base-uri 'self'
```

Three built-in pages need more, and each gets a policy scoped to its
exact path rather than widening the default for every route:

- **Homepage** (`/`, `QUOIN_SECURITY_CSP_HOME`) — Google Fonts
  (`fonts.googleapis.com` / `fonts.gstatic.com`), tech-logo icons
  (`cdn.simpleicons.org`), and one inline `<style>` block. Its
  behaviour lives in `app/static/js/home.js`, not in an inline
  `<script>` or an `onclick`-style attribute; `script-src` without
  `'unsafe-inline'` blocks both. The Swagger link is omitted when docs
  are disabled, and Swagger's `/docs/oauth2-redirect` page is not
  registered.
- **Swagger UI** (`/docs`) and **ReDoc** (`/redoc`) — FastAPI loads
  their UI assets and favicon from `cdn.jsdelivr.net` and
  `fastapi.tiangolo.com`, and each needs a directive no other page
  does; see below.

### The doc-UI exceptions

`script-src` deliberately omits `'unsafe-inline'` — it is the directive
scanners flag first, and nothing the template *serves* needs it. The two
built-in doc UIs are the exceptions, and each gets its own policy rather
than loosening the default for every route:

| Path | Setting | Needs | Why |
| :--- | :--- | :--- | :--- |
| `/docs` | `QUOIN_SECURITY_CSP_DOCS` | `script-src 'unsafe-inline'`, `img-src data:` | FastAPI generates an inline `<script>` that bootstraps `SwaggerUIBundle`; toolbar icons are `data:` URIs |
| `/redoc` | `QUOIN_SECURITY_CSP_REDOC` | `img-src data: https://cdn.redoc.ly`, `worker-src blob:` | Anchor icons are `data:` URIs, the "powered by" logo comes from ReDoc's CDN, and the search index is built in a `blob:` worker |

`SecurityHeadersMiddleware` scopes each to its exact path; every other
route — your own included — gets the strict default. In `production`
neither docs route is registered, so neither relaxed policy is ever
emitted there.

!!! warning "worker-src falls back to script-src"
    A `blob:` worker is checked against `worker-src`, and when that
    directive is *absent* the browser falls back to `script-src` —
    where neither `'self'` nor `'unsafe-inline'` covers a `blob:` URL.
    That is why the ReDoc policy names `worker-src` explicitly. Dropping
    it silently breaks ReDoc's search.

!!! note "style-src 'unsafe-inline'"
    `style-src` still allows inline styles: the homepage carries one
    `<style>` block, and both Swagger UI and ReDoc inject styles at
    runtime. Inline *styles* are a far smaller lever than inline
    scripts.

Override the default for your own frontend:

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

## Trusted Hosts

`TrustedHostMiddleware` rejects any request whose `Host` header is not in
`QUOIN_ALLOWED_HOSTS`, so a forged `Host` can't poison absolute URLs or
cache keys. Patterns are exact hosts, `*.example.com` subdomain
wildcards, or a bare `*` (which turns the check off).

| Variable | Default | Notes |
| :--- | :--- | :--- |
| `QUOIN_ALLOWED_HOSTS` | `["localhost", "127.0.0.1", "test", "*.orb.local"]` | **Required in production**; the development default is refused there |

A rejected request gets a `400` `application/problem+json` response
(`Invalid host header`), and the host is logged as `invalid_host_header`.
The middleware is QuoinAPI's own rather than Starlette's, so the failure
looks like every other error; see
[Middleware ordering](#middleware-ordering) for why it sits outside CORS.

```bash
QUOIN_ALLOWED_HOSTS=["api.example.com","*.internal.example.com"]
```

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
(`validate_production_settings()` is called from `create_app()`), and
the JWKS URI must be `https://` — an `http://` endpoint would let an
on-path attacker substitute signing keys. A misconfigured production
deployment therefore crash-loops rather than serving 401s while
appearing healthy. The check lives in `create_app()` rather than on
config import so data-plane tooling that only imports settings —
Alembic migrations, scripts — stays decoupled from OAuth. Development
and test skip the check.

### What else production refuses to boot without

`validate_production_settings()` covers more than OAuth:

| Setting | In production | Why |
| :--- | :--- | :--- |
| `QUOIN_OAUTH_JWKS_URI` | Required, `https://` | Signing-key substitution |
| `QUOIN_OAUTH_ISSUER` | Required | PyJWT skips an unset `iss` |
| `QUOIN_OAUTH_AUDIENCE` | Required | Token replay across audiences |
| `QUOIN_ALLOWED_HOSTS` | Required, must differ from the default | The default rejects every real `Host` with a 400 |
| `QUOIN_BACKEND_CORS_ORIGINS` | Warns on `localhost` entries | A leftover dev origin in a production allow-list |
| `QUOIN_POSTGRES_PASSWORD` | Warns if left at the default | A development credential on a production database |

`ALLOWED_HOSTS` is a **hard** failure rather than a warning because the
default fails *closed*: the service is safe but returns 400 to
everything, which pages as an outage instead of pointing at the config.
Localhost CORS origins only *warn* — they are a smell in production but
harmless on their own, and a deployment may legitimately keep one for a
bastion. The warning is logged as `production_local_cors_origins`.

The default database password also only warns, logged as
`production_default_database_password`. The database belongs to the
deployer, and a private network may make the default harmless.

### JWKS refresh backoff

A token carrying an unknown `kid` normally triggers a JWKS refetch to
pick up rotated keys. Left unbounded, an attacker spraying garbage-`kid`
tokens could force an outbound HTTP call on every request. `JWKSCache`
caps unknown-`kid` refetches to at most one per
`QUOIN_OAUTH_JWKS_MIN_REFRESH_SECONDS` (default `30`), and the backoff
timer is set before the fetch so a *failed* fetch backs off too. Tokens
inside the window are rejected from cache with no outbound call.

A token whose `kid` is already cached never waits on a fetch. When the
cached set is past its one-hour TTL, the cached key is served and the
set is refreshed in the background (stale-while-revalidate); only an
unknown `kid` waits, and only for the one fetch in flight. A slow IdP
therefore delays new keys, not every authenticated request.

The refresh itself goes through the shared
[resilient HTTP client](outbound-http.md) — retries with backoff and a
per-host circuit breaker, with a 3-second per-attempt timeout rather
than `QUOIN_HTTP_TIMEOUT_SECONDS` — rather than a bare per-refresh
client. A hard-down authorization server
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
AccessLogMiddleware        ← inside RequestID, so every line has request_id
TrustedHostMiddleware      ← validates Host before CORS can short-circuit
CORSMiddleware
TimeoutMiddleware          ← reject oversize before the timeout clock ticks
RequestSizeLimitMiddleware
InFlightRequestMiddleware
UnhandledErrorMiddleware   ← innermost, closest to the router
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

`TrustedHostMiddleware` is QuoinAPI's own, not Starlette's: its `400`
is `application/problem+json` like every other error, so a wrong
`QUOIN_ALLOWED_HOSTS` looks like any other failure. Patterns are exact
hosts, `*.example.com`, or `*`; Starlette's `www.` redirect is not
kept. A CORS preflight rejected by `CORSMiddleware` (disallowed origin,
method, or header) is still Starlette's `text/plain` `400`, the one
exception: only the browser reads it.

`UnhandledErrorMiddleware` is innermost for the same reason, inverted:
it catches an escaping exception *before* it unwinds past the stack, so
the 500 it builds travels back out through CORS, `SecurityHeaders`, and
`RequestID` like any other response. A handler registered against bare
`Exception` cannot do this — Starlette moves it to
`ServerErrorMiddleware`, outside everything. See the
[error handling guide](error-handling.md#catch-all-for-uncaught-exceptions).

`AccessLogMiddleware` sits inside `RequestID` (so the `request_id`
contextvar is already bound) but outside the timeout and size limits, so
504s, 413s, and 500s are logged with their real status and duration.

---

## Testing

The thing that breaks silently here is **order**, not behaviour. Each
layer works in isolation while the stack as a whole stops protecting
anything — a size limit registered after the body is read, or CORS
outside the error handler so a rejected preflight comes back without
its headers.

`configure_middlewares` is a plain function, and `app.user_middleware`
after calling it is the assembled list, so the stack can be inspected
directly rather than inferred from a live request. `tests/core/test_middlewares.py` uses
it to assert every layer is **present** — and it is worth being precise
that presence is all it asserts. The ordering above is not currently
pinned by a test; it is held by this table and by the behaviour tests
that would fail if a layer moved.

Those behaviour tests carry the rest: CORS present when enabled and
absent when disabled, the Host allowlist applied, an unsafe
`X-Request-ID` rejected rather than echoed, and a slow request answered
with `504` while a fast one passes.

Two are worth copying if you add a layer of your own. A timeout that
fires **after the response has started** must not try to send a second
response — that is a different code path from the ordinary timeout, and
it is the one that crashes. And a rejected request must still carry
`X-Request-ID`, or the log line you need in order to debug it has
nothing to join on.

Settings-driven behaviour belongs with the settings tests: build a
`Settings` with the value you want and assert the layer reacts, rather
than mutating the process environment mid-suite.

## See Also

- [Configuration reference](configuration.md) — all `QUOIN_SECURITY_*` variables
- [Dependency Scanning](dependency-scanning.md) — Dependabot + secret scanning
- [Deployment guide](deployment.md) — production environment setup
- [`app/core/middlewares.py`](../../app/core/middlewares.py) — implementation
