"""Helper functions for route validation and error handling.

This module provides reusable validation functions to reduce duplication
across route handlers, following DRY principles from sync-hostaway.
"""

from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.engine import Engine

from sync_airbnb.db.readers import accounts as account_readers
from sync_airbnb.models.account import Account


def validate_account_exists(engine: Engine, account_id: str) -> Account:
    """Validate that an account exists and return it.

    Args:
        engine: Database engine
        account_id: Account ID to validate

    Returns:
        Account model if found

    Raises:
        HTTPException: 404 if account not found
    """
    account = account_readers.get_account(engine, account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Account {account_id} not found")
    return account


def validate_date_range(start_date: date, end_date: date) -> None:
    """Validate that start_date is before end_date.

    Args:
        start_date: Start date (inclusive)
        end_date: End date (exclusive)

    Raises:
        HTTPException: 400 if start_date >= end_date
    """
    if start_date >= end_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="start_date must be before end_date")
