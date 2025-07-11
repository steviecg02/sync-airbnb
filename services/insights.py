import logging
from utils.airbnb_sync import AirbnbSync
from config import DEBUG, engine
from datetime import date
from db.insights import (
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


# Temporary: assume this is not the first run
def is_first_run() -> bool:
    return False


def run_insights_poller(window_start: date, window_end: date, scrape_day: date):
    """
    Executes the full Airbnb insights polling workflow.

    This function fetches ChartQuery and ListOfMetricsQuery data for a defined date window
    and listing set, flattens the results, and inserts them into the database.

    Args:
        window_start (date): Start date of the polling window (aligned to Sunday).
        window_end (date): End date of the polling window (aligned to Saturday).
        scrape_day (date): The logical "today" date used to anchor offset calculations.
                           This controls how far forward Airbnb allows data retrieval.

    Raises:
        Any exceptions raised by the underlying sync or insert logic are logged.
    """
    logger.info("🔁 Starting Airbnb Insights Poller")

    poller = AirbnbSync(scrape_day=scrape_day, debug=DEBUG)
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

    parsed_chunks = poller.parse_all()
    logger.info("🧱 Polling complete. Inserting to DB...")

    insert_chart_query_rows(engine, parsed_chunks["chart_query"])
    insert_chart_summary_rows(engine, parsed_chunks["chart_summary"])
    insert_list_of_metrics_rows(engine, parsed_chunks["list_of_metrics"])

    logger.info("✅ Database inserts complete.")
