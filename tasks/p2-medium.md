# P2 Medium Priority Issues - Code Quality Debt

**Status:** Should be addressed before scaling to production
**Total Issues:** 8
**Estimated Effort:** 25-37 hours

---

## Issue 14: Emoji Logging Breaks JSON Parsers

**Priority:** P2 - MEDIUM
**Severity:** Operations, observability
**Impact:** Log aggregation tools (Datadog, Splunk, ELK) fail to parse logs
**Status:** Open
**Estimated Effort:** 1-2 hours

### Current State

Logs contain emoji characters throughout the codebase:

```python
logger.info("✅ Sync completed successfully")
logger.error("❌ Sync failed")
logger.warning("⚠️ Rate limit approaching")
```

### Problem

Modern log aggregation tools expect structured JSON logs:

```json
{"timestamp": "2025-10-21T12:00:00Z", "level": "INFO", "message": "Sync completed"}
```

Emojis break JSON parsers:
```json
{"message": "✅ Sync completed"}  // Invalid JSON (encoding issues)
```

### Recommended Solution

Remove all emojis, use plain text:

```python
# BEFORE
logger.info("✅ Sync completed successfully")
logger.error("❌ Sync failed")
logger.warning("⚠️ Rate limit approaching")

# AFTER
logger.info("Sync completed successfully")
logger.error("Sync failed")
logger.warning("Rate limit approaching")
```

### Implementation Steps

1. Search for all emoji usage:
   ```bash
   grep -r "✅\|❌\|⚠️\|📊\|🔍\|⏰" sync_airbnb/
   ```

2. Replace with plain text equivalents

3. Update logging standards in CONTRIBUTING.md

4. Add pre-commit hook to block emojis:
   ```yaml
   # .pre-commit-config.yaml
   - repo: local
     hooks:
       - id: no-emoji-in-code
         name: No emoji in code
         entry: bash -c 'if git diff --cached | grep -E "✅|❌|⚠️"; then echo "ERROR: Emojis not allowed in code"; exit 1; fi'
         language: system
   ```

### Files to Modify

All Python files in `sync_airbnb/` (search and replace).

---

## Issue 15: Database Connection Pool Not Tuned

**Priority:** P2 - MEDIUM
**Severity:** Performance, scalability
**Impact:** Connection exhaustion under load, slow response times
**Status:** Open
**Estimated Effort:** 2-3 hours

### Current State

SQLAlchemy engine created with defaults:

```python
# sync_airbnb/config.py
engine = create_engine(DATABASE_URL, future=True)
# No pool_size, max_overflow, pool_recycle settings
```

Default settings:
- `pool_size=5` (only 5 connections)
- `max_overflow=10` (max 15 total)
- `pool_recycle=-1` (connections never recycled)

### Problem

In production with multiple workers:
- Worker 1: 5 connections
- Worker 2: 5 connections
- Worker 3: 5 connections
- **Total:** 15 connections (may exceed DB limit)

### Recommended Solution

Configure connection pool based on deployment:

```python
# sync_airbnb/config.py
import os
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

# Connection pool settings from environment
POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))
MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "20"))
POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "3600"))  # 1 hour
POOL_PRE_PING = os.getenv("DB_POOL_PRE_PING", "true").lower() == "true"

engine = create_engine(
    DATABASE_URL,
    future=True,
    poolclass=QueuePool,
    pool_size=POOL_SIZE,
    max_overflow=MAX_OVERFLOW,
    pool_recycle=POOL_RECYCLE,
    pool_pre_ping=POOL_PRE_PING,  # Verify connection before use
    echo=False,
)
```

### Sizing Guidelines

Formula: `pool_size = (num_workers * 2) + 1`

Examples:
- 1 worker: `pool_size=3`
- 5 workers: `pool_size=11`
- 10 workers: `pool_size=21`

Ensure DB max_connections > total pool size across all services.

### Implementation Steps

1. Add pool configuration to `config.py`
2. Add environment variables to `.env`
3. Document sizing guidelines
4. Add connection pool metrics
5. Test under load

---

## Issue 16: No Dry-Run Mode for Testing

**Priority:** P2 - MEDIUM
**Severity:** Testing, safety
**Impact:** Cannot safely test against production database
**Status:** Open
**Estimated Effort:** 2-3 hours

### Current State

No way to test sync logic without writing to database.

### Recommended Solution

Add `DRY_RUN` environment variable:

```python
# sync_airbnb/config.py
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"

# sync_airbnb/db/writers/insights.py
def insert_chart_query_rows(engine: Engine, rows: list[dict]) -> None:
    if config.DRY_RUN:
        logger.info(f"[DRY RUN] Would insert {len(rows)} chart_query rows")
        logger.debug(f"[DRY RUN] Sample row: {rows[0] if rows else None}")
        return

    with engine.begin() as conn:
        stmt = insert(ChartQuery).values(rows)
        stmt = stmt.on_conflict_do_update(...)
        conn.execute(stmt)
```

### Testing Requirements

```bash
# Run in dry-run mode
DRY_RUN=true uvicorn sync_airbnb.main:app

# Trigger sync - should log but not write
curl -X POST http://localhost:8000/api/v1/accounts/123/sync

# Check logs - should see "[DRY RUN]" messages
# Check database - should have no new rows
```

---

## Issue 17: Inconsistent Error Messages

**Priority:** P2 - MEDIUM
**Severity:** User experience, debugging
**Impact:** Harder to debug issues, poor API usability
**Status:** Open
**Estimated Effort:** 3-4 hours

### Current State

