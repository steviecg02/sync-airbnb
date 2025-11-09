import logging
import random
import time
from datetime import date
from typing import Any

from sync_airbnb.config import DEBUG, engine
from sync_airbnb.db.insights import (
    insert_chart_query_rows,
    insert_list_of_metrics_rows,
)
from sync_airbnb.db.writers.accounts import update_last_sync
from sync_airbnb.metrics import (
    errors_total,
    sync_jobs_active,
    sync_jobs_duration_seconds,
    sync_jobs_total,
    sync_listings_processed_total,
)
from sync_airbnb.models.account import Account
from sync_airbnb.network.http_headers import build_headers
from sync_airbnb.utils.airbnb_sync import AirbnbSync
from sync_airbnb.utils.date_window import get_poll_window

logger = logging.getLogger(__name__)

# --- Poll Configuration ---
METRIC_QUERIES = {
    "ChartQuery": [
        # ("CONVERSION", ["conversion_rate"]),  # REMOVED: 25% traffic reduction
        #   - Daily conversion rates not needed (have 7-day aggregates in ListOfMetricsQuery)
        #   - Saves 49 API calls per listing per 25-week backfill (7 listings)
        #   - chart_query table conversion_rate_* columns will be NULL
        ("CONVERSION", ["p3_impressions"]),  # Keep: Daily page view counts for graphing
    ],
    "ListOfMetricsQuery": [
        ("CONVERSION", ["conversion_rate"]),  # Keep: Returns 4 metrics in one call!
        #   - conversion_rate (0.11% - Overall conversion)
        #   - search_conversion_rate (5.63% - Search to listing)
        #   - listing_conversion_rate (1.96% - Listing to booking)
        #   - p2_impressions_first_page_rate (69.9% - First page rate)
        ("CONVERSION", ["p3_impressions"]),  # Keep: Returns 2 metrics
        #   - p3_impressions (460 - Total page views)
        #   - p2_impressions (8166 - Total first-page search impressions)
    ],
}


