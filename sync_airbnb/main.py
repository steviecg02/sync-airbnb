import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from apscheduler.schedulers.background import BackgroundScheduler

from sync_airbnb import config
from sync_airbnb.api.routes import health, accounts
from sync_airbnb.utils.logging import setup_logging

# Configure logging
setup_logging()

logger = logging.getLogger(__name__)

# Initialize scheduler for worker mode
scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events."""
    logger.info(f"Starting sync_airbnb service in {config.MODE} mode")

    # Start scheduler in worker or hybrid mode
    if config.MODE in ("worker", "hybrid"):
        from sync_airbnb.services.scheduler import setup_scheduler, run_sync_on_startup
        logger.info(f"Starting scheduler for account {config.ACCOUNT_ID}")

        # Run startup sync in background thread (supports K8s Operator pattern)
        # This allows the API to be available immediately while sync runs
        def startup_sync_wrapper():
            run_sync_on_startup()

        sync_thread = threading.Thread(target=startup_sync_wrapper, daemon=True)
        sync_thread.start()
        logger.info("Startup sync initiated in background (if needed)")

        setup_scheduler(scheduler)
        scheduler.start()

    yield

    # Shutdown
    if scheduler.running:
        logger.info("Shutting down scheduler")
        scheduler.shutdown()


# Create FastAPI app
app = FastAPI(
    title="Sync Airbnb",
    description="Multi-account Airbnb metrics sync service",
    version="1.0.0",
    lifespan=lifespan,
)

# Include routers
app.include_router(health.router, tags=["health"])

# Admin/hybrid mode: include account management routes
if config.MODE in ("admin", "hybrid"):
    app.include_router(accounts.router, prefix="/api/v1", tags=["accounts"])
