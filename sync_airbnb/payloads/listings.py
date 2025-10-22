import logging

logger = logging.getLogger(__name__)


def build_listings_payload() -> dict:
    """
    Build the GraphQL payload for the ListingsSectionQuery.

    This query is used to retrieve listing IDs and internal names,
    grouped by occupancy rate.

    Returns:
        dict: The full request payload for Airbnb's ListingsSectionQuery.
    """
    return {
        "operationName": "ListingsSectionQuery",
        "locale": "en",
        "currency": "USD",
        "variables": {
            "request": {
                "clientName": "web-performance-dash-listings",
                "arguments": {
                    "metricType": "CONVERSION",
                    "groupBys": ["RATING_CATEGORY"],
                    "groupByValues": ["occupancy_rate"],
                },
                "useStubbedData": False,
            }
        },
        "extensions": {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": "7a646c07b45ad35335b2cde4842e5c5bf69ccebde508b2ba60276832bfb1816b",
            }
        },
    }
