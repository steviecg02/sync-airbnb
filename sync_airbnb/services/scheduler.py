"""
Scheduler service for running Airbnb insights polling on a schedule.

This module defines the scheduled jobs that run in worker/hybrid mode to
periodically fetch and sync Airbnb metrics for a specific account.
"""

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from sync_airbnb import config
from sync_airbnb.db.readers.accounts import get_account
from sync_airbnb.services.insights import run_insights_poller

logger = logging.getLogger(__name__)


def run_sync_on_startup():
    """
    Run sync on worker startup if needed.

    Only runs sync if:
    1. Never synced before (last_sync_at is None), OR
    2. Last sync was before today's scheduled cron time AND cron already ran (or should have)

    This enables the Kubernetes Operator pattern while avoiding duplicate syncs
    when containers restart near the scheduled cron time.
    """
    try:
        if config.ACCOUNT_ID is None:
            logger.error("ACCOUNT_ID not configured, cannot run startup sync")
            return

        logger.info(f"Checking if startup sync needed for account {config.ACCOUNT_ID}")

        account = get_account(config.engine, config.ACCOUNT_ID)
        if not account:
            logger.error(f"Account {config.ACCOUNT_ID} not found in database")
            return

        if not account.is_active:
            logger.warning(f"Account {config.ACCOUNT_ID} is inactive, skipping startup sync")
            return

        # Determine if sync is needed
        if account.last_sync_at is None:
            # Never synced - run now
            logger.info(f"First sync for account {config.ACCOUNT_ID}, running startup sync...")
            run_insights_poller(account, trigger="startup")
            logger.info(f"Startup sync completed for account {config.ACCOUNT_ID}")
        else:
            # Check if we need to run based on cron schedule
            now = datetime.now(timezone.utc)
            today = now.date()
            cron_time_today = now.replace(
                hour=config.SYNC_CRON_HOUR, minute=config.SYNC_CRON_MINUTE, second=0, microsecond=0
            )

            if account.last_sync_at.date() < today:
                # Last sync was yesterday or earlier
                if now < cron_time_today:
                    # Cron hasn't run yet today - let it handle it
                    logger.info(
                        f"Last sync was {account.last_sync_at.strftime('%Y-%m-%d %H:%M:%S')} UTC, "
                        f"but cron will run at {cron_time_today.strftime('%Y-%m-%d %H:%M:%S')} UTC, skipping startup sync"
                    )
                else:
                    # Cron already ran (or should have) - we missed it, sync now
                    logger.info(
                        f"Last sync was {account.last_sync_at.strftime('%Y-%m-%d %H:%M:%S')} UTC, "
                        f"and cron already ran at {cron_time_today.strftime('%H:%M')} UTC, running startup sync"
                    )
                    run_insights_poller(account, trigger="startup")
            else:
                # Already synced today
                logger.info(
                    f"Account {config.ACCOUNT_ID} already synced today at "
                    f"{account.last_sync_at.strftime('%Y-%m-%d %H:%M:%S')} UTC, skipping startup sync"
                )

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
        if config.ACCOUNT_ID is None:
            logger.error("ACCOUNT_ID not configured, cannot run scheduled sync")
            return

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
        run_insights_poller(account, trigger="scheduled")

        logger.info(f"Completed scheduled sync for account {config.ACCOUNT_ID}")

    except Exception as e:
        logger.error(f"Error in scheduled sync for account {config.ACCOUNT_ID}: {e}", exc_info=True)


def setup_scheduler(scheduler: BackgroundScheduler):
    """
    Configure the scheduler with all jobs.

    Args:
        scheduler: APScheduler BackgroundScheduler instance
    """
    # Run insights sync daily at configured time (default 5:00 AM UTC)
    scheduler.add_job(
        sync_insights_job,
        trigger="cron",
        hour=config.SYNC_CRON_HOUR,
        minute=config.SYNC_CRON_MINUTE,
        timezone="UTC",
        id="sync_insights",
        name="Sync Airbnb Insights",
        replace_existing=True,
    )

    logger.info(
        f"Scheduler configured with insights sync job "
        f"(daily at {config.SYNC_CRON_HOUR:02d}:{config.SYNC_CRON_MINUTE:02d} UTC)"
    )
