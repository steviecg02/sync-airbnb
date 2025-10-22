import threading
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from sync_airbnb import config
from sync_airbnb.db.readers import accounts as account_readers
from sync_airbnb.db.writers import accounts as account_writers
from sync_airbnb.schemas.account import AccountCreate, AccountUpdate, AccountResponse
from sync_airbnb.models.account import extract_account_id_from_cookie
from sync_airbnb.services.insights import run_insights_poller

router = APIRouter()


class SyncResponse(BaseModel):
    message: str
    account_id: str


@router.post("/accounts", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(account: AccountCreate):
    """Create or update an account."""
    # Validate that account_id matches the one in the cookie
    extracted_id = extract_account_id_from_cookie(account.airbnb_cookie)
    if extracted_id != account.account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"account_id mismatch: provided {account.account_id}, extracted {extracted_id}"
        )

    result = account_writers.create_or_update_account(config.engine, account)

    # TODO: Kubernetes Operator Integration
    # When K8s operator is implemented:
    # - Operator watches accounts table for is_active=true
    # - Validates account credentials (test Airbnb API call)
    # - Creates worker Deployment with ACCOUNT_ID env var
    # - Worker auto-syncs on startup if last_sync_at is NULL
    # - No code changes needed here, operator handles everything

    return AccountResponse.model_validate(result)


@router.get("/accounts", response_model=list[AccountResponse])
async def list_accounts(active_only: bool = False):
    """List all accounts."""
    accounts = account_readers.get_all_accounts(config.engine, active_only=active_only)
    return [AccountResponse.model_validate(acc) for acc in accounts]


@router.get("/accounts/{account_id}", response_model=AccountResponse)
async def get_account(account_id: str):
    """Get a single account by ID."""
    account = account_readers.get_account(config.engine, account_id)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account {account_id} not found"
        )
    return AccountResponse.model_validate(account)


@router.patch("/accounts/{account_id}", response_model=AccountResponse)
async def update_account(account_id: str, updates: AccountUpdate):
    """Update an account."""
    account = account_writers.update_account(config.engine, account_id, updates)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account {account_id} not found"
        )
    return AccountResponse.model_validate(account)


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(account_id: str):
    """Delete an account."""
    deleted = account_writers.delete_account(config.engine, account_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account {account_id} not found"
        )


@router.post("/accounts/{account_id}/sync", response_model=SyncResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_sync(account_id: str):
    """
    Manually trigger a sync for an account.

    Runs the sync in a background thread and returns immediately.
    Useful for testing or triggering an immediate sync outside the schedule.
    """
    # Fetch account
    account = account_readers.get_account(config.engine, account_id)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account {account_id} not found"
        )

    if not account.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Account {account_id} is inactive"
        )

    # Run sync in background thread
    def run_sync():
        try:
            run_insights_poller(account)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Error in manual sync for {account_id}: {e}", exc_info=True)

    thread = threading.Thread(target=run_sync, daemon=True)
    thread.start()

    return SyncResponse(
        message="Sync initiated in background",
        account_id=account_id
    )
