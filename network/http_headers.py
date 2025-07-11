"""
Defines standard headers used when making authenticated requests to Airbnb's GraphQL API.

Environment variables are loaded at module level via get_env(). Missing required vars will raise at import time.
"""

from config import get_env

HEADERS = {
    # Session + Auth
    "Cookie": get_env("AIRBNB_COOKIE"),
    "X-Airbnb-API-Key": "d306zoyjsyarp7ifhu67rjxn52tv0t20",  # Public API key used by web clients
    "X-CSRF-Token": get_env("X_CSRF_TOKEN", required=False, default=""),
    "X-CSRF-Without-Token": "1",
    # Client Context
    "X-Client-Version": get_env("X_CLIENT_VERSION"),
    "X-Client-Request-Id": get_env(
        "X_CLIENT_REQUEST_ID", required=False, default="manual-dev"
    ),
    "X-Airbnb-Client-Trace-Id": get_env("X_AIRBNB_CLIENT_TRACE_ID"),
    "User-Agent": get_env("USER_AGENT", required=False, default="Mozilla/5.0"),
    # Internal Feature Flags
    "X-Airbnb-GraphQL-Platform": "web",
    "X-Airbnb-GraphQL-Platform-Client": "minimalist-niobe",
    "X-Airbnb-Supports-Airlock-V2": "true",
    "X-Niobe-Short-Circuited": "true",
    # Standard HTTP headers
    "Accept": "*/*",
    "Content-Type": "application/json",
}
