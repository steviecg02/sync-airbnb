from datetime import date
import pytest
from payloads.insights import build_metric_payload


@pytest.fixture
def base_args():
    return {
        "listing_id": "12345",
        "start_date": date(2025, 7, 7),
        "end_date": date(2025, 7, 14),
        "scrape_day": date(2025, 7, 5),
        "metric_type": "RATING",
        "group_values": ["POSITIVE"],
    }


def test_chart_query_payload_has_expected_structure(base_args):
    payload = build_metric_payload(query_type="ChartQuery", **base_args)
    assert payload["operationName"] == "ChartQuery"
    assert payload["variables"]["request"]["arguments"]["relativeDsStart"] == 5
    assert payload["variables"]["request"]["arguments"]["relativeDsEnd"] == 12
    assert payload["variables"]["request"]["arguments"]["groupByValues"] == ["POSITIVE"]
    assert "metricComparisonType" not in payload["variables"]["request"]["arguments"]


def test_include_comparison_adds_market_flag(base_args):
    payload = build_metric_payload(
        query_type="ChartQuery", include_comparison=True, **base_args
    )
    args = payload["variables"]["request"]["arguments"]
    assert args["metricComparisonType"] == "MARKET"


def test_invalid_query_type_raises():
    with pytest.raises(ValueError, match="Unsupported query_type"):
        build_metric_payload(
            query_type="FakeQuery",
            listing_id="123",
            start_date=date.today(),
            end_date=date.today(),
            scrape_day=date.today(),
            metric_type="FAKE",
            group_values=[],
        )
