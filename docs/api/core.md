# Core

Infrastructure shared across the whole application. Every section below
is generated from the module's own docstrings, so it cannot drift from
the code it describes.

---

## Configuration

::: app.core.config

**Usage:** see the [Configuration guide](../guides/configuration.md#key-settings).

**Source:** [app/core/config.py](https://github.com/balakmran/quoin-api/blob/main/app/core/config.py)

---

## Metadata

::: app.core.metadata

**Source:** [app/core/metadata.py](https://github.com/balakmran/quoin-api/blob/main/app/core/metadata.py)

---

## Logging

::: app.core.logging

**Usage:** see the [Observability guide](../guides/observability.md).

**Source:** [app/core/logging.py](https://github.com/balakmran/quoin-api/blob/main/app/core/logging.py)

---

## Exceptions

::: app.core.exceptions

**Usage:** see the [Error Handling guide](../guides/error-handling.md).

**Source:** [app/core/exceptions.py](https://github.com/balakmran/quoin-api/blob/main/app/core/exceptions.py)

---

## Schemas

::: app.core.schemas

**Source:** [app/core/schemas.py](https://github.com/balakmran/quoin-api/blob/main/app/core/schemas.py)

---

## Exception Handlers

::: app.core.exception_handlers

**Usage:** see the [Error Handling guide](../guides/error-handling.md).

**Source:** [app/core/exception_handlers.py](https://github.com/balakmran/quoin-api/blob/main/app/core/exception_handlers.py)

---

## Middlewares

::: app.core.middlewares

**Usage:** see the [Security guide](../guides/security.md#middleware-ordering).

**Source:** [app/core/middlewares.py](https://github.com/balakmran/quoin-api/blob/main/app/core/middlewares.py)

---

## Security

::: app.core.security

**Usage:** see the [Authentication guide](../guides/authentication.md).

**Source:** [app/core/security.py](https://github.com/balakmran/quoin-api/blob/main/app/core/security.py)

---

## Lifecycle

::: app.core.lifecycle

**Usage:** see [Graceful Shutdown](../guides/deployment.md#graceful-shutdown).

**Source:** [app/core/lifecycle.py](https://github.com/balakmran/quoin-api/blob/main/app/core/lifecycle.py)

---

## Telemetry

::: app.core.telemetry

**Usage:** see the [Observability guide](../guides/observability.md).

**Source:** [app/core/telemetry.py](https://github.com/balakmran/quoin-api/blob/main/app/core/telemetry.py)

---

## Pagination

::: app.core.pagination

**Usage:** see the [Pagination guide](../guides/pagination.md).

**Source:** [app/core/pagination.py](https://github.com/balakmran/quoin-api/blob/main/app/core/pagination.py)

---

## Versioning

::: app.core.versioning

**Usage:** see the [Deprecating Endpoints guide](../guides/deprecating-endpoints.md).

**Source:** [app/core/versioning.py](https://github.com/balakmran/quoin-api/blob/main/app/core/versioning.py)

---

## OpenAPI

::: app.core.openapi

**Usage:** see [OpenAPI Documentation](../guides/error-handling.md#openapi-documentation).

**Source:** [app/core/openapi.py](https://github.com/balakmran/quoin-api/blob/main/app/core/openapi.py)

---

## Database Session

::: app.db.session

**Usage:** see the [Architecture overview](../architecture/overview.md#database-layer-appdb).

**Source:** [app/db/session.py](https://github.com/balakmran/quoin-api/blob/main/app/db/session.py)

---

## Outbound HTTP Client

::: app.http.client

**Usage:** see the [Outbound HTTP guide](../guides/outbound-http.md#using-it-in-a-service).

**Source:** [app/http/client.py](https://github.com/balakmran/quoin-api/blob/main/app/http/client.py)

---

## See Also

- [Configuration Guide](../guides/configuration.md) — Environment setup
- [Error Handling Guide](../guides/error-handling.md) — Exception patterns
- [Observability Guide](../guides/observability.md) — Logging and tracing
