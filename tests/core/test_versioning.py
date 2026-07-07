"""Tests for the endpoint deprecation mechanism (RFC 8594)."""

from datetime import date

from fastapi import Depends, FastAPI, status
from httpx import ASGITransport, AsyncClient, Response

from app.core.versioning import deprecated


def _app_with_deprecated_route(
    *, sunset: date | None = None, link: str | None = None
) -> FastAPI:
    """Build a minimal app with one deprecated route for testing."""
    app = FastAPI()

    @app.get(
        "/legacy",
        dependencies=[Depends(deprecated(sunset=sunset, link=link))],
    )
    async def legacy() -> dict[str, str]:
        return {"ok": "true"}

    return app


async def _get(app: FastAPI) -> Response:
    """Issue a GET /legacy against an in-process app."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.get("/legacy")


async def test_deprecation_header_always_set() -> None:
    """Every deprecated route advertises ``Deprecation: true``."""
    response = await _get(_app_with_deprecated_route())
    assert response.status_code == status.HTTP_200_OK
    assert response.headers["Deprecation"] == "true"
    # No sunset or link configured -> those headers are absent.
    assert "Sunset" not in response.headers
    assert "Link" not in response.headers


async def test_sunset_header_is_http_date() -> None:
    """A sunset date is emitted as an IMF-fixdate ``Sunset`` header."""
    response = await _get(_app_with_deprecated_route(sunset=date(2027, 1, 1)))
    assert response.headers["Sunset"] == "Fri, 01 Jan 2027 00:00:00 GMT"


async def test_link_header_uses_deprecation_relation() -> None:
    """A docs link is emitted with ``rel="deprecation"``."""
    url = "https://docs.example.com/api/legacy-removal"
    response = await _get(_app_with_deprecated_route(link=url))
    assert response.headers["Link"] == f'<{url}>; rel="deprecation"'
