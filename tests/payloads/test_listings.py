from sync_airbnb.payloads.listings import build_listings_payload


def test_build_listings_payload_structure():
    payload = build_listings_payload()
    assert "operationName" in payload
    assert payload["operationName"] == "ListingsSectionQuery"
    assert "variables" in payload
    assert "extensions" in payload
    assert "sha256Hash" in payload["extensions"]["persistedQuery"]
