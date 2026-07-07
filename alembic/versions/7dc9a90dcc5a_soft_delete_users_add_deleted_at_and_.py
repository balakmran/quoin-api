"""Soft delete users: add deleted_at and partial unique email index.

Revision ID: 7dc9a90dcc5a
Revises: f023486abc0e
Create Date: 2026-07-06 23:28:52.897775

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7dc9a90dcc5a"
down_revision: str | Sequence[str] | None = "f023486abc0e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Recreate the case-insensitive unique email index as a *partial*
    # index so a soft-deleted row (deleted_at set) keeps its email but no
    # longer blocks re-registration of that address. Autogenerate cannot
    # diff the WHERE clause on a functional index, so this is hand-written.
    op.drop_index("ix_users_email_lower", table_name="users")
    op.create_index(
        "ix_users_email_lower",
        "users",
        [sa.literal_column("lower(email)")],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_users_email_lower", table_name="users")
    op.create_index(
        "ix_users_email_lower",
        "users",
        [sa.literal_column("lower(email)")],
        unique=True,
    )
    op.drop_column("users", "deleted_at")
