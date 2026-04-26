import uuid

from app.modules.user.exceptions import DuplicateEmailError, UserNotFoundError
from app.modules.user.models import User
from app.modules.user.repository import UserRepository
from app.modules.user.schemas import UserCreate, UserUpdate


class UserService:
    """Business-logic layer for User operations."""

    def __init__(self, repository: UserRepository) -> None:
        """Inject the repository used for all persistence operations.

        Args:
            repository: The UserRepository instance to delegate to.
        """
        self.repository = repository

    async def create_user(self, user_create: UserCreate) -> User:
        """Create a new user, enforcing email uniqueness.

        Args:
            user_create: Validated creation payload from the request.

        Returns:
            The persisted User with all DB-assigned fields populated.

        Raises:
            DuplicateEmailError: If the email is already registered.
        """
        existing_user = await self.repository.get_by_email(user_create.email)
        if existing_user:
            raise DuplicateEmailError(email=user_create.email)
        return await self.repository.create(user_create)

    async def get_user(self, user_id: uuid.UUID) -> User:
        """Retrieve a user by ID, raising if absent.

        Args:
            user_id: UUID of the user to retrieve.

        Returns:
            The matching User record.

        Raises:
            UserNotFoundError: If no user with user_id exists.
        """
        user = await self.repository.get(user_id)
        if not user:
            raise UserNotFoundError(user_id=str(user_id))
        return user

    async def list_users(self, skip: int = 0, limit: int = 100) -> list[User]:
        """Return a paginated list of users.

        Args:
            skip: Number of records to skip (offset).
            limit: Maximum number of records to return.

        Returns:
            Ordered list of User records; may be empty.
        """
        return await self.repository.list(skip, limit)

    async def update_user(
        self, user_id: uuid.UUID, user_update: UserUpdate
    ) -> User:
        """Apply a partial update to an existing user.

        Validates that the new email (if changed) is not already taken
        by another account before writing to the database.

        Args:
            user_id: UUID of the user to update.
            user_update: Partial payload; unset fields are left unchanged.

        Returns:
            The updated User with refreshed field values.

        Raises:
            UserNotFoundError: If no user with user_id exists.
            DuplicateEmailError: If the new email belongs to another user.
        """
        user = await self.get_user(user_id)
        if user_update.email is not None and user_update.email != user.email:
            existing = await self.repository.get_by_email(
                str(user_update.email)
            )
            if existing and existing.id != user_id:
                raise DuplicateEmailError(email=str(user_update.email))
        return await self.repository.update(user, user_update)

    async def delete_user(self, user_id: uuid.UUID) -> None:
        """Delete a user by ID.

        Args:
            user_id: UUID of the user to remove.

        Raises:
            UserNotFoundError: If no user with user_id exists.
        """
        user = await self.get_user(user_id)
        await self.repository.delete(user)
