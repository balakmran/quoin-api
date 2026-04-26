import uuid

from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.modules.user.models import User
from app.modules.user.schemas import UserCreate, UserUpdate


class UserRepository:
    """Repository for User persistence operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Bind the repository to an active database session.

        Args:
            session: The async session used for all database operations.
        """
        self.session = session

    async def create(self, user_create: UserCreate) -> User:
        """Persist a new User record and return it with DB-assigned fields.

        Args:
            user_create: Validated creation payload.

        Returns:
            The newly created User with id, created_at, and updated_at
            set.
        """
        db_user = User.model_validate(user_create)
        self.session.add(db_user)
        await self.session.commit()
        await self.session.refresh(db_user)
        return db_user

    async def get(self, user_id: uuid.UUID) -> User | None:
        """Fetch a single User by primary key.

        Args:
            user_id: UUID of the user to look up.

        Returns:
            The matching User, or None if not found.
        """
        return await self.session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        """Fetch a single User by email address.

        Args:
            email: Email address to search for (case-sensitive).

        Returns:
            The matching User, or None if not found.
        """
        statement = select(User).where(User.email == email)  # type: ignore
        result = await self.session.exec(statement)  # type: ignore
        return result.scalars().first()

    async def list(self, skip: int = 0, limit: int = 100) -> list[User]:
        """Fetch a paginated slice of all User records.

        Args:
            skip: Number of rows to skip (offset).
            limit: Maximum number of rows to return.

        Returns:
            Ordered list of User records; may be empty.
        """
        statement = select(User).offset(skip).limit(limit)
        result = await self.session.exec(statement)  # type: ignore
        return list(result.scalars().all())

    async def update(self, user: User, user_update: UserUpdate) -> User:
        """Apply a partial update to an existing User record.

        Only fields present in user_update (i.e. not unset) are written.

        Args:
            user: The User instance to mutate; must be attached to the
                session.
            user_update: Partial payload with fields to overwrite.

        Returns:
            The updated User with all fields refreshed from the database.
        """
        user_data = user_update.model_dump(exclude_unset=True)
        for key, value in user_data.items():
            setattr(user, key, value)
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def delete(self, user: User) -> None:
        """Remove a User record from the database.

        Args:
            user: The User instance to delete; must be attached to the
                session.
        """
        await self.session.delete(user)
        await self.session.commit()
