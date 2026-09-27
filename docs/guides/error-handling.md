# Error Handling

Services raise domain exceptions; global handlers turn every one of them
into an [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457)
`application/problem+json` response. You never build an error response
by hand, and you never raise `HTTPException` outside a route.

```mermaid
graph LR
    A[Service or repository] -->|raises| B[Module exception]
    B -->|subclass of| C[QuoinError]
    C -->|caught by| D[Global handler]
    D -->|returns| E[application/problem+json]
```

## Exceptions

Import from `app.core.exceptions`. All inherit from `QuoinError`, which
carries a `message`, a `status_code`, and optional `headers`.

| Exception                     | Status | Use Case                                  |
| :---------------------------- | :----: | :---------------------------------------- |
| `BadRequestError`             | 400    | Invalid request data or parameters        |
| `UnauthorizedError`           | 401    | Missing or invalid Bearer token           |
| `ForbiddenError`              | 403    | Insufficient permissions                  |
| `NotFoundError`               | 404    | Resource not found                        |
| `ConflictError`               | 409    | Resource conflict (e.g., duplicate email) |
| `QuoinRequestValidationError` | 422    | Pydantic validation errors (internal)     |
| `InternalServerError`         | 500    | A failure in your own code                |
| `BadGatewayError`             | 502    | Upstream returned an invalid response     |
| `ServiceUnavailableError`     | 503    | Required dependency unreachable; retry later |
| `GatewayTimeoutError`         | 504    | Request exceeded the configured timeout   |

### Module exceptions

Each module subclasses these in its own `exceptions.py`, with a message
that carries the relevant IDs:

```python
# app/modules/user/exceptions.py
from app.core.exceptions import ConflictError, NotFoundError


class UserNotFoundError(NotFoundError):
    def __init__(self, user_id: str) -> None:
        super().__init__(message=f"User with ID '{user_id}' not found")


class DuplicateEmailError(ConflictError):
    def __init__(self, email: str) -> None:
        super().__init__(message=f"Email '{email}' is already registered")
```

No handler registration is needed. The response `type` is derived from
the class name, so `UserNotFoundError` becomes
`urn:quoin:error:user_not_found_error`.

### Raising them

```python
async def get_user(self, user_id: uuid.UUID) -> User:
    user = await self.repository.get(user_id)
    if not user:
        raise UserNotFoundError(user_id=str(user_id))
    return user
```

A service-level check such as "does this email exist?" is a fast path,
not a guarantee: two concurrent requests can both pass it. The
repository closes the race by catching the `IntegrityError` at
`flush()`, confirming it came from the email uniqueness index, and
raising `DuplicateEmailError`. Any other `IntegrityError` propagates
unchanged. That is why a duplicate is always a 409, never a 500, even
under concurrent writes.

## Response Format

```json
{
  "type": "urn:quoin:error:not_found_error",
  "title": "Not Found",
  "status": 404,
  "detail": "User with ID 'f47ac10b' not found",
  "instance": "/api/v1/users/f47ac10b"
}
```

| Field      | Description                                            |
| :--------- | :----------------------------------------------------- |
| `type`     | `urn:quoin:error:<snake_case_class_name>`              |
| `title`    | Standard HTTP reason phrase for the status code        |
| `status`   | HTTP status code (mirrors the response status)         |
| `detail`   | The exception's message                                |
| `instance` | Request path where the error occurred                  |
| `errors`   | Per-field array; only present on 422 responses         |

The only response that isn't problem details is a CORS preflight that
`CORSMiddleware` rejects: a `text/plain` 400 that only the browser
reads.

### Validation errors (422)

Request parsing failures add an `errors` array:

```json
{
  "type": "urn:quoin:error:validation_error",
  "title": "Unprocessable Content",
  "status": 422,
  "detail": "Request validation failed",
  "instance": "/api/v1/users/",
  "errors": [
    {
      "type": "string_type",
      "loc": ["body", "email"],
      "msg": "Input should be a valid string",
      "input": 42
    }
  ]
}
```

Each entry is JSON-encoded safely (a raising `field_validator` puts an
exception object in `ctx.error`), Pydantic's `url` is dropped, and
`input` is cut to 200 characters so a response never echoes unbounded
client data.

Only `RequestValidationError` and `QuoinRequestValidationError` map to
422. A bare `pydantic.ValidationError` means an internal model failed,
which is a server bug, so it becomes a 500.

## Request Timeouts

