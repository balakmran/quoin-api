# System

Documentation for the System module — the operational endpoints that
sit outside `/api/v1/`.

---

## Routes

`app/modules/system/` registers three routes at the application root
rather than under the versioned prefix, because orchestrators and
uptime checks expect them at fixed paths. All three are declared
`include_in_schema=False`, so none appears in the OpenAPI document, and
none requires a token.

| Method | Endpoint  | Description       | Status   |
| :----- | :-------- | :---------------- | :------- |
| `GET`  | `/`       | Landing page      | 200      |
| `GET`  | `/health` | Liveness probe    | 200      |
| `GET`  | `/ready`  | Readiness probe   | 200, 503 |

### Landing page — `GET /`

Renders `app/templates/index.html` with the application's name,
version, and description from [Metadata](core.md#metadata). The Swagger
link is omitted in production, where `/docs` is not registered. Page
behaviour lives in `app/static/js/home.js` rather than an inline
`<script>`, so the landing-page CSP needs no `'unsafe-inline'` in
`script-src`.

### Liveness probe — `GET /health`

Answers `{"status": "healthy"}` whenever the process is serving. It
touches no dependency, so it stays up while the database is down —
that distinction is what makes it safe as a liveness probe, where a
failure restarts the container.

```bash
curl http://localhost:8000/health
```

### Readiness probe — `GET /ready`

Answers `{"status": "ready"}` only when this instance should receive
traffic. It returns `503` in two cases:

- **Shutting down** — once `begin_shutdown()` has been called
  (see [Lifecycle](core.md#lifecycle)), so orchestrators route new
  traffic elsewhere while in-flight requests drain.
- **Database unreachable** — the probe runs `SELECT 1` on a request
  session and reports `503` rather than a `500` if it fails.

```bash
curl http://localhost:8000/ready
```

Both failures are `ServiceUnavailableError`, so the body is the same
RFC 9457 problem document as any other error.

!!! warning "Keep probes off the public internet"
    `/ready` runs an unauthenticated query on every hit. See
    [Health Checks](../guides/deployment.md#health-checks) for probe
    wiring and exposure guidance.

**Source:** [app/modules/system/routes.py](https://github.com/balakmran/quoin-api/blob/main/app/modules/system/routes.py)

---

## See Also

- [Deployment](../guides/deployment.md#health-checks) — probe wiring and
  graceful shutdown
- [Conventions](conventions.md) — why these routes sit outside
  `/api/v1/`
- [Core](core.md#lifecycle) — the shutdown flag the readiness probe
  reads
