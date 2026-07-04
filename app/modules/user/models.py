import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Index, func, literal_column
from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    """User model."""

    __tablename__ = "users"
    __table_args__ = (
        Index(
            "ix_users_email_lower",
            func.lower(literal_column("email")),
            unique=True,
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: str = Field(index=True, max_length=255)
    full_name: str | None = Field(default=None, max_length=255)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
            onupdate=lambda: datetime.now(UTC),
        ),
    )
