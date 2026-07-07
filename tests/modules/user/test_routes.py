import uuid
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.modules.user.exceptions import DuplicateEmailError
from app.modules.user.models import User
from app.modules.user.repository import UserRepository
from app.modules.user.schemas import UserCreate, UserUpdate


async def test_create_user(admin_client: AsyncClient) -> None:
    """Test creating a new user (admin required)."""
    response = await admin_client.post(
        "/api/v1/users/",
        json={"email": "test@example.com", "full_name": "Test User"},
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["full_name"] == "Test User"
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


async def test_create_user_duplicate_email(admin_client: AsyncClient) -> None:
    """Test creating a user with a duplicate email."""
    # Create the first user
    await admin_client.post(
        "/api/v1/users/",
        json={"email": "duplicate@example.com", "full_name": "User 1"},
    )

    # Try to create a second user with the same email
    response = await admin_client.post(
        "/api/v1/users/",
        json={"email": "duplicate@example.com", "full_name": "User 2"},
    )
    body = response.json()
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.headers["content-type"] == "application/problem+json"
    assert body["type"] == "urn:quoin:error:duplicate_email_error"
    assert body["status"] == status.HTTP_409_CONFLICT
    assert (
        body["detail"] == "Email 'duplicate@example.com' is already registered"
    )


async def test_list_users(
    read_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test listing users (read access)."""
    # Create a user directly via DB
    user = User(email="list@example.com", full_name="List User")
    db_session.add(user)
    await db_session.commit()

    response = await read_client.get("/api/v1/users/")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert isinstance(data["items"], list)
    assert len(data["items"]) >= 1
    assert data["total"] >= 1
    assert data["limit"] == 100  # noqa: PLR2004
    assert data["offset"] == 0


async def test_get_user(
    read_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test getting a user by ID (read access)."""
    user = User(email="get@example.com", full_name="Get User")
    db_session.add(user)
    await db_session.commit()

    # Get the user (read required)
    response = await read_client.get(f"/api/v1/users/{user.id}")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["email"] == "get@example.com"
    assert data["id"] == str(user.id)


async def test_get_user_not_found(read_client: AsyncClient) -> None:
    """Test getting a non-existent user."""
    random_id = uuid.uuid4()
    response = await read_client.get(f"/api/v1/users/{random_id}")
    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_update_user(admin_client: AsyncClient) -> None:
    """Test updating a user (admin required)."""
    # Create a user
    create_res = await admin_client.post(
        "/api/v1/users/",
        json={"email": "update@example.com", "full_name": "Original Name"},
    )
    user_id = create_res.json()["id"]

    # Update the user
    response = await admin_client.patch(
        f"/api/v1/users/{user_id}",
        json={"full_name": "Updated Name"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["full_name"] == "Updated Name"


async def test_delete_user(admin_client: AsyncClient) -> None:
    """Soft delete hides the user from reads and returns 204."""
    # Create a user
    create_res = await admin_client.post(
        "/api/v1/users/",
        json={"email": "delete@example.com", "full_name": "Delete Me"},
    )
    user_id = create_res.json()["id"]

    # Delete the user
    response = await admin_client.delete(f"/api/v1/users/{user_id}")
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert response.content == b""  # 204 has no content

    # Verify deletion by attempting to get the user
    get_res = await admin_client.get(f"/api/v1/users/{user_id}")
    assert get_res.status_code == status.HTTP_404_NOT_FOUND

    # A soft-deleted user is excluded from listings too
    list_res = await admin_client.get("/api/v1/users/?limit=100")
    ids = [row["id"] for row in list_res.json()["items"]]
    assert user_id not in ids


async def test_delete_user_frees_email_for_reuse(
    admin_client: AsyncClient,
) -> None:
    """A tombstoned email can be registered again (partial unique index)."""
    first = await admin_client.post(
        "/api/v1/users/",
        json={"email": "reuse@example.com"},
    )
    await admin_client.delete(f"/api/v1/users/{first.json()['id']}")

    second = await admin_client.post(
        "/api/v1/users/",
        json={"email": "reuse@example.com"},
    )
    assert second.status_code == status.HTTP_201_CREATED
    assert second.json()["id"] != first.json()["id"]


async def test_delete_user_twice_returns_404(
    admin_client: AsyncClient,
) -> None:
    """Deleting an already soft-deleted user is a 404, not a repeat 204."""
    created = await admin_client.post(
        "/api/v1/users/",
        json={"email": "delete-twice@example.com"},
    )
    user_id = created.json()["id"]

    first = await admin_client.delete(f"/api/v1/users/{user_id}")
    assert first.status_code == status.HTTP_204_NO_CONTENT

    second = await admin_client.delete(f"/api/v1/users/{user_id}")
    assert second.status_code == status.HTTP_404_NOT_FOUND


async def test_update_user_email_to_new_valid_email(
    admin_client: AsyncClient,
) -> None:
    """PATCH email to a fresh address that is not taken returns 200."""
    create_res = await admin_client.post(
        "/api/v1/users/",
        json={"email": "before-change@example.com"},
    )
    user_id = create_res.json()["id"]

    response = await admin_client.patch(
        f"/api/v1/users/{user_id}",
        json={"email": "after-change@example.com"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["email"] == "after-change@example.com"


async def test_update_user_duplicate_email(admin_client: AsyncClient) -> None:
    """PATCH with an email already taken by another user returns 409."""
    r1 = await admin_client.post(
        "/api/v1/users/",
        json={"email": "patch-owner@example.com"},
    )
    await admin_client.post(
        "/api/v1/users/",
        json={"email": "patch-taken@example.com"},
    )
    user1_id = r1.json()["id"]

    response = await admin_client.patch(
        f"/api/v1/users/{user1_id}",
        json={"email": "patch-taken@example.com"},
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    assert "already registered" in response.json()["detail"]


async def test_list_users_stable_order(
    read_client: AsyncClient, db_session: AsyncSession
) -> None:
    """B1 regression: list_users orders by created_at, id (no overlap/gap)."""
    users = [
        User(email=f"order-{i}@example.com", full_name=f"Order {i}")
        for i in range(3)
    ]
    for user in users:
        db_session.add(user)
        await db_session.commit()

    page1 = await read_client.get("/api/v1/users/?offset=0&limit=2")
    page2 = await read_client.get("/api/v1/users/?offset=2&limit=2")

    ids_page1 = [row["id"] for row in page1.json()["items"]]
    ids_page2 = [row["id"] for row in page2.json()["items"]]
    assert not set(ids_page1) & set(ids_page2)

    full = await read_client.get("/api/v1/users/?offset=0&limit=100")
    emails = [row["email"] for row in full.json()["items"]]
    # created_at is monotonic with insertion order, so the three seeded
    # users must appear in that order in the full listing.
    seeded = [e for e in emails if e.startswith("order-")]
    assert seeded == [
        "order-0@example.com",
        "order-1@example.com",
        "order-2@example.com",
    ]


async def test_list_users_total_ignores_pagination(
    read_client: AsyncClient, db_session: AsyncSession
) -> None:
    """The envelope total counts all matches, not just the page slice."""
    for i in range(3):
        db_session.add(User(email=f"total-{i}@example.com"))
    await db_session.commit()

    response = await read_client.get("/api/v1/users/?limit=1")
    body = response.json()
    assert len(body["items"]) == 1
    assert body["total"] >= 3  # noqa: PLR2004


async def test_list_users_sort_descending(
    read_client: AsyncClient, db_session: AsyncSession
) -> None:
    """`sort=-email` orders the page by email descending."""
    for name in ("sort-a", "sort-b", "sort-c"):
        db_session.add(User(email=f"{name}@example.com"))
    await db_session.commit()

    response = await read_client.get(
        "/api/v1/users/?sort=-email&q=sort-&limit=100"
    )
    emails = [row["email"] for row in response.json()["items"]]
    assert emails == [
        "sort-c@example.com",
        "sort-b@example.com",
        "sort-a@example.com",
    ]


async def test_list_users_sort_rejects_unknown_field(
    read_client: AsyncClient,
) -> None:
    """An un-sortable field is a 400, not a 500."""
    response = await read_client.get("/api/v1/users/?sort=password")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Sortable fields" in response.json()["detail"]


async def test_list_users_filter_is_active(
    read_client: AsyncClient, db_session: AsyncSession
) -> None:
    """`is_active=false` returns only inactive users."""
    db_session.add(User(email="active@example.com", is_active=True))
    db_session.add(User(email="inactive@example.com", is_active=False))
    await db_session.commit()

    response = await read_client.get("/api/v1/users/?is_active=false&limit=100")
    emails = [row["email"] for row in response.json()["items"]]
    assert "inactive@example.com" in emails
    assert "active@example.com" not in emails


async def test_list_users_filter_search(
    read_client: AsyncClient, db_session: AsyncSession
) -> None:
    """`q` matches case-insensitively on email and full name."""
    db_session.add(User(email="findme@example.com", full_name="Alice"))
    db_session.add(User(email="other@example.com", full_name="Bob"))
    await db_session.commit()

    by_email = await read_client.get("/api/v1/users/?q=FINDME&limit=100")
    emails = [row["email"] for row in by_email.json()["items"]]
    assert emails == ["findme@example.com"]

    by_name = await read_client.get("/api/v1/users/?q=alice&limit=100")
    names = [row["full_name"] for row in by_name.json()["items"]]
    assert names == ["Alice"]


async def test_repository_create_race_returns_duplicate_email_error(
    db_session: AsyncSession,
) -> None:
    """B2 regression: a commit-time uniqueness violation raises 409, not 500.

    Simulates two concurrent creates racing past the service's
    get_by_email pre-check by calling the repository directly twice.
    """
    repository = UserRepository(db_session)
    user_create = UserCreate(email="race@example.com")
    await repository.create(user_create)

    with pytest.raises(DuplicateEmailError):
        await repository.create(user_create)


async def test_repository_update_race_returns_duplicate_email_error(
    db_session: AsyncSession,
) -> None:
    """B2 regression: an update-time uniqueness violation raises 409."""
    repository = UserRepository(db_session)
    await repository.create(UserCreate(email="update-race-taken@example.com"))
    victim = await repository.create(
        UserCreate(email="update-race-victim@example.com")
    )

    with pytest.raises(DuplicateEmailError):
        await repository.update(
            victim, UserUpdate(email="update-race-taken@example.com")
        )


async def test_repository_create_other_integrity_error_propagates() -> None:
    """An IntegrityError from an unrelated constraint isn't mislabeled.

    Only a violation of the email-uniqueness index should be translated
    to DuplicateEmailError; anything else must propagate unchanged.
    """
    mock_orig = Mock(spec=["constraint_name", "__cause__"])
    mock_orig.constraint_name = "some_other_constraint"
    mock_orig.__cause__ = None
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.flush.side_effect = IntegrityError("INSERT", {}, mock_orig)
    repository = UserRepository(mock_session)

    with pytest.raises(IntegrityError):
        await repository.create(UserCreate(email="other@example.com"))


async def test_repository_update_other_integrity_error_propagates() -> None:
    """A non-email IntegrityError on update propagates unchanged.

    Also exercises the constraint-name lookup when no exception in the
    ``__cause__`` chain exposes ``constraint_name`` at all, so the
    violation is correctly treated as "not an email uniqueness" error.
    """
    mock_orig = Mock(spec=["__cause__"])
    mock_orig.__cause__ = None
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.flush.side_effect = IntegrityError("UPDATE", {}, mock_orig)
    repository = UserRepository(mock_session)
    user = User(email="orig@example.com")

    with pytest.raises(IntegrityError):
        await repository.update(user, UserUpdate(full_name="New Name"))


async def test_create_user_full_name_too_long_returns_422(
    admin_client: AsyncClient,
) -> None:
    """B6 regression: an over-length full_name is rejected before Postgres."""
    response = await admin_client.post(
        "/api/v1/users/",
        json={
            "email": "toolong@example.com",
            "full_name": "x" * 300,
        },
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


async def test_create_user_email_normalized_and_case_insensitive_duplicate(
    admin_client: AsyncClient,
) -> None:
    """B7 regression: emails are lowercased and compared case-insensitively."""
    create_res = await admin_client.post(
        "/api/v1/users/",
        json={"email": "Mixed.Case@Example.com"},
    )
    assert create_res.status_code == status.HTTP_201_CREATED
    assert create_res.json()["email"] == "mixed.case@example.com"

    dup_res = await admin_client.post(
        "/api/v1/users/",
        json={"email": "mixed.case@EXAMPLE.com"},
    )
    assert dup_res.status_code == status.HTTP_409_CONFLICT
