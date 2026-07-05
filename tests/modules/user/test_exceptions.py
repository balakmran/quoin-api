import uuid

from fastapi import status

from app.modules.user.exceptions import (
    DuplicateEmailError,
    UserInUseError,
    UserNotFoundError,
)


def test_user_not_found_error() -> None:
    """Test UserNotFoundError initialization."""
    user_id = str(uuid.uuid4())
    err = UserNotFoundError(user_id=user_id)
    assert err.message == f"User with ID '{user_id}' not found"
    assert err.status_code == status.HTTP_404_NOT_FOUND


def test_duplicate_email_error() -> None:
    """Test DuplicateEmailError initialization."""
    email = "test@example.com"
    err = DuplicateEmailError(email=email)
    assert err.message == f"Email '{email}' is already registered"
    assert err.status_code == status.HTTP_409_CONFLICT


def test_user_in_use_error() -> None:
    """Test UserInUseError initialization."""
    user_id = str(uuid.uuid4())
    err = UserInUseError(user_id=user_id)
    assert err.message == (
        f"User '{user_id}' cannot be deleted: it is referenced by other records"
    )
    assert err.status_code == status.HTTP_409_CONFLICT
