import logging
import threading

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.engine import Engine

from sync_airbnb.api.routes._helpers import validate_account_exists
from sync_airbnb.db.readers import accounts as account_readers
from sync_airbnb.db.writers import accounts as account_writers
from sync_airbnb.dependencies import get_db_engine
from sync_airbnb.models.account import extract_account_id_from_cookie
from sync_airbnb.schemas.account import AccountCreate, AccountListResponse, AccountResponse, AccountUpdate
from sync_airbnb.services.insights import run_insights_poller

router = APIRouter()
logger = logging.getLogger(__name__)

# Track manual sync threads (imported from main for graceful shutdown)
# Note: In production, consider using a proper job queue (Celery, RQ, etc.)
_manual_sync_threads: list[threading.Thread] = []


class SyncResponse(BaseModel):
    message: str
    account_id: str


@router.post(
    "/accounts",
    response_model=AccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or update an account",
    description="""
    Create a new Airbnb account or update an existing one.

    This endpoint:
    - Validates that the account_id matches the one in the cookie
    - Stores account credentials for future sync jobs
    - Sets is_active=true by default (account will be synced by scheduler)

    **Note:** The account_id must match the ID extracted from the
    _user_attributes cookie parameter.

    **Authentication Required:** API key (future enhancement - P0-1)
    """,
    responses={
        201: {
            "description": "Account created or updated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "account_id": "310316675",
                        "customer_id": None,
                        "is_active": True,
                        "last_sync_at": None,
                        "created_at": "2025-10-21T12:00:00Z",
                        "updated_at": "2025-10-21T12:00:00Z",
                    }
                }
            },
        },
        400: {
            "description": "Invalid request - account_id mismatch or invalid credentials",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "VALIDATION_ERROR",
                            "message": "account_id mismatch: provided 123, extracted 456",
                            "details": {},
                            "request_id": "uuid-here",
                        }
                    }
                }
            },
        },
    },
)
async def create_account(
    account: AccountCreate = Body(
        ...,
        example={
            "account_id": "310316675",
            "customer_id": None,
            "airbnb_cookie": "bev=1754402040_EANGVmYTkzYzA5Nz; _user_attributes=%7B%22id_str%22%3A%22310316675%22...",
            "x_airbnb_client_trace_id": "0xeqejq03czxpg1r5d5bo00reszs",
            "x_client_version": "b71ed06bcc67f9ee0e17a616de44eba7fd5d41a3",
            "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "is_active": True,
        },
    ),
    engine: Engine = Depends(get_db_engine),
):
    """Create or update an account."""
    # Validate that account_id matches the one in the cookie
    extracted_id = extract_account_id_from_cookie(account.airbnb_cookie)
    if extracted_id != account.account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"account_id mismatch: provided {account.account_id}, extracted {extracted_id}",
        )

    result = account_writers.create_or_update_account(engine, account)

    # TODO: Kubernetes Operator Integration
    # When K8s operator is implemented:
    # - Operator watches accounts table for is_active=true
    # - Validates account credentials (test Airbnb API call)
    # - Creates worker Deployment with ACCOUNT_ID env var
    # - Worker auto-syncs on startup if last_sync_at is NULL
    # - No code changes needed here, operator handles everything

    return AccountResponse.model_validate(result)


