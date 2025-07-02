from .utils import get_first_component

def flatten_listing_ids(response: dict) -> dict[str, str]:
    """
    Extract {listing_id: internal_name} from raw ListingsSectionQuery response.
    """
    try:
        rows = get_first_component(response).get("tableRows", [])
        return {row["id"]: row["internalName"] for row in rows}
    except Exception as e:
        raise ValueError(f"Failed to flatten listing IDs: {e}")