Error messages vary in format:

```python
# Some return generic messages
raise HTTPException(status_code=404, detail="Not found")

# Some return detailed messages
raise HTTPException(status_code=400, detail=f"Account {account_id} not found")

# Some include stack traces, some don't
logger.error("Error occurred", exc_info=True)
logger.error(f"Error: {str(e)}")  # No traceback
```

### Recommended Solution

Standardize error response format:

```python
# sync_airbnb/api/errors.py
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

class ErrorResponse:
    """Standard error response format."""

    @staticmethod
    def format(
        error_code: str,
        message: str,
        details: dict | None = None,
        request_id: str | None = None,
    ) -> dict:
        return {
            "error": {
                "code": error_code,
                "message": message,
                "details": details or {},
                "request_id": request_id,
            }
        }

# Exception handlers
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse.format(
            error_code=f"HTTP_{exc.status_code}",
            message=exc.detail,
            request_id=request.state.request_id,
        ),
    )

# Register in main.py
app.add_exception_handler(HTTPException, http_exception_handler)
```

### Usage

```python
# Consistent error raising
from sync_airbnb.api.errors import ErrorResponse

if not account:
    raise HTTPException(
        status_code=404,
        detail=ErrorResponse.format(
            error_code="ACCOUNT_NOT_FOUND",
            message=f"Account {account_id} does not exist",
            details={"account_id": account_id},
        ),
    )
```

---

## Issue 18: No Request ID Tracking

**Priority:** P2 - MEDIUM
**Severity:** Observability, debugging
**Impact:** Cannot trace requests across logs and services
**Status:** Open
**Estimated Effort:** 2-3 hours

### Current State

No way to correlate logs for a single request.

### Recommended Solution

Add middleware to generate request IDs:

```python
# sync_airbnb/middleware/request_id.py
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Generate or extract request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        # Add to response headers
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

# sync_airbnb/main.py
from sync_airbnb.middleware.request_id import RequestIDMiddleware

app.add_middleware(RequestIDMiddleware)
```

Include in all logs:

```python
logger.info(
    "Account created",
    extra={
        "request_id": request.state.request_id,
        "account_id": account_id,
    },
)
```

---

## Issue 19: Missing Pydantic Validation

**Priority:** P2 - MEDIUM
**Severity:** Data quality
**Impact:** Invalid data can enter database
**Status:** Open
**Estimated Effort:** 2-3 hours

### Current State

Basic Pydantic models with no validators:

```python
class AccountCreate(BaseModel):
    account_id: str  # No validation
    airbnb_cookie: str  # No length check
    x_client_version: str  # No format check
```

### Recommended Solution

Add field validators:

```python
from pydantic import BaseModel, Field, validator

class AccountCreate(BaseModel):
    account_id: str = Field(..., min_length=1, max_length=255, regex="^[0-9]+$")
    airbnb_cookie: str = Field(..., min_length=50)
    x_airbnb_client_trace_id: str = Field(..., regex="^[a-f0-9-]+$")
    x_client_version: str = Field(..., regex="^[0-9.]+$")
    user_agent: str = Field(..., min_length=10)

    @validator("account_id")
    def validate_account_id(cls, v):
        if not v.isdigit():
            raise ValueError("account_id must be numeric")
        return v
```

---

## Issue 20: Datetime Handling Inconsistencies

**Priority:** P2 - MEDIUM
**Severity:** Data quality, bugs
**Impact:** Timezone bugs, DST issues
**Status:** Open
**Estimated Effort:** 3-4 hours

### Current State

Mix of aware and naive datetimes:

```python
# Some use naive datetime
from datetime import datetime
now = datetime.now()  # Naive

# Some use date
from datetime import date
today = date.today()  # No timezone
```

### Recommended Solution

Always use UTC timezone-aware datetimes:

```python
from datetime import datetime, timezone

# ALWAYS use UTC
now = datetime.now(timezone.utc)

# Helper functions
def utc_now() -> datetime:
    """Get current UTC datetime."""
    return datetime.now(timezone.utc)

def to_utc(dt: datetime) -> datetime:
    """Convert datetime to UTC."""
    if dt.tzinfo is None:
        # Assume naive is UTC
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
```

---

## Issue 21: No Database Migration Testing

**Priority:** P2 - MEDIUM
**Severity:** Operations, reliability
**Impact:** Migrations may fail in production
**Status:** Open
**Estimated Effort:** 2-3 hours

### Current State

No CI tests for migrations.

### Recommended Solution

Add migration tests to CI:

```yaml
# .github/workflows/ci.yml
- name: Test migrations
  run: |
    # Start test database
    docker run -d --name test-db -p 5432:5432 timescale/timescaledb:latest-pg15

    # Apply all migrations
    alembic upgrade head

    # Rollback all migrations
    alembic downgrade base

    # Re-apply all migrations
    alembic upgrade head

    # Verify schema is correct
    psql -h localhost -U postgres -c "\dt airbnb.*"
```

---

## Summary

These 8 P2 issues represent code quality debt that should be addressed before scaling to production.

**Priority Order:**
1. Issue 15 - Connection pool tuning (stability)
2. Issue 17 - Error message standardization (UX)
3. Issue 18 - Request ID tracking (observability)
4. Issue 20 - Datetime handling (correctness)
5. Issue 19 - Pydantic validation (data quality)
6. Issue 21 - Migration testing (reliability)
7. Issue 16 - Dry-run mode (testing)
8. Issue 14 - Emoji logging (observability)

**Total Effort:** 25-37 hours (~4-5 days for one developer)
