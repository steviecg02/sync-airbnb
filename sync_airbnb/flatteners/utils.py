import logging
from typing import Any

from sync_airbnb.network.http_client import AirbnbAuthError

logger = logging.getLogger(__name__)


def get_first_component(response: dict) -> dict:
    """
    Return the first component from a standard Airbnb GraphQL metrics response.

    Handles deep nesting:
        data → porygon → getPerformanceComponents → components[0]

    Args:
        response (dict): Parsed JSON response from Airbnb GraphQL.

    Returns:
        dict: The first component block, or an empty dict if missing.
    """
    # Check for authentication errors in the response
    errors = response.get("errors", [])
    auth_error = any(err.get("extensions", {}).get("errorType") == "authentication_required" for err in errors)

    # Fallback: check if getPerformanceComponents is explicitly set to null (not just missing)
    # Only treat as auth error if "porygon" key exists and getPerformanceComponents is explicitly None
    if not auth_error and "porygon" in response.get("data", {}):
        porygon = response["data"]["porygon"]
        if "getPerformanceComponents" in porygon and porygon["getPerformanceComponents"] is None:
            auth_error = True

    if auth_error:
        # Extract error message from Airbnb's response
        error_msg = "Please login to continue (credentials expired)"
        if errors:
            error_msg = errors[0].get("message", error_msg)
        # Raise specific auth error to stop sync immediately
        logger.error(f"[AUTH_FAILURE] {error_msg}")
        raise AirbnbAuthError(f"Airbnb authentication failed: {error_msg}")

    try:
        component = (
            response.get("data", {}).get("porygon", {}).get("getPerformanceComponents", {}).get("components", [{}])[0]
        )
        return component or {}
    except Exception as e:
        logger.exception("Failed to extract first component from response")
        raise ValueError("Could not resolve component structure") from e


def extract_numeric_value(value_dict: Any) -> int | float | None:
    """
    Extracts a numeric value from a GraphQL numeric wrapper dict.

    GraphQL responses may store numbers under:
        - "doubleValue" (float)
        - "longValue" (int)

    Args:
        value_dict (dict): The value wrapper dict.

    Returns:
        int | float | None: The extracted number, or None if missing.
    """
    if not isinstance(value_dict, dict):
        logger.debug("Expected dict for value extraction, got: %s", type(value_dict))
        return None
    if value_dict.get("doubleValue") is not None:
        return value_dict["doubleValue"]
    return value_dict.get("longValue")


def coerce_number(val: Any) -> int | float | None:
    """
    Coerce string representations of numbers to int or float, return None for invalid values.

    Args:
        val (Any): The value to coerce.

    Returns:
        int | float | None: The coerced number or None if coercion fails or value is invalid.
    """
    # Handle None explicitly
    if val is None:
        return None

    # Handle numeric types directly
    if isinstance(val, int | float):
        return val

    # Handle strings
    if isinstance(val, str):
        try:
            return int(val) if val.isdigit() else float(val)
        except ValueError:
            logger.debug("Failed to coerce string to number: %s", val)
            return None

    # Defensive: catch unexpected types (like SQLAlchemy bindparam objects)
    logger.warning(
        "Unexpected value type in coerce_number: %s (type=%s). Returning None.",
        repr(val)[:100],
        type(val).__name__,
    )
    return None
