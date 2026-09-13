import json

import pydantic
import pytest
from fastapi import HTTPException, status
from httpx2 import ASGITransport, AsyncClient
from pydantic import field_validator

from app.core.exception_handlers import _sanitize_validation_errors
from app.main import create_app


class _InternalModel(pydantic.BaseModel):
    """Stand-in for an internal model whose construction can fail."""

    n: int


@pytest.mark.asyncio
async def test_bare_pydantic_validation_error_returns_500_not_422() -> None:
    """Internal ValidationError (not a request body) falls through to 500."""
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


class _ValidatedBody(pydantic.BaseModel):
    """Request body with a field_validator that can raise on bad input."""

    name: str

    @field_validator("name")
    @classmethod
    def _reject_bad(cls, value: str) -> str:
        """Reject the sentinel value; Pydantic's documented raise idiom."""
        if value == "bad":
            raise ValueError("name may not be 'bad'")
        return value


@pytest.mark.asyncio
async def test_request_validator_raising_value_error_returns_422() -> None:
    """B2 regression: a raising field_validator yields 422, not 500."""
    app = create_app()

    @app.post("/test-validated-body")
    async def _endpoint(body: _ValidatedBody) -> dict[str, str]:
        return {"name": body.name}

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/test-validated-body", json={"name": "bad"})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["type"] == "urn:quoin:error:validation_error"
    error = body["errors"][0]
    assert "url" not in error
    assert "may not be 'bad'" in error["msg"]


@pytest.mark.asyncio
async def test_validation_error_input_is_truncated() -> None:
    """A validation error never echoes an unbounded `input` value."""
    app = create_app()

    @app.post("/test-long-input")
    async def _endpoint(body: _InternalModel) -> dict[str, int]:
        return {"n": body.n}

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    long_value = "x" * 5000
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/test-long-input", json={"n": long_value})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    error = response.json()["errors"][0]
    assert len(error["input"]) < len(long_value)
    assert error["input"].endswith("…")


@pytest.mark.asyncio
async def test_oversize_non_string_input_is_dropped_not_retyped() -> None:
    """An over-long structured `input` is dropped, not turned into a str."""
    app = create_app()

    @app.post("/test-structured-input")
    async def _endpoint(body: _InternalModel) -> dict[str, int]:
        return {"n": body.n}

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    small = {"a": 1}
    large = {f"field_{i}": i for i in range(50)}
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        small_response = await ac.post(
            "/test-structured-input", json={"n": small}
        )
        large_response = await ac.post(
            "/test-structured-input", json={"n": large}
        )

    # Small enough to reflect: kept, and still a JSON object.
    small_error = small_response.json()["errors"][0]
    assert small_error["input"] == small

    # Too large: the key is absent rather than holding a stringified dict.
    large_error = large_response.json()["errors"][0]
    assert "input" not in large_error


def test_sanitize_validation_errors_tolerates_missing_input() -> None:
    """An error dict without an `input` key passes through untouched."""
    errors = [{"loc": ("body", "name"), "msg": "field required", "url": "x"}]

    sanitized = _sanitize_validation_errors(errors)

    assert sanitized == [{"loc": ["body", "name"], "msg": "field required"}]


@pytest.mark.asyncio
async def test_starlette_http_exception_is_problem_json() -> None:
    """Starlette's own HTTPException is problem+json, in the right shape.

    Regression test: Starlette's default handler for its own
    ``HTTPException`` — raised internally when no route matches, or a
    route matches the wrong method — used to win over
    ``http_exception_handler`` and ship a bare ``{"detail": ...}`` body,
    the one gap the problem-details contract otherwise upholds
    everywhere else (the same class of gap as B3).

    Two more shapes the handler must preserve from Starlette's and
    FastAPI's defaults are checked here too:

    - a **bodyless status** (304, 204) must stay bodyless. A body there
      is a protocol violation uvicorn rejects mid-send with "Response
      content longer than Content-Length", after the headers are
      already on the wire.
    - a **structured ``detail``** (``detail={...}``, valid FastAPI
      usage) must stay parseable JSON; a bare ``str()`` would emit a
      single-quoted Python repr no client can read.

    Every case shares one ``create_app()`` / one client: two separate
    apps each logging through ``exception_handlers.logger`` — each app
    creation re-runs ``setup_logging()`` — has been observed to leave a
    *later*, unrelated test's ``capture_logs()`` unable to intercept
    that module's logger, so this suite keeps one app per handler under
    test rather than one app per scenario.
    """
    app = create_app()

    @app.get("/test-not-modified")
    async def _not_modified() -> None:
        raise HTTPException(status_code=status.HTTP_304_NOT_MODIFIED)

    @app.get("/test-structured-detail")
    async def _structured_detail() -> None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "bad_thing", "field": "email"},
        )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        not_found = await ac.get("/api/v1/does-not-exist")
        # Starlette attaches an `Allow` header to a 405; it must survive
        # being rewrapped into a ProblemDetail response.
        wrong_method = await ac.patch("/api/v1/users/")
        not_modified = await ac.get("/test-not-modified")
        structured = await ac.get("/test-structured-detail")

    assert not_found.status_code == status.HTTP_404_NOT_FOUND
    assert not_found.headers["content-type"] == "application/problem+json"
    not_found_body = not_found.json()
    assert not_found_body["type"] == "urn:quoin:error:not_found"
    assert not_found_body["title"] == "Not Found"
    assert not_found_body["status"] == status.HTTP_404_NOT_FOUND

    assert wrong_method.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    assert wrong_method.headers["content-type"] == "application/problem+json"
    assert "Allow" in wrong_method.headers
    assert wrong_method.json()["type"] == "urn:quoin:error:method_not_allowed"

    assert not_modified.status_code == status.HTTP_304_NOT_MODIFIED
    assert not_modified.content == b""
    assert "content-type" not in not_modified.headers

    assert structured.status_code == status.HTTP_400_BAD_REQUEST
    assert structured.headers["content-type"] == "application/problem+json"
    # Valid JSON, not "{'code': 'bad_thing', ...}".
    assert json.loads(structured.json()["detail"]) == {
        "code": "bad_thing",
        "field": "email",
    }
