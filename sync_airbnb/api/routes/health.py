from fastapi import APIRouter
from pydantic import BaseModel

from sync_airbnb import config

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    mode: str
    account_id: str | None


@router.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    return HealthResponse(
        status="ok",
        mode=config.MODE,
        account_id=config.ACCOUNT_ID,
    )
