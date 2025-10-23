"""add soft delete to accounts

Revision ID: b173c060e492
Revises: c8fc3d1477cb
Create Date: 2025-10-23 11:10:10.070763

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b173c060e492"
down_revision: str | Sequence[str] | None = "c8fc3d1477cb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add deleted_at column for soft delete
    op.add_column(
        "accounts",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema="airbnb",
    )

    # Add index for efficient queries excluding deleted accounts
    op.create_index(
        "idx_accounts_deleted_at",
        "accounts",
        ["deleted_at"],
        schema="airbnb",
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop index first
    op.drop_index("idx_accounts_deleted_at", table_name="accounts", schema="airbnb")

    # Drop deleted_at column
    op.drop_column("accounts", "deleted_at", schema="airbnb")
