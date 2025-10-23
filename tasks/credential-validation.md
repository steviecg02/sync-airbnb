# Airbnb Credential Validation

**Priority:** P1 - High (Security & Data Quality)
**Status:** Not implemented
**Estimated effort:** 3-4 hours

---

## Overview

Implement validation of Airbnb credentials before accepting account creation/update requests. This ensures invalid credentials are rejected early rather than failing during sync jobs.

---

## Problem

Currently, the API accepts any credentials without validation:
- Invalid cookies are stored in database
- Worker pods start successfully but fail on first API call
- Wasted resources (pod scheduling, startup time)
- Poor user experience (no immediate feedback)
- Debug overhead (why did sync fail?)

---

## Solution

Add a validation step that makes a test Airbnb API call to verify credentials work before storing them.

---

## Implementation

### 1. Create Validation Function

**File:** `sync_airbnb/services/credential_validator.py`

```python
"""Airbnb credential validation service."""

import logging
from typing import Dict

from sync_airbnb.network.http_client import AirbnbRequestError, post_with_retry
from sync_airbnb.network.http_headers import build_headers
from sync_airbnb.payloads.listings import build_listings_section_query

logger = logging.getLogger(__name__)

AIRBNB_API_URL = "https://www.airbnb.com/api/v3/BatchedGqlOperations"


class CredentialValidationError(Exception):
    """Raised when Airbnb credentials are invalid."""
    pass


def validate_airbnb_credentials(
    airbnb_cookie: str,
    x_client_version: str,
    x_airbnb_client_trace_id: str,
    user_agent: str,
    timeout: int = 10,
) -> bool:
    """
    Validate Airbnb credentials by making a test API call.

    Args:
        airbnb_cookie: Airbnb authentication cookie
        x_client_version: Client version header
        x_airbnb_client_trace_id: Client trace ID header
        user_agent: User agent header
        timeout: Request timeout in seconds

    Returns:
        True if credentials are valid

    Raises:
        CredentialValidationError: If credentials are invalid or validation fails
    """
    # Build headers from credentials
    headers = build_headers(
        airbnb_cookie=airbnb_cookie,
        x_client_version=x_client_version,
        x_airbnb_client_trace_id=x_airbnb_client_trace_id,
        user_agent=user_agent,
    )

    # Make lightweight test API call (listings query)
    payload = build_listings_section_query()

    try:
        response = post_with_retry(
            url=AIRBNB_API_URL,
            json=payload,
            headers=headers,
            timeout=timeout,
            debug=False,
            context="credential_validation",
        )

        # Check for valid response structure
        if "data" not in response:
            raise CredentialValidationError("Invalid response structure from Airbnb API")

        # Check for authentication errors in response
        if "errors" in response:
            errors = response["errors"]
            if any("authentication" in str(e).lower() for e in errors):
                raise CredentialValidationError("Authentication failed - invalid credentials")

        logger.info("Airbnb credentials validated successfully")
        return True

    except AirbnbRequestError as e:
        # Check for auth-related errors
        error_msg = str(e).lower()
        if "401" in error_msg or "403" in error_msg or "auth" in error_msg:
            raise CredentialValidationError(f"Invalid Airbnb credentials: {e}") from e
        else:
            # Network error, rate limit, etc - don't fail validation
            logger.warning(f"Credential validation skipped due to API error: {e}")
            return True  # Assume valid (fail open)

    except Exception as e:
        logger.error(f"Unexpected error during credential validation: {e}", exc_info=True)
        # Fail open - don't block account creation on validation errors
        return True
```

### 2. Update Account Creation Endpoint

**File:** `sync_airbnb/api/routes/accounts.py`

```python
from sync_airbnb.services.credential_validator import (
    CredentialValidationError,
    validate_airbnb_credentials,
)

@router.post("/accounts", ...)
async def create_account(account: AccountCreate, engine: Engine = Depends(get_db_engine)):
    """Create or update an account with credential validation."""
    # Existing validation: account_id matches cookie
    extracted_id = extract_account_id_from_cookie(account.airbnb_cookie)
    if extracted_id != account.account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"account_id mismatch: provided {account.account_id}, extracted {extracted_id}",
        )

    # NEW: Validate credentials
    try:
        validate_airbnb_credentials(
            airbnb_cookie=account.airbnb_cookie,
            x_client_version=account.x_client_version,
            x_airbnb_client_trace_id=account.x_airbnb_client_trace_id,
            user_agent=account.user_agent,
        )
    except CredentialValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid Airbnb credentials: {str(e)}",
        )

    # Proceed with account creation
    result = account_writers.create_or_update_account(engine, account)
    return AccountResponse.model_validate(result)
```

### 3. Update Account Update Endpoint

**File:** `sync_airbnb/api/routes/accounts.py`

