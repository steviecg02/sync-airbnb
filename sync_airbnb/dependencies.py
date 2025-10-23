"""FastAPI dependency injection for database engine.

This module provides dependency injection for the database engine,
following the pattern from sync-hostaway for better testability and
separation of concerns.
"""

from collections.abc import Generator

from sqlalchemy.engine import Engine

from sync_airbnb import config


def get_db_engine() -> Generator[Engine, None, None]:
    """Dependency that provides database engine.

    This allows routes to receive the engine via dependency injection
    instead of importing it directly from config. Benefits:
    - Easier to mock in tests
    - Clear dependency declaration in route signatures
    - Follows FastAPI best practices

    Yields:
        Engine: SQLAlchemy database engine

    Example:
        @router.get("/accounts")
        async def list_accounts(engine: Engine = Depends(get_db_engine)):
            accounts = get_all_accounts(engine)
            return accounts
    """
    yield config.engine
