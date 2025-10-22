"""
HTTP client for making POST requests to Airbnb's internal GraphQL API,
with retry handling and structured error responses.
"""

import logging
import requests
import backoff
from typing import Any, Optional

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {500, 502, 503, 504}


class AirbnbRequestError(Exception):
    """Raised when an Airbnb API call fails or returns an unexpected response."""


@backoff.on_exception(
    backoff.expo,
    (requests.exceptions.RequestException,),
    max_tries=5,
    jitter=None,
)
def post_with_retry(
    url: str,
    json: dict,
    headers: dict,
    timeout: int = 10,
    debug: bool = False,
    context: Optional[str] = None,
) -> dict[str, Any]:
    """
    Makes a POST request to Airbnb's API with retries and structured error handling.

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
        requests.exceptions.RequestException: For retryable HTTP errors.
    """
    try:
        res = requests.post(url, json=json, headers=headers, timeout=timeout)
    except requests.exceptions.RequestException as e:
        raise AirbnbRequestError(f"[{context}] Request failed: {e}") from e

    if debug:
        logger.debug("POST %s\nPayload:\n%s", url, json)
        logger.debug("Response status: %s", res.status_code)
        logger.debug("Response text:\n%s", res.text)

    if res.status_code in {401, 403}:
        raise AirbnbRequestError(
            f"[{context}] Auth error: {res.status_code} - {res.text.strip()}"
        )

    if res.status_code in RETRYABLE_STATUS_CODES:
        raise requests.exceptions.RequestException(
            f"[{context}] Retryable error: {res.status_code} - {res.text.strip()}"
        )

    try:
        data = res.json()
    except ValueError:
        raise AirbnbRequestError(
            f"[{context}] Invalid JSON response: {res.text.strip()}"
        )

    if not isinstance(data, dict) or "data" not in data:
        raise AirbnbRequestError(f"[{context}] Unexpected response structure: {data}")

    return data
