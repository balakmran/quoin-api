# Deprecating Endpoints

The API version lives in the URL prefix — everything is served under
`/api/v1`. A new **major** version (`/api/v2`) is the tool for breaking
the whole contract. This guide is about the smaller, more common case:
retiring or replacing a **single endpoint** ahead of that, and telling
clients before it disappears.

QuoinAPI ships the signalling *mechanism* — standard headers defined by
[RFC 8594](https://www.rfc-editor.org/rfc/rfc8594) — not a stability
promise about the example `user` module (this repo is a template you
fork). Use it to deprecate *your* endpoints.

## The mechanism

[`app/core/versioning.py`](https://github.com/balakmran/quoin-api/blob/main/app/core/versioning.py)
provides a `deprecated()` dependency. Attach it to any route and it
stamps three headers on every response, without touching the handler:

| Header        | Value                              | When                    |
| :------------ | :--------------------------------- | :---------------------- |
| `Deprecation` | `true`                             | Always.                 |
| `Sunset`      | HTTP-date (e.g. `Sat, 01 Jan 2027 00:00:00 GMT`) | When a removal date is given. |
| `Link`        | `<url>; rel="deprecation"`         | When a docs URL is given. |

```python
from datetime import date
from fastapi import APIRouter, Depends

from app.core.versioning import deprecated

router = APIRouter(prefix="/widgets")


@router.get(
    "/legacy-search",
    dependencies=[
        Depends(
            deprecated(
                sunset=date(2027, 1, 1),
                link="https://your-docs.example.com/widgets/search-migration",
            )
        )
    ],
)
async def legacy_search() -> ...:
    ...
```

Both `sunset` and `link` are optional. With neither, the route still
advertises `Deprecation: true` — useful when you've decided an endpoint
is deprecated but haven't set a firm removal date yet.

Clients (and tooling like linters or API gateways) can detect the
`Deprecation` header and warn, and the `Sunset` date tells them how long
they have. The `Link` points to human-readable migration docs.

## A suggested policy

The mechanism is unopinionated; here is a sensible default policy to
document for your own API:

1. **Announce** — add `deprecated()` with a `Sunset` at least one release
   cycle out and a `link` to migration docs. Note it in the changelog.
2. **Overlap** — keep the deprecated endpoint working alongside its
   replacement for the whole deprecation window.
3. **Remove** — delete the endpoint on or after the `Sunset` date, in a
   release whose notes call out the removal.

Reserve a new URL major version (`/api/v2`) for changes too broad to land
endpoint-by-endpoint.