```python
@router.patch("/accounts/{account_id}", ...)
async def update_account(
    account_id: str,
    updates: AccountUpdate,
    engine: Engine = Depends(get_db_engine),
):
    """Update account with credential validation if credentials changed."""
    # If any credential field is being updated, validate
    credential_fields = [
        "airbnb_cookie",
        "x_client_version",
        "x_airbnb_client_trace_id",
        "user_agent",
    ]

    if any(getattr(updates, field, None) is not None for field in credential_fields):
        # Fetch current account to get full credentials
        current_account = validate_account_exists(engine, account_id)

        # Build complete credential set (use new if provided, else current)
        airbnb_cookie = updates.airbnb_cookie or current_account.airbnb_cookie
        x_client_version = updates.x_client_version or current_account.x_client_version
        x_airbnb_client_trace_id = (
            updates.x_airbnb_client_trace_id or current_account.x_airbnb_client_trace_id
        )
        user_agent = updates.user_agent or current_account.user_agent

        # Validate
        try:
            validate_airbnb_credentials(
                airbnb_cookie=airbnb_cookie,
                x_client_version=x_client_version,
                x_airbnb_client_trace_id=x_airbnb_client_trace_id,
                user_agent=user_agent,
            )
        except CredentialValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid Airbnb credentials: {str(e)}",
            )

    # Proceed with update
    account = account_writers.update_account(engine, account_id, updates)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Account {account_id} not found")
    return AccountResponse.model_validate(account)
```

---

## Testing

### Unit Tests

**File:** `tests/services/test_credential_validator.py`

```python
"""Tests for credential validation."""

import pytest
from unittest.mock import patch

from sync_airbnb.services.credential_validator import (
    CredentialValidationError,
    validate_airbnb_credentials,
)


def test_validate_credentials_with_valid_response_returns_true():
    """Test validation succeeds with valid API response."""
    with patch("sync_airbnb.services.credential_validator.post_with_retry") as mock_post:
        mock_post.return_value = {"data": {"presentation": {"staysSearch": {}}}}

        result = validate_airbnb_credentials(
            airbnb_cookie="valid_cookie",
            x_client_version="v1",
            x_airbnb_client_trace_id="trace",
            user_agent="Mozilla/5.0",
        )

        assert result is True


def test_validate_credentials_with_auth_error_raises_exception():
    """Test validation fails with 401/403 error."""
    from sync_airbnb.network.http_client import AirbnbRequestError

    with patch("sync_airbnb.services.credential_validator.post_with_retry") as mock_post:
        mock_post.side_effect = AirbnbRequestError("Auth error: 401")

        with pytest.raises(CredentialValidationError):
            validate_airbnb_credentials(
                airbnb_cookie="invalid_cookie",
                x_client_version="v1",
                x_airbnb_client_trace_id="trace",
                user_agent="Mozilla/5.0",
            )


def test_validate_credentials_with_network_error_fails_open():
    """Test validation passes (fail open) on network errors."""
    from sync_airbnb.network.http_client import AirbnbRequestError

    with patch("sync_airbnb.services.credential_validator.post_with_retry") as mock_post:
        mock_post.side_effect = AirbnbRequestError("Network timeout")

        result = validate_airbnb_credentials(
            airbnb_cookie="valid_cookie",
            x_client_version="v1",
            x_airbnb_client_trace_id="trace",
            user_agent="Mozilla/5.0",
        )

        assert result is True  # Fail open
```

---

## Acceptance Criteria

- [ ] `POST /api/v1/accounts` validates credentials before creating account
- [ ] `PATCH /api/v1/accounts/{id}` validates credentials when updating credential fields
- [ ] Returns 400 Bad Request with clear error message for invalid credentials
- [ ] Validation uses lightweight API call (listings query, not full sync)
- [ ] Validation fails open (allows account creation) on network errors or rate limits
- [ ] Unit tests cover valid credentials, invalid credentials, and network errors
- [ ] Validation timeout is configurable (default 10 seconds)
- [ ] Prometheus metrics track validation success/failure rates

---

## Trade-offs

**Pros:**
- Early failure detection (better UX)
- Prevents wasted resources on invalid accounts
- Easier debugging (know credentials are bad before sync)

**Cons:**
- Adds latency to account creation (~200-500ms for API call)
- Additional Airbnb API request (rate limit consideration)
- Fail-open strategy means some invalid credentials could slip through

**Decision:** Accept trade-offs. Benefits outweigh costs, and fail-open prevents blocking valid accounts during Airbnb API outages.

---

## Future Enhancements

1. **Periodic Revalidation:** Background job to check existing accounts' credentials still work
2. **Cache Validation Results:** Skip validation for N minutes after successful validation
3. **Detailed Error Messages:** Parse Airbnb API error responses for specific failure reasons