def run_insights_poller(
    account: Account, scrape_day: date | None = None, trigger: str = "manual", force_full: bool = False
) -> dict[str, Any]:
    """
    Executes the full Airbnb insights polling workflow for a specific account.

    This function fetches ChartQuery and ListOfMetricsQuery data for a defined date window
    and listing set, flattens the results, and inserts them into the database.

    Per-listing error recovery ensures that one listing failure doesn't break the entire sync.

    Args:
        account (Account): Account object with credentials and last_sync_at timestamp
        scrape_day (date, optional): The logical "today" date. Defaults to date.today().
        trigger (str): How the sync was triggered (manual, scheduled, startup)
        force_full (bool): Force full backfill (ignore last_sync_at). Defaults to False.

    Returns:
        dict: Summary of sync results with counts and errors:
            {
                "total_listings": int,
                "succeeded": int,
                "failed": int,
                "errors": list[dict],
            }
    """
    if scrape_day is None:
        scrape_day = date.today()

    # Track sync job start
    sync_jobs_total.labels(account_id=account.account_id, trigger=trigger).inc()
    sync_jobs_active.inc()
    start_time = time.time()

    logger.info(f"Starting Airbnb Insights Poller for account {account.account_id}")

    # Calculate polling window based on whether this is first run OR force_full flag
    is_first_run = force_full or (account.last_sync_at is None)
    window_start, window_end = get_poll_window(is_first_run=is_first_run, today=scrape_day)
    logger.info(f"Sync window: {window_start} to {window_end} (first_run={is_first_run}, force_full={force_full})")

    # Step 1: Get fresh Akamai Bot Manager cookies via preflight
    logger.info("[PREFLIGHT] Requesting fresh Akamai cookies from Airbnb homepage...")
    from sync_airbnb.network.preflight import get_fresh_akamai_cookies
    from sync_airbnb.utils.cookie_utils import extract_auth_cookies, merge_cookies, parse_cookie_string

    try:
        # Extract auth cookies from stored cookie string (these are long-lived)
        auth_cookies = extract_auth_cookies(account.airbnb_cookie)
        logger.info(f"[COOKIES] Using {len(auth_cookies)} auth cookies: {list(auth_cookies.keys())}")

        # Get fresh Akamai cookies (these expire quickly and trigger bot detection if stale)
        fresh_akamai_cookies = get_fresh_akamai_cookies(
            user_agent=account.user_agent,
            auth_cookie=account.airbnb_cookie,
        )
        logger.info(
            f"[PREFLIGHT] Received {len(fresh_akamai_cookies)} fresh Akamai cookies: {list(fresh_akamai_cookies.keys())}"
        )

        # Merge auth + fresh Akamai cookies
        merged_cookie_string = merge_cookies(auth_cookies, fresh_akamai_cookies)
        merged_cookies = parse_cookie_string(merged_cookie_string)
        logger.info(
            f"[COOKIES] Merged cookie string has {len(merged_cookies)} total cookies "
            f"(auth: {len(auth_cookies)}, akamai: {len(fresh_akamai_cookies)})"
        )

    except Exception as e:
        logger.error(f"[PREFLIGHT] Failed to get fresh Akamai cookies: {e}")
        logger.warning("[PREFLIGHT] Continuing with stored cookies (may fail with auth errors)")
        merged_cookie_string = account.airbnb_cookie

    # Build headers from account credentials with merged cookies
    # Note: x_airbnb_client_trace_id is auto-generated in build_headers()
    headers = build_headers(
        airbnb_cookie=merged_cookie_string,
        x_client_version=account.x_client_version,
        user_agent=account.user_agent,
    )

    poller = AirbnbSync(scrape_day=scrape_day, debug=DEBUG, headers=headers)
    listings = poller.fetch_listing_ids()

    if not listings:
        logger.warning("No listings returned. Exiting.")
        return {"total_listings": 0, "succeeded": 0, "failed": 0, "errors": []}

    # Track results for observability
    results: dict[str, Any] = {"total_listings": len(listings), "succeeded": 0, "failed": 0, "errors": []}

    logger.info(f"Processing {len(listings)} listings for account {account.account_id}")

    for listing_idx, (listing_id, listing_name) in enumerate(sorted(listings.items(), key=lambda x: x[1])):
        try:
            logger.info(f"Processing listing {listing_id} ({listing_name})...")

            # Poll all queries for this listing
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

            # Parse and insert data for this listing
            parsed_chunks = poller.parse_all()

            # Add account_id to all rows before inserting
            for row in parsed_chunks["chart_query"]:
                row["account_id"] = account.account_id
            # chart_summary is skipped (not needed for analysis)
            # for row in parsed_chunks["chart_summary"]:
            #     row["account_id"] = account.account_id
            for row in parsed_chunks["list_of_metrics"]:
                row["account_id"] = account.account_id

            # Insert to database (each table separately to isolate failures)
            insert_chart_query_rows(engine, parsed_chunks["chart_query"])
            # insert_chart_summary_rows(engine, parsed_chunks["chart_summary"])  # Skipped: not needed
            insert_list_of_metrics_rows(engine, parsed_chunks["list_of_metrics"])

            results["succeeded"] += 1
            sync_listings_processed_total.labels(account_id=account.account_id, status="success").inc()
            logger.info(f"Listing {listing_id} ({listing_name}) completed successfully")

        except Exception as e:
            # Check if this is an auth failure - if so, stop immediately
            from sync_airbnb.network.http_client import AirbnbAuthError

            if isinstance(e, AirbnbAuthError):
                logger.error(
                    f"[AUTH_FAILURE] Authentication failed for account {account.account_id}. "
                    f"Stopping sync immediately. Please refresh cookies."
                )
                errors_total.labels(error_type="AirbnbAuthError", component="sync").inc()
                # Re-raise to stop all sync operations
                raise

            results["failed"] += 1
            sync_listings_processed_total.labels(account_id=account.account_id, status="failure").inc()
            errors_total.labels(error_type=type(e).__name__, component="sync").inc()
            error_detail = {
                "listing_id": listing_id,
                "listing_name": listing_name,
                "error": str(e),
                "error_type": type(e).__name__,
            }
            results["errors"].append(error_detail)
            logger.error(
                f"Listing {listing_id} ({listing_name}) failed: {error_detail['error_type']}: {e}",
                exc_info=True,
                extra=error_detail,
            )

        finally:
            # Always clear parsed chunks for next listing, even on error
            poller._parsed_chunks.clear()

            # Rate limiting: mimic human navigating between listings (15-30 seconds)
            if listing_idx < len(listings) - 1:  # Don't delay after last listing
                delay = random.uniform(15, 30)
                logger.info(f"[RATE_LIMIT] Waiting {delay:.1f}s before next listing...")
                time.sleep(delay)

    # Log summary
    logger.info(
        f"Sync complete for account {account.account_id}: "
        f"{results['succeeded']}/{results['total_listings']} succeeded, "
        f"{results['failed']} failed"
    )

    if results["errors"]:
        logger.warning(f"Errors occurred in {len(results['errors'])} listings:")
        for error in results["errors"]:
            logger.warning(f"  - {error['listing_id']} ({error['listing_name']}): {error['error_type']}")

    # Update last_sync_at timestamp (even if some listings failed)
    # This ensures we don't get stuck retrying the same window forever
    update_last_sync(engine, account.account_id)
    logger.info(f"Updated last_sync_at for account {account.account_id}")

    # Track sync job completion
    duration = time.time() - start_time
    status = "success" if results["failed"] == 0 else "partial_failure"
    sync_jobs_duration_seconds.labels(account_id=account.account_id, status=status).observe(duration)
    sync_jobs_active.dec()

    return results