`TimeoutMiddleware` cancels a request that runs past
`QUOIN_REQUEST_TIMEOUT_SECONDS` (default `30.0`; `0` or less disables
it) and returns a 504 `gateway_timeout_error`. It uses an `anyio` cancel
scope, which reliably cancels nested async calls where
`asyncio.wait_for` can leave a coroutine running.

## Global Exception Handlers

`add_exception_handlers(app)` in
[`app/core/exception_handlers.py`](https://github.com/balakmran/quoin-api/blob/main/app/core/exception_handlers.py)
registers the handlers from `create_app()`:

- `quoin_exception_handler` — any `QuoinError`, using its status,
  message, and headers
- `validation_exception_handler` — the 422s above
- `unhandled_exception_handler` — the final fallback, below

A handler you add for a third-party exception must type `exc` as `Any`.

### Catch-all for uncaught exceptions

Anything no specific handler catches, such as a bare `KeyError` or an
`httpx2.InvalidURL` escaping the outbound client, still returns a
problem details 500 with `detail` set to `"Internal Server Error"`. The
real message and traceback go to the log as `unhandled_exception`, never
to the client.

Two layers produce that 500:

| Layer | Handles | Why it exists |
| :--- | :--- | :--- |
| `UnhandledErrorMiddleware` (`app/core/middlewares.py`) | Anything raised by a route or the layers inside it | Innermost, so its 500 passes back out through CORS, `SecurityHeaders`, and `RequestID` and gets their headers |
| `unhandled_exception_handler` | Exceptions raised by a middleware itself, and non-HTTP scopes | A final fallback registered on `Exception` |

The middleware is needed because Starlette runs an `Exception` handler
in its outermost layer, after the exception has unwound past every other
middleware, so that 500 would carry no request ID, security, or CORS
headers. Exactly one layer logs each exception.

Treat the catch-all as a safety net. Raise a `QuoinError` subclass
whenever you know what went wrong.

## Logging

Every `QuoinError` is logged as `quoin_error` before the response goes
out: `error` with traceback for 5xx, `warning` for 401 and 403, `info`
for other 4xx. See
[Error Response Levels](observability.md#error-response-levels).

## OpenAPI Documentation

Two helpers in `app.core.openapi` declare error responses so every
module documents the same shapes.

`DEFAULT_ERROR_RESPONSES` covers what any authenticated endpoint can
return (401, 403, 422, 500). Put it on the module router:

```python
router = APIRouter(
    prefix="/users",
    tags=["users"],
    responses=DEFAULT_ERROR_RESPONSES,
)
```

`error_responses(*codes)` adds what a specific route can raise, with
optional better descriptions:

```python
@router.get(
    "/{user_id}",
    response_model=UserRead,
    responses=error_responses(404, descriptions={404: "User not found"}),
)
async def get_user(...) -> User: ...
```

Mistakes fail loudly: an unknown code raises `KeyError`, and a
`descriptions` key that matches no requested code raises `ValueError`.
400 isn't in the default set, since most routes never raise it; add
`error_responses(400)` where one does.

Two details of the generated schema:

- FastAPI files every response model under `application/json`, so
  `_use_problem_media_type` relabels responses that reference
  `ProblemDetail` as `application/problem+json` after generation.
- Declaring 422 replaces FastAPI's `HTTPValidationError` model, which
  describes a payload this API never sends.

## Testing

Assert on the domain exception in service tests, and on the whole
problem details body in route tests:

```python
async def test_create_user_duplicate_email(admin_client: AsyncClient):
    payload = {"email": "test@example.com", "full_name": "Test User"}
    await admin_client.post("/api/v1/users/", json=payload)

    response = await admin_client.post("/api/v1/users/", json=payload)

    body = response.json()
    assert response.status_code == 409
    assert response.headers["content-type"] == "application/problem+json"
    assert body["type"] == "urn:quoin:error:duplicate_email_error"
    assert body["instance"] == "/api/v1/users/"
```

The `client` fixture also checks every 4xx and 5xx response against
this contract automatically; see
[Testing](testing.md#fixtures).

## See Also

- [Observability](observability.md) — where error logs go
- [Optimistic Concurrency](optimistic-concurrency.md) — adding `412`
  responses for conflicting writes
- [app/core/exceptions.py](https://github.com/balakmran/quoin-api/blob/main/app/core/exceptions.py) — the exception classes
- [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457) — Problem Details for HTTP APIs
