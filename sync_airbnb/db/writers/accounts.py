import logging

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine

from sync_airbnb import config
from sync_airbnb.models.account import Account
from sync_airbnb.schemas.account import AccountCreate, AccountUpdate
from sync_airbnb.utils.datetime_utils import utc_now

logger = logging.getLogger(__name__)


def create_or_update_account(engine: Engine, account_data: AccountCreate) -> Account:
    """
    Create a new account or update if it already exists (upsert).
    Returns the created/updated account.
    """
    with engine.begin() as conn:
        stmt = insert(Account).values(
            account_id=account_data.account_id,
            customer_id=account_data.customer_id,
            airbnb_cookie=account_data.airbnb_cookie,
            # x_airbnb_client_trace_id removed - auto-generated in build_headers()
            x_client_version=account_data.x_client_version,
            user_agent=account_data.user_agent,
            is_active=account_data.is_active,
        )

        # On conflict, update all fields except account_id and timestamps
        stmt = stmt.on_conflict_do_update(
            index_elements=["account_id"],
            set_={
                "customer_id": stmt.excluded.customer_id,
                "airbnb_cookie": stmt.excluded.airbnb_cookie,
                # x_airbnb_client_trace_id removed - auto-generated in build_headers()
                "x_client_version": stmt.excluded.x_client_version,
                "user_agent": stmt.excluded.user_agent,
                "is_active": stmt.excluded.is_active,
                "updated_at": utc_now(),
            },
        )

        returning_stmt = stmt.returning(Account)
        result = conn.execute(returning_stmt)
        account = result.fetchone()
        logger.info(f"Created/updated account {account_data.account_id}")

        # Convert row to Account object
        if account is None:
            raise RuntimeError(f"Failed to create/update account {account_data.account_id}")
        return Account(**dict(account._mapping))


def update_account(engine: Engine, account_id: str, updates: AccountUpdate) -> Account | None:
    """
    Update an existing account with partial updates.
    Returns the updated account or None if not found.
    """
    update_dict = {k: v for k, v in updates.model_dump().items() if v is not None}
    if not update_dict:
        logger.warning(f"No updates provided for account {account_id}")
        return None

    update_dict["updated_at"] = utc_now()

    with engine.begin() as conn:
        from sqlalchemy import update as sa_update

        stmt = sa_update(Account).where(Account.account_id == account_id).values(**update_dict).returning(Account)
        result = conn.execute(stmt)
        row = result.fetchone()
        if row:
            logger.info(f"Updated account {account_id}")
            return Account(**dict(row._mapping))
        else:
            logger.warning(f"Account {account_id} not found for update")
            return None


def update_account_cookies(engine: Engine, account_id: str, cookie_string: str) -> None:
    """
    Update only the airbnb_cookie field for an account.

    Called after each sync to persist evolved cookies from Session.
    Only stores auth cookies (bot detection cookies are ephemeral and obtained fresh each run).

    Args:
        engine: SQLAlchemy engine
        account_id: Account ID to update
        cookie_string: New cookie string containing only auth cookies

    Example:
        >>> update_account_cookies(engine, "310316675", "_airbed_session_id=abc; _aaj=xyz")
    """
    logger.info(f"[DB] Updating cookies for account {account_id}")
    logger.info(f"[DB] Cookie string length: {len(cookie_string)} chars")

    with engine.begin() as conn:
        from sqlalchemy import update as sa_update

        stmt = (
            sa_update(Account)
            .where(Account.account_id == account_id)
            .values(airbnb_cookie=cookie_string, updated_at=utc_now())
        )
        result = conn.execute(stmt)

        if result.rowcount == 0:
            logger.warning(f"[DB] Account {account_id} not found for cookie update")
        else:
            logger.info(f"[DB] Successfully updated cookies for account {account_id}")


def update_last_sync(engine: Engine, account_id: str) -> None:
    """Update the last_sync_at timestamp for an account."""
    if config.INSIGHTS_DRY_RUN:
        logger.info(f"[DRY RUN] Would update last_sync_at for account {account_id}")
        return

    with engine.begin() as conn:
        from sqlalchemy import update as sa_update

        stmt = (
            sa_update(Account)
            .where(Account.account_id == account_id)
            .values(last_sync_at=utc_now(), updated_at=utc_now())
        )
        conn.execute(stmt)
        logger.info(f"Updated last_sync_at for account {account_id}")


def soft_delete_account(engine: Engine, account_id: str) -> bool:
    """
    Soft delete an account by setting deleted_at timestamp.
    Returns True if deleted, False if not found.

    Note: Soft-deleted accounts can be restored with restore_account().
    """
    with engine.begin() as conn:
        from sqlalchemy import update as sa_update

        stmt = (
            sa_update(Account)
            .where(Account.account_id == account_id)
            .where(Account.deleted_at.is_(None))  # Only delete if not already deleted
            .values(deleted_at=utc_now(), updated_at=utc_now())
        )
        result = conn.execute(stmt)
        deleted = result.rowcount > 0
        if deleted:
            logger.info(f"Soft deleted account {account_id}")
        else:
            logger.warning(f"Account {account_id} not found or already deleted")
        return deleted


def restore_account(engine: Engine, account_id: str) -> bool:
    """
    Restore a soft-deleted account by clearing deleted_at timestamp.
    Returns True if restored, False if not found or not deleted.
    """
    with engine.begin() as conn:
        from sqlalchemy import update as sa_update

        stmt = (
            sa_update(Account)
            .where(Account.account_id == account_id)
            .where(Account.deleted_at.isnot(None))  # Only restore if deleted
            .values(deleted_at=None, updated_at=utc_now())
        )
        result = conn.execute(stmt)
        restored = result.rowcount > 0
        if restored:
            logger.info(f"Restored account {account_id}")
        else:
            logger.warning(f"Account {account_id} not found or not deleted")
        return restored


def delete_account(engine: Engine, account_id: str) -> bool:
    """
    Hard delete an account (permanently removes from database).
    Returns True if deleted, False if not found.

    Warning: This permanently deletes the account. Consider using
    soft_delete_account() instead.

    Note: This will fail if there are foreign key references.
    """
    with engine.begin() as conn:
        from sqlalchemy import delete

        stmt = delete(Account).where(Account.account_id == account_id)
        result = conn.execute(stmt)
        deleted = result.rowcount > 0
        if deleted:
            logger.info(f"Hard deleted account {account_id}")
        else:
            logger.warning(f"Account {account_id} not found for deletion")
        return deleted
