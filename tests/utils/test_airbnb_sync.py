# tests/utils/test_airbnb_sync.py

from pathlib import Path
import json
import pytest
from datetime import date
from sync_airbnb.utils.airbnb_sync import AirbnbSync

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def sync_instance():
    return AirbnbSync(scrape_day=date(2025, 7, 11), debug=True)


@pytest.fixture
def listings_fixture():
    with open(FIXTURE_DIR / "ListingsSectionQuery.json") as f:
        return json.load(f)


@pytest.fixture
def chart_query_fixture():
    with open(FIXTURE_DIR / "ChartQuery_CONVERSION_conversion_rate.json") as f:
        return json.load(f)


@pytest.fixture
def list_of_metrics_fixture():
    with open(FIXTURE_DIR / "ListOfMetricsQuery_CONVERSION_conversion_rate.json") as f:
        return json.load(f)


def test_flatten_listings_section(sync_instance, listings_fixture):
    result = sync_instance.flatten("ListingsSectionQuery", {"data": listings_fixture})
    assert isinstance(result, dict)
    assert all(isinstance(k, str) and isinstance(v, str) for k, v in result.items())


def test_flatten_chart_query(sync_instance, chart_query_fixture):
    response = {
        "data": chart_query_fixture,
        "meta": {
            "listing_id": "123",
            "listing_name": "Test Listing",
            "query_type": "ChartQuery",
        },
    }
    result = sync_instance.flatten("ChartQuery", response)
    assert "meta" in result
    assert "timeseries_rows" in result


def test_flatten_list_of_metrics(sync_instance, list_of_metrics_fixture):
    response = {
        "data": list_of_metrics_fixture,
        "meta": {
            "listing_id": "123",
            "listing_name": "Test Listing",
            "query_type": "ListOfMetricsQuery",
        },
    }
    result = sync_instance.flatten("ListOfMetricsQuery", response)
    assert "meta" in result
    assert "timeseries_rows" in result


def test_get_url_valid(sync_instance):
    url = sync_instance.get_url("ChartQuery")
    assert url.startswith("https://")


def test_get_url_invalid(sync_instance):
    with pytest.raises(ValueError):
        sync_instance.get_url("InvalidQuery")


def test_parse_all_empty(sync_instance):
    result = sync_instance.parse_all()
    assert set(result.keys()) == {"chart_query", "chart_summary", "list_of_metrics"}
