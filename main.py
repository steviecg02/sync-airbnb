import logging
from datetime import timedelta

from config import LOG_LEVEL, DEBUG, get_scrape_day, engine
from db.metrics import insert_chart_query_rows, insert_chart_summary_rows, insert_list_of_metrics_rows
from pollers.airbnb import AirbnbMetricPoller
from utils.logger import setup_logging

# --- Setup logging ---
setup_logging(LOG_LEVEL)
logger = logging.getLogger(__name__)

# --- Config ---
SCRAPE_DAY = get_scrape_day()
WINDOW_START = SCRAPE_DAY - timedelta(days=14)
WINDOW_END = SCRAPE_DAY + timedelta(days=180)
WINDOW_SIZE = 7

# What metrics to query (you control this)
METRIC_QUERIES = {
    "ChartQuery": [
        ("CONVERSION", ["conversion_rate"]),
        ("CONVERSION", ["p3_impressions"]),
    ],
    "ListOfMetricsQuery": [
        ("CONVERSION", ["conversion_rate"]),
        ("CONVERSION", ["p3_impressions"]),
    ]
}

def main():
    logger.info("Starting Airbnb metrics poller")

    poller = AirbnbMetricPoller(scrape_day=SCRAPE_DAY, debug=DEBUG)

    listings = poller.fetch_listing_ids()
    if not listings:
        logger.warning("No listings returned. Exiting.")
        return

    for listing_id, listing_name in sorted(listings.items(), key=lambda x: x[1]):
        logger.info(f"Polling {listing_name} ({listing_id})")

        for query_type, metrics in METRIC_QUERIES.items():
            poller.poll_range_and_flatten(
                listing_id=listing_id,
                listing_name=listing_name,
                query_type=query_type,
                metrics=metrics,
                start_date=WINDOW_START,
                end_date=WINDOW_END,
                window_size_days=WINDOW_SIZE,
            )

            logger.info(f"✔ {listing_name}: finished {query_type}")
    
    logger.info("✔ All polling complete. Parsed chunks across all devices and queries:")
    parsed_chunks = poller.parse_all()
    insert_chart_query_rows(engine, parsed_chunks["chart_query"])
    insert_chart_summary_rows(engine, parsed_chunks["chart_summary"])
    insert_list_of_metrics_rows(engine, parsed_chunks["list_of_metrics"])
    logger.info("✔ Database inserts complete.")    

if __name__ == "__main__":
    main()