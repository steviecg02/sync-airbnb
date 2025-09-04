from typing import List, Dict
from datetime import date
import logging

logger = logging.getLogger(__name__)


def build_metric_payload(
    *,
    query_type: str,
    listing_id: str,
    start_date: date,
    end_date: date,
    scrape_day: date,
    metric_type: str,
    group_values: List[str],
    include_comparison: bool = False,
    debug: bool = False,
) -> Dict:
    """
    Build a GraphQL payload for Airbnb metric queries (ChartQuery or ListOfMetricsQuery).
    Applies Airbnb's known +2 offset from scrape_day to match UI behavior.

    Args:
        query_type: One of "ListOfMetricsQuery", "ChartQuery"
        listing_id: Airbnb listing ID to query
        start_date, end_date: Real dates to pull data for
        scrape_day: Date the poll is being run (used for Airbnb offset logic)
        metric_type: Airbnb metric type (e.g., "RATING", "BOOKING")
        group_values: Grouping values (e.g., ["RATING_CATEGORY"])
        include_comparison: If True, adds MARKET comparison
        debug: If True, logs full payload

    Returns:
        Dict: A GraphQL payload matching Airbnb's internal dashboard format
    """
    if query_type not in {"ListOfMetricsQuery", "ChartQuery"}:
        raise ValueError(f"Unsupported query_type: {query_type}")

    # Airbnb UI offset = +3
    offset_start = (start_date - scrape_day).days + 3
    offset_end = (end_date - scrape_day).days + 3

    sha256_hash = {
        "ListOfMetricsQuery": "b22a5ded5e6c6d168f1d224b78f34182e7366e5cc65203ec04f1e718286a09e1",
        "ChartQuery": "aa6e318cc066bbf19511b86acdce32fc59219d8596448b861d794491f46631c5",
    }[query_type]

    client_name = {
        "ListOfMetricsQuery": "web-performance-dash-metrics",
        "ChartQuery": "web-performance-dash-chart",
    }[query_type]

    arguments = {
        "relativeDsStart": offset_start,
        "relativeDsEnd": offset_end,
        "filters": {"listingIds": [listing_id]},
        "metricType": metric_type,
        "groupBys": ["RATING_CATEGORY"],
        "groupByValues": group_values,
    }

    if include_comparison:
        arguments["metricComparisonType"] = "MARKET"

    payload = {
        "operationName": query_type,
        "locale": "en",
        "currency": "USD",
        "variables": {
            "request": {
                "clientName": client_name,
                "arguments": arguments,
                "useStubbedData": False,
            }
        },
        "extensions": {"persistedQuery": {"version": 1, "sha256Hash": sha256_hash}},
    }

    if debug:
        logger.debug("Generated %s payload:\n%s", query_type, payload)

    return payload
