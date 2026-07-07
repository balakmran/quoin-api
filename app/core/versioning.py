"""Endpoint deprecation signalling (RFC 8594 / Deprecation header).

The API version lives in the URL prefix (``/api/v1``). When an
individual endpoint needs to be retired ahead of a version bump, attach
`deprecated()` to its dependencies to advertise that on every response
with the standard headers, so clients (and their tooling) can detect it
without reading the changelog:

- ``Deprecation: true``
- ``Sunset: <HTTP-date>`` — the date on/after which it may stop working
- ``Link: <url>; rel="deprecation"`` — human-readable migration docs

Usage::

    from datetime import date
    from app.core.versioning import deprecated


    @router.get(
        "/legacy",
        dependencies=[
            Depends(
                deprecated(
                    sunset=date(2027, 1, 1),
                    link="https://docs.example.com/api/legacy-removal",
                )
            )
        ],
    )
    async def legacy_endpoint() -> ...: ...

See `docs/guides/deprecating-endpoints.md` for the full policy.
"""

from collections.abc import Callable
from datetime import UTC, date, datetime, time
from email.utils import format_datetime

from fastapi import Response


def deprecated(
    *,
    sunset: date | None = None,
    link: str | None = None,
) -> Callable[[Response], None]:
    """Build a dependency that marks an endpoint deprecated (RFC 8594).

    The returned callable is a FastAPI dependency; add it to a route via
    ``dependencies=[Depends(deprecated(...))]`` so the headers are set on
    every response without changing the handler's return value.

    Args:
        sunset: Date on/after which the endpoint may be removed or stop
            functioning. Emitted as an HTTP-date ``Sunset`` header
            (midnight UTC). Omit to signal deprecation without a firm
            removal date.
        link: URL of human-readable documentation describing the
            deprecation and migration path. Emitted as a ``Link`` header
            with ``rel="deprecation"``.

    Returns:
        A dependency callable that stamps the deprecation headers.
    """
    sunset_header = (
        format_datetime(
            datetime.combine(sunset, time(0, 0), tzinfo=UTC), usegmt=True
        )
        if sunset is not None
        else None
    )
    link_header = f'<{link}>; rel="deprecation"' if link is not None else None

    def _stamp_deprecation_headers(response: Response) -> None:
        """Set the RFC 8594 deprecation headers on the response."""
        response.headers["Deprecation"] = "true"
        if sunset_header is not None:
            response.headers["Sunset"] = sunset_header
        if link_header is not None:
            response.headers["Link"] = link_header

    return _stamp_deprecation_headers