@router.get(
    "/accounts",
    response_model=AccountListResponse,
    summary="List accounts with pagination",
    description="""
    Retrieve a paginated list of Airbnb accounts.

    **Query Parameters:**
    - active_only: Filter to only active accounts (is_active=true)
    - include_deleted: Include soft-deleted accounts (default: false)
    - offset: Number of records to skip (default: 0)
    - limit: Maximum records per page (default: 50, max: 100)

    **Pagination Example:**
    ```bash
    # Get first page (50 accounts)
    GET /api/v1/accounts?limit=50&offset=0

    # Get second page (next 50 accounts)
    GET /api/v1/accounts?limit=50&offset=50

    # Get all active accounts (first page)
    GET /api/v1/accounts?active_only=true&limit=50&offset=0

    # Get all accounts including deleted
    GET /api/v1/accounts?include_deleted=true&limit=50&offset=0
    ```

    **Response Format:**
    - items: Array of accounts in current page
    - total: Total count matching filters
    - offset: Current offset
    - limit: Page size
    - has_more: True if more results exist

    **Authentication Required:** API key (future enhancement - P0-1)
    """,
    responses={
        200: {
            "description": "Paginated list of accounts",
            "content": {
                "application/json": {
                    "example": {
                        "items": [
                            {
                                "account_id": "310316675",
                                "customer_id": None,
                                "is_active": True,
                                "last_sync_at": "2025-10-21T12:00:00Z",
                                "created_at": "2025-10-21T11:00:00Z",
                                "updated_at": "2025-10-21T12:00:00Z",
                            },
                            {
                                "account_id": "987654321",
                                "customer_id": "550e8400-e29b-41d4-a716-446655440000",
                                "is_active": False,
                                "last_sync_at": None,
                                "created_at": "2025-10-20T10:00:00Z",
                                "updated_at": "2025-10-20T10:00:00Z",
                            },
                        ],
                        "total": 125,
                        "offset": 0,
                        "limit": 50,
                        "has_more": True,
                    }
                }
            },
        },
    },
)
async def list_accounts(
    active_only: bool = Query(False, description="Filter to only active accounts"),
    include_deleted: bool = Query(False, description="Include soft-deleted accounts"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum records per page"),
    engine: Engine = Depends(get_db_engine),
):
    """List accounts with pagination."""
    # Get accounts for current page
    accounts = account_readers.get_all_accounts(
        engine,
        active_only=active_only,
        include_deleted=include_deleted,
        offset=offset,
        limit=limit,
    )

    # Get total count
    total = account_readers.count_accounts(engine, active_only=active_only, include_deleted=include_deleted)

    # Convert to response models
    items = [AccountResponse.model_validate(acc) for acc in accounts]

    return AccountListResponse(
        items=items,
        total=total,
        offset=offset,
        limit=limit,
        has_more=(offset + limit) < total,
    )


@router.get(
    "/accounts/{account_id}",
    response_model=AccountResponse,
    summary="Get account by ID",
    description="""
    Retrieve a single Airbnb account by its ID.

    **Path Parameters:**
    - account_id: The Airbnb account ID (numeric string)

    **Authentication Required:** API key (future enhancement - P0-1)
    """,
    responses={
        200: {
            "description": "Account found",
            "content": {
                "application/json": {
                    "example": {
                        "account_id": "310316675",
                        "customer_id": None,
                        "is_active": True,
                        "last_sync_at": "2025-10-21T12:00:00Z",
                        "created_at": "2025-10-21T11:00:00Z",
                        "updated_at": "2025-10-21T12:00:00Z",
                    }
                }
            },
        },
        404: {
            "description": "Account not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "NOT_FOUND",
                            "message": "Account 310316675 not found",
                            "details": {},
                            "request_id": "uuid-here",
                        }
                    }
                }
            },
        },
    },
)
async def get_account(
    account_id: str,
    engine: Engine = Depends(get_db_engine),
):
    """Get a single account by ID."""
    account = validate_account_exists(engine, account_id)
    return AccountResponse.model_validate(account)


@router.patch(
    "/accounts/{account_id}",
    response_model=AccountResponse,
    summary="Update account",
    description="""
    Update an existing Airbnb account.

    **Path Parameters:**
    - account_id: The Airbnb account ID (numeric string)

    **Body:** Partial account update (all fields optional)

    Common use cases:
    - Update cookie when it expires
    - Deactivate account (is_active=false)
    - Change customer_id assignment

    **Authentication Required:** API key (future enhancement - P0-1)
    """,
    responses={
        200: {
            "description": "Account updated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "account_id": "310316675",
                        "customer_id": "550e8400-e29b-41d4-a716-446655440000",
                        "is_active": True,
                        "last_sync_at": "2025-10-21T12:00:00Z",
                        "created_at": "2025-10-21T11:00:00Z",
                        "updated_at": "2025-10-21T13:00:00Z",
                    }
                }
            },
        },
        404: {
            "description": "Account not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "NOT_FOUND",
                            "message": "Account 310316675 not found",
                            "details": {},
                            "request_id": "uuid-here",
                        }
                    }
                }
            },
        },
    },
)
async def update_account(
    account_id: str,
    updates: AccountUpdate = Body(
        ...,
        example={
            "is_active": False,
            "customer_id": "550e8400-e29b-41d4-a716-446655440000",
        },
    ),
    engine: Engine = Depends(get_db_engine),
):
    """Update an account."""
    account = account_writers.update_account(engine, account_id, updates)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Account {account_id} not found")
    return AccountResponse.model_validate(account)


