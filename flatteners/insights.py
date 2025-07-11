import logging
from typing import Any, Dict, List
from flatteners.utils import get_first_component, extract_numeric_value

logger = logging.getLogger(__name__)


def flatten_chart_query(response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flatten the Airbnb ChartQuery response into structured components.

    Args:
        response (dict): Parsed JSON response from Airbnb's ChartQuery GraphQL query.

    Returns:
        dict: A dictionary with the following keys:
            - "timeseries_rows" (List[dict]): One row per dataPoint (grouped by granularity and label).
            - "primary_metric" (dict): Summary of the main metric (e.g., conversion rate).
            - "secondary_metrics" (List[dict]): List of secondary metrics shown on the chart.

    Raises:
        ValueError: If the response is not in the expected format.
    """
    try:
        component = get_first_component(response)

        timeseries_rows = []
        for chart in component.get("metricLineCharts", []):
            granularity = chart.get("granularity", "UNKNOWN")
            source_label = chart.get("label", "")
            for point in chart.get("dataPoints", []):
                timeseries_rows.append(
                    {
                        "granularity": granularity,
                        "ds": point["ds"],
                        "label": point.get("label"),
                        "value": extract_numeric_value(point["value"]),
                        "value_string": point.get("valueString"),
                        "value_type": point.get("valueType"),
                        "source_label": source_label,
                    }
                )

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
            secondary_metrics.append(
                {
                    "metric_name": metric.get("metricName"),
                    "label": metric.get("label"),
                    "value": extract_numeric_value(metric.get("value", {})),
                    "value_string": metric.get("valueString"),
                    "value_type": metric.get("valueType"),
                }
            )

        logger.debug(
            "Flattened ChartQuery: %d rows, primary='%s', secondary=%d",
            len(timeseries_rows),
            primary_metric["metric_name"],
            len(secondary_metrics),
        )

        return {
            "timeseries_rows": timeseries_rows,
            "primary_metric": primary_metric,
            "secondary_metrics": secondary_metrics,
        }

    except Exception as e:
        logger.exception("Error flattening ChartQuery response")
        raise ValueError(f"Failed to flatten ChartQuery response: {e}")


def flatten_list_of_metrics_query(
    response: Dict[str, Any]
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Flatten the Airbnb ListOfMetricsQuery response.

    Args:
        response (dict): Parsed JSON response from Airbnb's ListOfMetricsQuery.

    Returns:
        dict: A dictionary with a single key:
            - "timeseries_rows" (List[dict]): One row per metric in the component block.

    Raises:
        ValueError: If the expected structure is missing or invalid.
    """
    try:
        component = get_first_component(response)

        rows = []
        for metric in component.get("metrics", []):
            rows.append(
                {
                    "metric_name": metric.get("metricName"),
                    "label": metric.get("label"),
                    "value": extract_numeric_value(metric.get("value", {})),
                    "value_string": metric.get("valueString"),
                    "value_type": metric.get("valueType"),
                }
            )

        logger.debug("Flattened ListOfMetricsQuery: %d metrics", len(rows))
        return {"timeseries_rows": rows}

    except Exception as e:
        logger.exception("Error flattening ListOfMetricsQuery response")
        raise ValueError(f"Failed to flatten ListOfMetricsQuery response: {e}")
