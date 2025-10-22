from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class AccountCreate(BaseModel):
    """Schema for creating a new account."""
    account_id: str = Field(..., description="Airbnb account ID (extracted from cookie)")
    customer_id: UUID | None = Field(None, description="Internal customer UUID")
    airbnb_cookie: str = Field(..., description="Full Airbnb cookie string")
    x_airbnb_client_trace_id: str = Field(..., description="Airbnb client trace ID header")
    x_client_version: str = Field(..., description="Airbnb client version header")
    user_agent: str = Field(..., description="Browser user agent string")
    is_active: bool = Field(True, description="Whether account is active")


class AccountUpdate(BaseModel):
    """Schema for updating an existing account."""
    customer_id: UUID | None = None
    airbnb_cookie: str | None = None
    x_airbnb_client_trace_id: str | None = None
    x_client_version: str | None = None
    user_agent: str | None = None
    is_active: bool | None = None


class AccountResponse(BaseModel):
    """Schema for account responses."""
    account_id: str
    customer_id: UUID | None
    is_active: bool
    last_sync_at: datetime | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
