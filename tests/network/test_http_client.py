from unittest.mock import Mock, patch

import pytest

from sync_airbnb.network.http_client import AirbnbRequestError, post_with_retry


@pytest.fixture
def mock_response():
    mock = Mock()
    mock.status_code = 200
    mock.json.return_value = {"data": {"foo": "bar"}}
    return mock


def test_successful_post(mock_response):
    with patch("sync_airbnb.network.http_client.requests.post", return_value=mock_response):
        result = post_with_retry("https://example.com", json={}, headers={}, context="test")
        assert "data" in result


def test_auth_401():
    mock = Mock(status_code=401, text="Unauthorized")
    with patch("sync_airbnb.network.http_client.requests.post", return_value=mock):
        with pytest.raises(AirbnbRequestError) as e:
            post_with_retry("https://example.com", json={}, headers={}, context="auth_test")
        assert "Auth error" in str(e.value)


def test_invalid_json():
    mock = Mock(status_code=200)
    mock.json.side_effect = ValueError("No JSON could be decoded")
    with patch("sync_airbnb.network.http_client.requests.post", return_value=mock):
        with pytest.raises(AirbnbRequestError) as e:
            post_with_retry("https://example.com", json={}, headers={}, context="bad_json")
        assert "Invalid JSON" in str(e.value)


def test_unexpected_structure():
    mock = Mock(status_code=200)
    mock.json.return_value = {"not_data": {}}
    with patch("sync_airbnb.network.http_client.requests.post", return_value=mock):
        with pytest.raises(AirbnbRequestError) as e:
            post_with_retry("https://example.com", json={}, headers={}, context="structure")
        assert "Unexpected response structure" in str(e.value)


def test_retryable_503():
    mock = Mock(status_code=503, text="Service Unavailable")
    with patch("sync_airbnb.network.http_client.requests.post", return_value=mock):
        with pytest.raises(Exception) as e:  # backoff raises original RequestException
            post_with_retry("https://example.com", json={}, headers={}, context="retry")
        assert "Retryable error" in str(e.value)
