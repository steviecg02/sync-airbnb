import logging
from .utils import get_first_component

logger = logging.getLogger(__name__)


def flatten_listing_ids(response: dict) -> dict[str, str]:
    """
    Extract a mapping of listing IDs to internal names from the ListingsSectionQuery response.

    Args:
        response (dict): Raw JSON response from Airbnb's ListingsSectionQuery.

    Returns:
        dict[str, str]: Dictionary mapping listing_id to internal_name.

    Raises:
        ValueError: If the expected structure is missing or parsing fails.
    """
    try:
        rows = get_first_component(response).get("tableRows", [])
        listing_map = {row["id"]: row["internalName"] for row in rows}
        logger.debug(f"Flattened {len(listing_map)} listing IDs.")
        return listing_map
    except Exception as e:
        logger.exception("Error flattening listing IDs.")
        raise ValueError(f"Failed to flatten listing IDs: {e}")
