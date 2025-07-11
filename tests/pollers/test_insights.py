from datetime import date
from unittest.mock import patch


@patch("pollers.insights.run_insights_poller")
@patch("pollers.insights.get_poll_window")
def test_pollers_main_calls_get_poll_window_and_service(
    mock_get_window, mock_run_poller
):
    window_start = date(2025, 7, 1)
    window_end = date(2025, 7, 7)
    mock_get_window.return_value = (window_start, window_end)

    from pollers.insights import main

    main()

    mock_get_window.assert_called_once()
    mock_run_poller.assert_called_once_with(
        scrape_day=date(2025, 7, 11), window_start=window_start, window_end=window_end
    )
