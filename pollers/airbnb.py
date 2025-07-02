from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Dict, List
import requests
import json
import logging

from payloads.metrics import build_metric_payload
from payloads.listings import build_listings_payload
from flatteners.metrics import flatten_chart_query, flatten_list_of_metrics_query
from flatteners.listings import flatten_listing_ids
from flatteners.utils import coerce_number
from config import HEADERS

logger = logging.getLogger(__name__)


class AirbnbMetricPoller:
    _API_URLS = {
        "ChartQuery": "https://www.airbnb.com/api/v3/ChartQuery/aa6e318cc066bbf19511b86acdce32fc59219d8596448b861d794491f46631c5",
        "ListingsSectionQuery": "https://www.airbnb.com/api/v3/ListingsSectionQuery/7a646c07b45ad35335b2cde4842e5c5bf69ccebde508b2ba60276832bfb1816b",
        "ListOfMetricsQuery": "https://www.airbnb.com/api/v3/ListOfMetricsQuery/b22a5ded5e6c6d168f1d224b78f34182e7366e5cc65203ec04f1e718286a09e1"
    }

    _FLATTENER_BY_QUERY_TYPE = {
        "ChartQuery": flatten_chart_query,
        "ListOfMetricsQuery": flatten_list_of_metrics_query,
        "ListingsSectionQuery": flatten_listing_ids,
    }

    _PAYLOAD_BUILDER_BY_QUERY_TYPE = {
        "ChartQuery": build_metric_payload,
        "ListOfMetricsQuery": build_metric_payload,
        "ListingsSectionQuery": build_listings_payload,
    }

    MAX_METRIC_OFFSET_DAYS = 182  # Airbnb hard limit for relative offset range    

    def __init__(self, scrape_day: date, debug: bool = False):
        self.scrape_day = scrape_day
        self.debug = debug
        self.session = requests.Session()
        self._parsed_chunks: List[dict] = []  # store parsed results per device/poll

    def get_url(self, query_type: str) -> str:
        """
        Returns the Airbnb GraphQL API endpoint URL for a given query type.

        Args:
            query_type (str): The type of GraphQL query to execute. Must be one of
                              "ChartQuery", "ListOfMetricsQuery", or "ListingsSectionQuery".

        Returns:
            str: The full URL endpoint string associated with the given query type.

        Raises:
            ValueError: If the query_type is unsupported.
        """
        if query_type not in self._API_URLS:
            raise ValueError(f"Unsupported query type: {query_type}")
        return self._API_URLS[query_type]

    def build_payload(
        self,
        query_type: str,
        listing_id: str = None,
        offset_start: int = None,
        offset_end: int = None,
        metric_type: str = None,
        group_values: List[str] = None,
    ) -> Dict[str, Any]:
        """
        Builds the appropriate GraphQL payload for a given query type and listing.

        Args:
            query_type (str): One of "ChartQuery", "ListOfMetricsQuery", or "ListingsSectionQuery".
            listing_id (str, optional): Airbnb listing ID. Required for metric queries.
            offset_start (int, optional): Relative start offset in days from scrape day.
            offset_end (int, optional): Relative end offset in days from scrape day.
            metric_type (str, optional): Type of metric to query (e.g. "CONVERSION", "SEARCH").
            group_values (List[str], optional): Grouping values such as ["YOUR_LISTINGS", "SIMILAR_LISTINGS"].

        Returns:
            Dict[str, Any]: A dictionary representing the request payload to be sent to Airbnb's API.

        Raises:
            ValueError: If the query_type is not supported or missing a builder function.
        """
        builder = self._PAYLOAD_BUILDER_BY_QUERY_TYPE.get(query_type)
        if not builder:
            raise ValueError(f"No payload builder for query type: {query_type}")
        if query_type == "ListingsSectionQuery":
            return builder()
        return builder(
            query_type=query_type,
            listing_id=listing_id,
            offset_start=offset_start,
            offset_end=offset_end,
            metric_type=metric_type,
            group_values=group_values,
            include_comparison=(query_type == "ChartQuery"),
            debug=self.debug,
        )

    def poll(
        self,
        query_type: str,
        listing_id: str = "",
        listing_name: str = "",
        start_date: date = None,
        end_date: date = None,
        metric_type: str = None,
        group_values: List[str] = None,
    ) -> Dict[str, Any]:
        """
        Sends a GraphQL request to Airbnb's metrics API for the specified query type and parameters.

        Converts calendar dates to Airbnb-relative offsets (+2) and returns both the raw response
        and polling metadata for later flattening and debugging.
        
        This method constructs the request payload, logs it if debugging is enabled, performs the HTTP POST,
        and parses the response JSON. Used for both metrics and listings queries.

        Args:
            query_type (str): The GraphQL query type (e.g. "ChartQuery", "ListOfMetricsQuery").
            listing_id (str, optional): Airbnb listing ID for metrics queries.
            listing_name (str, optional): Airbnb listing name.
            start_date (date, optional): Start date.
            end_date (date, optional): End date.
            metric_type (str, optional): Metric category to request.
            group_values (List[str], optional): Groups to include (e.g. ["YOUR_LISTINGS"]).

        Returns:
            Dict[str, Any]: Parsed JSON response returned by Airbnb's GraphQL API.
        """
        if query_type == "ListingsSectionQuery":
            payload = self.build_payload(query_type=query_type)
            url = self.get_url(query_type)

            if self.debug:
                logger.debug("Listings payload:\n%s", json.dumps(payload, indent=2))

            res = self.session.post(url, json=payload, headers=HEADERS)
            res.raise_for_status()
            data = res.json()

            if self.debug:
                logger.debug("Listings response:\n%s", json.dumps(data, indent=2))

            return {"data": data, "meta": {"query_type": query_type}}

        offset_start = (start_date - self.scrape_day).days + 2
        offset_end = (end_date - self.scrape_day).days + 2

        url = self.get_url(query_type)
        payload = self.build_payload(
            query_type=query_type,
            listing_id=listing_id,
            offset_start=offset_start,
            offset_end=offset_end,
            metric_type=metric_type,
            group_values=group_values,
        )

        if self.debug:
            logger.debug("Payload for %s (%s):\n%s", query_type, listing_id, json.dumps(payload, indent=2))

        res = self.session.post(url, json=payload, headers=HEADERS)
        res.raise_for_status()
        data = res.json()

        if self.debug:
            logger.debug("Response from %s (%s):\n%s", query_type, listing_id, json.dumps(data, indent=2))

        return {
            "data": data,
            "meta": {
                "listing_id": listing_id,
                "listing_name": listing_name,
                "query_type": query_type,
                "metric_type": metric_type,
                "group_values": group_values,
                "window_start": start_date.isoformat(),
                "window_end": end_date.isoformat(),
                "offset_start": offset_start,
                "offset_end": offset_end
            },
        }

    def flatten(
        self,
        query_type: str,
        response: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Dispatches the raw API response to the appropriate flattener function based on query type.
        Attaches polling metadata to the flattened result.

        Args:
            query_type (str): The type of query executed (e.g. "ChartQuery", "ListOfMetricsQuery").
            response (Dict[str, Any]): The raw parsed JSON response returned by Airbnb.

        Returns:
            Dict[str, Any]: The structured result from the flattener. May include:
                - "timeseries_rows": List[Dict[str, Any]]
                - "primary_metric": Dict[str, Any]
                - "secondary_metrics": List[Dict[str, Any]]
            For ListingsSectionQuery, the return is a simple dict[str, str].

        Raises:
            ValueError: If no flattener is defined for the given query type.
        """
        flattener = self._FLATTENER_BY_QUERY_TYPE.get(query_type)
        if not flattener:
            raise ValueError(f"No flattener defined for query type: {query_type}")

        if query_type == "ListingsSectionQuery":
            result = flattener(response["data"])
            # Strip any attached meta keys (in case flatteners leak it)
            if isinstance(result, dict) and "meta" in result:
                result.pop("meta")
            return result

        result = flattener(
            response=response["data"],
        )
        
        result["meta"] = response.get("meta", {})

        if self.debug:
            logger.debug("Flattened output:\n%s", json.dumps(result, indent=2))

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
    ) -> Dict[str, Any]:
        """
        Polls a single date window and flattens the result, embedding window metadata.

        Args:
            query_type (str): The type of query to run (e.g. "ChartQuery", "ListOfMetricsQuery").
            listing_id (str): The Airbnb listing ID.
            listing_name (str): The name of the listing.
            start_date (date): Start date.
            end_date (date): End date.
            metric_type (str): Type of metric (e.g. "CONVERSION", "SEARCH").
            group_values (List[str]): Metric grouping (e.g. ["YOUR_LISTINGS", "SIMILAR_LISTINGS"]).

        Returns:
            Dict[str, Any]: Dictionary containing flattener output. Usually includes keys like:
                - "timeseries_rows": List[Dict[str, Any]]
                - "primary_metric": Dict[str, Any]
                - "secondary_metrics": List[Dict[str, Any]]
        """
        wrapped = self.poll(
            query_type=query_type,
            listing_id=listing_id,
            listing_name=listing_name,
            start_date=start_date,
            end_date=end_date,
            metric_type=metric_type,
            group_values=group_values,
        )
        return self.flatten(
            query_type=query_type,
            response=wrapped,
        )

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
        Polls metrics in rolling windows and flattens each result.

        Args:
            listing_id (str): Airbnb listing ID.
            listing_name (str): Display name for reference.
            query_type (str): "ChartQuery" or "ListOfMetricsQuery".
            metrics (list): List of (metric_type, group_values) pairs.
            start_date (date): Start of date range.
            end_date (date): End of date range (inclusive).
            window_size_days (int): Length of each rolling window in days.

        Returns:
            int: Returns the total number of polls completed 
        """
        results = []
        max_end_date = self.scrape_day + timedelta(days=182)
        if end_date > max_end_date:
            end_date = max_end_date

        current_start = start_date

        while current_start <= end_date:
            current_end = min(current_start + timedelta(days=window_size_days - 1), end_date)

            for metric_type, group_values in metrics:
                if self.debug:
                    logger.debug(
                        f"Polling {query_type} | {listing_name} ({listing_id}) | "
                        f"{metric_type} {group_values} | "
                        f"{current_start.isoformat()} → {current_end.isoformat()}"
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

    def fetch_listing_ids(self) -> dict[str, str]:
        """
        Fetches Airbnb listing IDs and their corresponding internal listing names
        using the ListingsSectionQuery GraphQL endpoint.

        Returns:
            dict[str, str]: A mapping of Airbnb listing ID → listing name.
        """
        raw = self.poll(
            query_type="ListingsSectionQuery",
            listing_id=None,
            start_date=self.scrape_day,
            end_date=self.scrape_day,
            metric_type=None,
            group_values=[],
        )
        return self.flatten(query_type="ListingsSectionQuery", response=raw)
    
    def debug_print_chunks(self):
        print(json.dumps(self._parsed_chunks, indent=2))

    def parse_all(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Wide-format timeseries_rows for ChartQuery: one row per listing × date,
        multiple metrics flattened into columns using metric + tag (your/similar).
        """
        results = {
            "chart_query": self._extract_chart_timeseries_rows(),
            "chart_summary": self._extract_chart_summary_metrics(),
            "list_of_metrics": self._extract_list_of_metrics(),
        }

        if self.debug:
            import json
            logger.debug("Parsed result from parse_all():\n%s", json.dumps(results, indent=2))

        return results

    @staticmethod
    def test_parse_all_from_file(path: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        For testing outside full script context. Load parsed_chunks and run parse_all logic.
        """
        with open(path, "r") as f:
            parsed_chunks = json.load(f)
        poller = AirbnbMetricPoller(scrape_day=date.today())
        poller._parsed_chunks = parsed_chunks
        return poller.parse_all()
    
    def _extract_chart_timeseries_rows(self) -> List[Dict[str, Any]]:
        """
        One row per listing × date, with multiple metric columns.
        Pivoted from ChartQuery responses.
        """
        from collections import defaultdict

        pivoted_rows = defaultdict(dict)

        for chunk in self._parsed_chunks:
            meta = chunk.get("meta", {})
            if meta.get("query_type") != "ChartQuery":
                continue

            airbnb_listing_id = meta.get("listing_id")
            airbnb_internal_name = meta.get("listing_name")
            # window_start = meta.get("window_start")
            # window_end = meta.get("window_end")
            # offset_start = meta.get("offset_start")
            # offset_end = meta.get("offset_end")
            metric_name = meta.get("group_values", ["unknown"])[0]

            for row in chunk.get("timeseries_rows", []):
                ds = row["ds"]
                tag = row.get("source_label", "")
                tag_key = "your" if "your" in tag.lower() else "similar"

                row_key = (airbnb_listing_id, ds)
                base = pivoted_rows[row_key]

                if not base:
                    base["airbnb_listing_id"] = airbnb_listing_id
                    base["airbnb_internal_name"] = airbnb_internal_name
                    base["date"] = ds
                    # base["window_start"] = window_start
                    # base["window_end"] = window_end
                    # base["offset_start"] = offset_start
                    # base["offset_end"] = offset_end

                base[f"{metric_name}_{tag_key}_value"] = coerce_number(row.get("value"))
                base[f"{metric_name}_{tag_key}_value_string"] = row.get("value_string")

        return list(pivoted_rows.values())

    def _extract_chart_summary_metrics(self) -> List[Dict[str, Any]]:
        """
        One row per listing per window.
        All primary + secondary ChartQuery metrics flattened into top-level columns.
        No suffixing — these are always 'your listing' metrics.
        """
        from collections import defaultdict

        summary_rows = defaultdict(dict)

        for chunk in self._parsed_chunks:
            meta = chunk.get("meta", {})
            if meta.get("query_type") != "ChartQuery":
                continue

            airbnb_listing_id = meta.get("listing_id")
            airbnb_internal_name = meta.get("listing_name")
            window_start = meta.get("window_start")
            window_end = meta.get("window_end")
            # offset_start = meta.get("offset_start")
            # offset_end = meta.get("offset_end")

            row_key = (airbnb_listing_id, window_start, window_end)
            row = summary_rows[row_key]

            if not row:
                row["airbnb_listing_id"] = airbnb_listing_id
                row["airbnb_internal_name"] = airbnb_internal_name
                row["window_start"] = window_start
                row["window_end"] = window_end
                # row["offset_start"] = offset_start
                # row["offset_end"] = offset_end

            # Primary metric
            primary = chunk.get("primary_metric", {})
            if primary:
                metric = primary.get("metric_name")
                row[f"{metric}_value"] = coerce_number(primary.get("value"))
                row[f"{metric}_value_string"] = primary.get("value_string")
                row[f"{metric}_value_change"] = coerce_number(primary.get("value_change"))
                row[f"{metric}_value_change_string"] = primary.get("value_change_string")

            # Secondary metrics
            for metric in chunk.get("secondary_metrics", []):
                name = metric.get("metric_name")
                row[f"{name}_value"] = coerce_number(metric.get("value"))
                row[f"{name}_value_string"] = metric.get("value_string")

        return list(summary_rows.values())

    def _extract_list_of_metrics(self) -> List[Dict[str, Any]]:
        """
        Wide-format row per listing per window from ListOfMetricsQuery.
        Each metric is flattened into columns: {metric_name}_value and _value_string.
        """
        from collections import defaultdict

        grouped_rows = defaultdict(dict)

        for chunk in self._parsed_chunks:
            meta = chunk.get("meta", {})
            if meta.get("query_type") != "ListOfMetricsQuery":
                continue

            airbnb_listing_id = meta.get("listing_id")
            airbnb_internal_name = meta.get("listing_name")
            window_start = meta.get("window_start")
            window_end = meta.get("window_end")
            # offset_start = meta.get("offset_start")
            # offset_end = meta.get("offset_end")

            row_key = (airbnb_listing_id, window_start, window_end)
            row = grouped_rows[row_key]

            if not row:
                row["airbnb_listing_id"] = airbnb_listing_id
                row["airbnb_internal_name"] = airbnb_internal_name
                row["window_start"] = window_start
                row["window_end"] = window_end
                # row["offset_start"] = offset_start
                # row["offset_end"] = offset_end

            for metric in chunk.get("timeseries_rows", []):
                metric_name = metric.get("metric_name")
                row[f"{metric_name}_value"] = coerce_number(metric.get("value"))
                row[f"{metric_name}_value_string"] = metric.get("value_string")

        return list(grouped_rows.values())