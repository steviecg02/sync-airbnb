"""
Preflight request handler to create an authenticated Session with fresh cookies.

Before making GraphQL API requests, we create a curl_cffi Session, load auth cookies,
and make a GET request to /hosting/insights to obtain fresh bot detection cookies.
The Session automatically captures Set-Cookie headers (for both auth and bot cookies),
allowing cookies to evolve over time like a real browser.

This pattern ensures:
1. Auth cookies are rotated when Airbnb sends updated values via Set-Cookie
2. Bot detection cookies (ak_bmsc, bm_sv) are fresh for each sync
3. Session is validated (not redirected to login)
"""

import logging

from curl_cffi import requests as curl_requests

from sync_airbnb.network.http_client import AirbnbAuthError

logger = logging.getLogger(__name__)

# Preflight URL - authenticated page that triggers cookie rotation
PREFLIGHT_URL = "https://www.airbnb.com/hosting/insights"


def create_preflight_session(
    user_agent: str,
    auth_cookies: dict[str, str],
    timeout: int = 30,
) -> curl_requests.Session:
    """
    Create an authenticated curl_cffi Session with fresh cookies via preflight request.

    This function:
    1. Creates a Session with Chrome 110 TLS fingerprinting
    2. Loads auth cookies from database into Session
    3. Makes GET request to /hosting/insights (triggers cookie rotation)
    4. Validates session is alive (not redirected to login)
    5. Returns Session with evolved cookies (auth + fresh bot cookies)

    The Session automatically captures all Set-Cookie headers from responses,
    so cookies evolve throughout the sync just like in a real browser.

    Args:
        user_agent: Browser user agent string
        auth_cookies: Dict of auth cookie names to values from database
        timeout: Request timeout in seconds

    Returns:
        curl_requests.Session: Authenticated session ready for GraphQL requests,
            with cookies automatically managed (captures Set-Cookie headers)

    Raises:
        AirbnbAuthError: If session is dead (redirected to login)
        Exception: If preflight request fails

    Example:
        >>> auth_cookies = {'_airbed_session_id': 'abc', '_aaj': 'xyz', ...}
        >>> session = create_preflight_session("Mozilla/5.0...", auth_cookies)
        >>> # Use session for GraphQL requests
        >>> response = session.post(graphql_url, json=payload)
    """
    logger.info("[PREFLIGHT] Creating session with Chrome 110 impersonation")

    # Create Session with Chrome TLS fingerprinting
    session = curl_requests.Session(impersonate="chrome110")

    # Set standard browser headers
    session.headers.update(
        {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Upgrade-Insecure-Requests": "1",
        }
    )

    # Load auth cookies into Session
    logger.info(f"[PREFLIGHT] Loading {len(auth_cookies)} auth cookies into session: {list(auth_cookies.keys())}")
    for name, value in auth_cookies.items():
        session.cookies.set(name, value, domain=".airbnb.com")

    logger.info(f"[PREFLIGHT] Session has {len(session.cookies)} cookies before preflight")

    # Make preflight request
    logger.info(f"[PREFLIGHT] Requesting {PREFLIGHT_URL}")

    try:
        response = session.get(
            PREFLIGHT_URL,
            allow_redirects=True,
            timeout=timeout,
        )

        response.raise_for_status()

        # Log response details
        logger.info(f"[PREFLIGHT] Response: {response.status_code} from {response.url}")

        # Check if redirected to login (session dead)
        if "login" in response.url.lower() or "authenticate" in response.url.lower():
            logger.error(f"[PREFLIGHT] SESSION DEAD - Redirected to login at {response.url}")
            raise AirbnbAuthError(f"Session expired, redirected to login: {response.url}")

        logger.info("[PREFLIGHT] Session valid (not redirected to login)")

        # Log Set-Cookie headers received
        try:
            set_cookie_list = response.headers.get_list("set-cookie")
            if set_cookie_list:
                cookie_names = [cookie.split("=")[0] for cookie in set_cookie_list]
                logger.info(f"[PREFLIGHT] Received {len(set_cookie_list)} Set-Cookie headers: {cookie_names}")
            else:
                logger.info("[PREFLIGHT] No Set-Cookie headers in response (cookies unchanged)")
        except Exception as e:
            logger.debug(f"[PREFLIGHT] Could not parse Set-Cookie headers: {e}")

        # Log final cookie count (Session auto-captured Set-Cookie headers)
        logger.info(f"[PREFLIGHT] Session now has {len(session.cookies)} total cookies")

        return session

    except AirbnbAuthError:
        # Re-raise auth errors
        raise
    except Exception as e:
        logger.error(f"[PREFLIGHT] Request failed: {e}", exc_info=True)
        raise
