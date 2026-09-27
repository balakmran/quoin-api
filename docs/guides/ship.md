# Ship

Everything between "it works on my machine" and "it is running in
production and someone is on call for it".

- [Testing](testing.md) — write integration tests against a real
  database, with per-test rollback
- [Quality Checks](quality-checks.md) — the format, lint, typecheck,
  and migration-drift gate behind `just check`
- [Security](security.md) — the middleware stack, response headers,
  host allowlist, and what production refuses to boot without
- [Dependency Scanning](dependency-scanning.md) — audit runtime
  dependencies for known advisories
- [Deployment](deployment.md) — build the image and apply migrations in
  production
- [Observability](observability.md) — structured logs and OpenTelemetry
  traces that correlate by request and caller

Every setting named in these guides is listed in
[Configuration](configuration.md), under Reference.
