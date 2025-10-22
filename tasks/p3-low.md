# P3 Low Priority Issues - Nice-to-Have Improvements

**Status:** Optional enhancements, not blocking production
**Total Issues:** 7
**Estimated Effort:** 19-29 hours

---

## Issue 22: No API Versioning Strategy

**Priority:** P3 - LOW
**Severity:** Maintenance, compatibility
**Impact:** Breaking changes affect all clients simultaneously
**Status:** Open
**Estimated Effort:** 1-2 hours

### Current State

API uses `/api/v1/` prefix but no documented versioning strategy.

### Problem

Without versioning strategy:
- Can't make breaking changes without breaking all clients
- No deprecation process
- No migration path for clients

### Recommended Solution

Document API versioning policy:

```markdown
# docs/api-versioning.md

## API Versioning Policy

### Version Format

APIs use semantic versioning in URL: `/api/v{major}/...`

- Major version (v1, v2): Breaking changes
- Minor/patch changes: Backwards compatible

### Version Lifecycle

1. **Active** - Current version, fully supported
2. **Deprecated** - Old version, still works, sunset date announced
3. **Sunset** - Old version removed

### Deprecation Process

1. Announce deprecation 6 months before sunset
2. Add `Deprecation` header to responses
3. Update documentation with migration guide
4. Monitor usage via logs
5. Sunset version when usage < 1%

### Example Deprecation Header

```http
HTTP/1.1 200 OK
Deprecation: true
Sunset: Sat, 01 Jun 2026 00:00:00 GMT
Link: </api/v2/accounts>; rel="successor-version"
```

### Making Breaking Changes

1. Create new major version (v2)
2. Maintain v1 for 6 months
3. Deprecate v1
4. Sunset v1 after migration period
```

---

## Issue 23: Missing OpenAPI Documentation

**Priority:** P3 - LOW
**Severity:** Developer experience
**Impact:** Harder for users to understand API
**Status:** Open
**Estimated Effort:** 2-3 hours

### Current State

FastAPI auto-generates basic docs at `/docs`, but missing:
- Endpoint descriptions
- Request/response examples
- Error response documentation
- Authentication documentation

### Recommended Solution

Add comprehensive docstrings:

```python
@router.post(
    "/accounts",
    status_code=201,
    response_model=AccountResponse,
    summary="Create or update an account",
    description="""
    Create a new Airbnb account or update an existing one.

    This endpoint validates account credentials by making a test API call
    to Airbnb. If credentials are invalid, returns 400 error.

    **Note:** Account ID is extracted from Airbnb cookie and must match
    the account_id field.
    """,
    responses={
        201: {
            "description": "Account created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "account_id": "310316675",
                        "customer_id": null,
                        "is_active": true,
                        "last_sync_at": null,
                        "created_at": "2025-10-21T12:00:00Z",
                        "updated_at": "2025-10-21T12:00:00Z",
                        "validation": {
                            "valid": true,
                            "listing_count": 5,
                        },
                    }
                }
            },
        },
        400: {
            "description": "Invalid credentials",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "INVALID_CREDENTIALS",
                            "message": "Account credentials are invalid",
                            "details": {"error": "401 Unauthorized"},
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
            "airbnb_cookie": "your_cookie_here...",
            "x_airbnb_client_trace_id": "abc-123-def",
            "x_client_version": "1.2.3",
            "user_agent": "Mozilla/5.0...",
            "is_active": true,
        },
    ),
):
    """Create or update Airbnb account with credential validation."""
    ...
```

---

## Issue 24: No Pagination on List Endpoints

**Priority:** P3 - LOW
**Severity:** Performance, scalability
**Impact:** Slow responses with many accounts (>1000)
**Status:** Open
**Estimated Effort:** 2-3 hours

### Current State

`GET /api/v1/accounts` returns all accounts (no pagination).

### Problem

With 1000+ accounts:
- Large response size (>1MB)
- Slow database query
- High memory usage
- Poor user experience

### Recommended Solution

Add offset/limit pagination:

```python
from fastapi import Query

@router.get("/accounts")
async def list_accounts(
    active_only: bool = Query(False),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> dict:
    """List accounts with pagination."""
    accounts = get_accounts(
        engine,
        active_only=active_only,
        offset=offset,
        limit=limit,
    )
    total = count_accounts(engine, active_only=active_only)

    return {
        "items": accounts,
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": (offset + limit) < total,
    }
```

Alternative: Cursor-based pagination for better performance:

```python
@router.get("/accounts")
async def list_accounts(
    cursor: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
):
    """List accounts with cursor pagination."""
    if cursor:
        # Decode cursor (base64 encoded account_id)
        last_account_id = base64.b64decode(cursor).decode()
        accounts = get_accounts_after(engine, last_account_id, limit)
    else:
        accounts = get_accounts(engine, limit=limit)

    next_cursor = None
    if len(accounts) == limit:
        # Encode last account_id as cursor
        next_cursor = base64.b64encode(accounts[-1].account_id.encode()).decode()

    return {
        "items": accounts,
        "next_cursor": next_cursor,
    }
```

---

## Issue 25: Docker Image Size

**Priority:** P3 - LOW
**Severity:** Deployment speed, costs
**Impact:** Slower deployments, higher storage/bandwidth costs
**Status:** Open
**Estimated Effort:** 1-2 hours

### Current State

Dockerfile uses full Python image (~900 MB):

```dockerfile
FROM python:3.10
```

### Recommended Solution

Use slim image with multi-stage build:

