"""Tests for API route helper functions."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from sync_airbnb.api.routes._helpers import validate_account_exists, validate_date_range
from sync_airbnb.models.account import Account


def test_validate_account_exists_returns_account_when_found():
    """Test that validate_account_exists returns account when it exists."""
    mock_engine = MagicMock()
    mock_account = Account(
        account_id="123",
        airbnb_cookie="test",
        x_client_version="v1",
        # x_airbnb_client_trace_id removed - auto-generated in build_headers()
        user_agent="agent",
        is_active=True,
    )

    with patch("sync_airbnb.api.routes._helpers.account_readers.get_account", return_value=mock_account):
        result = validate_account_exists(mock_engine, "123")

    assert result is not None
    assert result.account_id == "123"


def test_validate_account_exists_raises_404_when_not_found():
    """Test that validate_account_exists raises 404 when account not found."""
    mock_engine = MagicMock()

    with patch("sync_airbnb.api.routes._helpers.account_readers.get_account", return_value=None):
        with pytest.raises(HTTPException) as exc_info:
            validate_account_exists(mock_engine, "nonexistent")

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


def test_validate_date_range_accepts_valid_range():
    """Test that validate_date_range accepts start_date < end_date."""
    start = date(2025, 1, 1)
    end = date(2025, 1, 31)

    # Should not raise
    validate_date_range(start, end)


def test_validate_date_range_raises_400_when_start_equals_end():
    """Test that validate_date_range raises 400 when start_date == end_date."""
    same_date = date(2025, 1, 1)

    with pytest.raises(HTTPException) as exc_info:
        validate_date_range(same_date, same_date)

    assert exc_info.value.status_code == 400
    assert "before" in exc_info.value.detail.lower()


def test_validate_date_range_raises_400_when_start_after_end():
    """Test that validate_date_range raises 400 when start_date > end_date."""
    start = date(2025, 1, 31)
    end = date(2025, 1, 1)

    with pytest.raises(HTTPException) as exc_info:
        validate_date_range(start, end)

    assert exc_info.value.status_code == 400
    assert "before" in exc_info.value.detail.lower()
