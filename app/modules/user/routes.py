import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.openapi import APITag
from app.core.pagination import Page, PageParams
from app.core.schemas import ProblemDetail
from app.core.security import ServicePrincipal, require_roles
from app.db.session import get_session
from app.modules.user.models import User
from app.modules.user.repository import UserRepository
from app.modules.user.schemas import UserCreate, UserRead, UserUpdate
from app.modules.user.service import UserService

router = APIRouter(
    prefix="/users",
    tags=[APITag.users],
    responses={
        401: {
            "model": ProblemDetail,
            "description": "Unauthorized - Missing or invalid token",
        },
        403: {
            "model": ProblemDetail,
            "description": "Forbidden - Token lacks the required domain scope",
        },
        500: {
            "model": ProblemDetail,
            "description": "Internal Server Error",
        },
    },
)


def get_user_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserService:
    """Get the user service."""
    repository = UserRepository(session)
    return UserService(repository)


class UserListQuery:
    """Sort and filter query parameters for listing users.

    Module-specific filters live in a dependency (rather than loose
    route arguments) so the route signature stays flat and the filter
    surface is documented in one place. Pagination is separate
    (`PageParams`) because it is shared by every module.
    """

    def __init__(
        self,
        sort: Annotated[
            str | None,
            Query(description="Sort fields, e.g. `-created_at,email`."),
        ] = None,
        is_active: Annotated[
            bool | None, Query(description="Filter by active flag.")
        ] = None,
        q: Annotated[
            str | None,
            Query(description="Case-insensitive search on email/full name."),
        ] = None,
    ) -> None:
        """Capture the validated sort and filter inputs.

        Args:
            sort: Comma-separated sort fields (``-`` prefix descending).
            is_active: Optional exact filter on the active flag.
            q: Optional case-insensitive substring on email/full name.
        """
        self.sort = sort
        self.is_active = is_active
        self.q = q


@router.post(
    "/",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        409: {
            "model": ProblemDetail,
            "description": "User with this email already exists",
        }
    },
)
async def create_user(
    user_create: UserCreate,
    service: Annotated[UserService, Depends(get_user_service)],
    caller: Annotated[ServicePrincipal, Depends(require_roles("users.write"))],
) -> User:
    """Create a new user."""
    return await service.create_user(user_create)


@router.get("/", response_model=Page[UserRead])
async def list_users(
    service: Annotated[UserService, Depends(get_user_service)],
    caller: Annotated[ServicePrincipal, Depends(require_roles("users.read"))],
    page: Annotated[PageParams, Depends()],
    query: Annotated[UserListQuery, Depends()],
) -> Page[User]:
    """List users with pagination, sorting, and filtering."""
    rows, total = await service.list_users(
        page, sort=query.sort, is_active=query.is_active, q=query.q
    )
    return Page.create(rows, total, page)


@router.get(
    "/{user_id}",
    response_model=UserRead,
    responses={
        404: {
            "model": ProblemDetail,
            "description": "User not found",
        }
    },
)
async def get_user(
    user_id: uuid.UUID,
    service: Annotated[UserService, Depends(get_user_service)],
    caller: Annotated[ServicePrincipal, Depends(require_roles("users.read"))],
) -> User:
    """Get a user by ID."""
    return await service.get_user(user_id)


@router.patch(
    "/{user_id}",
    response_model=UserRead,
    responses={
        404: {"model": ProblemDetail, "description": "User not found"},
        409: {
            "model": ProblemDetail,
            "description": "Email already registered to another user",
        },
    },
)
async def update_user(
    user_id: uuid.UUID,
    user_update: UserUpdate,
    service: Annotated[UserService, Depends(get_user_service)],
    caller: Annotated[ServicePrincipal, Depends(require_roles("users.write"))],
) -> User:
    """Update a user."""
    return await service.update_user(user_id, user_update)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {
            "model": ProblemDetail,
            "description": "User not found",
        },
    },
)
async def delete_user(
    user_id: uuid.UUID,
    service: Annotated[UserService, Depends(get_user_service)],
    caller: Annotated[ServicePrincipal, Depends(require_roles("users.write"))],
) -> None:
    """Soft-delete a user (sets the deleted_at tombstone)."""
    await service.delete_user(user_id)
