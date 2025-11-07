from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class AccountCreate(BaseModel):
    """Schema for creating a new account."""

    account_id: str = Field(..., min_length=1, max_length=255, description="Airbnb account ID (extracted from cookie)")
    customer_id: UUID | None = Field(None, description="Internal customer UUID")
    airbnb_cookie: str = Field(..., min_length=50, description="Full Airbnb cookie string")
    # x_airbnb_client_trace_id removed - auto-generated in build_headers() (not validated by Airbnb)
    x_client_version: str = Field(..., min_length=1, max_length=50, description="Airbnb client version header")
    user_agent: str = Field(..., min_length=10, max_length=500, description="Browser user agent string")
    is_active: bool = Field(True, description="Whether account is active")

    @field_validator("account_id")
    @classmethod
    def validate_account_id(cls, v: str) -> str:
        """Validate account_id is numeric."""
        if not v.isdigit():
            raise ValueError("account_id must be numeric")
        return v

    @field_validator("airbnb_cookie")
    @classmethod
    def validate_cookie_has_user_attributes(cls, v: str) -> str:
        """Validate cookie contains _user_attributes."""
        if "_user_attributes=" not in v:
            raise ValueError("airbnb_cookie must contain _user_attributes")
        return v


class AccountUpdate(BaseModel):
    """Schema for updating an existing account."""

    customer_id: UUID | None = None
    airbnb_cookie: str | None = None
    # x_airbnb_client_trace_id removed - auto-generated in build_headers() (not validated by Airbnb)
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
    deleted_at: datetime | None = Field(None, description="Soft delete timestamp (None if not deleted)")

    class Config:
        from_attributes = True


class AccountListResponse(BaseModel):
    """Schema for paginated account list responses."""

    items: list[AccountResponse] = Field(..., description="List of accounts in this page")
    total: int = Field(..., description="Total number of accounts matching filters")
    offset: int = Field(..., description="Number of records skipped")
    limit: int = Field(..., description="Maximum number of records per page")
    has_more: bool = Field(..., description="Whether there are more results available")
