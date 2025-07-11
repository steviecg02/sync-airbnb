"""create airbnb performance tables

Revision ID: 8521f7bed1ac
Revises: 
Create Date: 2025-07-02 13:51:51.109315

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8521f7bed1ac"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Ensure TimescaleDB is enabled
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")

    # Time series table: chart_query
    op.create_table(
        "airbnb_chart_query",
        sa.Column(
            "time",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("airbnb_listing_id", sa.Text, nullable=False),
        sa.Column("airbnb_internal_name", sa.Text),
        sa.Column("metric_date", sa.Date, nullable=False),
        sa.Column("conversion_rate_your_value", sa.Float),
        sa.Column("conversion_rate_your_value_string", sa.Text),
        sa.Column("conversion_rate_similar_value", sa.Float),
        sa.Column("conversion_rate_similar_value_string", sa.Text),
        sa.Column("p3_impressions_your_value", sa.Integer),
        sa.Column("p3_impressions_your_value_string", sa.Text),
        sa.Column("p3_impressions_similar_value", sa.Integer),
        sa.Column("p3_impressions_similar_value_string", sa.Text),
    )
    op.execute(
        "SELECT create_hypertable('airbnb_chart_query', 'time', if_not_exists => TRUE);"
    )
    op.create_index(
        "ix_airbnb_chart_query_listing_date",
        "airbnb_chart_query",
        ["airbnb_listing_id", "metric_date", "time"],
    )

    # Weekly summary table: chart_summary
    op.create_table(
        "airbnb_chart_summary",
        sa.Column(
            "time",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("airbnb_listing_id", sa.Text, nullable=False),
        sa.Column("airbnb_internal_name", sa.Text),
        sa.Column("window_start", sa.Date, nullable=False),
        sa.Column("window_end", sa.Date, nullable=False),
        sa.Column("conversion_rate_value", sa.Float),
        sa.Column("conversion_rate_value_string", sa.Text),
        sa.Column("conversion_rate_value_change", sa.Float),
        sa.Column("conversion_rate_value_change_string", sa.Text),
        sa.Column("p2_impressions_first_page_rate_value", sa.Float),
        sa.Column("p2_impressions_first_page_rate_value_string", sa.Text),
        sa.Column("search_conversion_rate_value", sa.Float),
        sa.Column("search_conversion_rate_value_string", sa.Text),
        sa.Column("listing_conversion_rate_value", sa.Float),
        sa.Column("listing_conversion_rate_value_string", sa.Text),
        sa.Column("p3_impressions_value", sa.Integer),
        sa.Column("p3_impressions_value_string", sa.Text),
        sa.Column("p3_impressions_value_change", sa.Float),
        sa.Column("p3_impressions_value_change_string", sa.Text),
        sa.Column("p2_impressions_value", sa.Integer),
        sa.Column("p2_impressions_value_string", sa.Text),
    )
    op.execute(
        "SELECT create_hypertable('airbnb_chart_summary', 'time', if_not_exists => TRUE);"
    )
    op.create_index(
        "ix_airbnb_chart_summary_listing_date",
        "airbnb_chart_summary",
        ["airbnb_listing_id", "window_start", "time"],
    )

    # Weekly summary table: list_of_metrics
    op.create_table(
        "airbnb_list_of_metrics",
        sa.Column(
            "time",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("airbnb_listing_id", sa.Text, nullable=False),
        sa.Column("airbnb_internal_name", sa.Text),
        sa.Column("window_start", sa.Date, nullable=False),
        sa.Column("window_end", sa.Date, nullable=False),
        sa.Column("conversion_rate_value", sa.Float),
        sa.Column("conversion_rate_value_string", sa.Text),
        sa.Column("p2_impressions_first_page_rate_value", sa.Float),
        sa.Column("p2_impressions_first_page_rate_value_string", sa.Text),
        sa.Column("search_conversion_rate_value", sa.Float),
        sa.Column("search_conversion_rate_value_string", sa.Text),
        sa.Column("listing_conversion_rate_value", sa.Float),
        sa.Column("listing_conversion_rate_value_string", sa.Text),
        sa.Column("p3_impressions_value", sa.Integer),
        sa.Column("p3_impressions_value_string", sa.Text),
        sa.Column("p2_impressions_value", sa.Integer),
        sa.Column("p2_impressions_value_string", sa.Text),
    )
    op.execute(
        "SELECT create_hypertable('airbnb_list_of_metrics', 'time', if_not_exists => TRUE);"
    )
    op.create_index(
        "ix_airbnb_list_of_metrics_listing_date",
        "airbnb_list_of_metrics",
        ["airbnb_listing_id", "window_start", "time"],
    )


def downgrade():
    op.drop_table("airbnb_list_of_metrics")
    op.drop_table("airbnb_chart_summary")
    op.drop_table("airbnb_chart_query")
