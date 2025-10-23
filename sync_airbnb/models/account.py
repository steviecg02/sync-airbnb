import json
import re
from datetime import datetime
from uuid import UUID as UUIDType

from sqlalchemy import Boolean, Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from sync_airbnb.config import SCHEMA
from sync_airbnb.models.base import Base


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = {"schema": SCHEMA}

    account_id: str = Column(String, primary_key=True, index=True)  # type: ignore[assignment]
    customer_id: UUIDType | None = Column(UUID(as_uuid=True), nullable=True, index=True)  # type: ignore[assignment,misc]

    # Airbnb authentication headers
    airbnb_cookie: str = Column(Text, nullable=False)  # type: ignore[assignment]
    x_airbnb_client_trace_id: str = Column(String, nullable=False)  # type: ignore[assignment]
    x_client_version: str = Column(String, nullable=False)  # type: ignore[assignment]
    user_agent: str = Column(Text, nullable=False)  # type: ignore[assignment]

    # Status tracking
    is_active: bool = Column(Boolean, nullable=False, default=True)  # type: ignore[assignment]
    last_sync_at: datetime | None = Column(DateTime(timezone=True), nullable=True)  # type: ignore[assignment]

    # Timestamps
    created_at: datetime = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)  # type: ignore[assignment]
    updated_at: datetime = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)  # type: ignore[assignment]
    deleted_at: datetime | None = Column(DateTime(timezone=True), nullable=True)  # type: ignore[assignment]  # Soft delete timestamp


def extract_account_id_from_cookie(cookie: str) -> str:
    """
    Extract Airbnb account_id from the _user_attributes cookie.

    Example cookie contains: _user_attributes=%7B%22id_str%22%3A%22310316675%22%2C...
    Which decodes to: {"id_str":"310316675",...}

    Args:
        cookie: Full cookie string

    Returns:
        account_id as string (e.g., "310316675")

    Raises:
        ValueError: If account_id cannot be extracted
    """
    # Find _user_attributes cookie value
    match = re.search(r"_user_attributes=([^;]+)", cookie)
    if not match:
        raise ValueError("_user_attributes not found in cookie")

    import urllib.parse

    user_attrs_encoded = match.group(1)
    user_attrs_decoded = urllib.parse.unquote(user_attrs_encoded)

    try:
        user_data = json.loads(user_attrs_decoded)
        account_id = user_data.get("id_str") or str(user_data.get("id"))
        if not account_id:
            raise ValueError("No id_str or id found in _user_attributes")
        return account_id
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse _user_attributes: {e}")
