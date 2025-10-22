import logging
from sqlalchemy.engine import Engine
from sqlalchemy import select

from sync_airbnb.models.account import Account

logger = logging.getLogger(__name__)


def get_account(engine: Engine, account_id: str) -> Account | None:
    """Get a single account by ID."""
    with engine.connect() as conn:
        stmt = select(Account).where(Account.account_id == account_id)
        result = conn.execute(stmt)
        row = result.fetchone()
        if row:
            return Account(**dict(row._mapping))
        return None


def get_all_accounts(engine: Engine, active_only: bool = False) -> list[Account]:
    """Get all accounts, optionally filtered by is_active."""
    with engine.connect() as conn:
        stmt = select(Account)
        if active_only:
            stmt = stmt.where(Account.is_active == True)
        result = conn.execute(stmt)
        return [Account(**dict(row._mapping)) for row in result.fetchall()]
