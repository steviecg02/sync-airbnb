"""Remove x_airbnb_client_trace_id column (auto-generated)

Revision ID: caf75040fccc
Revises: b173c060e492
Create Date: 2025-11-07 12:58:17.788519

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "caf75040fccc"
down_revision: str | Sequence[str] | None = "b173c060e492"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Remove x_airbnb_client_trace_id column from accounts table.

    This column is no longer needed as the trace ID is auto-generated per request
    in build_headers(). Testing confirmed Airbnb does not validate this header.
    """
    op.drop_column("accounts", "x_airbnb_client_trace_id", schema="airbnb")


def downgrade() -> None:
    """Restore x_airbnb_client_trace_id column to accounts table."""
    op.add_column(
        "accounts",
        sa.Column("x_airbnb_client_trace_id", sa.String(), nullable=False, server_default=""),
        schema="airbnb",
    )
