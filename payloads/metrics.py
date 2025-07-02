def build_metric_payload(
    *,
    query_type: str,
    listing_id: str,
    offset_start: int,
    offset_end: int,
    metric_type: str,
    group_values: list,
    include_comparison: bool = False,
    debug: bool = False
):
    """
    Generic payload builder for Airbnb GraphQL metric queries.
    Accepts absolute offsets (+2 UI offset already applied by caller).
    """

    if query_type not in ("ListOfMetricsQuery", "ChartQuery"):
        raise ValueError(f"Unsupported query_type: {query_type}")

    sha256_hash = {
        "ListOfMetricsQuery": "b22a5ded5e6c6d168f1d224b78f34182e7366e5cc65203ec04f1e718286a09e1",
        "ChartQuery": "aa6e318cc066bbf19511b86acdce32fc59219d8596448b861d794491f46631c5"
    }[query_type]

    client_name = {
        "ListOfMetricsQuery": "web-performance-dash-metrics",
        "ChartQuery": "web-performance-dash-chart"
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
        "extensions": {
            "persistedQuery": {"version": 1, "sha256Hash": sha256_hash}
        }
    }

    return payload