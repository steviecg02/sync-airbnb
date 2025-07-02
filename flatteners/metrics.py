from typing import Any, Dict, List
from uuid import UUID
from flatteners.utils import get_first_component, extract_numeric_value


def flatten_chart_query(
    response: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Flattens the Airbnb ChartQuery GraphQL response into structured rows for DB insertion.

    Args:
        response (Dict[str, Any]): Raw ChartQuery GraphQL response from Airbnb.
        poll_date (str): Date the data was scraped (YYYY-MM-DD).
        listing_id (UUID): Internal UUID for the listing.
        listing_name (str): Display name for the listing.

    Returns:
        Dict[str, Any]: A dictionary with three keys:
            - "timeseries_rows": list of daily or weekly metric rows (one per dataPoint).
            - "primary_metric": one row summarizing the top-level primary metric.
            - "secondary_metrics": list of rows for each secondary metric shown in the chart.
    """
    component = get_first_component(response)

    timeseries_rows = []
    for chart in component.get("metricLineCharts", []):
        granularity = chart.get("granularity", "UNKNOWN")
        source_label = chart.get("label", "")
        for point in chart.get("dataPoints", []):
            timeseries_rows.append({
                "granularity": granularity,
                "ds": point["ds"],
                "label": point.get("label"),                    #
                "value":  extract_numeric_value(point["value"]),
                "value_string": point.get("valueString"),
                "value_type": point.get("valueType"),           #
                "source_label": source_label,
            })

    primary = component.get("primaryMetric", {})
    primary_metric = {
        "metric_name": primary.get("metricName"),
        "label": primary.get("label"),
        "value": extract_numeric_value(primary.get("value", {})),
        "value_string": primary.get("valueString"),
        "value_type": primary.get("valueType"),
        "value_change": extract_numeric_value(primary.get("valueChange", {})),
        "value_change_string": primary.get("valueChangeString"),
    }

    secondary_metrics = []
    for metric in component.get("secondaryMetrics", []):
        secondary_metrics.append({
            "metric_name": metric.get("metricName"),
            "label": metric.get("label"),
            "value": extract_numeric_value(metric.get("value", {})),
            "value_string": metric.get("valueString"),
            "value_type": metric.get("valueType"),
        })

    return {
        "timeseries_rows": timeseries_rows,
        "primary_metric": primary_metric,
        "secondary_metrics": secondary_metrics,
    }

def flatten_list_of_metrics_query(
    response: dict,
) -> dict:
    component = get_first_component(response)

    rows = []
    for metric in component.get("metrics", []):
        rows.append({
            "metric_name": metric.get("metricName"),
            "label": metric.get("label"),
            "value": extract_numeric_value(metric.get("value", {})),
            "value_string": metric.get("valueString"),
            "value_type": metric.get("valueType")
        })

    return {"timeseries_rows": rows}