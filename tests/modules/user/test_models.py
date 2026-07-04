import uuid

from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession


async def test_timestamps_have_server_side_defaults(
    db_session: AsyncSession,
) -> None:
    """B8 regression: a raw-SQL insert without timestamps still succeeds."""
    user_id = uuid.uuid4()
    await db_session.exec(  # type: ignore
        text(
            "INSERT INTO users (id, email, full_name, is_active) "
            "VALUES (:id, :email, :full_name, :is_active)"
        ),
        params={
            "id": user_id,
            "email": "raw-insert@example.com",
            "full_name": "Raw Insert",
            "is_active": True,
        },
    )
    await db_session.commit()

    row = (
        await db_session.exec(  # type: ignore
            text("SELECT created_at, updated_at FROM users WHERE id = :id"),
            params={"id": user_id},
        )
    ).first()

    assert row is not None
    assert row[0] is not None
    assert row[1] is not None
