"""Unit tests for the shared pagination/sort primitives."""

from typing import Any

import pytest
from sqlalchemy import column

from app.core.exceptions import BadRequestError
from app.core.pagination import parse_sort

_ALLOWED: dict[str, Any] = {
    "created_at": column("created_at"),
    "email": column("email"),
}
_DEFAULT = [column("created_at").asc()]


def _names(terms: list[Any]) -> list[str]:
    """Return ``(column, direction)`` names for asserting order-by terms."""
    return [
        f"{t.element.name} {t.modifier.__name__.removesuffix('_op')}"
        for t in terms
    ]


def test_parse_sort_none_returns_default() -> None:
    """No sort value falls back to the caller's default ordering."""
    assert parse_sort(None, _ALLOWED, default=_DEFAULT) == _DEFAULT


def test_parse_sort_respects_direction_prefix() -> None:
    """A leading ``-`` selects descending; bare names are ascending."""
    terms = parse_sort("-created_at,email", _ALLOWED, default=_DEFAULT)
    assert _names(terms) == ["created_at desc", "email asc"]


def test_parse_sort_skips_empty_segments() -> None:
    """Blank segments from stray commas are ignored, not errors."""
    terms = parse_sort(" , email , ", _ALLOWED, default=_DEFAULT)
    assert _names(terms) == ["email asc"]


def test_parse_sort_all_empty_segments_falls_back_to_default() -> None:
    """A value of only commas yields the default ordering."""
    assert parse_sort(",,", _ALLOWED, default=_DEFAULT) == _DEFAULT


def test_parse_sort_unknown_field_raises() -> None:
    """A non-whitelisted field is a 400, and the message lists options."""
    with pytest.raises(BadRequestError) as exc_info:
        parse_sort("password", _ALLOWED, default=_DEFAULT)
    assert "Sortable fields: created_at, email" in exc_info.value.message
