# Optimistic Concurrency (ETag / `If-Match`)

Two clients read the same resource, both edit it, both `PATCH` it back.
The second write silently overwrites the first — neither client ever
learns that an update was lost. This is the *lost update* problem, and
HTTP already has the answer: conditional requests, defined in
[RFC 9110 §13](https://www.rfc-editor.org/rfc/rfc9110#section-13).

QuoinAPI does **not** ship this. Most CRUD APIs never hit the problem —
concurrent edits to the same row by different clients are rarer than they
feel, and a last-write-wins outcome is usually acceptable. Adding ETag
plumbing to every endpoint costs real complexity, so the template leaves
it out and documents the pattern here instead.

Reach for it when a resource has **multiple concurrent editors and a
lost update is a correctness bug**, not an annoyance: inventory counts,
account balances, workflow state machines, anything where the new value
is derived from the value just read.

## How the exchange works

```text
GET /api/v1/widgets/{id}
    200 OK
    ETag: "7"

PATCH /api/v1/widgets/{id}
    If-Match: "7"
        -> 200 OK          the row is still at version 7; write applied
        -> 412 Precondition Failed   someone else wrote first; re-read
        -> 428 Precondition Required no If-Match sent at all
```

The client never has to understand versioning. It echoes back the opaque
`ETag` it was handed, and the server decides whether the write is still
safe.

## Choose the ETag source first

Everything else follows from this decision.

**A version column is the better default.** Add an integer that the
database increments on every write, and the ETag is just that number.
Comparison is exact, cheap, and unambiguous.

**A content hash** (`sha256` over the serialised body) avoids a schema
change and works when you cannot alter the table. But it makes every
conditional request re-serialise the resource, and two semantically
different states can collide if your serialisation drops a field.

Prefer the version column unless you cannot change the schema.

## Add the version column

Following [Database Migrations](database-migrations.md) — edit the
SQLModel, then generate the migration, never the other way round:

```python
class Widget(SQLModel, table=True):
    """A widget with an optimistic-concurrency version counter."""

    __tablename__ = "widgets"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=200)
    version: int = Field(default=1, nullable=False)


# Declared after the class so the column object already exists.
Widget.__mapper_args__ = {"version_id_col": Widget.__table__.c.version}
```

The `version_id_col` mapper argument is what makes this safe: with it
set, SQLAlchemy appends `WHERE version = :expected`
to every `UPDATE` and raises `StaleDataError` when zero rows match. That
closes the race *inside the database*, which a manual compare in Python
cannot do — between your `SELECT` and your `UPDATE`, another transaction
can always slip in.

Then:

```bash
just migrate-gen "add version column to widgets"
just migrate-up
```

## Add a 412 domain exception

`app/core/exceptions.py` ships 400, 401, 403, 404, 409, and the 5xx
family, but no 412. Add one beside the others — and never raise
`HTTPException` from a service or repository, per
[Error Handling](error-handling.md):

```python
class PreconditionFailedError(QuoinError):
    """Raised when an If-Match precondition does not hold."""

    def __init__(
        self,
        message: str = "The resource was modified by another request.",
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialise the error.

        Args:
            message: Human-readable explanation for the response body.
            headers: Optional headers to attach to the response.
        """
        super().__init__(message, status_code=412, headers=headers)
```

The global handler turns it into an RFC 9457 problem document with no
further work, exactly like `ConflictError`.

## Repository: translate the stale write

`StaleDataError` is a SQLAlchemy detail and must not escape the
repository — the same boundary rule that keeps `IntegrityError` from
leaking out of `UserRepository`:

```python
from sqlalchemy.orm.exc import StaleDataError

from app.core.exceptions import PreconditionFailedError


async def update(self, widget: Widget, data: WidgetUpdate) -> Widget:
    """Apply a partial update, enforcing the version precondition.

    Args:
        widget: The Widget to mutate; must be attached to the session.
        data: Partial payload with fields to overwrite.

    Returns:
        The updated Widget, refreshed from the database.

    Raises:
        PreconditionFailedError: If another transaction wrote this row
            first, leaving the caller's expected version stale.
    """
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(widget, key, value)
    self.session.add(widget)
    try:
        await self.session.flush()
    except StaleDataError as exc:
        raise PreconditionFailedError() from exc
    await self.session.refresh(widget)
    return widget
```

## Service: compare the caller's expectation

The service owns the precondition policy — whether `If-Match` is
mandatory, and what a mismatch means:

```python
async def update_widget(
    self,
    widget_id: uuid.UUID,
    data: WidgetUpdate,
    if_match: str | None,
) -> Widget:
    """Update a widget behind an If-Match precondition.

    Args:
        widget_id: UUID of the widget to update.
        data: Partial payload; unset fields are left unchanged.
        if_match: Raw If-Match header value, or None when absent.

    Returns:
        The updated Widget.

    Raises:
        BadRequestError: If If-Match is missing on a guarded resource.
        PreconditionFailedError: If the caller's version is stale.
    """
    if if_match is None:
        raise BadRequestError(
            message="This endpoint requires an If-Match header."
        )
    widget = await self.get_widget(widget_id)
    if _etag(widget) != if_match.strip():
        raise PreconditionFailedError()
    return await self.repository.update(widget, data)
```

The in-service comparison is a fast path that returns 412 without
touching the database. It is **not** the safety mechanism — the
`version_id_col` check is. Keep both: one gives a clean error, the other
closes the race.

## Route: emit and accept the header

```python
@router.get("/{widget_id}", response_model=WidgetRead)
async def get_widget(
    widget_id: uuid.UUID,
    response: Response,
    service: Annotated[WidgetService, Depends(get_widget_service)],
    caller: Annotated[ServicePrincipal, Depends(require_roles("widgets.read"))],
) -> Widget:
    """Return a single widget and its current ETag."""
    widget = await service.get_widget(widget_id)
    response.headers["ETag"] = _etag(widget)
    return widget


@router.patch("/{widget_id}", response_model=WidgetRead)
async def update_widget(
    widget_id: uuid.UUID,
    data: WidgetUpdate,
    response: Response,
    service: Annotated[WidgetService, Depends(get_widget_service)],
    caller: Annotated[
        ServicePrincipal, Depends(require_roles("widgets.write"))
    ],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> Widget:
    """Update a widget, rejecting writes against a stale version."""
    widget = await service.update_widget(widget_id, data, if_match)
    response.headers["ETag"] = _etag(widget)
    return widget
```

with the formatter kept in one place so the two ends cannot drift:

```python
def _etag(widget: Widget) -> str:
    """Format a widget's version as a strong entity tag.

    Args:
        widget: The widget whose version to encode.

    Returns:
        The version as a quoted entity tag, e.g. ``"7"``.
    """
    return f'"{widget.version}"'
```

The quotes are required by RFC 9110 and are part of the value — `"7"`
and `7` are not the same entity tag.

## Strong vs weak tags

A tag prefixed `W/` is *weak*: it claims semantic equivalence, not
byte-for-byte identity. `If-Match` requires the strong comparison
function, so **weak tags never match** and a `W/"7"` precondition fails
every time. Emit strong tags for anything you intend to guard.

## Testing

The project's per-test SAVEPOINT rollback (see [Testing](testing.md))
gives each test its own transaction, so the two-writer race needs two
sessions. The cheaper and more stable test asserts the contract rather
than the race:

```python
async def test_stale_if_match_is_rejected(
    client: AsyncClient, widget: Widget
) -> None:
    """A PATCH carrying an outdated ETag is refused with 412."""
    first = await client.get(f"/api/v1/widgets/{widget.id}")
    stale = first.headers["ETag"]

    await client.patch(
        f"/api/v1/widgets/{widget.id}",
        json={"name": "renamed once"},
        headers={"If-Match": stale},
    )
    second = await client.patch(
        f"/api/v1/widgets/{widget.id}",
        json={"name": "renamed twice"},
        headers={"If-Match": stale},
    )

    assert second.status_code == 412
```

Cover three cases per guarded endpoint: a matching tag succeeds, a stale
tag returns 412, and a missing header returns your chosen error.

## What's intentionally not here

- **`If-None-Match` for caching** — the same header family also powers
  conditional `GET`s that return `304 Not Modified`. That is a bandwidth
  optimisation, not a correctness one, and belongs behind a CDN or
  reverse proxy that can serve the 304 without waking the application.
- **Automatic ETags on every endpoint** — middleware that hashes every
  response body looks appealing and is nearly always wrong: it pays the
  serialisation cost everywhere to protect the few resources that
  actually have concurrent editors.
- **`428 Precondition Required`** —
  [RFC 6585](https://www.rfc-editor.org/rfc/rfc6585) defines a dedicated
  status for "you must send `If-Match`". The example
  above uses `BadRequestError` (400) to stay inside the shipped
  exception set; add a 428 the same way `PreconditionFailedError` is
  added if you prefer the precise code.

## See Also

- [Error Handling](error-handling.md) — domain exceptions and the
  RFC 9457 problem-details contract
- [Database Migrations](database-migrations.md) — the model-first
  workflow the version column follows
- [Soft Delete](soft-delete.md) — the other write-path convention that
  changes what an update means
