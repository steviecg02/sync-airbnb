"""Tests for cookie parsing and management utilities."""

from sync_airbnb.utils.cookie_utils import (
    build_cookie_string,
    extract_akamai_cookies,
    extract_auth_cookies,
    merge_cookies,
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


def test_extract_auth_cookies():
    """Test extracting only auth cookies."""
    cookie_string = "_airbed_session_id=abc; ak_bmsc=xyz; _aaj=token; _ga=analytics"
    result = extract_auth_cookies(cookie_string)
    assert "_airbed_session_id" in result
    assert "_aaj" in result
    assert "ak_bmsc" not in result  # Akamai cookie should be filtered out
    assert "_ga" not in result  # Analytics cookie should be filtered out


def test_extract_auth_cookies_empty():
    """Test extracting auth cookies from string with no auth cookies."""
    cookie_string = "ak_bmsc=xyz; _ga=analytics"
    result = extract_auth_cookies(cookie_string)
    assert result == {}


def test_extract_akamai_cookies():
    """Test extracting only Akamai cookies."""
    cookie_string = "ak_bmsc=xyz123; bm_sv=abc456; _airbed_session_id=abc"
    result = extract_akamai_cookies(cookie_string)
    assert result == {"ak_bmsc": "xyz123", "bm_sv": "abc456"}


def test_extract_akamai_cookies_empty():
    """Test extracting Akamai cookies from string with no Akamai cookies."""
    cookie_string = "_airbed_session_id=abc; user=test"
    result = extract_akamai_cookies(cookie_string)
    assert result == {}


def test_merge_cookies():
    """Test merging auth and Akamai cookies."""
    auth_cookies = {"_airbed_session_id": "abc", "_aaj": "token"}
    akamai_cookies = {"ak_bmsc": "xyz", "bm_sv": "123"}
    result = merge_cookies(auth_cookies, akamai_cookies)

    # Parse back to dict to check contents (order may vary)
    parsed = parse_cookie_string(result)
    assert parsed == {
        "_airbed_session_id": "abc",
        "_aaj": "token",
        "ak_bmsc": "xyz",
        "bm_sv": "123",
    }


def test_merge_cookies_akamai_overwrites():
    """Test that fresh Akamai cookies overwrite old ones when merging."""
    auth_cookies = {"_airbed_session_id": "abc", "ak_bmsc": "old_value"}
    akamai_cookies = {"ak_bmsc": "new_value", "bm_sv": "123"}
    result = merge_cookies(auth_cookies, akamai_cookies)

    parsed = parse_cookie_string(result)
    assert parsed["ak_bmsc"] == "new_value"  # Fresh Akamai cookie should win


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


def test_real_world_akamai_cookie_example():
    """Test with real Akamai cookie values from the cURL examples."""
    # From the actual cURL command
    full_cookie = (
        "ak_bmsc=C473307E22B99A0A68D7D829548C89B6~000000000000000000000000000000~YAAQzmjcFx6OhTOaAQAAvaHqXh2i45DI2InTth3H1ZDIEE3f+SCqnJ8evZttmtPejAQBWSJuBusT9Cv0Sl+I0F/RKqV55a7uTnp8N31p/ew9E6OmVWnAzFk67/GyEr5J1kgq/4VbJy3BmtHdS9u2lRomIRfQ8r51r+RIZ2ilcG6f5lGpCK0+shH94rJPcfeXLe2zj2qNJ5nKpQGl2SbD/Z27yaqtR8uD3me0voGOb9GvFkoKiUUvFOs6c218AKMfZMmptV7YoyfislvziGRvo1sRVh0edmHBYxLMEH27k1HTND/P5J2zIyuGVC95SxrNbA21ZRMLZgyrCh2Sr2qoThVhaKcB3g8td3jSu22PTgA8GAkkY0EONfL2IpBiZj+kmDg=; "
        "bm_sv=2EFC7187B746862A73E4C22C30B45EEA~YAAQ02jcF6onYimaAQAAvKfxXh1ZMlcrS8gHqZirr22GMEB6vTOkoHLa8DsrZC8/ZEWhZumvtSr6q9n2BYXihET7v+78ediiT6AnQpHiufUkm4KtUBKgHrb6SxJW5K1aV8gl2uHPpwG1lMeyNHILouL73E56uLZe4ldG5AqLv0jx9MTwuf2sVwOi4hNjus0QTMQ0Jz4iutMJlfutKlsAEHJSjM/ICa6oBoomuWXUp7pb+0IEEsNUB5KYXFwoxd8Jw0c=~1; "
        "_airbed_session_id=fb84ec6b188baf2473b48b1338ed390f"
    )

    akamai = extract_akamai_cookies(full_cookie)
    auth = extract_auth_cookies(full_cookie)

    assert "ak_bmsc" in akamai
    assert "bm_sv" in akamai
    assert "_airbed_session_id" in auth
    assert "_airbed_session_id" not in akamai
    assert "ak_bmsc" not in auth
