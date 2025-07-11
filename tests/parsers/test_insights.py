import json
from pathlib import Path

from parsers.insights import parse_all
from jsonschema import validate

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures"
SCHEMA_DIR = Path(__file__).parent.parent.parent / "schemas"


def load_fixture(name: str):
    with open(FIXTURE_DIR / name) as f:
        return json.load(f)


def load_schema(name: str):
    with open(SCHEMA_DIR / name) as f:
        return json.load(f)


def test_parse_all_structure_keys():
    """
    Ensures top-level keys returned by parse_all are correct.
    """
    chunks = load_fixture("parsed_chunks.json")
    result = parse_all(chunks)

    assert isinstance(result, dict)
    assert set(result.keys()) == {"chart_query", "chart_summary", "list_of_metrics"}


def test_chart_query_timeseries_has_expected_columns():
    """
    Validates structure of parsed chart_query rows.
    """
    chunks = load_fixture("parsed_chunks.json")
    result = parse_all(chunks)
    chart_rows = result["chart_query"]

    assert isinstance(chart_rows, list)
    if chart_rows:
        row = chart_rows[0]
        assert "airbnb_listing_id" in row
        assert "airbnb_internal_name" in row
        assert "date" in row
        assert any("value" in k for k in row)


def test_chart_summary_metrics_pivoted_flat():
    """
    Validates structure of chart_summary (window-level pivot).
    """
    chunks = load_fixture("parsed_chunks.json")
    result = parse_all(chunks)
    rows = result["chart_summary"]

    if rows:
        row = rows[0]
        assert "airbnb_listing_id" in row
        assert "window_start" in row
        assert "window_end" in row
        assert any("_value" in k for k in row)


def test_list_of_metrics_query_window_grouping_and_fields():
    """
    Validates structure of list_of_metrics output (listing × window).
    """
    chunks = load_fixture("parsed_chunks.json")
    result = parse_all(chunks)
    rows = result["list_of_metrics"]

    if rows:
        row = rows[0]
        assert "airbnb_listing_id" in row
        assert "window_start" in row
        assert "window_end" in row
        assert any(k.endswith("_value") for k in row)


def test_parse_all_chart_query_matches_schema():
    """
    Validates chart_query section against schema.
    """
    chunks = load_fixture("parsed_chunks.json")
    result = parse_all(chunks)
    schema = load_schema("parsed_chart_query.schema.json")

    for row in result["chart_query"]:
        validate(instance=row, schema=schema)


def test_parse_all_chart_summary_matches_schema():
    """
    Validates chart_summary section against schema.
    """
    chunks = load_fixture("parsed_chunks.json")
    result = parse_all(chunks)
    schema = load_schema("parsed_chart_summary.schema.json")

    for row in result["chart_summary"]:
        validate(instance=row, schema=schema)


def test_parse_all_list_of_metrics_matches_schema():
    """
    Validates list_of_metrics section against schema.
    """
    chunks = load_fixture("parsed_chunks.json")
    result = parse_all(chunks)
    schema = load_schema("parsed_list_of_metrics.schema.json")

    for row in result["list_of_metrics"]:
        validate(instance=row, schema=schema)
