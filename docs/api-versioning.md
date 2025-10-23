# API Versioning Policy

## Overview

This document defines the API versioning strategy for sync-airbnb to ensure stable, predictable API evolution without breaking existing clients.

## Version Format

APIs use semantic versioning in URL path: `/api/v{major}/...`

- **Major version** (v1, v2, v3): Breaking changes that require client updates
- **Minor/patch changes**: Backwards-compatible changes within a major version

### Examples

```
/api/v1/accounts          # Version 1 - Current stable
/api/v2/accounts          # Version 2 - Future breaking changes
```

## Version Lifecycle

Each API version goes through three stages:

### 1. Active

- **Status**: Current version, fully supported
- **Support**: Bug fixes, security patches, new features
- **Deprecation**: None
- **Example**: `/api/v1/` (current)

### 2. Deprecated

- **Status**: Old version still works but sunset date announced
- **Support**: Critical bug fixes and security patches only
- **Deprecation**: Warning headers added to all responses
- **Duration**: Minimum 6 months before sunset
- **Example**: If v2 launches, v1 enters deprecated state

### 3. Sunset

- **Status**: Version removed, returns 410 Gone
- **Support**: None - clients must upgrade
- **Timing**: After 6-month deprecation period
- **Migration**: All clients migrated to newer version

## Deprecation Process

When introducing breaking changes, follow this process:

### 1. Announce Deprecation (T-6 months)

- Publish migration guide in documentation
- Add deprecation notice to `/docs` page
- Send notification to all API users
- Set sunset date (6 months minimum)

### 2. Add Deprecation Headers (T-6 months)

All deprecated API responses include:

```http
HTTP/1.1 200 OK
Deprecation: true
Sunset: Sat, 01 Jun 2026 00:00:00 GMT
Link: </api/v2/accounts>; rel="successor-version"
X-API-Warn: "API v1 is deprecated and will be removed on 2026-06-01. Migrate to v2: https://docs.example.com/migration-v1-to-v2"
```

### 3. Monitor Usage (T-6 to T-0 months)

- Track request counts per version via logs
- Identify clients still using deprecated version
- Reach out to heavy users to assist migration
- Publish monthly usage stats

### 4. Sunset Version (T-0)

When usage < 1% or sunset date reached:

1. Change deprecated endpoints to return `410 Gone`:

```json
{
  "error": {
    "code": "VERSION_SUNSET",
    "message": "API v1 was sunset on 2026-06-01. Please upgrade to v2.",
    "details": {
      "sunset_date": "2026-06-01",
      "successor_version": "v2",
      "migration_guide": "https://docs.example.com/migration-v1-to-v2"
    }
  }
}
```

2. Update documentation to remove v1 references
3. Archive v1 code for reference

## Making Breaking Changes

Breaking changes require a new major version. Follow these steps:

### 1. Identify Breaking Change

Breaking changes include:
- Removing endpoints or fields
- Changing field types (string -> int)
- Renaming fields or endpoints
- Changing authentication methods
- Modifying error response formats

Non-breaking changes (safe for minor versions):
- Adding new endpoints
- Adding new optional fields
- Adding new query parameters (with defaults)
- Improving error messages

### 2. Create New Major Version

```python
# New version router
from fastapi import APIRouter

router_v2 = APIRouter(prefix="/api/v2", tags=["v2"])

@router_v2.post("/accounts")
async def create_account_v2(account: AccountCreateV2):
    """v2 endpoint with breaking changes."""
    pass

# Register in main.py
app.include_router(router_v2)
```

### 3. Maintain Old Version (6 months)

Keep v1 code running in parallel:

```python
# Old version still works
router_v1 = APIRouter(prefix="/api/v1", tags=["v1"])

@router_v1.middleware("http")
async def add_deprecation_headers(request, call_next):
    response = await call_next(request)
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "Sat, 01 Jun 2026 00:00:00 GMT"
    response.headers["Link"] = '</api/v2/accounts>; rel="successor-version"'
    return response
```

### 4. Publish Migration Guide

Create detailed migration documentation:

```markdown
# Migration Guide: v1 to v2

## Breaking Changes

### 1. Account ID Format Changed

**Before (v1):**
```json
{"account_id": "310316675"}
```

**After (v2):**
```json
{"account_id": "acct_310316675"}
```

**Migration:**
Prefix all account IDs with `acct_` when calling v2 endpoints.

### 2. Date Format Changed to ISO 8601

**Before (v1):**
```json
{"created_at": "2025-10-21 12:00:00"}
```

**After (v2):**
```json
{"created_at": "2025-10-21T12:00:00Z"}
```

**Migration:**
Update date parsers to handle ISO 8601 format.
```

### 5. Deprecate v1 After 6 Months

Follow deprecation process above.

## Example: v1 to v2 Migration

Let's say we need to change account ID format from numeric to prefixed string.

### Current State (v1)

```python
@router.post("/api/v1/accounts", status_code=201)
async def create_account(account: AccountCreate):
    # account_id is "310316675" (numeric string)
    pass
```

### New Version (v2)

```python
@router.post("/api/v2/accounts", status_code=201)
async def create_account_v2(account: AccountCreateV2):
    # account_id is "acct_310316675" (prefixed)
    pass
```

### Timeline

- **2025-10-21**: Launch v2, deprecate v1 (sunset 2026-04-21)
- **2025-10-21 to 2026-04-21**: Both versions active, v1 returns deprecation headers
- **2026-04-21**: Sunset v1, returns 410 Gone

## Version-Specific Documentation

Each version should have its own documentation:

```
/docs/v1          # Swagger UI for v1 (deprecated)
/docs/v2          # Swagger UI for v2 (current)
/docs             # Redirect to latest version
```

## Backwards-Compatible Changes

These changes DO NOT require a new major version:

### Safe to Add
- New endpoints
- New optional fields (with defaults)
- New query parameters (with defaults)
- New response fields (clients ignore unknown fields)

### Example: Adding Optional Field

```python
# v1 - original
class AccountCreate(BaseModel):
    account_id: str
    airbnb_cookie: str

# v1 - updated (backwards compatible)
class AccountCreate(BaseModel):
    account_id: str
    airbnb_cookie: str
    customer_id: str | None = None  # NEW: optional, defaults to None
```

This is safe because:
- Old clients can omit the field (defaults to None)
- New clients can provide the field
- No breaking changes

## Summary

- **Major versions**: Breaking changes (v1 -> v2)
- **Deprecation period**: Minimum 6 months
- **Deprecation headers**: Added to all responses
- **Migration guides**: Required for all breaking changes
- **Sunset process**: Usage < 1% or date reached
- **Backwards-compatible changes**: Safe within major version

## Current Status

- **Active**: v1 (all endpoints)
- **Deprecated**: None
- **Sunset**: None

When v2 is needed, update this section with migration timeline.
