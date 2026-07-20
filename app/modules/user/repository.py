import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.pagination import PageParams, parse_sort
from app.modules.user.exceptions import DuplicateEmailError
from app.modules.user.models import User
from app.modules.user.schemas import UserCreate, UserUpdate

_EMAIL_UNIQUE_CONSTRAINT = "ix_users_email_lower"

#: Fields the list endpoint may sort on, mapped to their columns.
USER_SORTABLE: dict[str, Any] = {
    "created_at": User.created_at,
    "updated_at": User.updated_at,
    "email": User.email,
    "full_name": User.full_name,
}


def _is_email_uniqueness_violation(exc: IntegrityError) -> bool:
    """Check whether an IntegrityError was raised by the email index.

    The DBAPI driver (asyncpg) raises its own error type, which
    SQLAlchemy's dialect wraps in turn before setting it as ``.orig``.
    The attribute carrying the constraint name lives on whichever
    exception in that ``__cause__`` chain actually came from the
    driver, so this walks the chain instead of only checking ``.orig``
    itself.

    Args:
        exc: The IntegrityError caught around a flush.

    Returns:
        True if the underlying DB error names the unique index on
        lower(email); False for any other constraint violation.
    """
    error: BaseException | None = exc.orig
    while error is not None:
        constraint_name = getattr(error, "constraint_name", None)
        if constraint_name is not None:
            return constraint_name == _EMAIL_UNIQUE_CONSTRAINT
        error = error.__cause__
    return False


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

        Raises:
            DuplicateEmailError: If a concurrent insert already
                committed this email between the service's pre-check
                and this write.
            IntegrityError: If the flush fails for any other reason.
        """
        db_user = User.model_validate(user_create)
        self.session.add(db_user)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            if not _is_email_uniqueness_violation(exc):
                raise
            raise DuplicateEmailError(email=user_create.email) from exc
        await self.session.refresh(db_user)
        return db_user

    async def get(self, user_id: uuid.UUID) -> User | None:
        """Fetch a single live User by primary key.

        Soft-deleted users (``deleted_at`` set) are treated as absent.

        Args:
            user_id: UUID of the user to look up.

        Returns:
            The matching live User, or None if not found or deleted.
        """
        statement = select(User).where(
            User.id == user_id,  # type: ignore
            User.deleted_at.is_(None),  # type: ignore
        )
        result = await self.session.exec(statement)  # type: ignore
        return result.scalars().first()

    async def get_by_email(self, email: str) -> User | None:
        """Fetch a single live User by email address.

        Soft-deleted users are ignored, so a tombstoned email is free to
        be registered again.

        Args:
            email: Email address to search for (case-insensitive).

        Returns:
            The matching live User, or None if not found or deleted.
        """
        statement = select(User).where(
            User.email == email.lower(),  # type: ignore
            User.deleted_at.is_(None),  # type: ignore
        )
        result = await self.session.exec(statement)  # type: ignore
        return result.scalars().first()

    @staticmethod
    def _apply_filters(
        statement: Select[Any],
        *,
        is_active: bool | None,
        q: str | None,
    ) -> Select[Any]:
        """Apply the shared list filters to a select statement.

        The same predicates back both the page query and its total
        count, so they live in one place.

        Args:
            statement: The base select to constrain.
            is_active: When set, restrict to users with this active flag.
            q: When set, case-insensitive substring match on email or
                full name.

        Returns:
            The statement with any requested filters applied.
        """
        # Soft-deleted rows are excluded from every listing.
        statement = statement.where(User.deleted_at.is_(None))  # type: ignore
        if is_active is not None:
            statement = statement.where(User.is_active == is_active)  # type: ignore
        if q:
            pattern = f"%{q.lower()}%"
            statement = statement.where(
                or_(
                    func.lower(User.email).like(pattern),
                    func.lower(User.full_name).like(pattern),
                )
            )
        return statement

    async def list(
        self,
        params: PageParams,
        *,
        sort: str | None = None,
        is_active: bool | None = None,
        q: str | None = None,
    ) -> tuple[list[User], int]:
        """Fetch a filtered, sorted page of User records and its total.

        Args:
            params: Pagination window (limit/offset).
            sort: Comma-separated sort fields (``-`` prefix for
                descending); defaults to ``created_at`` ascending.
            is_active: Optional exact filter on the active flag.
            q: Optional case-insensitive substring on email/full name.

        Returns:
            A ``(rows, total)`` tuple where ``total`` counts all rows
            matching the filters, ignoring pagination.

        Raises:
            BadRequestError: If ``sort`` names a non-sortable field.
        """
        order_by = parse_sort(
            sort,
            USER_SORTABLE,
            default=[User.created_at.asc()],  # type: ignore
        )
        rows_stmt = (
            self._apply_filters(select(User), is_active=is_active, q=q)
            .order_by(*order_by, User.id)  # type: ignore
            .offset(params.offset)
            .limit(params.limit)
        )
        result = await self.session.exec(rows_stmt)  # type: ignore
        rows = list(result.scalars().all())

        count_stmt = self._apply_filters(
            select(func.count()).select_from(User), is_active=is_active, q=q
        )
        total = (await self.session.exec(count_stmt)).scalars().one()  # type: ignore
        return rows, total

    async def update(self, user: User, user_update: UserUpdate) -> User:
        """Apply a partial update to an existing User record.

        Only fields present in user_update (i.e. not unset) are written.

        Args:
            user: The User instance to mutate; must be attached to the
                session.
            user_update: Partial payload with fields to overwrite.

        Returns:
            The updated User with all fields refreshed from the database.

        Raises:
            DuplicateEmailError: If a concurrent write already
                committed the new email between the service's
                pre-check and this write.
            IntegrityError: If the flush fails for any other reason.
        """
        user_data = user_update.model_dump(exclude_unset=True)
        for key, value in user_data.items():
            setattr(user, key, value)
        new_email = user.email
        self.session.add(user)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            if not _is_email_uniqueness_violation(exc):
                raise
            raise DuplicateEmailError(email=new_email) from exc
        await self.session.refresh(user)
        return user

    async def delete(self, user: User) -> None:
        """Soft-delete a User by stamping its ``deleted_at`` tombstone.

        The row is retained; subsequent reads exclude it and its email
        frees up for re-registration (via the partial unique index).
        ``is_active`` is left untouched — it is an independent,
        client-controlled business flag, not a lifecycle marker.

        Args:
            user: The live User instance to soft-delete; must be
                attached to the session.
        """
        user.deleted_at = datetime.now(UTC)
        self.session.add(user)
        await self.session.flush()
