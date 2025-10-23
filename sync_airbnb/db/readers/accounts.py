import logging

from sqlalchemy import func, select
from sqlalchemy.engine import Engine

from sync_airbnb.models.account import Account

logger = logging.getLogger(__name__)


def get_account(engine: Engine, account_id: str, include_deleted: bool = False) -> Account | None:
    """
    Get a single account by ID.

    Args:
        engine: Database engine
        account_id: Account ID to fetch
        include_deleted: Whether to include soft-deleted accounts (default: False)

    Returns:
        Account object or None if not found
    """
    with engine.connect() as conn:
        stmt = select(Account).where(Account.account_id == account_id)
        if not include_deleted:
            stmt = stmt.where(Account.deleted_at.is_(None))
        result = conn.execute(stmt)
        row = result.fetchone()
        if row:
            return Account(**dict(row._mapping))
        return None


def get_all_accounts(
    engine: Engine,
    active_only: bool = False,
    include_deleted: bool = False,
    offset: int = 0,
    limit: int | None = None,
) -> list[Account]:
    """
    Get accounts with optional filtering and pagination.

    Args:
        engine: Database engine
        active_only: Filter to only active accounts
        include_deleted: Whether to include soft-deleted accounts (default: False)
        offset: Number of records to skip (for pagination)
        limit: Maximum number of records to return (None = no limit)

    Returns:
        List of Account objects
    """
    with engine.connect() as conn:
        stmt = select(Account)

        # Exclude deleted accounts by default
        if not include_deleted:
            stmt = stmt.where(Account.deleted_at.is_(None))

        # Filter by active status
        if active_only:
            stmt = stmt.where(Account.is_active)

        # Apply pagination
        stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)

        result = conn.execute(stmt)
        return [Account(**dict(row._mapping)) for row in result.fetchall()]


def count_accounts(engine: Engine, active_only: bool = False, include_deleted: bool = False) -> int:
    """
    Count total number of accounts.

    Args:
        engine: Database engine
        active_only: Filter to only active accounts
        include_deleted: Whether to include soft-deleted accounts (default: False)

    Returns:
        Total count of accounts
    """
    with engine.connect() as conn:
        stmt = select(func.count()).select_from(Account)

        # Exclude deleted accounts by default
        if not include_deleted:
            stmt = stmt.where(Account.deleted_at.is_(None))

        # Filter by active status
        if active_only:
            stmt = stmt.where(Account.is_active)

        result = conn.execute(stmt)
        return result.scalar() or 0
