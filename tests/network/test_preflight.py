"""Tests for preflight session creation."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from sync_airbnb.network.http_client import AirbnbAuthError
from sync_airbnb.network.preflight import create_preflight_session


@patch("sync_airbnb.network.preflight.curl_requests.Session")
def test_create_preflight_session_success(mock_session_class):
    """Test successful preflight session creation."""
    # Setup mock
    mock_session = Mock()
    mock_session.cookies = MagicMock()
    mock_session_class.return_value = mock_session

    # Mock response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.url = "https://www.airbnb.com/hosting/insights"
    mock_response.headers.get_list.return_value = [
        "ak_bmsc=xyz; Path=/",
        "bm_sv=abc; Path=/",
    ]
    mock_session.get.return_value = mock_response

    # Execute
    user_agent = "Mozilla/5.0"
    auth_cookies = {"_airbed_session_id": "abc", "_aaj": "xyz"}
    session = create_preflight_session(user_agent, auth_cookies, timeout=30)

    # Verify
    assert session == mock_session
    mock_session_class.assert_called_once_with(impersonate="chrome110")
    mock_session.get.assert_called_once()
    mock_response.raise_for_status.assert_called_once()


@patch("sync_airbnb.network.preflight.curl_requests.Session")
def test_create_preflight_session_redirects_to_login(mock_session_class):
    """Test preflight raises AirbnbAuthError when redirected to login."""
    # Setup mock
    mock_session = Mock()
    mock_session.cookies = MagicMock()
    mock_session_class.return_value = mock_session

    # Mock response - redirected to login
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.url = "https://www.airbnb.com/login"
    mock_session.get.return_value = mock_response

    # Execute and verify exception
    with pytest.raises(AirbnbAuthError, match="Session expired"):
        create_preflight_session("Mozilla/5.0", {"_airbed_session_id": "abc"})


@patch("sync_airbnb.network.preflight.curl_requests.Session")
def test_create_preflight_session_redirects_to_authenticate(mock_session_class):
    """Test preflight raises AirbnbAuthError when redirected to authenticate."""
    # Setup mock
    mock_session = Mock()
    mock_session.cookies = MagicMock()
    mock_session_class.return_value = mock_session

    # Mock response - redirected to authenticate
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.url = "https://www.airbnb.com/authenticate"
    mock_session.get.return_value = mock_response

    # Execute and verify exception
    with pytest.raises(AirbnbAuthError, match="Session expired"):
        create_preflight_session("Mozilla/5.0", {"_airbed_session_id": "abc"})


@patch("sync_airbnb.network.preflight.curl_requests.Session")
def test_create_preflight_session_http_error(mock_session_class):
    """Test preflight raises exception on HTTP error."""
    # Setup mock
    mock_session = Mock()
    mock_session.cookies = MagicMock()
    mock_session_class.return_value = mock_session

    # Mock GET to raise exception
    mock_session.get.side_effect = Exception("Connection timeout")

    # Execute and verify exception
    with pytest.raises(Exception, match="Connection timeout"):
        create_preflight_session("Mozilla/5.0", {"_airbed_session_id": "abc"})


@patch("sync_airbnb.network.preflight.curl_requests.Session")
def test_create_preflight_session_loads_cookies(mock_session_class):
    """Test that auth cookies are loaded into session."""
    # Setup mock with iterable cookies that have len()
    mock_session = Mock()
    mock_cookies = MagicMock()
    mock_cookies.__len__ = Mock(return_value=5)  # After loading 3 auth cookies + 2 bot cookies
    mock_session.cookies = mock_cookies
    mock_session_class.return_value = mock_session

    # Mock response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.url = "https://www.airbnb.com/hosting/insights"
    mock_response.headers.get_list.return_value = []
    mock_session.get.return_value = mock_response

    # Execute
    auth_cookies = {
        "_airbed_session_id": "abc",
        "_aaj": "xyz",
        "_aat": "token",
    }
    create_preflight_session("Mozilla/5.0", auth_cookies)

    # Verify cookies were set
    assert mock_session.cookies.set.call_count == 3
    mock_session.cookies.set.assert_any_call("_airbed_session_id", "abc", domain=".airbnb.com")
    mock_session.cookies.set.assert_any_call("_aaj", "xyz", domain=".airbnb.com")
    mock_session.cookies.set.assert_any_call("_aat", "token", domain=".airbnb.com")
