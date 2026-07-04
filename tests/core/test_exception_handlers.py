import pydantic
import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient

from app.main import create_app


class _InternalModel(pydantic.BaseModel):
    """Stand-in for an internal model whose construction can fail."""

    n: int


@pytest.mark.asyncio
async def test_bare_pydantic_validation_error_returns_500_not_422() -> None:
    """B3 regression: internal ValidationError falls through to a 500."""
    app = create_app()

    @app.get("/test-internal-validation-bug")
    async def _buggy() -> dict[str, str]:
        _InternalModel.model_validate({"n": "not-an-int"})
        return {}

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/test-internal-validation-bug")

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["type"] == "urn:quoin:error:internal_server_error"
    assert body["detail"] == "Internal Server Error"
