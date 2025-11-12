from datetime import date
from unittest.mock import MagicMock, patch

from sync_airbnb.models.account import Account
from sync_airbnb.services import insights


@patch("sync_airbnb.services.insights.sync_listings_processed_total")
@patch("sync_airbnb.services.insights.sync_jobs_duration_seconds")
@patch("sync_airbnb.services.insights.sync_jobs_active")
@patch("sync_airbnb.services.insights.sync_jobs_total")
@patch("sync_airbnb.services.insights.errors_total")
@patch("sync_airbnb.services.insights.engine")
@patch("sync_airbnb.services.insights.update_last_sync")
@patch("sync_airbnb.db.writers.accounts.update_account_cookies")
@patch("sync_airbnb.network.preflight.create_preflight_session")
@patch("sync_airbnb.utils.cookie_utils.filter_auth_cookies_only")
@patch("sync_airbnb.utils.cookie_utils.parse_cookie_string")
@patch("sync_airbnb.services.insights.insert_list_of_metrics_rows")
@patch("sync_airbnb.services.insights.insert_chart_query_rows")
@patch("sync_airbnb.services.insights.get_poll_window")
@patch("sync_airbnb.services.insights.AirbnbSync")
def test_run_insights_poller_happy_path(
    mock_airbnb_sync,
    mock_get_poll_window,
    mock_insert_chart_query_rows,
    mock_insert_list_of_metrics_rows,
    mock_parse_cookie_string,
    mock_filter_auth_cookies_only,
    mock_create_preflight_session,
    mock_update_last_sync,
    mock_update_account_cookies,
    mock_engine,
    mock_errors_total,
    mock_sync_jobs_total,
    mock_sync_jobs_active,
    mock_sync_jobs_duration_seconds,
    mock_sync_listings_processed_total,
):
    # Mock Prometheus metrics
    mock_sync_jobs_total.labels.return_value.inc = MagicMock()
    mock_sync_jobs_active.inc = MagicMock()
    mock_sync_jobs_active.dec = MagicMock()
    mock_sync_jobs_duration_seconds.observe = MagicMock()
    mock_sync_listings_processed_total.labels.return_value.inc = MagicMock()
    mock_errors_total.labels.return_value.inc = MagicMock()

    # Mock poll window
    mock_get_poll_window.return_value = (date(2025, 7, 1), date(2025, 7, 7))

    # Mock cookie parsing
    mock_parse_cookie_string.return_value = {"_airbed_session_id": "abc", "_aaj": "xyz"}
    mock_filter_auth_cookies_only.side_effect = lambda x: x  # Return same dict

    # Mock preflight session
    mock_session = MagicMock()
    mock_session.cookies.items.return_value = [
        ("_airbed_session_id", "abc"),
        ("_aaj", "xyz_new"),  # Changed value
    ]
    # Mock session.post() to return valid GraphQL responses
    mock_post_response = MagicMock()
    mock_post_response.status_code = 200
    mock_post_response.json.return_value = {"data": {}}
    mock_post_response.headers.get_list.return_value = []
    mock_session.post.return_value = mock_post_response
    mock_create_preflight_session.return_value = mock_session

    # Mock listings
    mock_sync_instance = MagicMock()
    mock_sync_instance.fetch_listing_ids.return_value = {"999": "Test Listing"}
    mock_sync_instance.parse_all.return_value = {
        "chart_query": [],  # Empty - insert function is mocked
        "chart_summary": [],
        "list_of_metrics": [],
    }
    mock_sync_instance._parsed_chunks.clear = MagicMock()
    mock_airbnb_sync.return_value = mock_sync_instance

    # Mock account (trace_id removed - auto-generated in build_headers())
    mock_account = Account(
        account_id="test_account",
        airbnb_cookie="test_cookie",
        x_client_version="test_version",
        user_agent="test_agent",
        is_active=True,
        last_sync_at=None,
    )

    # Run
    insights.run_insights_poller(account=mock_account, scrape_day=date(2025, 7, 11))

    # Assertions
    mock_get_poll_window.assert_called_once_with(is_first_run=True, today=date(2025, 7, 11))
    mock_parse_cookie_string.assert_called_once()
    mock_create_preflight_session.assert_called_once()
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

    # Verify last_sync and cookies were updated
    mock_update_last_sync.assert_called_once()
    mock_update_account_cookies.assert_called_once()
