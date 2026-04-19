import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.openapi import APITag
from app.core.schemas import ErrorResponse
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
            "model": ErrorResponse,
            "description": "Unauthorized - Missing or invalid token",
        },
        403: {
            "model": ErrorResponse,
            "description": "Forbidden - Token lacks the required domain scope",
        },
        500: {
            "model": ErrorResponse,
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


@router.post(
    "/",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        409: {
            "model": ErrorResponse,
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


@router.get("/", response_model=list[UserRead])
async def list_users(
    service: Annotated[UserService, Depends(get_user_service)],
    caller: Annotated[ServicePrincipal, Depends(require_roles("users.read"))],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> list[User]:
    """List users."""
    return await service.list_users(skip, limit)


@router.get(
    "/{user_id}",
    response_model=UserRead,
    responses={
        404: {
            "model": ErrorResponse,
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
        404: {"model": ErrorResponse, "description": "User not found"},
        409: {
            "model": ErrorResponse,
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
            "model": ErrorResponse,
            "description": "User not found",
        }
    },
)
async def delete_user(
    user_id: uuid.UUID,
    service: Annotated[UserService, Depends(get_user_service)],
    caller: Annotated[ServicePrincipal, Depends(require_roles("users.write"))],
) -> None:
    """Delete a user."""
    await service.delete_user(user_id)
