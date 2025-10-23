"""
Defines standard headers used when making authenticated requests to Airbnb's GraphQL API.

Can be loaded from environment variables (for backwards compatibility) or dynamically
built from account credentials.
"""

from sync_airbnb.config import get_env


def build_headers(
    airbnb_cookie: str,
    x_client_version: str,
    x_airbnb_client_trace_id: str,
    user_agent: str,
    airbnb_api_key: str | None = None,
) -> dict[str, str]:
    """
    Build Airbnb API headers from account credentials.

    Args:
        airbnb_cookie: Full Airbnb cookie string
        x_client_version: Airbnb client version
        x_airbnb_client_trace_id: Airbnb client trace ID
        user_agent: Browser user agent string
        airbnb_api_key: Airbnb API key (defaults to env var)

    Returns:
        dict: Headers dictionary ready for requests
    """
    if airbnb_api_key is None:
        airbnb_api_key = get_env("AIRBNB_API_KEY") or ""

    return {
        # Session + Auth
        "Cookie": airbnb_cookie,
        "X-Airbnb-API-Key": airbnb_api_key,
        "X-CSRF-Token": "",
        "X-CSRF-Without-Token": "1",
        # Client Context
        "X-Client-Version": x_client_version,
        "X-Client-Request-Id": "manual-dev",
        "X-Airbnb-Client-Trace-Id": x_airbnb_client_trace_id,
        "User-Agent": user_agent,
        # Internal Feature Flags
        "X-Airbnb-GraphQL-Platform": "web",
        "X-Airbnb-GraphQL-Platform-Client": "minimalist-niobe",
        "X-Airbnb-Supports-Airlock-V2": "true",
        "X-Niobe-Short-Circuited": "true",
        # Standard HTTP headers
        "Accept": "*/*",
        "Content-Type": "application/json",
    }


# Backwards compatibility: default headers from environment variables
HEADERS = build_headers(
    airbnb_cookie=get_env("AIRBNB_COOKIE") or "",
    x_client_version=get_env("X_CLIENT_VERSION") or "",
    x_airbnb_client_trace_id=get_env("X_AIRBNB_CLIENT_TRACE_ID") or "",
    user_agent=get_env("USER_AGENT", required=False, default="Mozilla/5.0") or "Mozilla/5.0",
)
