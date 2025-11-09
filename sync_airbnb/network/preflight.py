"""
Preflight request handler to obtain fresh Akamai Bot Manager cookies.

Before making GraphQL API requests, we make a GET request to an Airbnb page to obtain
fresh ak_bmsc and bm_sv cookies. These are merged with stored auth cookies to avoid
triggering bot detection with stale Akamai tokens.

This pattern is likely what competitors like RankBreeze use to maintain long-lived sessions.
"""

import logging

from curl_cffi import requests as curl_requests

from sync_airbnb.utils.cookie_utils import extract_akamai_cookies, parse_set_cookie_headers

logger = logging.getLogger(__name__)

# Preflight URL - use Airbnb homepage
# Note: Airbnb may not set Akamai cookies on simple GET requests anymore.
# The cookies might only be set via JavaScript or after certain user interactions.
PREFLIGHT_URL = "https://www.airbnb.com/"


def get_fresh_akamai_cookies(user_agent: str, auth_cookie: str | None = None, timeout: int = 10) -> dict[str, str]:
    """
    Make preflight GET request to obtain fresh Akamai Bot Manager cookies.

    This function mimics a browser visiting Airbnb before making GraphQL requests.
    The response includes fresh ak_bmsc and bm_sv cookies that are valid for the
    current session.

    Args:
        user_agent: Browser user agent string
        auth_cookie: Optional auth cookie string (if accessing authenticated pages)
        timeout: Request timeout in seconds

    Returns:
        dict: Dictionary of Akamai cookie names to values (ak_bmsc, bm_sv, bm_sz)

    Raises:
        Exception: If preflight request fails

    Example:
        >>> cookies = get_fresh_akamai_cookies("Mozilla/5.0...")
        >>> cookies
        {'ak_bmsc': 'C473307E...', 'bm_sv': '2EFC7187...'}
    """
    logger.debug(f"Making preflight request to {PREFLIGHT_URL}")

    headers = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Upgrade-Insecure-Requests": "1",
    }

    # Add auth cookie if provided (for accessing authenticated pages)
    if auth_cookie:
        headers["Cookie"] = auth_cookie

    try:
        # Use curl-cffi with Chrome impersonation for TLS fingerprinting
        response = curl_requests.get(
            PREFLIGHT_URL,
            headers=headers,
            timeout=timeout,
            allow_redirects=True,
            impersonate="chrome110",  # Mimic Chrome 110's TLS fingerprint
        )

        response.raise_for_status()

        # Log response details for debugging
        logger.debug(f"[PREFLIGHT] Response status: {response.status_code}")
        logger.debug(f"[PREFLIGHT] Response URL: {response.url}")

        # Log ALL response headers to debug why we're not getting Set-Cookie
        logger.debug("[PREFLIGHT] All response headers:")
        try:
            for header_name, header_value in response.headers.items():
                # Truncate long header values
                truncated_value = header_value[:100] + "..." if len(header_value) > 100 else header_value
                logger.debug(f"  {header_name}: {truncated_value}")
        except Exception as e:
            logger.warning(f"[PREFLIGHT] Could not iterate response headers: {e}")
            logger.debug(f"[PREFLIGHT] Headers type: {type(response.headers)}")

        # Extract cookies from Set-Cookie headers
        # curl_cffi returns headers as list of tuples
        set_cookies = parse_set_cookie_headers(response.headers)

        # Filter to only Akamai cookies
        akamai_cookies = extract_akamai_cookies("; ".join(f"{k}={v}" for k, v in set_cookies.items()))

        if not akamai_cookies:
            logger.warning("Preflight request succeeded but no Akamai cookies found in response")
            logger.warning(f"Set-Cookie headers received: {list(set_cookies.keys())}")
            # Log the raw Set-Cookie values using get_list() which handles multiple Set-Cookie headers
            try:
                set_cookie_list = response.headers.get_list("set-cookie")
                logger.warning(f"Number of Set-Cookie headers in response: {len(set_cookie_list)}")
                if set_cookie_list:
                    logger.debug(f"Set-Cookie values: {set_cookie_list}")
            except Exception as e:
                logger.debug(f"Could not get Set-Cookie list: {e}")
        else:
            logger.info(f"Preflight request successful, obtained {len(akamai_cookies)} Akamai cookies")
            # Log cookie names and truncated values for debugging (first 20 + last 20 chars)
            for name, value in akamai_cookies.items():
                truncated = f"{value[:20]}...{value[-20:]}" if len(value) > 40 else value
                logger.info(f"[PREFLIGHT] {name}={truncated}")

        return akamai_cookies

    except Exception as e:
        logger.error(f"Preflight request failed: {e}", exc_info=True)
        # Return empty dict instead of raising - caller can decide how to handle
        return {}
