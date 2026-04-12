import pytest
from fastapi import FastAPI, status
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from app.core.exception_handlers import add_exception_handlers
from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    InternalServerError,
    NotFoundError,
    QuoinError,
)


def test_quoin_error_init() -> None:
    """Test QuoinError initialization."""
    err = QuoinError(
        message="Test Error",
        status_code=status.HTTP_400_BAD_REQUEST,
        headers={"X-Error": "True"},
    )
    assert err.message == "Test Error"
    assert err.status_code == status.HTTP_400_BAD_REQUEST
    assert err.headers == {"X-Error": "True"}


def test_internal_server_error_init() -> None:
    """Test InternalServerError initialization."""
    err = InternalServerError()
    assert err.message == "Internal Server Error"
    assert err.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert err.headers is None

    err_custom = InternalServerError(
        message="Custom Error", headers={"X-Custom": "1"}
    )
    assert err_custom.message == "Custom Error"
    assert err_custom.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert err_custom.headers == {"X-Custom": "1"}


@pytest.mark.asyncio
async def test_exception_handlers() -> None:
    """Test exception handlers via a temporary app."""
    app = FastAPI()
    add_exception_handlers(app)

    @app.get("/quoin_error")
    async def raise_quoin_error() -> None:
        raise QuoinError(
            message="Custom App Error", status_code=status.HTTP_418_IM_A_TEAPOT
        )

    @app.get("/generic_error")
    async def raise_generic_error() -> None:
        raise ValueError("Something went wrong")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        # Test QuoinError handler
        response = await ac.get("/quoin_error")
        assert response.status_code == status.HTTP_418_IM_A_TEAPOT
        assert response.json() == {"detail": "Custom App Error"}

        # Test generic exception handler (should raise exception)
        with pytest.raises(ValueError):
            await ac.get("/generic_error")


@pytest.mark.asyncio
async def test_not_found_error() -> None:
    """Test NotFoundError initialization and handler."""
    err = NotFoundError(message="User not found")
    assert err.message == "User not found"
    assert err.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_conflict_error() -> None:
    """Test ConflictError initialization and handler."""
    err = ConflictError(message="Email already exists")
    assert err.message == "Email already exists"
    assert err.status_code == status.HTTP_409_CONFLICT


@pytest.mark.asyncio
async def test_bad_request_error() -> None:
    """Test BadRequestError initialization and handler."""
    err = BadRequestError(message="Invalid input")
    assert err.message == "Invalid input"
    assert err.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_forbidden_error() -> None:
    """Test ForbiddenError initialization and handler."""
    err = ForbiddenError(message="Access denied")
    assert err.message == "Access denied"
    assert err.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_quoin_request_validation_error() -> None:
    """Test QuoinRequestValidationError initialization and errors method."""
    from app.core.exceptions import (  # noqa: PLC0415
        QuoinRequestValidationError,
        ValidationError,
    )

    # Create validation errors list
    errors: list[ValidationError] = [
        {
            "loc": ("field1",),
            "msg": "field required",
            "type": "missing",
            "input": {},
        },
        {
            "loc": ("field2",),
            "msg": "value is not a valid integer",
            "type": "int_parsing",
            "input": "not_an_int",
        },
    ]

    err = QuoinRequestValidationError(errors=errors)

    # Test that errors() method returns proper Pydantic error format
    pydantic_errors = err.errors()
    assert len(pydantic_errors) == 2  # noqa: PLR2004
    assert pydantic_errors[0]["loc"] == ("field1",)
    assert pydantic_errors[1]["loc"] == ("field2",)


@pytest.mark.asyncio
async def test_fastapi_request_validation_handling() -> None:
    """Test standard FastAPI parameter validations under Starlette >= 0.46.0."""
    app = FastAPI()
    add_exception_handlers(app)

    class Item(BaseModel):
        name: str
        price: float

    @app.post("/items/")
    async def create_item(item: Item) -> Item:
        return item

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        # Pass a bad payload to trigger FastAPI validation error
        response = await ac.post(
            "/items/", json={"name": "test", "price": "not_a_float"}
        )

        # Verify Starlette exception handler routes the 422 properly
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "detail" in response.json()
