import logging
from sync_airbnb.utils.airbnb_sync import AirbnbSync
from sync_airbnb.utils.date_window import get_poll_window
from sync_airbnb.config import DEBUG, engine
from sync_airbnb.models.account import Account
from sync_airbnb.network.http_headers import build_headers
from sync_airbnb.db.writers.accounts import update_last_sync
from datetime import date
from sync_airbnb.db.insights import (
    insert_chart_query_rows,
    insert_chart_summary_rows,
    insert_list_of_metrics_rows,
)

logger = logging.getLogger(__name__)

# --- Poll Configuration ---
METRIC_QUERIES = {
    "ChartQuery": [
        ("CONVERSION", ["conversion_rate"]),
        ("CONVERSION", ["p3_impressions"]),
    ],
    "ListOfMetricsQuery": [
        ("CONVERSION", ["conversion_rate"]),
        ("CONVERSION", ["p3_impressions"]),
    ],
}


def run_insights_poller(account: Account, scrape_day: date | None = None):
    """
    Executes the full Airbnb insights polling workflow for a specific account.

    This function fetches ChartQuery and ListOfMetricsQuery data for a defined date window
    and listing set, flattens the results, and inserts them into the database.

    Args:
        account (Account): Account object with credentials and last_sync_at timestamp
        scrape_day (date, optional): The logical "today" date. Defaults to date.today().

    Raises:
        Any exceptions raised by the underlying sync or insert logic are logged.
    """
    if scrape_day is None:
        scrape_day = date.today()

    logger.info(f"🔁 Starting Airbnb Insights Poller for account {account.account_id}")

    # Calculate polling window based on whether this is first run
    is_first_run = account.last_sync_at is None
    window_start, window_end = get_poll_window(is_first_run=is_first_run, today=scrape_day)

    # Build headers from account credentials
    headers = build_headers(
        airbnb_cookie=account.airbnb_cookie,
        x_client_version=account.x_client_version,
        x_airbnb_client_trace_id=account.x_airbnb_client_trace_id,
        user_agent=account.user_agent,
    )

    poller = AirbnbSync(scrape_day=scrape_day, debug=DEBUG, headers=headers)
    listings = poller.fetch_listing_ids()

    if not listings:
        logger.warning("No listings returned. Exiting.")
        return

    for listing_id, listing_name in sorted(listings.items(), key=lambda x: x[1]):
        logger.info(f"📡 Polling {listing_name} ({listing_id})")

        for query_type, metrics in METRIC_QUERIES.items():
            poller.poll_range_and_flatten(
                listing_id=listing_id,
                listing_name=listing_name,
                query_type=query_type,
                metrics=metrics,
                start_date=window_start,
                end_date=window_end,
                window_size_days=28 if query_type == "ChartQuery" else 7,
            )

        logger.info(f"✅ Finished polling all queries for {listing_name}")

        # Parse and insert data for this listing
        parsed_chunks = poller.parse_all()
        logger.info(f"🧱 Inserting {listing_name} data to DB...")

        # Add account_id to all rows before inserting
        for row in parsed_chunks["chart_query"]:
            row["account_id"] = account.account_id
        for row in parsed_chunks["chart_summary"]:
            row["account_id"] = account.account_id
        for row in parsed_chunks["list_of_metrics"]:
            row["account_id"] = account.account_id

        insert_chart_query_rows(engine, parsed_chunks["chart_query"])
        insert_chart_summary_rows(engine, parsed_chunks["chart_summary"])
        insert_list_of_metrics_rows(engine, parsed_chunks["list_of_metrics"])

        logger.info(f"✅ Inserted {listing_name} data to DB")

        # Clear parsed chunks for next listing
        poller._parsed_chunks.clear()

    logger.info("✅ All listings processed and inserted.")

    # Update last_sync_at timestamp
    update_last_sync(engine, account.account_id)
    logger.info(f"✅ Updated last_sync_at for account {account.account_id}")
