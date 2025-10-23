from jsonschema import validate

from sync_airbnb.flatteners.listings import flatten_listing_ids
from tests.utils.fixture import load_fixture
from tests.utils.schema import load_schema


def test_flatten_listing_ids_returns_string_map():
    data = load_fixture("ListingsSectionQuery.json")
    result = flatten_listing_ids(response=data)

    assert isinstance(result, dict)
    assert all(isinstance(k, str) and isinstance(v, str) for k, v in result.items())


def test_listing_id_to_name_mapping():
    data = load_fixture("ListingsSectionQuery.json")
    result = flatten_listing_ids(response=data)

    sample_id, name = next(iter(result.items()))
    assert sample_id.isdigit() or sample_id.isalnum()
    assert isinstance(name, str)


def test_listing_section_query_matches_schema():
    data = load_fixture("ListingsSectionQuery.json")
    result = flatten_listing_ids(response=data)
    schema = load_schema("listings_section.schema.json")
    validate(instance=result, schema=schema)
