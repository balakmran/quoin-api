import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


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
    """Schema for updating a user."""

    email: EmailStr | None = None
    full_name: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str | None) -> str | None:
        """Lowercase email so uniqueness checks are case-insensitive."""
        return value.lower() if value is not None else value


class UserRead(BaseModel):
    """Schema for reading a user."""

    id: uuid.UUID
    email: EmailStr
    full_name: str | None = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
