import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class UserBase(BaseModel):
    """Base user schema."""

    email: EmailStr
    full_name: str | None = None
    is_active: bool = True

    model_config = ConfigDict(extra="forbid")


class UserCreate(UserBase):
    """Schema for creating a user."""

    pass


class UserUpdate(BaseModel):
    """Schema for updating a user."""

    email: EmailStr | None = None
    full_name: str | None = None
    is_active: bool | None = None

    model_config = ConfigDict(extra="forbid")


class UserRead(BaseModel):
    """Schema for reading a user."""

    id: uuid.UUID
    email: EmailStr
    full_name: str | None = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
