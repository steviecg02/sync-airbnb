import logging
import json
from datetime import date, timedelta
from typing import Any, Dict, List

from network.http_client import post_with_retry
from network.http_headers import HEADERS
from payloads.insights import build_metric_payload
from payloads.listings import build_listings_payload
from flatteners.insights import flatten_chart_query, flatten_list_of_metrics_query
from flatteners.listings import flatten_listing_ids
from parsers.insights import parse_all

logger = logging.getLogger(__name__)


class AirbnbSync:
    """
    Core interface for fetching and transforming Airbnb GraphQL metrics data.
    """

    _API_URLS = {
        "ChartQuery": "https://www.airbnb.com/api/v3/ChartQuery/aa6e318cc066bbf19511b86acdce32fc59219d8596448b861d794491f46631c5",
        "ListingsSectionQuery": "https://www.airbnb.com/api/v3/ListingsSectionQuery/7a646c07b45ad35335b2cde4842e5c5bf69ccebde508b2ba60276832bfb1816b",
        "ListOfMetricsQuery": "https://www.airbnb.com/api/v3/ListOfMetricsQuery/b22a5ded5e6c6d168f1d224b78f34182e7366e5cc65203ec04f1e718286a09e1",
    }

    _FLATTENER_BY_QUERY_TYPE = {
        "ChartQuery": flatten_chart_query,
        "ListOfMetricsQuery": flatten_list_of_metrics_query,
        "ListingsSectionQuery": flatten_listing_ids,
    }

    MAX_METRIC_OFFSET_DAYS = 182

    def __init__(self, scrape_day: date, debug: bool = False):
        """
        Args:
            scrape_day (date): Anchor date for calculating relative offsets in GraphQL payloads.
            debug (bool): If True, logs full payloads and responses.
        """
        self.scrape_day = scrape_day
        self.debug = debug
        self._parsed_chunks: List[dict] = []

    def get_url(self, query_type: str) -> str:
        """
        Returns the GraphQL endpoint URL for a given query type.

        Args:
            query_type (str): "ChartQuery", "ListOfMetricsQuery", or "ListingsSectionQuery"

        Returns:
            str: URL string

        Raises:
            ValueError: If unsupported query_type
        """
        if query_type not in self._API_URLS:
            raise ValueError(f"Unsupported query type: {query_type}")
        return self._API_URLS[query_type]

    def fetch_listing_ids(self) -> dict[str, str]:
        """
        Fetch Airbnb listing ID → name mappings using ListingsSectionQuery.

        Returns:
            dict[str, str]: {listing_id: internal_name}
        """
        response = self.poll(
            query_type="ListingsSectionQuery",
            listing_id=None,
            start_date=self.scrape_day,
            end_date=self.scrape_day,
        )
        return self.flatten("ListingsSectionQuery", response)

    def poll(
        self,
        query_type: str,
        listing_id: str = "",
        listing_name: str = "",
        start_date: date = None,
        end_date: date = None,
        metric_type: str = None,
        group_values: List[str] = None,
    ) -> dict:
        """
        Poll the Airbnb API with correct payload based on query_type.

        Args:
            query_type (str): GraphQL query type
            listing_id (str): Listing ID (metrics only)
            listing_name (str): Listing name (for logging/meta)
            start_date (date): Start of polling window
            end_date (date): End of polling window
            metric_type (str): "CONVERSION", "SEARCH", etc.
            group_values (List[str]): ["conversion_rate"], etc.

        Returns:
            dict: {
                "data": raw parsed response,
                "meta": request metadata
            }
        """
        url = self.get_url(query_type)

        if query_type == "ListingsSectionQuery":
            payload = build_listings_payload()
        else:
            if not (listing_id and start_date and end_date):
                raise ValueError("Missing required arguments for metric query")

            payload = build_metric_payload(
                query_type=query_type,
                listing_id=listing_id,
                start_date=start_date,
                end_date=end_date,
                scrape_day=self.scrape_day,
                metric_type=metric_type,
                group_values=group_values,
                include_comparison=(query_type == "ChartQuery"),
                debug=self.debug,
            )

        if self.debug:
            logger.debug(f"[{query_type}] Payload:\n%s", json.dumps(payload, indent=2))

        response = post_with_retry(url=url, headers=HEADERS, json=payload)

        if self.debug:
            logger.debug(
                f"[{query_type}] Response:\n%s", json.dumps(response, indent=2)
            )

        return {
            "data": response,
            "meta": {
                "query_type": query_type,
                "listing_id": listing_id,
                "listing_name": listing_name,
                "metric_type": metric_type,
                "group_values": group_values,
                "window_start": start_date.isoformat() if start_date else None,
                "window_end": end_date.isoformat() if end_date else None,
            },
        }

    def flatten(self, query_type: str, response: dict) -> dict:
        """
        Apply appropriate flattener to raw GraphQL response.

        Args:
            query_type (str): "ChartQuery", etc.
            response (dict): Raw parsed API response

        Returns:
            dict: Flattened result
        """
        flattener = self._FLATTENER_BY_QUERY_TYPE.get(query_type)
        if not flattener:
            raise ValueError(f"No flattener for query type: {query_type}")

        result = flattener(response["data"])

        if query_type != "ListingsSectionQuery":
            result["meta"] = response.get("meta", {})

        if self.debug:
            logger.debug("Flattened result:\n%s", json.dumps(result, indent=2))

        return result

    def poll_and_flatten(
        self,
        query_type: str,
        listing_id: str,
        listing_name: str,
        start_date: date,
        end_date: date,
        metric_type: str,
        group_values: List[str],
    ) -> dict:
        """
        Poll and flatten a single time window.

        Returns:
            dict: Flattened result including meta
        """
        response = self.poll(
            query_type=query_type,
            listing_id=listing_id,
            listing_name=listing_name,
            start_date=start_date,
            end_date=end_date,
            metric_type=metric_type,
            group_values=group_values,
        )
        return self.flatten(query_type, response)

    def poll_range_and_flatten(
        self,
        listing_id: str,
        listing_name: str,
        query_type: str,
        metrics: List[tuple],
        start_date: date,
        end_date: date,
        window_size_days: int,
    ) -> int:
        """
        Polls metrics in aligned rolling intervals and flattens results into _parsed_chunks.

        Args:
            listing_id (str): Airbnb listing ID.
            listing_name (str): Display name.
            query_type (str): "ChartQuery" or "ListOfMetricsQuery".
            metrics (list): List of (metric_type, group_values) pairs.
            start_date (date): Start of polling window.
            end_date (date): End of polling window.
            window_size_days (int): Size of each interval (7 for ListOfMetricsQuery, 28 for ChartQuery).

        Returns:
            int: Number of successful parsed chunks.
        """
        max_end_date = self.scrape_day + timedelta(days=self.MAX_METRIC_OFFSET_DAYS)
        if end_date > max_end_date:
            raise ValueError(
                f"Polling end date {end_date} exceeds Airbnb offset limit {max_end_date}. "
                f"Adjust LOOKAHEAD_WEEKS or scrape_day."
            )

        current_start = start_date
        while current_start <= end_date:
            current_end = min(
                current_start + timedelta(days=window_size_days - 1), end_date
            )

            for metric_type, group_values in metrics:
                if self.debug:
                    logger.debug(
                        f"Polling {query_type} | {listing_name} ({listing_id}) | "
                        f"{metric_type} {group_values} | {current_start} → {current_end}"
                    )
                try:
                    flat = self.poll_and_flatten(
                        query_type=query_type,
                        listing_id=listing_id,
                        listing_name=listing_name,
                        start_date=current_start,
                        end_date=current_end,
                        metric_type=metric_type,
                        group_values=group_values,
                    )
                    self._parsed_chunks.append(flat)
                except Exception as e:
                    logger.error(
                        f"{query_type} failed for {listing_id} ({current_start} – {current_end}): {e}"
                    )

            current_start = current_end + timedelta(days=1)

        return len(self._parsed_chunks)

    def parse_all(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Run the final parser layer to produce wide-format metrics rows.

        Returns:
            dict: {chart_query, chart_summary, list_of_metrics}
        """
        return parse_all(self._parsed_chunks)

    def debug_print_chunks(self):
        """
        Print raw parsed chunks for debugging.
        """
        print(json.dumps(self._parsed_chunks, indent=2))
