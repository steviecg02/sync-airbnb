import logging
from datetime import datetime
from sqlalchemy.engine import Engine
from sqlalchemy.dialects.postgresql import insert

from sync_airbnb.models.account import Account
from sync_airbnb.schemas.account import AccountCreate, AccountUpdate

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
            x_airbnb_client_trace_id=account_data.x_airbnb_client_trace_id,
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
                "x_airbnb_client_trace_id": stmt.excluded.x_airbnb_client_trace_id,
                "x_client_version": stmt.excluded.x_client_version,
                "user_agent": stmt.excluded.user_agent,
                "is_active": stmt.excluded.is_active,
                "updated_at": datetime.utcnow(),
            }
        )

        stmt = stmt.returning(Account)
        result = conn.execute(stmt)
        account = result.fetchone()
        logger.info(f"Created/updated account {account_data.account_id}")

        # Convert row to Account object
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

    update_dict["updated_at"] = datetime.utcnow()

    with engine.begin() as conn:
        from sqlalchemy import update as sa_update
        stmt = (
            sa_update(Account)
            .where(Account.account_id == account_id)
            .values(**update_dict)
            .returning(Account)
        )
        result = conn.execute(stmt)
        row = result.fetchone()
        if row:
            logger.info(f"Updated account {account_id}")
            return Account(**dict(row._mapping))
        else:
            logger.warning(f"Account {account_id} not found for update")
            return None


def update_last_sync(engine: Engine, account_id: str) -> None:
    """Update the last_sync_at timestamp for an account."""
    with engine.begin() as conn:
        from sqlalchemy import update as sa_update
        stmt = (
            sa_update(Account)
            .where(Account.account_id == account_id)
            .values(last_sync_at=datetime.utcnow(), updated_at=datetime.utcnow())
        )
        conn.execute(stmt)
        logger.info(f"Updated last_sync_at for account {account_id}")


def delete_account(engine: Engine, account_id: str) -> bool:
    """
    Delete an account. Returns True if deleted, False if not found.
    Note: This will fail if there are foreign key references.
    """
    with engine.begin() as conn:
        from sqlalchemy import delete
        stmt = delete(Account).where(Account.account_id == account_id)
        result = conn.execute(stmt)
        deleted = result.rowcount > 0
        if deleted:
            logger.info(f"Deleted account {account_id}")
        else:
            logger.warning(f"Account {account_id} not found for deletion")
        return deleted
