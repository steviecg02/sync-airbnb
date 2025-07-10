import os
from datetime import date, timedelta
from dotenv import load_dotenv
from sqlalchemy import create_engine

# --- Load .env only in dev ---
if os.getenv("ENV") != "production" and os.path.exists(".env"):
    load_dotenv()

# --- Determine log level ---
if "LOG_LEVEL" in os.environ:
    LOG_LEVEL = os.environ["LOG_LEVEL"].upper()
else:
    LOG_LEVEL = "DEBUG" if os.path.exists(".env") else "INFO"

DEBUG = LOG_LEVEL == "DEBUG"  # <-- Add this

# --- Env access helper ---
def get_env(key: str, required: bool = True, default: str | None = None) -> str | None:
    val = os.getenv(key, default)
    if required and not val:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return val

# --- Airbnb API configuration ---
AIRBNB_API_URLS = {
    "LISTINGS": "https://www.airbnb.com/api/v3/ListingsSectionQuery/7a646c07b45ad35335b2cde4842e5c5bf69ccebde508b2ba60276832bfb1816b",
    "METRICS":  "https://www.airbnb.com/api/v3/ListOfMetricsQuery/b22a5ded5e6c6d168f1d224b78f34182e7366e5cc65203ec04f1e718286a09e1",
    "CHART":    "https://www.airbnb.com/api/v3/ChartQuery/aa6e318cc066bbf19511b86acdce32fc59219d8596448b861d794491f46631c5"
}

HEADERS = {
    "Cookie": get_env("AIRBNB_COOKIE"),
    "X-Airbnb-API-Key": "d306zoyjsyarp7ifhu67rjxn52tv0t20",
    "X-Client-Version": get_env("X_CLIENT_VERSION"),
    "X-Client-Request-Id": get_env("X_CLIENT_REQUEST_ID", required=False, default="manual-dev"),
    "X-Airbnb-Client-Trace-Id": get_env("X_AIRBNB_CLIENT_TRACE_ID"),
    "User-Agent": get_env("USER_AGENT", required=False, default="Mozilla/5.0"),
    "X-Airbnb-GraphQL-Platform": "web",
    "X-Airbnb-GraphQL-Platform-Client": "minimalist-niobe",
    "X-Airbnb-Supports-Airlock-V2": "true",
    "X-Niobe-Short-Circuited": "true",
    "X-CSRF-Token": get_env("X_CSRF_TOKEN", required=False, default=""),
    "X-CSRF-Without-Token": "1",
    "Accept": "*/*",
    "Content-Type": "application/json",
}

# --- Polling window configuration (in Airbnb UI-relative format) ---
SCRAPE_DAY = date.today()
WINDOW_START = SCRAPE_DAY - timedelta(days=int(os.getenv("WINDOW_START_DAYS_AGO", 180)))
WINDOW_END   = SCRAPE_DAY + timedelta(days=int(os.getenv("WINDOW_END_DAYS_AHEAD", 180)))
WINDOW_SIZE  = int(os.getenv("WINDOW_SIZE", 28))


DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set in .env")

engine = create_engine(DATABASE_URL, future=True)