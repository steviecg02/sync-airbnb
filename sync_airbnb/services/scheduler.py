"""
Scheduler service for running Airbnb insights polling on a schedule.

This module defines the scheduled jobs that run in worker/hybrid mode to
periodically fetch and sync Airbnb metrics for a specific account.
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler

from sync_airbnb import config
from sync_airbnb.db.readers.accounts import get_account
from sync_airbnb.services.insights import run_insights_poller

logger = logging.getLogger(__name__)


def run_sync_on_startup():
    """
    Run sync on worker startup if this is the first sync for the account.

    This enables the Kubernetes Operator pattern where workers auto-sync
    immediately after being created for new accounts.
    """
    try:
        logger.info(f"Checking if startup sync needed for account {config.ACCOUNT_ID}")

        account = get_account(config.engine, config.ACCOUNT_ID)
        if not account:
            logger.error(f"Account {config.ACCOUNT_ID} not found in database")
            return

        if not account.is_active:
            logger.warning(f"Account {config.ACCOUNT_ID} is inactive, skipping startup sync")
            return

        if account.last_sync_at is None:
            logger.info(f"First sync for account {config.ACCOUNT_ID}, running startup sync...")
            run_insights_poller(account)
            logger.info(f"Startup sync completed for account {config.ACCOUNT_ID}")
        else:
            logger.info(f"Account {config.ACCOUNT_ID} already synced (last: {account.last_sync_at}), skipping startup sync")

    except Exception as e:
        logger.error(f"Error in startup sync for account {config.ACCOUNT_ID}: {e}", exc_info=True)


def sync_insights_job():
    """
    Scheduled job that fetches account and runs insights poller.

    This job:
    1. Fetches the account from the database using ACCOUNT_ID from config
    2. Runs the insights poller with account credentials
    3. Handles errors and logs them
    """
    try:
        logger.info(f"Starting scheduled sync for account {config.ACCOUNT_ID}")

        # Fetch account from database
        account = get_account(config.engine, config.ACCOUNT_ID)
        if not account:
            logger.error(f"Account {config.ACCOUNT_ID} not found in database")
            return

        if not account.is_active:
            logger.warning(f"Account {config.ACCOUNT_ID} is inactive, skipping sync")
            return

        # Run insights poller
        run_insights_poller(account)

        logger.info(f"Completed scheduled sync for account {config.ACCOUNT_ID}")

    except Exception as e:
        logger.error(f"Error in scheduled sync for account {config.ACCOUNT_ID}: {e}", exc_info=True)


def setup_scheduler(scheduler: BackgroundScheduler):
    """
    Configure the scheduler with all jobs.

    Args:
        scheduler: APScheduler BackgroundScheduler instance
    """
    # Run insights sync daily at 5 AM UTC (1 AM EDT / 12 AM EST)
    scheduler.add_job(
        sync_insights_job,
        trigger='cron',
        hour=5,
        minute=0,
        timezone='UTC',
        id='sync_insights',
        name='Sync Airbnb Insights',
        replace_existing=True,
    )

    logger.info("Scheduler configured with insights sync job (daily at 5:00 UTC)")
