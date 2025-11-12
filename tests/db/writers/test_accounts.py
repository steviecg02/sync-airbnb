"""Tests for account database writers."""

from datetime import datetime, timezone
from unittest.mock import Mock, patch

from sync_airbnb.db.writers.accounts import update_account_cookies


@patch("sync_airbnb.db.writers.accounts.utc_now")
def test_update_account_cookies_success(mock_utc_now):
    """Test successful cookie update."""
    # Mock utc_now
    now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    mock_utc_now.return_value = now

    # Mock engine with context manager
    mock_engine = Mock()
    mock_conn = Mock()
    mock_context = Mock()
    mock_context.__enter__ = Mock(return_value=mock_conn)
    mock_context.__exit__ = Mock(return_value=False)
    mock_engine.begin.return_value = mock_context

    # Mock successful update
    mock_result = Mock()
    mock_result.rowcount = 1
    mock_conn.execute.return_value = mock_result

    # Execute
    account_id = "310316675"
    cookie_string = "_airbed_session_id=abc; _aaj=xyz"
    update_account_cookies(mock_engine, account_id, cookie_string)

    # Verify
    mock_engine.begin.assert_called_once()
    mock_conn.execute.assert_called_once()


@patch("sync_airbnb.db.writers.accounts.utc_now")
def test_update_account_cookies_not_found(mock_utc_now):
    """Test cookie update when account doesn't exist."""
    # Mock utc_now
    now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    mock_utc_now.return_value = now

    # Mock engine with context manager
    mock_engine = Mock()
    mock_conn = Mock()
    mock_context = Mock()
    mock_context.__enter__ = Mock(return_value=mock_conn)
    mock_context.__exit__ = Mock(return_value=False)
    mock_engine.begin.return_value = mock_context

    # Mock update with no rows affected
    mock_result = Mock()
    mock_result.rowcount = 0
    mock_conn.execute.return_value = mock_result

    # Execute - should not raise exception
    account_id = "999999999"
    cookie_string = "_airbed_session_id=abc"
    update_account_cookies(mock_engine, account_id, cookie_string)

    # Verify it completed without error
    mock_engine.begin.assert_called_once()


def test_update_account_cookies_empty_string():
    """Test cookie update with empty cookie string."""
    # Mock engine with context manager
    mock_engine = Mock()
    mock_conn = Mock()
    mock_context = Mock()
    mock_context.__enter__ = Mock(return_value=mock_conn)
    mock_context.__exit__ = Mock(return_value=False)
    mock_engine.begin.return_value = mock_context

    # Mock successful update
    mock_result = Mock()
    mock_result.rowcount = 1
    mock_conn.execute.return_value = mock_result

    # Execute with empty string
    update_account_cookies(mock_engine, "310316675", "")

    # Verify it completed
    mock_engine.begin.assert_called_once()
