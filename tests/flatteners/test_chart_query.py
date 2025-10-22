from jsonschema import validate
from sync_airbnb.flatteners.insights import flatten_chart_query
from tests.utils.fixture import load_fixture
from tests.utils.schema import load_schema


def test_chart_query_conversion_rate_structure():
    data = load_fixture("ChartQuery_CONVERSION_conversion_rate.json")
    result = flatten_chart_query(response=data)

    assert "timeseries_rows" in result
    assert isinstance(result["timeseries_rows"], list)


def test_chart_query_p3_impressions_primary_metric():
    data = load_fixture("ChartQuery_CONVERSION_p3_impressions.json")
    result = flatten_chart_query(response=data)

    primary = result["primary_metric"]
    assert isinstance(primary, dict)
    assert primary.get("metric_name") == "p3_impressions"


def test_chart_query_grouping_and_pivoting():
    data = load_fixture("ChartQuery_CONVERSION_conversion_rate.json")
    result = flatten_chart_query(response=data)
    rows = result["timeseries_rows"]

    assert len(rows) > 0
    assert "ds" in rows[0]


def test_chart_query_response_conversions_matches_schema():
    data = load_fixture("ChartQuery_CONVERSION_conversion_rate.json")
    result = flatten_chart_query(data)
    schema = load_schema("chart_query.schema.json")
    validate(instance=result, schema=schema)


def test_chart_query_response_impressions_matches_schema():
    data = load_fixture("ChartQuery_CONVERSION_p3_impressions.json")
    result = flatten_chart_query(data)
    schema = load_schema("chart_query.schema.json")
    validate(instance=result, schema=schema)
