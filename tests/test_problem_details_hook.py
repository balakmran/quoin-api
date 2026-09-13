"""The problem-details contract hook rejects what it claims to reject.

The hook runs on every response in the suite, so a check in it that
silently passes would weaken every test at once.
"""

from typing import Any

import pytest
from httpx2 import Request, Response

from tests.conftest import _assert_problem_details_contract

_PATH = "/api/v1/users/42"


def _response(
    status: int,
    body: Any,
    *,
    method: str = "GET",
    media_type: str = "application/problem+json",
) -> Response:
    """Build an error response to the request for ``_PATH``."""
    return Response(
        status,
        content=body if isinstance(body, bytes) else None,
        json=None if isinstance(body, bytes) else body,
        headers={"content-type": media_type, "x-request-id": "abc"},
        request=Request(method, f"http://test{_PATH}?q=1"),
    )


def _problem(**overrides: Any) -> dict[str, Any]:
    """A valid problem body for a 404 on ``_PATH``."""
    return {
        "title": "Not Found",
        "status": 404,
        "detail": "User not found",
        "instance": _PATH,
        **overrides,
    }


async def test_valid_problem_passes() -> None:
    """A well-formed body whose query string is not in ``instance``."""
    await _assert_problem_details_contract(_response(404, _problem()))


async def test_success_response_is_not_checked() -> None:
    """Non-error responses are outside the contract."""
    await _assert_problem_details_contract(
        _response(200, b"ok", media_type="text/plain")
    )


async def test_head_response_checks_headers_only() -> None:
    """``HEAD`` carries no body to validate."""
    await _assert_problem_details_contract(_response(404, b"", method="HEAD"))


@pytest.mark.parametrize(
    ("body", "match"),
    [
        (_problem(status=500), "body status 500"),
        (_problem(instance="/elsewhere"), "instance '/elsewhere'"),
        (_problem(title=None), "validation error"),
        (b"not json", "Invalid JSON"),
    ],
    ids=["status", "instance", "shape", "json"],
)
async def test_malformed_problem_fails(body: Any, match: str) -> None:
    """Each body check fails on its own violation."""
    with pytest.raises((AssertionError, ValueError), match=match):
        await _assert_problem_details_contract(_response(404, body))
