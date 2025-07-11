from datetime import date
from unittest.mock import patch, MagicMock
from services import insights


@patch("services.insights.insert_list_of_metrics_rows")
@patch("services.insights.insert_chart_summary_rows")
@patch("services.insights.insert_chart_query_rows")
@patch("pollers.insights.get_poll_window")
@patch("services.insights.AirbnbSync")
def test_run_insights_poller_happy_path(
    mock_airbnb_sync,
    mock_get_poll_window,
    mock_insert_chart_query_rows,
    mock_insert_chart_summary_rows,
    mock_insert_list_of_metrics_rows,
):
    # Mock poll window
    mock_get_poll_window.return_value = ("2025-07-01", "2025-07-07")

    # Mock listings
    mock_sync_instance = MagicMock()
    mock_sync_instance.fetch_listing_ids.return_value = {"999": "Test Listing"}
    mock_sync_instance.parse_all.return_value = {
        "chart_query": [{"test": "chart"}],
        "chart_summary": [{"test": "summary"}],
        "list_of_metrics": [{"test": "metrics"}],
    }
    mock_airbnb_sync.return_value = mock_sync_instance

    # Run
    insights.run_insights_poller(
        *mock_get_poll_window.return_value, scrape_day=date(2025, 7, 11)
    )

    # Assertions
    mock_airbnb_sync.assert_called_once()
    mock_sync_instance.fetch_listing_ids.assert_called_once()
    mock_sync_instance.poll_range_and_flatten.assert_any_call(
        listing_id="999",
        listing_name="Test Listing",
        query_type="ChartQuery",
        metrics=insights.METRIC_QUERIES["ChartQuery"],
        start_date="2025-07-01",
        end_date="2025-07-07",
        window_size_days=28,
    )
    mock_sync_instance.poll_range_and_flatten.assert_any_call(
        listing_id="999",
        listing_name="Test Listing",
        query_type="ListOfMetricsQuery",
        metrics=insights.METRIC_QUERIES["ListOfMetricsQuery"],
        start_date="2025-07-01",
        end_date="2025-07-07",
        window_size_days=7,
    )

    mock_insert_chart_query_rows.assert_called_once()
    mock_insert_chart_summary_rows.assert_called_once()
    mock_insert_list_of_metrics_rows.assert_called_once()
