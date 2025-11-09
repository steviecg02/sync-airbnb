"""
HTTP client for making POST requests to Airbnb's internal GraphQL API,
with retry handling and structured error responses.

Uses curl-cffi to mimic Chrome's TLS fingerprint for better bot detection evasion.
"""

import logging
import random
import time
from typing import Any

import backoff
from curl_cffi import requests as curl_requests

from sync_airbnb.metrics import (
    airbnb_api_request_duration_seconds,
    airbnb_api_requests_total,
    airbnb_api_retries_total,
    errors_total,
)

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {500, 502, 503, 504}


class AirbnbRequestError(Exception):
    """Raised when an Airbnb API call fails or returns an unexpected response."""


class AirbnbAuthError(Exception):
    """Raised when Airbnb returns authentication/login required error.

    This is a critical error that should stop all sync operations immediately.
    """


def _log_retry(details):
    """Callback for backoff retries to track in Prometheus."""
    endpoint = details.get("args", ["unknown"])[0] if details.get("args") else "unknown"
    airbnb_api_retries_total.labels(endpoint=endpoint).inc()
    logger.warning(f"Retrying request to {endpoint} (attempt {details['tries']})")


@backoff.on_exception(
    backoff.expo,
    (Exception,),  # curl_cffi uses different exception types
    max_tries=5,
    jitter=None,
    on_backoff=_log_retry,
)
def post_with_retry(
    url: str,
    json: dict,
    headers: dict,
    timeout: int = 10,
    debug: bool = False,
    context: str | None = None,
) -> dict[str, Any]:
    """
    Makes a POST request to Airbnb's API with retries and structured error handling.

    Uses curl-cffi with Chrome impersonation to mimic real browser TLS fingerprint.
    This helps avoid Akamai Bot Manager detection.

    Args:
        url (str): Target API endpoint.
        json (dict): JSON body to send with the request.
        headers (dict): HTTP headers to include.
        timeout (int, optional): Timeout in seconds. Defaults to 10.
        debug (bool, optional): If True, logs request/response. Defaults to False.
        context (Optional[str], optional): Debug context for logging. Defaults to None.

    Returns:
        dict[str, Any]: Parsed JSON response.

    Raises:
        AirbnbRequestError: If the request fails or returns unexpected content.
        Exception: For retryable HTTP errors (caught by backoff decorator).
    """
    endpoint = context or url
    start_time = time.time()

    # Log every API call with context
    logger.info(f"[API_CALL] {context or 'Unknown'}")

    try:
        # Use curl-cffi with Chrome 110 impersonation for TLS fingerprinting
        res = curl_requests.post(
            url, json=json, headers=headers, timeout=timeout, impersonate="chrome110"  # Mimic Chrome's TLS fingerprint
        )
        duration = time.time() - start_time

        # Track request metrics
        airbnb_api_requests_total.labels(endpoint=endpoint, status_code=res.status_code).inc()
        airbnb_api_request_duration_seconds.labels(endpoint=endpoint).observe(duration)

    except Exception as e:
        duration = time.time() - start_time
        airbnb_api_request_duration_seconds.labels(endpoint=endpoint).observe(duration)
        airbnb_api_requests_total.labels(endpoint=endpoint, status_code="error").inc()
        errors_total.labels(error_type=type(e).__name__, component="network").inc()
        raise AirbnbRequestError(f"[{context}] Request failed: {e}") from e

    if debug:
        logger.debug("POST %s\nPayload:\n%s", url, json)
        logger.debug("Response status: %s", res.status_code)
        logger.debug("Response text:\n%s", res.text)

    if res.status_code in {401, 403}:
        errors_total.labels(error_type="AuthError", component="network").inc()
        raise AirbnbRequestError(f"[{context}] Auth error: {res.status_code} - {res.text}")

    if res.status_code == 429:
        # Rate limit hit - log prominently and raise for retry
        errors_total.labels(error_type="RateLimitError", component="network").inc()
        retry_after = res.headers.get("Retry-After", "unknown")
        logger.warning(f"RATE LIMIT HIT (429) - Context: {context}, Retry-After: {retry_after}s, Response: {res.text}")
        raise Exception(f"[{context}] Rate limit error (429) - Retry-After: {retry_after}s")

    if res.status_code in RETRYABLE_STATUS_CODES:
        raise Exception(f"[{context}] Retryable error: {res.status_code} - {res.text}")

    try:
        data = res.json()
    except ValueError:
        raise AirbnbRequestError(f"[{context}] Invalid JSON response: {res.text}")

    if not isinstance(data, dict) or "data" not in data:
        raise AirbnbRequestError(f"[{context}] Unexpected response structure: {data}")

    # Rate limiting: mimic human clicking through UI (5-10 seconds between requests)
    delay = random.uniform(5, 10)
    logger.debug(f"[RATE_LIMIT] Waiting {delay:.1f}s before next request")
    time.sleep(delay)

    return data
