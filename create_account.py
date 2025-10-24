#!/usr/bin/env python3
"""Create/update account from .env file via direct DB insert"""
import os

from dotenv import load_dotenv

from sync_airbnb.config import engine
from sync_airbnb.db.writers.accounts import create_or_update_account
from sync_airbnb.schemas.account import AccountCreate

load_dotenv()

# Create account object from environment variables
account = AccountCreate(
    account_id=os.getenv("ACCOUNT_ID"),
    airbnb_cookie=os.getenv("AIRBNB_COOKIE"),
    x_airbnb_client_trace_id=os.getenv("X_AIRBNB_CLIENT_TRACE_ID"),
    x_client_version=os.getenv("X_CLIENT_VERSION"),
    user_agent=os.getenv("USER_AGENT", "Mozilla/5.0"),
    is_active=True,
)

# Insert/update account directly in database
result = create_or_update_account(engine, account)

print(f"Account {result.account_id} created/updated successfully")
print(f"   Active: {result.is_active}")
print(f"   Last sync: {result.last_sync_at}")
print(f"   Created: {result.created_at}")
print(f"   Updated: {result.updated_at}")
