import logging
import signal
import sys
import threading
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError

from sync_airbnb import config
from sync_airbnb.api import errors
from sync_airbnb.api.routes import accounts, health, metrics
from sync_airbnb.middleware.request_id import RequestIDMiddleware
from sync_airbnb.utils.logging import setup_logging

# Configure logging
setup_logging()

logger = logging.getLogger(__name__)

# Initialize scheduler for worker mode
scheduler = BackgroundScheduler()

# Track active sync threads for graceful shutdown
active_threads: list[threading.Thread] = []
shutdown_event = threading.Event()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events."""
    logger.info(f"Starting sync_airbnb service in {config.MODE} mode")

    # Start scheduler in worker or hybrid mode
    if config.MODE in ("worker", "hybrid"):
        from sync_airbnb.services.scheduler import run_sync_on_startup, setup_scheduler

        logger.info(f"Starting scheduler for account {config.ACCOUNT_ID}")

        # Run startup sync in background thread (supports K8s Operator pattern)
        # This allows the API to be available immediately while sync runs
        def startup_sync_wrapper():
            try:
                run_sync_on_startup()
            finally:
                if threading.current_thread() in active_threads:
                    active_threads.remove(threading.current_thread())

        sync_thread = threading.Thread(target=startup_sync_wrapper, daemon=False, name="startup-sync")
        active_threads.append(sync_thread)
        sync_thread.start()
        logger.info("Startup sync initiated in background (if needed)")

        setup_scheduler(scheduler)
        scheduler.start()

    yield

    # Shutdown
    logger.info("Starting graceful shutdown...")

    # Stop scheduler first
    if scheduler.running:
        logger.info("Shutting down scheduler")
        scheduler.shutdown(wait=True)

    # Wait for active sync threads to complete
    if active_threads:
        logger.info(f"Waiting for {len(active_threads)} active sync threads to complete...")
        for thread in active_threads[:]:  # Copy list to avoid modification during iteration
            if thread.is_alive():
                logger.info(f"Waiting for thread {thread.name} to complete...")
                thread.join(timeout=300)  # 5 minute max wait per thread
                if thread.is_alive():
                    logger.error(f"Thread {thread.name} did not complete in 5 minutes")
                else:
                    logger.info(f"Thread {thread.name} completed successfully")

    logger.info("Graceful shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Sync Airbnb",
    description="Multi-account Airbnb metrics sync service",
    version="1.0.0",
    lifespan=lifespan,
)

# Add middleware
app.add_middleware(RequestIDMiddleware)

# Add exception handlers
app.add_exception_handler(HTTPException, errors.http_exception_handler)
app.add_exception_handler(RequestValidationError, errors.validation_exception_handler)
app.add_exception_handler(Exception, errors.general_exception_handler)

# Include routers
app.include_router(health.router, tags=["health"])

# Admin/hybrid mode: include account management and metrics routes
if config.MODE in ("admin", "hybrid"):
    app.include_router(accounts.router, prefix="/api/v1", tags=["accounts"])
    app.include_router(metrics.router, prefix="/api/v1", tags=["metrics"])


# Signal handlers for graceful shutdown
def handle_shutdown_signal(signum, frame):
    """Handle SIGTERM/SIGINT gracefully."""
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_event.set()

    # Stop scheduler
    if scheduler.running:
        logger.info("Stopping scheduler...")
        scheduler.shutdown(wait=False)

    # Wait for active threads with timeout
    if active_threads:
        logger.info(f"Waiting for {len(active_threads)} active sync threads...")
        for thread in active_threads[:]:
            if thread.is_alive():
                thread.join(timeout=300)
                if thread.is_alive():
                    logger.error(f"Thread {thread.name} did not complete in time")

    logger.info("Graceful shutdown complete")
    sys.exit(0)


# Register signal handlers (only if not in test mode)
if __name__ != "__main__":
    signal.signal(signal.SIGTERM, handle_shutdown_signal)
    signal.signal(signal.SIGINT, handle_shutdown_signal)
