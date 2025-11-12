"""Tests for cookie parsing and management utilities."""

from sync_airbnb.utils.cookie_utils import (
    build_cookie_string,
    filter_auth_cookies_only,
    parse_cookie_string,
    parse_set_cookie_headers,
)


def test_parse_cookie_string_single():
    """Test parsing a single cookie."""
    result = parse_cookie_string("session=abc123")
    assert result == {"session": "abc123"}


def test_parse_cookie_string_multiple():
    """Test parsing multiple cookies."""
    result = parse_cookie_string("session=abc123; user=test; lang=en")
    assert result == {"session": "abc123", "user": "test", "lang": "en"}


def test_parse_cookie_string_empty():
    """Test parsing empty cookie string."""
    result = parse_cookie_string("")
    assert result == {}


def test_parse_cookie_string_whitespace():
    """Test parsing cookie string with extra whitespace."""
    result = parse_cookie_string("session = abc123 ;  user = test ")
    assert result == {"session": "abc123", "user": "test"}


def test_build_cookie_string():
    """Test building cookie string from dict."""
    cookies = {"session": "abc123", "user": "test"}
    result = build_cookie_string(cookies)
    assert result in ["session=abc123; user=test", "user=test; session=abc123"]


def test_build_cookie_string_empty():
    """Test building empty cookie string."""
    result = build_cookie_string({})
    assert result == ""


def test_filter_auth_cookies_only():
    """Test filtering to only auth cookies."""
    all_cookies = {
        "_airbed_session_id": "abc123",
        "_aaj": "token",
        "_aat": "auth_token",
        "auth_jitney_session_id": "jitney123",
        "hli": "1",
        "li": "1",
        "_user_attributes": '{"id":123}',
        "_pt": "persistent",
        "rclu": "recent",
        "ak_bmsc": "xyz",  # Bot detection - should be filtered
        "bm_sv": "123",  # Bot detection - should be filtered
        "_ga": "analytics",  # Analytics - should be filtered
        "muxData": "video",  # Analytics - should be filtered
    }
    result = filter_auth_cookies_only(all_cookies)

    # Check all auth cookies are present
    assert "_airbed_session_id" in result
    assert "_aaj" in result
    assert "_aat" in result
    assert "auth_jitney_session_id" in result
    assert "hli" in result
    assert "li" in result
    assert "_user_attributes" in result
    assert "_pt" in result
    assert "rclu" in result

    # Check bot detection and analytics cookies are filtered out
    assert "ak_bmsc" not in result
    assert "bm_sv" not in result
    assert "_ga" not in result
    assert "muxData" not in result

    # Should have exactly 9 auth cookies
    assert len(result) == 9


def test_filter_auth_cookies_only_empty():
    """Test filtering when no auth cookies present."""
    all_cookies = {
        "ak_bmsc": "xyz",
        "bm_sv": "123",
        "_ga": "analytics",
    }
    result = filter_auth_cookies_only(all_cookies)
    assert result == {}


def test_filter_auth_cookies_only_partial():
    """Test filtering with only some auth cookies."""
    all_cookies = {
        "_airbed_session_id": "abc",
        "_aaj": "token",
        "ak_bmsc": "xyz",
        "_ga": "analytics",
    }
    result = filter_auth_cookies_only(all_cookies)
    assert result == {"_airbed_session_id": "abc", "_aaj": "token"}
    assert len(result) == 2


def test_parse_set_cookie_headers_dict_single():
    """Test parsing Set-Cookie header from dict (single cookie)."""
    headers = {"Set-Cookie": "ak_bmsc=xyz123; Path=/; HttpOnly"}
    result = parse_set_cookie_headers(headers)
    assert result == {"ak_bmsc": "xyz123"}


def test_parse_set_cookie_headers_dict_multiple():
    """Test parsing Set-Cookie header from dict (multiple cookies as list)."""
    headers = {
        "Set-Cookie": [
            "ak_bmsc=xyz123; Path=/; HttpOnly",
            "bm_sv=abc456; Path=/; Secure",
        ]
    }
    result = parse_set_cookie_headers(headers)
    assert result == {"ak_bmsc": "xyz123", "bm_sv": "abc456"}


def test_parse_set_cookie_headers_list_of_tuples():
    """Test parsing Set-Cookie headers from list of tuples (curl_cffi style)."""
    headers = [
        ("Content-Type", "application/json"),
        ("Set-Cookie", "ak_bmsc=xyz123; Path=/; HttpOnly"),
        ("Set-Cookie", "bm_sv=abc456; Path=/; Secure"),
        ("X-Custom-Header", "value"),
    ]
    result = parse_set_cookie_headers(headers)
    assert result == {"ak_bmsc": "xyz123", "bm_sv": "abc456"}


def test_parse_set_cookie_headers_empty_dict():
    """Test parsing empty headers dict."""
    result = parse_set_cookie_headers({})
    assert result == {}


def test_parse_set_cookie_headers_empty_list():
    """Test parsing empty headers list."""
    result = parse_set_cookie_headers([])
    assert result == {}


def test_parse_set_cookie_headers_no_set_cookie():
    """Test parsing headers without Set-Cookie."""
    headers = {"Content-Type": "application/json", "X-Custom": "value"}
    result = parse_set_cookie_headers(headers)
    assert result == {}
