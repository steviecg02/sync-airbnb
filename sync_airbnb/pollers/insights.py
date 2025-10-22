import logging
from sync_airbnb.config import LOG_LEVEL
from datetime import date
from sync_airbnb.services.insights import run_insights_poller
from sync_airbnb.utils.logging import setup_logging
from sync_airbnb.utils.date_window import get_poll_window


# Setup logging
setup_logging(LOG_LEVEL)
logger = logging.getLogger(__name__)


def is_first_run() -> bool:
    return False  # TODO: implement startup-state logic


def main():
    logger.info("Launching Airbnb poller")
    window_start, window_end = get_poll_window(is_first_run())
    run_insights_poller(
        scrape_day=date.today(), window_start=window_start, window_end=window_end
    )


if __name__ == "__main__":
    main()
