"""
Cookie parsing and management utilities for handling Airbnb authentication cookies.

Separates persistent auth cookies from ephemeral Akamai Bot Manager cookies to enable
preflight pattern for obtaining fresh bot detection tokens.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Auth cookies that should be stored persistently
AUTH_COOKIE_NAMES = {
    "_airbed_session_id",  # Core session identifier
    "_aaj",  # Auth token (rotates frequently)
    "_aat",  # Additional auth token
    "auth_jitney_session_id",  # Jitney session (Airbnb's auth service)
    "hli",  # Host listing indicator
    "li",  # Listing indicator
    "_user_attributes",  # User metadata
    "_pt",  # Persistent token
    "rclu",  # Recently clicked listing unit
}


def parse_cookie_string(cookie_string: str) -> dict[str, str]:
    """
    Parse a cookie string into a dictionary of name/value pairs.

    Args:
        cookie_string: Cookie string in format "name1=value1; name2=value2"

    Returns:
        dict: Dictionary mapping cookie names to values

    Example:
        >>> parse_cookie_string("session=abc123; user=test")
        {'session': 'abc123', 'user': 'test'}
    """
    cookies: dict[str, str] = {}

    if not cookie_string:
        return cookies

    for cookie_pair in cookie_string.split(";"):
        cookie_pair = cookie_pair.strip()
        if "=" not in cookie_pair:
            continue

        name, value = cookie_pair.split("=", 1)
        cookies[name.strip()] = value.strip()

    return cookies


def build_cookie_string(cookies: dict[str, str]) -> str:
    """
    Build a cookie string from a dictionary of name/value pairs.

    Args:
        cookies: Dictionary mapping cookie names to values

    Returns:
        str: Cookie string in format "name1=value1; name2=value2"

    Example:
        >>> build_cookie_string({'session': 'abc123', 'user': 'test'})
        'session=abc123; user=test'
    """
    return "; ".join(f"{name}={value}" for name, value in cookies.items())


def filter_auth_cookies_only(cookies: dict[str, str]) -> dict[str, str]:
    """
    Filter to only the 7 required auth cookies, removing bot detection and analytics cookies.

    This is used after sync to persist only the essential auth cookies to the database.
    Bot detection cookies (ak_bmsc, bm_sv) are ephemeral and should be obtained fresh
    each sync via preflight.

    Args:
        cookies: Dictionary of all cookie name/value pairs

    Returns:
        dict: Dictionary containing only the 7 auth cookies:
            _airbed_session_id, _aaj, _aat, auth_jitney_session_id,
            _user_attributes, hli, li

    Example:
        >>> all_cookies = {'_airbed_session_id': 'abc', 'ak_bmsc': 'xyz', '_ga': '123'}
        >>> filter_auth_cookies_only(all_cookies)
        {'_airbed_session_id': 'abc'}
    """
    auth_cookies = {name: value for name, value in cookies.items() if name in AUTH_COOKIE_NAMES}

    discarded_count = len(cookies) - len(auth_cookies)
    logger.info(f"[COOKIE_FILTER] Filtering {len(cookies)} cookies → {len(auth_cookies)} auth cookies only")
    logger.info(f"[COOKIE_FILTER] Keeping: {list(auth_cookies.keys())}")
    if discarded_count > 0:
        logger.info(f"[COOKIE_FILTER] Discarding {discarded_count} non-auth cookies")

    return auth_cookies


def parse_set_cookie_headers(headers: Any) -> dict[str, str]:
    """
    Parse Set-Cookie headers from HTTP response into cookie dictionary.

    Handles both dict-style headers and list of tuples (from curl_cffi).
    curl_cffi returns a custom Headers type that is iterable as list of tuples.

    Args:
        headers: Response headers (dict, list of tuples, or curl_cffi Headers object)

    Returns:
        dict: Dictionary of cookie names to values

    Example:
        >>> headers = {'Set-Cookie': 'ak_bmsc=xyz; Path=/; HttpOnly'}
        >>> parse_set_cookie_headers(headers)
        {'ak_bmsc': 'xyz'}
    """
    cookies: dict[str, str] = {}

    # Handle dict-style headers
    if isinstance(headers, dict):
        set_cookie_value = headers.get("Set-Cookie", "")
        if set_cookie_value:
            # Can be a single string or list of strings
            if isinstance(set_cookie_value, list):
                cookie_strings = set_cookie_value
            else:
                cookie_strings = [set_cookie_value]

            for cookie_string in cookie_strings:
                # Parse the cookie (only the name=value part, ignore attributes)
                if "=" in cookie_string:
                    cookie_pair = cookie_string.split(";")[0].strip()
                    name, value = cookie_pair.split("=", 1)
                    cookies[name.strip()] = value.strip()

    # Handle curl_cffi Headers object (has get_list method)
    else:
        try:
            # Try to use get_list() method (curl_cffi Headers)
            if hasattr(headers, "get_list"):
                set_cookie_list = headers.get_list("set-cookie")
                for header_value in set_cookie_list:
                    if "=" in header_value:
                        cookie_pair = header_value.split(";")[0].strip()
                        name, value = cookie_pair.split("=", 1)
                        cookies[name.strip()] = value.strip()
            # Fallback: try iterating as list of tuples
            else:
                for header_name, header_value in headers:
                    if header_name.lower() == "set-cookie":
                        if "=" in header_value:
                            cookie_pair = header_value.split(";")[0].strip()
                            name, value = cookie_pair.split("=", 1)
                            cookies[name.strip()] = value.strip()
        except (TypeError, ValueError, AttributeError):
            # If all methods fail, just return empty dict
            pass

    return cookies
