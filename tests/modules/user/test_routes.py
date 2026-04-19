import uuid

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.modules.user.models import User


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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
    assert response.status_code == status.HTTP_409_CONFLICT
    assert (
        response.json()["detail"]
        == "Email 'duplicate@example.com' is already registered"
    )


@pytest.mark.asyncio
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
    assert isinstance(data, list)
    assert len(data) >= 1
    # Check that pagination headers/metadata might be present in the future
    # Currently just returns a list


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_get_user_not_found(read_client: AsyncClient) -> None:
    """Test getting a non-existent user."""
    random_id = uuid.uuid4()
    response = await read_client.get(f"/api/v1/users/{random_id}")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_delete_user(admin_client: AsyncClient) -> None:
    """Test deleting a user (admin required)."""
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
