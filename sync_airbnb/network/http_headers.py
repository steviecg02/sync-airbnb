"""
Defines standard headers used when making authenticated requests to Airbnb's GraphQL API.

Can be loaded from environment variables (for backwards compatibility) or dynamically
built from account credentials.

Headers are based on actual Chrome browser requests captured via DevTools to accurately
mimic browser fingerprinting including Client Hints and Sec-Fetch headers.
"""

import random
import string

from sync_airbnb.config import get_env


def build_headers(
    airbnb_cookie: str,
    x_client_version: str,
    user_agent: str,
    airbnb_api_key: str | None = None,
    referer: str | None = None,
    x_client_request_id: str | None = None,
    x_airbnb_network_log_link: str | None = None,
) -> dict[str, str]:
    """
    Build Airbnb API headers that match Chrome browser exactly.

    Based on actual Chrome DevTools captured requests to match browser fingerprint.
    Includes all Client Hints and Sec-Fetch headers for proper CORS and fingerprinting.

    Args:
        airbnb_cookie: Full Airbnb cookie string
        x_client_version: Airbnb client version (e.g., git commit SHA)
        user_agent: Browser user agent string
        airbnb_api_key: Airbnb API key (defaults to env var)
        referer: Page referer URL (optional, specific to endpoint)
        x_client_request_id: Client request ID (auto-generated 30-char random string if not provided)
        x_airbnb_network_log_link: Network log link (auto-generated 30-char random string if not provided)

    Returns:
        dict: Headers dictionary ready for requests, matching Chrome exactly
    """
    if airbnb_api_key is None:
        airbnb_api_key = get_env("AIRBNB_API_KEY") or ""

    # Generate unique trace ID per session (30 chars to match browser - used for request tracing)
    x_airbnb_client_trace_id = "".join(random.choices(string.ascii_lowercase + string.digits, k=30))

    # Generate unique request ID if not provided (30 chars to match browser)
    if x_client_request_id is None:
        x_client_request_id = "".join(random.choices(string.ascii_lowercase + string.digits, k=30))

    # Generate network log link if not provided (30 chars to match browser)
    if x_airbnb_network_log_link is None:
        x_airbnb_network_log_link = "".join(random.choices(string.ascii_lowercase + string.digits, k=30))

    headers = {
        # Standard HTTP headers (order matters for some fingerprinting)
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Content-Type": "application/json",
        # Connection quality hint (4g = high-speed connection)
        "ECT": "4g",
        # Priority hints for resource loading
        "Priority": "u=1, i",
        # Sec-Fetch headers (CRITICAL for CORS and anti-bot detection)
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        # Client Hints (important for fingerprinting - match real Chrome)
        "Sec-CH-Device-Memory": "8",
        "Sec-CH-DPR": "1.6",
        "Sec-CH-UA": '"Google Chrome";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"macOS"',
        "Sec-CH-UA-Platform-Version": '"14.7.3"',
        "Sec-CH-Viewport-Width": "2240",
        # User Agent (must match Sec-CH-UA)
        "User-Agent": user_agent,
        # Airbnb-specific headers
        "X-Airbnb-API-Key": airbnb_api_key,
        "X-Airbnb-Client-Trace-Id": x_airbnb_client_trace_id,
        "X-Airbnb-GraphQL-Platform": "web",
        "X-Airbnb-GraphQL-Platform-Client": "minimalist-niobe",
        "X-Airbnb-Network-Log-Link": x_airbnb_network_log_link,
        "X-Airbnb-Supports-Airlock-V2": "true",
        "X-Client-Request-Id": x_client_request_id,
        "X-Client-Version": x_client_version,
        "X-CSRF-Token": "",
        "X-CSRF-Without-Token": "1",
        "X-Niobe-Short-Circuited": "true",
    }

    # Only add Cookie header for legacy mode (non-Session requests)
    # When using curl_cffi Session, let Session manage cookies automatically
    if airbnb_cookie:
        headers["Cookie"] = airbnb_cookie

    # Add referer if provided (specific to the API endpoint being called)
    if referer:
        headers["Referer"] = referer

    return headers


# Backwards compatibility: default headers from environment variables
# Note: X_AIRBNB_CLIENT_TRACE_ID is auto-generated (no longer needed in env)
HEADERS = build_headers(
    airbnb_cookie=get_env("AIRBNB_COOKIE") or "",
    x_client_version=get_env("X_CLIENT_VERSION") or "",
    user_agent=get_env("USER_AGENT", required=False, default="Mozilla/5.0") or "Mozilla/5.0",
)
