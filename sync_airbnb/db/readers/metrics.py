"""Database readers for metrics tables."""

import logging
from datetime import date

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def get_chart_query_metrics(
    engine: Engine,
    account_id: str,
    start_date: date,
    end_date: date,
) -> list[dict]:
    """
    Get chart_query metrics for an account and date range.

    Args:
        engine: Database engine
        account_id: Account ID to fetch metrics for
        start_date: Start date (inclusive)
        end_date: End date (exclusive)

    Returns:
        List of metric rows as dictionaries
    """
    with engine.connect() as conn:
        query = text(
            """
            SELECT
                time,
                account_id,
                listing_id,
                listing_name,
                metric_id,
                home_page_views,
                contact_host_clicks,
                visitors_views,
                search_appearances
            FROM airbnb.chart_query
            WHERE account_id = :account_id
                AND time >= :start_date
                AND time < :end_date
            ORDER BY time DESC, listing_id
        """
        )

        result = conn.execute(
            query,
            {
                "account_id": account_id,
                "start_date": start_date,
                "end_date": end_date,
            },
        )

        return [dict(row._mapping) for row in result.fetchall()]


def get_list_of_metrics_metrics(
    engine: Engine,
    account_id: str,
    start_date: date,
    end_date: date,
) -> list[dict]:
    """
    Get list_of_metrics metrics for an account and date range.

    Args:
        engine: Database engine
        account_id: Account ID to fetch metrics for
        start_date: Start date (inclusive)
        end_date: End date (exclusive)

    Returns:
        List of metric rows as dictionaries
    """
    with engine.connect() as conn:
        query = text(
            """
            SELECT
                time,
                account_id,
                listing_id,
                listing_name,
                avg_occupancy_rate,
                avg_nightly_price,
                total_revenue,
                total_nights_booked,
                total_payouts,
                avg_lead_time
            FROM airbnb.list_of_metrics
            WHERE account_id = :account_id
                AND time >= :start_date
                AND time < :end_date
            ORDER BY time DESC, listing_id
        """
        )

        result = conn.execute(
            query,
            {
                "account_id": account_id,
                "start_date": start_date,
                "end_date": end_date,
            },
        )

        return [dict(row._mapping) for row in result.fetchall()]


def get_chart_summary_metrics(
    engine: Engine,
    account_id: str,
    start_date: date,
    end_date: date,
) -> list[dict]:
    """
    Get chart_summary metrics for an account and date range.

    Args:
        engine: Database engine
        account_id: Account ID to fetch metrics for
        start_date: Start date (inclusive)
        end_date: End date (exclusive)

    Returns:
        List of metric rows as dictionaries
    """
    with engine.connect() as conn:
        query = text(
            """
            SELECT
                time,
                account_id,
                listing_id,
                listing_name,
                metric_id,
                total_visitors
            FROM airbnb.chart_summary
            WHERE account_id = :account_id
                AND time >= :start_date
                AND time < :end_date
            ORDER BY time DESC, listing_id
        """
        )

        result = conn.execute(
            query,
            {
                "account_id": account_id,
                "start_date": start_date,
                "end_date": end_date,
            },
        )

        return [dict(row._mapping) for row in result.fetchall()]


def get_all_metrics(
    engine: Engine,
    account_id: str,
    start_date: date,
    end_date: date,
) -> dict[str, list[dict]]:
    """
    Get all metrics (chart_query, list_of_metrics, chart_summary) for an account.

    Args:
        engine: Database engine
        account_id: Account ID to fetch metrics for
        start_date: Start date (inclusive)
        end_date: End date (exclusive)

    Returns:
        Dictionary with keys: "chart_query", "list_of_metrics", "chart_summary"
    """
    return {
        "chart_query": get_chart_query_metrics(engine, account_id, start_date, end_date),
        "list_of_metrics": get_list_of_metrics_metrics(engine, account_id, start_date, end_date),
        "chart_summary": get_chart_summary_metrics(engine, account_id, start_date, end_date),
    }
