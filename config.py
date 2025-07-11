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
LOG_LEVEL = get_env(
    "LOG_LEVEL", required=False, default="DEBUG" if os.path.exists(".env") else "INFO"
).upper()
DEBUG = LOG_LEVEL == "DEBUG"

# --- Required settings ---
DATABASE_URL = get_env("DATABASE_URL")
engine = create_engine(DATABASE_URL, future=True)

# --- Optional flags ---
INSIGHTS_DRY_RUN = get_env(
    "INSIGHTS_DRY_RUN", required=False, default="false"
).lower() in ("1", "true", "yes")

# --- Polling window configuration ---
# These control how far back and forward the Airbnb poller collects data.
# May be removed once backfill/forecast limits are confirmed.

LOOKBACK_WEEKS = int(get_env("LOOKBACK_WEEKS", required=False, default="25"))
LOOKAHEAD_WEEKS = int(get_env("LOOKAHEAD_WEEKS", required=False, default="25"))
MAX_LOOKBACK_DAYS = 180  # hard cap for backfill
