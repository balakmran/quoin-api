from app.core.exceptions import ConflictError, NotFoundError


class UserNotFoundError(NotFoundError):
    """Raised when a user is not found."""

    def __init__(self, user_id: str) -> None:
        """Initialize UserNotFoundError."""
        super().__init__(message=f"User with ID '{user_id}' not found")


class DuplicateEmailError(ConflictError):
    """Raised when email already exists."""

    def __init__(self, email: str) -> None:
        """Initialize DuplicateEmailError."""
        super().__init__(message=f"Email '{email}' is already registered")
