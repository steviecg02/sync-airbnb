import json
import logging
from collections import defaultdict
from typing import Any

from sync_airbnb.flatteners.utils import coerce_number

logger = logging.getLogger(__name__)


def parse_all(chunks: list[dict[str, Any]], debug: bool = False) -> dict[str, list[dict[str, Any]]]:
    """
    Parse all metric chunks from Airbnb flatteners into pivoted wide-format outputs.

    Args:
        chunks (List[Dict[str, Any]]): List of flattened poller responses.
        debug (bool): If True, logs full parsed output.

    Returns:
        Dict[str, List[Dict[str, Any]]]: Dictionary with keys:
            - "chart_query": timeseries rows (listing × date)
            - "chart_summary": summary metrics (listing × window)
            - "list_of_metrics": overview metrics (listing × window)
    """
    results = {
        "chart_query": _extract_chart_timeseries_rows(chunks),
        "chart_summary": _extract_chart_summary_metrics(chunks),
        "list_of_metrics": _extract_list_of_metrics(chunks),
    }

    if debug:
        logger.debug("Parsed results from parse_all:\n%s", json.dumps(results, indent=2))

    return results


def _extract_chart_timeseries_rows(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Pivot ChartQuery time series rows by listing + date.

    Args:
        chunks (List[Dict[str, Any]]): Flattened poller chunks of type 'ChartQuery'.

    Returns:
        List[Dict[str, Any]]: Rows with format:
            {
                airbnb_listing_id: str,
                airbnb_internal_name: str,
                date: str,
                <metric_label>_your_value: float,
                <metric_label>_similar_value_string: str,
                ...
            }
    """
    pivoted_rows: dict[tuple[str, str], dict[str, Any]] = defaultdict(dict)

    for chunk in chunks:
        meta = chunk.get("meta", {})
        if meta.get("query_type") != "ChartQuery":
            continue

        listing_id = meta.get("listing_id")
        listing_name = meta.get("listing_name")
        metric_name = meta.get("group_values", ["unknown"])[0]

        for row in chunk.get("timeseries_rows", []):
            ds = row["ds"]
            tag = row.get("source_label", "")
            tag_key = "your" if "your" in tag.lower() else "similar"
            key = (listing_id, ds)

            base = pivoted_rows[key]
            if not base:
                base["airbnb_listing_id"] = listing_id
                base["airbnb_internal_name"] = listing_name
                base["date"] = ds

            base[f"{metric_name}_{tag_key}_value"] = coerce_number(row.get("value"))
            base[f"{metric_name}_{tag_key}_value_string"] = row.get("value_string")

    return list(pivoted_rows.values())


def _extract_chart_summary_metrics(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Parse ChartQuery summary rows (primary + secondary) grouped by listing + window.

    Args:
        chunks (List[Dict[str, Any]]): Flattened poller chunks of type 'ChartQuery'.

    Returns:
        List[Dict[str, Any]]: Rows with format:
            {
                airbnb_listing_id: str,
                window_start: str,
                window_end: str,
                <metric_name>_value: float,
                <metric_name>_value_change_string: str,
                ...
            }
    """
    summary_rows: dict[tuple[str, str, str], dict[str, Any]] = defaultdict(dict)

    for chunk in chunks:
        meta = chunk.get("meta", {})
        if meta.get("query_type") != "ChartQuery":
            continue

        lid = meta.get("listing_id")
        name = meta.get("listing_name")
        start = meta.get("window_start")
        end = meta.get("window_end")
        key = (lid, start, end)

        row = summary_rows[key]
        if not row:
            row["airbnb_listing_id"] = lid
            row["airbnb_internal_name"] = name
            row["window_start"] = start
            row["window_end"] = end

        primary = chunk.get("primary_metric", {})
        if primary:
            metric = primary.get("metric_name")
            row[f"{metric}_value"] = coerce_number(primary.get("value"))
            row[f"{metric}_value_string"] = primary.get("value_string")
            row[f"{metric}_value_change"] = coerce_number(primary.get("value_change"))
            row[f"{metric}_value_change_string"] = primary.get("value_change_string")

        for m in chunk.get("secondary_metrics", []):
            metric = m.get("metric_name")
            row[f"{metric}_value"] = coerce_number(m.get("value"))
            row[f"{metric}_value_string"] = m.get("value_string")

    return list(summary_rows.values())


def _extract_list_of_metrics(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Parse ListOfMetricsQuery output into overview rows per listing × window.

    Args:
        chunks (List[Dict[str, Any]]): Flattened poller chunks of type 'ListOfMetricsQuery'.

    Returns:
        List[Dict[str, Any]]: Rows with format:
            {
                airbnb_listing_id: str,
                window_start: str,
                window_end: str,
                <metric_name>_value: float,
                <metric_name>_value_string: str,
                ...
            }
    """
    grouped: dict[tuple[str, str, str], dict[str, Any]] = defaultdict(dict)

    for chunk in chunks:
        meta = chunk.get("meta", {})
        if meta.get("query_type") != "ListOfMetricsQuery":
            continue

        lid = meta.get("listing_id")
        name = meta.get("listing_name")
        start = meta.get("window_start")
        end = meta.get("window_end")
        key = (lid, start, end)

        row = grouped[key]
        if not row:
            row["airbnb_listing_id"] = lid
            row["airbnb_internal_name"] = name
            row["window_start"] = start
            row["window_end"] = end

        for metric in chunk.get("timeseries_rows", []):
            metric_name = metric.get("metric_name")
            row[f"{metric_name}_value"] = coerce_number(metric.get("value"))
            row[f"{metric_name}_value_string"] = metric.get("value_string")

    return list(grouped.values())
