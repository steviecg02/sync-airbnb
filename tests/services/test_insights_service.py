from datetime import date
from unittest.mock import MagicMock, patch

from sync_airbnb.models.account import Account
from sync_airbnb.services import insights


@patch("sync_airbnb.services.insights.update_last_sync")
@patch("sync_airbnb.services.insights.build_headers")
@patch("sync_airbnb.services.insights.insert_list_of_metrics_rows")
@patch("sync_airbnb.services.insights.insert_chart_query_rows")
@patch("sync_airbnb.services.insights.get_poll_window")
@patch("sync_airbnb.services.insights.AirbnbSync")
def test_run_insights_poller_happy_path(
    mock_airbnb_sync,
    mock_get_poll_window,
    mock_insert_chart_query_rows,
    mock_insert_list_of_metrics_rows,
    mock_build_headers,
    mock_update_last_sync,
):
    # Mock poll window
    mock_get_poll_window.return_value = (date(2025, 7, 1), date(2025, 7, 7))

    # Mock headers
    mock_build_headers.return_value = {"X-API-Key": "test"}

    # Mock listings
    mock_sync_instance = MagicMock()
    mock_sync_instance.fetch_listing_ids.return_value = {"999": "Test Listing"}
    mock_sync_instance.parse_all.return_value = {
        "chart_query": [{"test": "chart"}],
        "chart_summary": [{"test": "summary"}],
        "list_of_metrics": [{"test": "metrics"}],
    }
    mock_sync_instance._parsed_chunks.clear = MagicMock()
    mock_airbnb_sync.return_value = mock_sync_instance

    # Mock account
    mock_account = Account(
        account_id="test_account",
        airbnb_cookie="test_cookie",
        x_client_version="test_version",
        x_airbnb_client_trace_id="test_trace",
        user_agent="test_agent",
        is_active=True,
        last_sync_at=None,
    )

    # Run
    insights.run_insights_poller(account=mock_account, scrape_day=date(2025, 7, 11))

    # Assertions
    mock_get_poll_window.assert_called_once_with(is_first_run=True, today=date(2025, 7, 11))
    mock_build_headers.assert_called_once()
    mock_airbnb_sync.assert_called_once()
    mock_sync_instance.fetch_listing_ids.assert_called_once()
    mock_sync_instance.poll_range_and_flatten.assert_any_call(
        listing_id="999",
        listing_name="Test Listing",
        query_type="ChartQuery",
        metrics=insights.METRIC_QUERIES["ChartQuery"],
        start_date=date(2025, 7, 1),
        end_date=date(2025, 7, 7),
        window_size_days=28,
    )
    mock_sync_instance.poll_range_and_flatten.assert_any_call(
        listing_id="999",
        listing_name="Test Listing",
        query_type="ListOfMetricsQuery",
        metrics=insights.METRIC_QUERIES["ListOfMetricsQuery"],
        start_date=date(2025, 7, 1),
        end_date=date(2025, 7, 7),
        window_size_days=7,
    )
    mock_sync_instance._parsed_chunks.clear.assert_called()

    # Verify data was inserted with account_id added
    mock_insert_chart_query_rows.assert_called_once()
    # chart_summary is skipped (not called)
    mock_insert_list_of_metrics_rows.assert_called_once()

    # Verify last_sync was updated
    mock_update_last_sync.assert_called_once()
