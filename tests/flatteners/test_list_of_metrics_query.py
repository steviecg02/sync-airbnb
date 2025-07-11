from jsonschema import validate
from flatteners.insights import flatten_list_of_metrics_query
from tests.utils.fixture import load_fixture
from tests.utils.schema import load_schema


def test_list_of_metrics_conversion_rate_structure():
    data = load_fixture("ListOfMetricsQuery_CONVERSION_conversion_rate.json")
    result = flatten_list_of_metrics_query(response=data)

    assert "timeseries_rows" in result
    assert isinstance(result["timeseries_rows"], list)

    if result["timeseries_rows"]:
        row = result["timeseries_rows"][0]
        assert "metric_name" in row
        assert "value" in row or "value_string" in row


def test_list_of_metrics_p3_impressions_expected_values():
    data = load_fixture("ListOfMetricsQuery_CONVERSION_p3_impressions.json")
    result = flatten_list_of_metrics_query(response=data)
    metrics = result.get("timeseries_rows", [])

    assert metrics
    assert "metric_name" in metrics[0]


def test_list_of_metrics_field_naming():
    data = load_fixture("ListOfMetricsQuery_CONVERSION_conversion_rate.json")
    result = flatten_list_of_metrics_query(response=data)
    rows = result["timeseries_rows"]

    assert rows
    metric = rows[0]
    assert "metric_name" in metric
    assert "value" in metric


def test_list_of_metrics_response_conversions_matches_schema():
    data = load_fixture("ListOfMetricsQuery_CONVERSION_conversion_rate.json")
    result = flatten_list_of_metrics_query(response=data)
    schema = load_schema("list_of_metrics.schema.json")
    validate(instance=result, schema=schema)


def test_list_of_metrics_response_impressions_matches_schema():
    data = load_fixture("ListOfMetricsQuery_CONVERSION_p3_impressions.json")
    result = flatten_list_of_metrics_query(response=data)
    schema = load_schema("list_of_metrics.schema.json")
    validate(instance=result, schema=schema)
