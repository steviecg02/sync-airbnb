# Task: Better Credential Error Detection and Handling

## Problem

When Airbnb credentials (cookie) expire or are invalid, the application crashes with unhelpful errors like:
- `AttributeError: 'NoneType' object has no attribute 'get'`
- `ValueError: Could not resolve component structure`

These errors don't indicate the real problem (expired credentials), and the container keeps restarting in a loop trying the same failed sync repeatedly.

## Current Behavior

1. Airbnb API returns an error response (likely 401/403 or HTML error page)
2. Code expects JSON with `data.porygon.getPerformanceComponents.components`
3. Instead gets `None` or error HTML
4. Crashes with parsing error
5. Container restarts (or uvicorn reloads in dev mode)
6. Tries again immediately
7. Infinite loop of failures

## Desired Behavior

1. Detect when Airbnb returns auth errors (expired cookie, invalid credentials)
2. Log clear error: "Airbnb authentication failed - cookie may be expired"
3. Mark account as `is_active=False` in database
4. Stop sync attempts for this account
5. Send alert/notification (future enhancement)
6. Don't restart/retry until credentials are updated

## Implementation Plan

### 1. Detect Auth Failures in HTTP Client

**File:** `sync_airbnb/network/http_client.py`

Add response validation to detect:
- HTTP 401/403 status codes
- Response that's HTML instead of JSON (Airbnb login redirect)
- Empty/null `data` field in response
- Error messages in response

```python
class AuthenticationError(Exception):
    """Raised when Airbnb credentials are invalid or expired"""
    pass

def make_request(...):
    response = requests.post(...)

    # Check for HTTP auth errors
    if response.status_code in (401, 403):
        raise AuthenticationError(f"Airbnb authentication failed: {response.status_code}")

    # Check for HTML redirect (login page)
    if response.headers.get("content-type", "").startswith("text/html"):
        raise AuthenticationError("Airbnb returned HTML (likely login redirect) - cookie may be expired")

    # Parse JSON
    try:
        data = response.json()
    except JSONDecodeError:
        raise AuthenticationError("Airbnb returned non-JSON response - authentication may have failed")

    # Check for null data (common auth failure response)
    if data.get("data") is None:
        error_msg = data.get("errors", [{}])[0].get("message", "Unknown error")
        raise AuthenticationError(f"Airbnb API error: {error_msg}")

    return data
```

### 2. Handle Auth Errors in Service Layer

**File:** `sync_airbnb/services/insights.py`

Catch `AuthenticationError` and handle gracefully:

```python
from sync_airbnb.network.http_client import AuthenticationError
from sync_airbnb.db.writers.accounts import deactivate_account

def run_insights_poller(account: Account, trigger: str = "manual") -> dict:
    try:
        # ... existing sync logic

    except AuthenticationError as e:
        logger.error(
            f"Authentication failed for account {account.account_id}: {e}",
            extra={
                "account_id": account.account_id,
                "error": str(e),
                "trigger": trigger,
            }
        )

        # Deactivate account to prevent further sync attempts
        deactivate_account(engine, account.account_id, reason="auth_failed")

        return {
            "status": "auth_failed",
            "error": str(e),
            "account_deactivated": True,
        }

    except Exception as e:
        # ... existing error handling for other errors
```

### 3. Add Account Deactivation Function

**File:** `sync_airbnb/db/writers/accounts.py`

```python
def deactivate_account(
    engine: Engine,
    account_id: str,
    reason: str | None = None
) -> None:
    """Deactivate an account to stop sync attempts"""
    with engine.begin() as conn:
        stmt = (
            update(Account)
            .where(Account.account_id == account_id)
            .values(
                is_active=False,
                updated_at=utc_now(),
            )
        )
        conn.execute(stmt)

    logger.warning(
        f"Account {account_id} deactivated",
        extra={"account_id": account_id, "reason": reason}
    )
```

### 4. Skip Inactive Accounts in Scheduler

**File:** `sync_airbnb/services/scheduler.py`

Check `is_active` before running sync:

```python
def run_sync_on_startup(account: Account):
    if not account.is_active:
        logger.info(f"Skipping sync for inactive account {account.account_id}")
        return

    # ... existing sync logic
```

### 5. Better Error Logging

Add structured logging with context:

```python
logger.error(
    "Airbnb authentication failed - cookie may be expired",
    extra={
        "account_id": account.account_id,
        "error_type": "auth_failed",
        "http_status": response.status_code,
        "response_type": response.headers.get("content-type"),
        "action_taken": "account_deactivated",
    }
)
```

### 6. Prevent Restart Loops

**File:** `sync_airbnb/services/scheduler.py`

Add exponential backoff or stop scheduler on auth failures:

```python
# Option A: Don't run scheduler if account is inactive
if not account.is_active:
    logger.warning(f"Account {account.account_id} is inactive, scheduler will not start")
    return

# Option B: Add cooldown after failures
last_failure = get_last_failure_time(account.account_id)
if last_failure and (utc_now() - last_failure) < timedelta(hours=24):
    logger.info(f"Account {account.account_id} in cooldown after auth failure")
    return
```

## Testing Plan

1. **Simulate expired cookie:**
   - Set invalid AIRBNB_COOKIE in .env
   - Start container
   - Verify: Clear "auth failed" error logged
   - Verify: Account marked as `is_active=False`
   - Verify: No restart loop

2. **Test HTML response:**
   - Mock Airbnb API to return HTML login page
   - Verify detection and handling

3. **Test null data:**
   - Mock response with `{"data": null, "errors": [...]}`
   - Verify proper error message extraction

## Acceptance Criteria

- [ ] Clear error message when cookie expires: "Airbnb authentication failed - cookie may be expired"
- [ ] Account automatically deactivated (`is_active=False`) on auth failure
- [ ] No restart loops - sync attempts stop for inactive accounts
- [ ] Structured logging with account_id and error context
- [ ] Can manually reactivate account after updating credentials via API
- [ ] Scheduler skips inactive accounts
- [ ] Works for both startup sync and scheduled sync

## Future Enhancements

- Email/Slack notification when credentials expire
- API endpoint to test credentials without running full sync
- Automatic credential refresh if Airbnb supports it
- Dashboard UI to show account status and last error
- Retry with exponential backoff before deactivating

## Related Files

- `sync_airbnb/network/http_client.py` - HTTP request handling
- `sync_airbnb/flatteners/utils.py` - Response parsing (currently crashes)
- `sync_airbnb/services/insights.py` - Sync orchestration
- `sync_airbnb/services/scheduler.py` - Scheduled sync jobs
- `sync_airbnb/db/writers/accounts.py` - Account management
- `sync_airbnb/models/account.py` - Account model (has `is_active` field)

## Priority

**HIGH** - This is causing production issues with restart loops and unclear error messages
