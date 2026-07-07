# Pagination, Sorting & Filtering

Every list endpoint in QuoinAPI returns the same envelope and accepts the
same pagination and sort query parameters, so clients learn the shape
once and it holds across every module. The primitives live in
[`app/core/pagination.py`](https://github.com/balakmran/quoin-api/blob/main/app/core/pagination.py);
the `user` module is the reference implementation.

## The response envelope

List endpoints return a `Page[T]` rather than a bare array:

```json
{
  "items": [ { "id": "...", "email": "..." } ],
  "total": 137,
  "limit": 100,
  "offset": 0
}
```

| Field    | Meaning                                                     |
| :------- | :--------------------------------------------------------- |
| `items`  | The rows on the current page.                              |
| `total`  | Rows matching the query **ignoring** pagination.          |
| `limit`  | Maximum rows requested for this page.                     |
| `offset` | Rows skipped before this page.                            |

`total` lets a client compute the number of pages without walking to the
end. It reflects the active filters, so a filtered listing reports the
filtered count, not the table size.

## Query parameters

### Pagination — shared everywhere

`PageParams` is a FastAPI dependency, so `limit` and `offset` appear with
identical bounds on every list route:

| Parameter | Type | Default | Bounds        |
| :-------- | :--- | :------ | :------------ |
| `limit`   | int  | `100`   | `1..100`      |
| `offset`  | int  | `0`     | `>= 0`        |

The upper bound (`MAX_LIMIT`) caps the cost of any single query. Requests
outside the bounds fail validation with `422`.

### Sorting — shared convention, per-module fields

The `sort` parameter is a comma-separated list of fields, each optionally
prefixed with `-` for descending order:

```
GET /api/v1/users/?sort=-created_at,email
```

Each module declares which fields are sortable (a name → column map).
`parse_sort` validates the request against that whitelist and returns a
`400 Bad Request` for anything else — an unknown or non-whitelisted field
is never silently ignored and never reaches the database:

```json
{ "detail": "Cannot sort by 'password'. Sortable fields: created_at, email, full_name, updated_at." }
```

Repositories always append their primary key as a final tiebreaker, so
the ordering is total and pagination stays stable across pages even when
the sort column has duplicate values.

### Filtering — explicit, per module

Filters are **not** a generic framework. Each module exposes the filters
that make sense for its resource as explicit, documented query
parameters. The `user` module demonstrates two common shapes:

| Parameter   | Filter                                                    |
| :---------- | :-------------------------------------------------------- |
| `is_active` | Exact match on the boolean flag.                          |
| `q`         | Case-insensitive substring on `email` or `full_name`.     |

Keeping filters explicit means the OpenAPI schema documents exactly what
a resource supports, and each filter can be typed and validated.

## Wiring it into a module

The layers pass the pagination window down and return a `(rows, total)`
tuple; only the route knows about the envelope.

=== "Route"

    ```python
    from app.core.pagination import Page, PageParams

    @router.get("/", response_model=Page[WidgetRead])
    async def list_widgets(
        service: Annotated[WidgetService, Depends(get_widget_service)],
        page: Annotated[PageParams, Depends()],
    ) -> Page[Widget]:
        rows, total = await service.list_widgets(page)
        return Page.create(rows, total, page)
    ```

=== "Repository"

    ```python
    from sqlalchemy import func, select
    from app.core.pagination import PageParams, parse_sort

    WIDGET_SORTABLE = {"created_at": Widget.created_at, "name": Widget.name}

    async def list(
        self, params: PageParams, *, sort: str | None = None
    ) -> tuple[list[Widget], int]:
        order_by = parse_sort(
            sort, WIDGET_SORTABLE, default=[Widget.created_at.asc()]
        )
        rows_stmt = (
            select(Widget)
            .order_by(*order_by, Widget.id)
            .offset(params.offset)
            .limit(params.limit)
        )
        rows = list((await self.session.exec(rows_stmt)).scalars().all())
        total = (
            await self.session.exec(select(func.count()).select_from(Widget))
        ).scalars().one()
        return rows, total
    ```

To add module-specific filters, bundle `sort` plus your filters into a
small dependency class (see `UserListQuery` in the user module) so the
route signature stays flat, then thread them through the service into the
repository's query — applying the same predicates to both the row query
and the count.

## What's intentionally not here

- **Cursor / keyset pagination** — offset pagination is sufficient
  through `1.0`; cursors matter only at million-row scale and stay in the
  [backlog](../project/roadmap.md#backlog).
- **A generic filter DSL** — per-module explicit filters are clearer and
  keep the schema honest.
