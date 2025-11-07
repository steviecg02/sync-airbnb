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

# Akamai Bot Manager cookies (ephemeral, obtained via preflight)
AKAMAI_COOKIE_NAMES = {
    "ak_bmsc",  # Akamai Bot Manager Session Cookie
    "bm_sv",  # Bot Manager Sensor Value
    "bm_sz",  # Bot Manager Size
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


def extract_auth_cookies(cookie_string: str) -> dict[str, str]:
    """
    Extract only auth cookies from a full cookie string.

    Filters out Akamai Bot Manager cookies and analytics cookies, keeping only
    the persistent authentication cookies needed for subsequent requests.

    Args:
        cookie_string: Full cookie string from browser

    Returns:
        dict: Dictionary of auth cookie names to values

    Example:
        >>> extract_auth_cookies("_airbed_session_id=abc; ak_bmsc=xyz; _ga=123")
        {'_airbed_session_id': 'abc'}
    """
    all_cookies = parse_cookie_string(cookie_string)
    auth_cookies = {name: value for name, value in all_cookies.items() if name in AUTH_COOKIE_NAMES}

    logger.debug(f"Extracted {len(auth_cookies)} auth cookies from {len(all_cookies)} total cookies")
    return auth_cookies


def extract_akamai_cookies(cookie_string: str) -> dict[str, str]:
    """
    Extract only Akamai Bot Manager cookies from a cookie string.

    Args:
        cookie_string: Cookie string from response

    Returns:
        dict: Dictionary of Akamai cookie names to values

    Example:
        >>> extract_akamai_cookies("ak_bmsc=xyz123; bm_sv=abc456; session=test")
        {'ak_bmsc': 'xyz123', 'bm_sv': 'abc456'}
    """
    all_cookies = parse_cookie_string(cookie_string)
    akamai_cookies = {name: value for name, value in all_cookies.items() if name in AKAMAI_COOKIE_NAMES}

    logger.debug(f"Extracted {len(akamai_cookies)} Akamai cookies from {len(all_cookies)} total cookies")
    return akamai_cookies


def merge_cookies(auth_cookies: dict[str, str], akamai_cookies: dict[str, str]) -> str:
    """
    Merge auth cookies with fresh Akamai cookies into a single cookie string.

    This is the core of the preflight pattern: combine stored auth cookies with
    freshly obtained Akamai Bot Manager tokens.

    Args:
        auth_cookies: Persistent auth cookies from storage
        akamai_cookies: Fresh Akamai cookies from preflight request

    Returns:
        str: Merged cookie string ready for API request

    Example:
        >>> merge_cookies({'session': 'abc'}, {'ak_bmsc': 'xyz'})
        'session=abc; ak_bmsc=xyz'
    """
    merged = {**auth_cookies, **akamai_cookies}
    return build_cookie_string(merged)


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

    # Handle list of tuples (curl_cffi style and curl_cffi Headers object)
    # curl_cffi Headers object is iterable as list of tuples
    else:
        try:
            for header_name, header_value in headers:
                if header_name.lower() == "set-cookie":
                    if "=" in header_value:
                        cookie_pair = header_value.split(";")[0].strip()
                        name, value = cookie_pair.split("=", 1)
                        cookies[name.strip()] = value.strip()
        except (TypeError, ValueError):
            # If iteration fails, just return empty dict
            pass

    return cookies
