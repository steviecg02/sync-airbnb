from datetime import date, timedelta

from sync_airbnb.config import LOOKAHEAD_WEEKS, LOOKBACK_WEEKS, MAX_LOOKBACK_DAYS
from sync_airbnb.utils.date_window import get_poll_window


def test_regular_run_aligned_to_sunday_saturday():
    """Ensure non-initial runs start on Sunday and end on Saturday."""
    today = date(2025, 1, 13)  # Monday
    start, end = get_poll_window(is_first_run=False, today=today)

    assert start.weekday() == 6  # Sunday
    assert end.weekday() == 5  # Saturday

    expected_days = ((LOOKBACK_WEEKS + LOOKAHEAD_WEEKS + 1) * 7) - 1  # inclusive
    assert (end - start).days == expected_days


def test_first_run_window_limits_and_alignment():
    """Ensure first-run start date is aligned to Sunday and within 180-day cap."""
    today = date(2025, 7, 10)
    start, end = get_poll_window(is_first_run=True, today=today)

    assert start.weekday() == 6  # Sunday
    assert end.weekday() == 5  # Saturday

    max_back_date = today - timedelta(days=MAX_LOOKBACK_DAYS)
    assert max_back_date <= start <= today


def test_first_run_alignment_math_specific_example():
    """Confirm specific date math: 180 days back and round forward to Sunday."""
    today = date(2025, 7, 14)
    start, _ = get_poll_window(is_first_run=True, today=today)

    # 180 days back = 2025-01-15 (Wed) → round forward to Sunday = 2025-01-19
    assert start == date(2025, 1, 19)


def test_consistent_alignment_on_standard_run():
    """Ensure standard (non-first) runs are aligned to Sunday and Saturday."""
    start, end = get_poll_window(is_first_run=False, today=date(2025, 7, 11))
    assert start.weekday() == 6
    assert end.weekday() == 5
