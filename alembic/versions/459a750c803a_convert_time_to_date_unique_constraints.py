"""Convert time to date + unique constraints

Revision ID: 459a750c803a
Revises: 8521f7bed1ac
Create Date: 2025-07-10 19:58:41.271161

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "459a750c803a"
down_revision: Union[str, Sequence[str], None] = "8521f7bed1ac"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Convert 'time' column from TIMESTAMP to DATE and set default to now()::date
    for table in [
        "airbnb_chart_query",
        "airbnb_chart_summary",
        "airbnb_list_of_metrics",
    ]:
        # Update existing values to DATE
        op.execute(f"UPDATE {table} SET time = time::date")

        # Drop existing column default
        op.execute(f"ALTER TABLE {table} ALTER COLUMN time DROP DEFAULT")

        # Alter type and set new default
        op.execute(f"ALTER TABLE {table} ALTER COLUMN time TYPE DATE USING time::date")
        op.execute(f"ALTER TABLE {table} ALTER COLUMN time SET DEFAULT (now()::date)")

    # Add unique constraints
    op.create_unique_constraint(
        "uq_airbnb_chart_query_listing_metric_date",
        "airbnb_chart_query",
        ["airbnb_listing_id", "metric_date", "time"],
    )
    op.create_unique_constraint(
        "uq_airbnb_chart_summary_listing_window",
        "airbnb_chart_summary",
        ["airbnb_listing_id", "window_start", "time"],
    )
    op.create_unique_constraint(
        "uq_airbnb_list_of_metrics_listing_window",
        "airbnb_list_of_metrics",
        ["airbnb_listing_id", "window_start", "time"],
    )


def downgrade():
    # Drop unique constraints
    op.drop_constraint(
        "uq_airbnb_chart_query_listing_metric_date",
        "airbnb_chart_query",
        type_="unique",
    )
    op.drop_constraint(
        "uq_airbnb_chart_summary_listing_window", "airbnb_chart_summary", type_="unique"
    )
    op.drop_constraint(
        "uq_airbnb_list_of_metrics_listing_window",
        "airbnb_list_of_metrics",
        type_="unique",
    )

    # Revert 'time' column back to TIMESTAMP with default now()
    for table in [
        "airbnb_chart_query",
        "airbnb_chart_summary",
        "airbnb_list_of_metrics",
    ]:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN time DROP DEFAULT")
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN time TYPE TIMESTAMP WITH TIME ZONE USING time::timestamp"
        )
        op.execute(f"ALTER TABLE {table} ALTER COLUMN time SET DEFAULT (now())")
