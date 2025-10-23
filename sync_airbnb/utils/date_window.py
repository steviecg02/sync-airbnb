"""
Date window calculation logic for Airbnb metrics polling.

Supports aligned Sunday–Saturday windows, lookback/forecast ranges, and
first-run logic based on configured constants.
"""

import logging
from datetime import date, timedelta

from sync_airbnb.config import LOOKAHEAD_WEEKS, LOOKBACK_WEEKS, MAX_LOOKBACK_DAYS

logger = logging.getLogger(__name__)


def get_poll_window(is_first_run: bool, today: date | None = None) -> tuple[date, date]:
    """
    Calculate the Airbnb polling window based on current date and config.

    Args:
        is_first_run (bool): True if this is the first-ever sync (uses MAX_LOOKBACK_DAYS),
                             False to use rolling LOOKBACK_WEEKS.
        today (date | None, optional): Defaults to `date.today()`. Override for testing.

    Returns:
        tuple[date, date]: (start_date, end_date) aligned to Sunday and Saturday.
    """
    if today is None:
        today = date.today()

    # Align to Sunday of this week
    current_sunday = today - timedelta(days=(today.weekday() + 1) % 7)

    if is_first_run:
        raw_start = today - timedelta(days=MAX_LOOKBACK_DAYS)
        days_to_sunday = (6 - raw_start.weekday()) % 7  # Sunday = 6
        start_date = raw_start + timedelta(days=days_to_sunday)
    else:
        start_date = current_sunday - timedelta(weeks=LOOKBACK_WEEKS)

    end_date = current_sunday + timedelta(weeks=LOOKAHEAD_WEEKS, days=6)

    logger.info(
        "[WINDOW] Calculated poll window: %s to %s (today=%s, first_run=%s)",
        start_date,
        end_date,
        today,
        is_first_run,
    )
    return start_date, end_date