@router.delete(
    "/accounts/{account_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete account",
    description="""
    Soft delete an Airbnb account by setting deleted_at timestamp.

    **Path Parameters:**
    - account_id: The Airbnb account ID (numeric string)

    **Behavior:**
    - Sets deleted_at timestamp (account marked as deleted)
    - Account excluded from list endpoints by default
    - Account can be restored with POST /accounts/{id}/restore
    - Account data remains in database (not permanently deleted)

    **Use Cases:**
    - Temporarily disable account
    - Archive old accounts
    - Safely delete with recovery option

    **Note:** To permanently delete, see hard_delete endpoint (not implemented).

    **Authentication Required:** API key (future enhancement - P0-1)
    """,
    responses={
        204: {
            "description": "Account soft deleted successfully (no content)",
        },
        404: {
            "description": "Account not found or already deleted",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "NOT_FOUND",
                            "message": "Account 310316675 not found",
                            "details": {},
                            "request_id": "uuid-here",
                        }
                    }
                }
            },
        },
    },
)
async def delete_account(
    account_id: str,
    engine: Engine = Depends(get_db_engine),
):
    """Soft delete an account."""
    deleted = account_writers.soft_delete_account(engine, account_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Account {account_id} not found")


@router.post(
    "/accounts/{account_id}/restore",
    response_model=AccountResponse,
    summary="Restore soft-deleted account",
    description="""
    Restore a soft-deleted account by clearing deleted_at timestamp.

    **Path Parameters:**
    - account_id: The Airbnb account ID (numeric string)

    **Behavior:**
    - Clears deleted_at timestamp (account marked as active)
    - Account appears in list endpoints again
    - All account data and history preserved

    **Use Cases:**
    - Recover accidentally deleted account
    - Reactivate archived account
    - Undo soft delete

    **Authentication Required:** API key (future enhancement - P0-1)
    """,
    responses={
        200: {
            "description": "Account restored successfully",
            "content": {
                "application/json": {
                    "example": {
                        "account_id": "310316675",
                        "customer_id": None,
                        "is_active": True,
                        "last_sync_at": "2025-10-21T12:00:00Z",
                        "created_at": "2025-10-21T11:00:00Z",
                        "updated_at": "2025-10-21T13:00:00Z",
                        "deleted_at": None,
                    }
                }
            },
        },
        404: {
            "description": "Account not found or not deleted",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "NOT_FOUND",
                            "message": "Account 310316675 not found or not deleted",
                            "details": {},
                            "request_id": "uuid-here",
                        }
                    }
                }
            },
        },
    },
)
async def restore_account(
    account_id: str,
    engine: Engine = Depends(get_db_engine),
):
    """Restore a soft-deleted account."""
    restored = account_writers.restore_account(engine, account_id)
    if not restored:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Account {account_id} not found or not deleted"
        )

    # Fetch and return restored account
    account = account_readers.get_account(engine, account_id, include_deleted=False)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Account {account_id} not found")
    return AccountResponse.model_validate(account)


@router.post(
    "/accounts/{account_id}/sync",
    response_model=SyncResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger manual sync",
    description="""
    Manually trigger a data sync for an account.

    **Path Parameters:**
    - account_id: The Airbnb account ID (numeric string)

    **Behavior:**
    - Starts sync job in background thread
    - Returns immediately (async, non-blocking)
    - Syncs last 1 week of data (same as scheduled sync)
    - Updates last_sync_at timestamp on completion

    **Use cases:**
    - Test new account after creation
    - Force immediate sync outside schedule
    - Re-sync after error or data corruption

    **Note:** Account must be active (is_active=true). Only one sync
    per account can run at a time. For job tracking, see P1-7.

    **Authentication Required:** API key (future enhancement - P0-1)
    """,
    responses={
        202: {
            "description": "Sync initiated successfully (background job)",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Sync initiated in background",
                        "account_id": "310316675",
                    }
                }
            },
        },
        400: {
            "description": "Account is inactive",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "ACCOUNT_INACTIVE",
                            "message": "Account 310316675 is inactive",
                            "details": {},
                            "request_id": "uuid-here",
                        }
                    }
                }
            },
        },
        404: {
            "description": "Account not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "NOT_FOUND",
                            "message": "Account 310316675 not found",
                            "details": {},
                            "request_id": "uuid-here",
                        }
                    }
                }
            },
        },
    },
)
async def trigger_sync(
    account_id: str,
    engine: Engine = Depends(get_db_engine),
):
    """
    Manually trigger a sync for an account.

    Runs the sync in a background thread and returns immediately.
    Useful for testing or triggering an immediate sync outside the schedule.
    """
    # Fetch account
    account = validate_account_exists(engine, account_id)

    if not account.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Account {account_id} is inactive")

    # Run sync in background thread
    def run_sync():
        try:
            run_insights_poller(account)
        except Exception as e:
            logger.error(f"Error in manual sync for {account_id}: {e}", exc_info=True)
        finally:
            # Remove thread from tracking list when done
            if threading.current_thread() in _manual_sync_threads:
                _manual_sync_threads.remove(threading.current_thread())

    thread = threading.Thread(target=run_sync, daemon=False, name=f"manual-sync-{account_id}")
    _manual_sync_threads.append(thread)
    thread.start()

    logger.info(f"Manual sync initiated for account {account_id} in thread {thread.name}")
    return SyncResponse(message="Sync initiated in background", account_id=account_id)
