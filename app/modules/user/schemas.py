import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from pydantic.json_schema import SkipJsonSchema


class UserBase(BaseModel):
    """Base user schema."""

    email: EmailStr = Field(max_length=255)
    full_name: str | None = Field(default=None, max_length=255)
    is_active: bool = True

    model_config = ConfigDict(extra="forbid")

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        """Lowercase email so uniqueness checks are case-insensitive."""
        return value.lower()


class UserCreate(UserBase):
    """Schema for creating a user."""

    pass


class UserUpdate(BaseModel):
    """Schema for partially updating a user.

    Every field may be omitted, but only ``full_name`` may be ``null``.
    The other columns are ``NOT NULL``, so an explicit null is rejected
    here as a 422 rather than failing the flush as a 500.
    """

    # `None` is only the "omitted" default, so it is kept out of the schema.
    email: EmailStr | SkipJsonSchema[None] = None
    full_name: str | None = Field(default=None, max_length=255)
    is_active: bool | SkipJsonSchema[None] = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("email", "is_active")
    @classmethod
    def _reject_null(cls, value: object) -> object:
        """Reject an explicit null; omit the field to leave it unchanged."""
        if value is None:
            raise ValueError("must not be null; omit the field instead")
        return value

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        """Lowercase email so uniqueness checks are case-insensitive."""
        return value.lower()


class UserRead(BaseModel):
    """Schema for reading a user."""

    id: uuid.UUID
    email: EmailStr
    full_name: str | None = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
