"""Shared pagination and sorting primitives for list endpoints.

Every module's list endpoint returns the same envelope (`Page`) and
accepts the same pagination/sort query parameters, so paginated
responses share one shape across the whole API. Module-specific
*filters* stay explicit query parameters on each route — only the
pagination and sort conventions live here.

Typical usage in a route::

    @router.get("/", response_model=Page[WidgetRead])
    async def list_widgets(
        service: Annotated[WidgetService, Depends(get_widget_service)],
        page: Annotated[PageParams, Depends()],
        sort: Annotated[str | None, Query()] = None,
    ) -> Page[Widget]:
        return await service.list_widgets(page, sort)

and in the repository::

    order_by = parse_sort(sort, WIDGET_SORTABLE, default=[Widget.id])
    ...
"""

from collections.abc import Mapping, Sequence
from typing import Annotated, Any

from fastapi import Query
from pydantic import BaseModel, Field
from sqlalchemy import UnaryExpression

from app.core.exceptions import BadRequestError

#: Default number of rows returned when the client omits ``limit``.
DEFAULT_LIMIT = 100

#: Hard upper bound on ``limit`` to cap the cost of any single query.
MAX_LIMIT = 100


class PageParams:
    """Offset-based pagination parameters shared by list endpoints.

    Declared as a FastAPI dependency (``Depends()``) so ``limit`` and
    ``offset`` appear as documented query parameters with consistent
    bounds on every list route.
    """

    def __init__(
        self,
        limit: Annotated[
            int,
            Query(ge=1, le=MAX_LIMIT, description="Maximum rows to return."),
        ] = DEFAULT_LIMIT,
        offset: Annotated[
            int,
            Query(ge=0, description="Rows to skip before the page."),
        ] = 0,
    ) -> None:
        """Capture the validated pagination window.

        Args:
            limit: Maximum number of rows to return (1..``MAX_LIMIT``).
            offset: Number of rows to skip before the current page.
        """
        self.limit = limit
        self.offset = offset


class Page[T](BaseModel):
    """Standard list-response envelope.

    Attributes:
        items: The rows on the current page.
        total: Total rows matching the query, ignoring pagination.
        limit: Maximum rows requested for this page.
        offset: Rows skipped before this page.
    """

    items: list[T]
    total: int = Field(ge=0, description="Total rows matching the query.")
    limit: int = Field(ge=1, description="Maximum rows requested.")
    offset: int = Field(ge=0, description="Rows skipped before this page.")

    @classmethod
    def create(
        cls, items: Sequence[T], total: int, params: PageParams
    ) -> Page[T]:
        """Build a page from a row slice, its total, and the params.

        Args:
            items: The rows on the current page.
            total: Total rows matching the query, ignoring pagination.
            params: The pagination window the slice was fetched with.

        Returns:
            A populated ``Page`` envelope.
        """
        return cls(
            items=list(items),
            total=total,
            limit=params.limit,
            offset=params.offset,
        )


def parse_sort(
    value: str | None,
    allowed: Mapping[str, Any],
    default: Sequence[UnaryExpression[Any]],
) -> list[UnaryExpression[Any]]:
    """Parse the ``sort`` query parameter into SQLAlchemy order-by terms.

    The value is a comma-separated list of field names, each optionally
    prefixed with ``-`` for descending order (e.g. ``-created_at,email``).
    Only fields present in ``allowed`` may be sorted on; anything else is
    a client error.

    Args:
        value: Raw ``sort`` query value, or None/empty for the default.
        allowed: Map of sortable field name to its model column.
        default: Order-by terms applied when ``value`` is empty. Callers
            should include a unique column (e.g. the primary key) so the
            ordering is total and pagination stays stable.

    Returns:
        Order-by expressions in the requested order. A stable tiebreaker
        is *not* appended here; repositories append their primary key.

    Raises:
        BadRequestError: If a requested field is not in ``allowed``.
    """
    if not value or not value.strip():
        return list(default)

    terms: list[UnaryExpression[Any]] = []
    for raw in value.split(","):
        field = raw.strip()
        if not field:
            continue
        descending = field.startswith("-")
        name = field[1:] if descending else field
        column = allowed.get(name)
        if column is None:
            raise BadRequestError(
                message=(
                    f"Cannot sort by '{name}'. Sortable fields: "
                    f"{', '.join(sorted(allowed))}."
                )
            )
        terms.append(column.desc() if descending else column.asc())
    return terms or list(default)
