import os

from dotenv import load_dotenv
from sqlalchemy import create_engine

# --- Load .env in non-prod environments ---
if os.path.exists(".env"):
    load_dotenv()


# --- Env access helper ---
def get_env(key: str, required: bool = True, default: str | None = None) -> str | None:
    val = os.getenv(key, default)
    if required and not val:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return val


# --- Logging configuration ---
LOG_LEVEL = (
    get_env("LOG_LEVEL", required=False, default="DEBUG" if os.path.exists(".env") else "INFO") or "INFO"
).upper()
DEBUG = LOG_LEVEL == "DEBUG"

# --- Required settings ---
DATABASE_URL = get_env("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is required")

# Create database engine with connection pool settings
engine = create_engine(
    DATABASE_URL,
    future=True,
    pool_pre_ping=True,  # Test connections before use (prevents stale connection errors)
    pool_recycle=3600,  # Recycle connections every hour (prevents leaks, handles network hiccups)
)

# --- Database schema ---
SCHEMA = "airbnb"

# --- Service mode configuration ---
MODE = get_env("MODE", required=False, default="hybrid")  # "admin", "worker", or "hybrid"
if MODE not in ("admin", "worker", "hybrid"):
    raise RuntimeError(f"MODE must be 'admin', 'worker', or 'hybrid', got: {MODE}")

# Worker/hybrid mode requires ACCOUNT_ID
ACCOUNT_ID = get_env("ACCOUNT_ID", required=(MODE in ("worker", "hybrid")), default=None)

# --- Optional flags ---
INSIGHTS_DRY_RUN = (get_env("INSIGHTS_DRY_RUN", required=False, default="false") or "false").lower() in (
    "1",
    "true",
    "yes",
)

# --- Polling window configuration ---
# These control how far back and forward the Airbnb poller collects data.
# May be removed once backfill/forecast limits are confirmed.

LOOKBACK_WEEKS = int(get_env("LOOKBACK_WEEKS", required=False, default="25") or "25")
LOOKAHEAD_WEEKS = int(get_env("LOOKAHEAD_WEEKS", required=False, default="25") or "25")
MAX_LOOKBACK_DAYS = 180  # hard cap for backfill

# --- Sync schedule configuration ---
# Cron schedule for daily sync jobs (used by scheduler and startup sync logic)
SYNC_CRON_HOUR = int(get_env("SYNC_CRON_HOUR", required=False, default="5") or "5")
SYNC_CRON_MINUTE = int(get_env("SYNC_CRON_MINUTE", required=False, default="0") or "0")