```dockerfile
# Build stage
FROM python:3.10-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Runtime stage
FROM python:3.10-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local

# Copy application code
COPY sync_airbnb/ ./sync_airbnb/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY entrypoint.sh .

# Make sure scripts are executable
RUN chmod +x entrypoint.sh

# Add .local/bin to PATH
ENV PATH=/root/.local/bin:$PATH

ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "sync_airbnb.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Before:** 900 MB
**After:** ~200 MB (77% reduction)

---

## Issue 26: No Account Soft Delete

**Priority:** P3 - LOW
**Severity:** Data safety
**Impact:** Account deleted by accident = data loss
**Status:** Open
**Estimated Effort:** 2-3 hours

### Current State

`DELETE /accounts/{id}` permanently deletes account:

```python
@router.delete("/accounts/{account_id}", status_code=204)
async def delete_account(account_id: str):
    delete_account_by_id(engine, account_id)  # PERMANENT DELETE
```

### Problem

- Accidental deletion = permanent data loss
- Cannot recover deleted accounts
- Audit trail lost

### Recommended Solution

Add soft delete with `deleted_at` timestamp:

```python
# Migration: Add deleted_at column
op.add_column(
    "accounts",
    sa.Column("deleted_at", sa.DateTime, nullable=True),
    schema="airbnb",
)

# Model
class Account(Base):
    # ... existing fields ...
    deleted_at = Column(DateTime, nullable=True)

# Delete endpoint - soft delete
@router.delete("/accounts/{account_id}", status_code=204)
async def delete_account(account_id: str):
    soft_delete_account(engine, account_id, deleted_at=datetime.utcnow())

# List endpoint - exclude deleted
@router.get("/accounts")
async def list_accounts(include_deleted: bool = False):
    accounts = get_accounts(
        engine,
        include_deleted=include_deleted,
    )
    return accounts

# Restore endpoint
@router.post("/accounts/{account_id}/restore", status_code=200)
async def restore_account(account_id: str):
    restore_deleted_account(engine, account_id)
```

---

## Issue 27: Missing Customer ID Usage

**Priority:** P3 - LOW
**Severity:** Documentation, feature completeness
**Impact:** Multi-tenant queries inefficient
**Status:** Open
**Estimated Effort:** 1-2 hours

### Current State

`customer_id` column exists on accounts but:
- Not documented how to use
- No API to filter by customer
- No example queries

### Recommended Solution

Document multi-tenant patterns:

```markdown
# docs/multi-tenant-usage.md

## Multi-Tenant Architecture

### Customer ID

The `customer_id` field allows grouping accounts by external customer/tenant.

**Use cases:**
- SaaS platform with multiple customers
- Agency managing multiple clients
- Internal teams with separate accounts

### Setting Customer ID

```python
# Create account with customer_id
account = AccountCreate(
    account_id="123",
    customer_id="cust_acme_corp",  # External customer ID
    ...
)
```

### Querying by Customer

```python
# Get all accounts for customer
GET /api/v1/accounts?customer_id=cust_acme_corp

# Get metrics for all customer accounts
SELECT *
FROM airbnb.chart_query
WHERE account_id IN (
    SELECT account_id
    FROM airbnb.accounts
    WHERE customer_id = 'cust_acme_corp'
);
```

### Database Indexes

Ensure index exists for efficient queries:

```sql
CREATE INDEX idx_accounts_customer_id ON airbnb.accounts(customer_id);
```
```

Add API filter:

```python
@router.get("/accounts")
async def list_accounts(
    customer_id: str | None = Query(None),
):
    if customer_id:
        accounts = get_accounts_by_customer(engine, customer_id)
    else:
        accounts = get_all_accounts(engine)
    return accounts
```

---

## Issue 28: No Metrics Export

**Priority:** P3 - LOW
**Severity:** Feature completeness
**Impact:** Hard to analyze data in BI tools (Excel, Tableau, etc.)
**Status:** Open
**Estimated Effort:** 4-6 hours

### Current State

No way to export metrics data from API.

### Recommended Solution

Add CSV/JSON export endpoints:

```python
from fastapi.responses import StreamingResponse
import csv
import io

@router.get("/accounts/{account_id}/metrics/export")
async def export_metrics(
    account_id: str,
    start_date: date = Query(...),
    end_date: date = Query(...),
    format: str = Query("csv", regex="^(csv|json)$"),
):
    """Export metrics for date range."""
    # Fetch metrics
    metrics = get_metrics(
        engine,
        account_id=account_id,
        start_date=start_date,
        end_date=end_date,
    )

    if format == "csv":
        # Generate CSV
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=metrics[0].keys())
        writer.writeheader()
        writer.writerows(metrics)

        # Return as streaming response
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=metrics_{account_id}_{start_date}_{end_date}.csv"
            },
        )

    else:
        # Return JSON
        return {
            "account_id": account_id,
            "start_date": str(start_date),
            "end_date": str(end_date),
            "metrics": metrics,
        }
```

---

## Summary

These 7 P3 issues are nice-to-have improvements that enhance the system but aren't critical for production deployment.

**Priority Order:**
1. Issue 24 - Pagination (performance at scale)
2. Issue 25 - Docker image optimization (deployment speed)
3. Issue 23 - OpenAPI docs (developer experience)
4. Issue 28 - Metrics export (feature completeness)
5. Issue 26 - Soft delete (data safety)
6. Issue 22 - API versioning strategy (future-proofing)
7. Issue 27 - Customer ID documentation (feature clarity)

**Total Effort:** 19-29 hours (~3-4 days for one developer)

**Note:** These can be implemented incrementally based on user feedback and actual needs.
