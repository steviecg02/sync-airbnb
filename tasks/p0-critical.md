# P0 Critical Issues - Blocking Production Deployment

**Status:** Must be resolved before any production deployment
**Total Issues:** 5
**Estimated Effort:** 10-18 hours

---

## Issue 1: No API Authentication

**Priority:** P0 - CRITICAL
**Severity:** Security vulnerability
**Impact:** Anyone can create/delete accounts, trigger syncs, access sensitive data
**Status:** Open
**Estimated Effort:** 4-8 hours

### Current State

All API endpoints are completely open with zero authentication:

```python
# sync_airbnb/api/routes/accounts.py
@router.post("/accounts", status_code=201)
async def create_account(account: AccountCreate):
    # NO AUTH CHECK - anyone can call this
    result = create_or_update_account(engine, account)
    return result

@router.delete("/accounts/{account_id}", status_code=204)
async def delete_account(account_id: str):
    # NO AUTH CHECK - anyone can delete accounts
    delete_account_by_id(engine, account_id)
```

### Security Risks

1. **Account Data Exposure**: Anyone can list all accounts (including cookies, credentials)
2. **Unauthorized Account Creation**: Attackers can create malicious accounts
3. **Account Deletion**: Attackers can delete legitimate accounts
4. **Sync Manipulation**: Anyone can trigger expensive sync operations (DoS vector)
5. **Data Theft**: Full access to all metrics data via account credentials

### Recommended Solution

Implement API key authentication using FastAPI's security utilities:

```python
from fastapi import Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

async def verify_api_key(api_key: str = Security(api_key_header)):
    """Verify API key from request header."""
    expected_key = os.getenv("API_KEY")
    if not expected_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API key not configured"
        )
    if api_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key"
        )
    return api_key

# Apply to all endpoints
@router.post("/accounts", status_code=201, dependencies=[Security(verify_api_key)])
async def create_account(account: AccountCreate):
    ...
```

### Alternative Solutions

1. **OAuth2 with scopes** (more complex, better for multi-user)
2. **JWT tokens** (stateless, good for microservices)
3. **mTLS** (best for service-to-service)

### Implementation Steps

1. Add `API_KEY` to environment variables
2. Create `sync_airbnb/api/security.py` with authentication logic
3. Add `Security(verify_api_key)` dependency to all routes
4. Add API key to .env.example (with placeholder value)
5. Update README with authentication instructions
6. Add tests for auth (valid key, invalid key, missing key)

### Testing Requirements

```python
def test_create_account_without_api_key_returns_403():
    response = client.post("/api/v1/accounts", json={...})
    assert response.status_code == 403

def test_create_account_with_invalid_api_key_returns_403():
    headers = {"X-API-Key": "wrong-key"}
    response = client.post("/api/v1/accounts", json={...}, headers=headers)
    assert response.status_code == 403

def test_create_account_with_valid_api_key_succeeds():
    headers = {"X-API-Key": os.getenv("API_KEY")}
    response = client.post("/api/v1/accounts", json={...}, headers=headers)
    assert response.status_code == 201
```

### Files to Modify

- `sync_airbnb/api/security.py` (create)
- `sync_airbnb/api/routes/accounts.py`
- `sync_airbnb/api/routes/health.py` (leave health check public)
- `.env` (add API_KEY)
- `.env.example` (add API_KEY placeholder)
- `README.md` (document authentication)
- `tests/api/test_authentication.py` (create)

### Dependencies

- None (uses built-in FastAPI security)

### Related Issues

- Issue 5 (secrets management)
- Issue 17 (consistent error messages)

---

## Issue 2: 15 Failing Tests (Import Paths)

**Priority:** P0 - CRITICAL
**Severity:** Quality assurance blocked
**Impact:** Cannot verify code correctness, high regression risk
**Status:** Open
**Estimated Effort:** 2-4 hours

### Current State

All tests are failing due to incorrect import paths in mock patches after refactoring:

```bash
$ pytest
...
ModuleNotFoundError: No module named 'network'
```

### Root Cause

The October 2025 refactoring moved all modules from top-level into `sync_airbnb/` package:

```
Before:
network/http_client.py

After:
sync_airbnb/network/http_client.py
```

Tests still use old import paths in `@patch()` decorators:

```python
# BROKEN - old path
@patch("network.http_client.requests.post")
def test_fetch_data(mock_post):
    ...

# CORRECT - new path
@patch("sync_airbnb.network.http_client.requests.post")
def test_fetch_data(mock_post):
    ...
```

### Affected Test Files

All test files need updates:

1. `tests/flatteners/test_chart_query.py`
2. `tests/flatteners/test_list_of_metrics_query.py`
3. `tests/flatteners/test_listings_section_query.py`
4. `tests/flatteners/test_utils.py`
5. `tests/network/test_http_client.py`
6. `tests/parsers/test_insights.py`
7. `tests/payloads/test_insights.py`
8. `tests/payloads/test_listings.py`
9. `tests/services/test_insights.py`
10. `tests/utils/test_airbnb_sync.py`
11. `tests/utils/test_date_window.py`

### Fix Pattern

Search and replace in all test files:

```python
# Old patterns (broken)
@patch("network.http_client.requests.post")
@patch("payloads.insights.build_chart_query_payload")
@patch("services.insights.run_insights_poller")
@patch("utils.date_window.get_poll_window")

# New patterns (correct)
@patch("sync_airbnb.network.http_client.requests.post")
@patch("sync_airbnb.payloads.insights.build_chart_query_payload")
@patch("sync_airbnb.services.insights.run_insights_poller")
@patch("sync_airbnb.utils.date_window.get_poll_window")
```

### Implementation Steps

1. Create script to automate fixes:
   ```bash
   # find_and_replace_imports.sh
   #!/bin/bash

   # Update @patch decorators
   find tests/ -name "*.py" -type f -exec sed -i '' \
     's/@patch("\([a-z_]*\)\.\([a-z_]*\)/@patch("sync_airbnb.\1.\2/g' {} \;

   # Update import statements
   find tests/ -name "*.py" -type f -exec sed -i '' \
     's/from \([a-z_]*\) import/from sync_airbnb.\1 import/g' {} \;
   ```

2. Run the script: `chmod +x find_and_replace_imports.sh && ./find_and_replace_imports.sh`

3. Manually review changes (script may have false positives)

4. Run tests: `pytest -v`

5. Fix any remaining import errors manually

6. Verify all tests pass: `pytest --tb=short`

### Manual Fix Example

```python
# tests/network/test_http_client.py - BEFORE
from unittest.mock import patch, Mock
from network.http_client import make_request

@patch("network.http_client.requests.post")
def test_make_request_success(mock_post):
    mock_post.return_value = Mock(status_code=200)
    result = make_request("https://api.airbnb.com", {})
    assert result is not None

# tests/network/test_http_client.py - AFTER
from unittest.mock import patch, Mock
from sync_airbnb.network.http_client import make_request

@patch("sync_airbnb.network.http_client.requests.post")
def test_make_request_success(mock_post):
    mock_post.return_value = Mock(status_code=200)
    result = make_request("https://api.airbnb.com", {})
    assert result is not None
```

### Testing Requirements

After fixes, all tests should pass:

```bash
pytest -v
# Expected: 40+ tests passed
```

### Files to Modify

All files in `tests/` directory (15 files).

### Dependencies

- None (pure refactoring)

### Related Issues

- None

---

## Issue 3: Missing JSON Schema Files

**Priority:** P0 - CRITICAL
**Severity:** Data quality risk
**Impact:** No validation of Airbnb API responses, cannot detect breaking changes
**Status:** Open
**Estimated Effort:** 4-6 hours

### Current State

JSON schema files were deleted during refactoring but are referenced in tests:

```bash
$ git status
D schemas/chart_query.schema.json
D schemas/list_of_metrics.schema.json
D schemas/listings_section.schema.json
D schemas/parsed_chart_query.schema.json
D schemas/parsed_chart_summary.schema.json
D schemas/parsed_list_of_metrics.schema.json
```

Tests that validate schema compliance are failing:

```python
# tests/flatteners/test_chart_query.py
def test_chart_query_response_conversions_matches_schema():
    with open("schemas/chart_query.schema.json") as f:  # FILE NOT FOUND
        schema = json.load(f)
    ...
```

### Impact

Without schema validation:

1. **Breaking changes undetected**: Airbnb changes API structure, code breaks silently
2. **Data quality issues**: Malformed responses inserted into database
3. **Hard to debug**: No clear error message when response structure changes
4. **Tests incomplete**: Cannot verify flattener output correctness

### Recommended Solution

Regenerate schemas from actual API responses:

#### Step 1: Capture Real API Responses

```python
# scripts/capture_api_responses.py
import json
from sync_airbnb.utils.airbnb_sync import AirbnbSync
from sync_airbnb.network.http_headers import build_headers
from datetime import date

# Use real credentials from .env
headers = build_headers(
    airbnb_cookie=os.getenv("AIRBNB_COOKIE"),
    x_client_version=os.getenv("X_CLIENT_VERSION"),
    x_airbnb_client_trace_id=os.getenv("X_AIRBNB_CLIENT_TRACE_ID"),
    user_agent=os.getenv("USER_AGENT"),
)

poller = AirbnbSync(scrape_day=date.today(), headers=headers)

# Capture listings response
listings = poller.fetch_listing_ids()
with open("schemas/samples/listings_section.json", "w") as f:
    json.dump(listings, f, indent=2)

# Capture chart query response
response = poller.poll_chart_query(listing_id="...", metrics=[...], start_date="...", end_date="...")
with open("schemas/samples/chart_query.json", "w") as f:
    json.dump(response, f, indent=2)

# Capture list of metrics response
response = poller.poll_list_of_metrics(listing_id="...", metrics=[...], start_date="...", end_date="...")
with open("schemas/samples/list_of_metrics.json", "w") as f:
    json.dump(response, f, indent=2)
```

#### Step 2: Generate JSON Schemas

Use `genson` library to generate schemas from samples:

```python
# scripts/generate_schemas.py
from genson import SchemaBuilder
import json

def generate_schema(sample_file, schema_file):
    builder = SchemaBuilder()

    with open(sample_file) as f:
        sample = json.load(f)

    builder.add_object(sample)
    schema = builder.to_schema()

    with open(schema_file, "w") as f:
        json.dump(schema, f, indent=2)

generate_schema("schemas/samples/chart_query.json", "schemas/chart_query.schema.json")
generate_schema("schemas/samples/list_of_metrics.json", "schemas/list_of_metrics.schema.json")
generate_schema("schemas/samples/listings_section.json", "schemas/listings_section.schema.json")
```

#### Step 3: Add Schema Validation to Flatteners

```python
# sync_airbnb/flatteners/insights.py
import json
from jsonschema import validate, ValidationError

def load_schema(schema_name: str) -> dict:
    """Load JSON schema from file."""
    schema_path = f"schemas/{schema_name}.schema.json"
    with open(schema_path) as f:
        return json.load(f)

def flatten_chart_query(response: dict) -> list[dict]:
    """Flatten chart query response with schema validation."""
    # Validate input
    schema = load_schema("chart_query")
    try:
        validate(instance=response, schema=schema)
    except ValidationError as e:
        logger.error(f"Chart query response schema validation failed: {e}")
        raise

    # Existing flattening logic
    ...
```

### Alternative Solution

Use Pydantic models instead of JSON schemas:

```python
from pydantic import BaseModel, Field
from typing import List, Optional

class ChartQueryResponse(BaseModel):
    data: dict
    extensions: Optional[dict] = None

    class Config:
        extra = "forbid"  # Reject unknown fields

# Validate in flattener
def flatten_chart_query(response: dict) -> list[dict]:
    validated = ChartQueryResponse(**response)  # Raises ValidationError if invalid
    ...
```

### Implementation Steps

1. Install genson: `pip install genson`
2. Create `scripts/capture_api_responses.py`
3. Run script to capture real API responses
4. Create `scripts/generate_schemas.py`
5. Run script to generate schemas
6. Move schemas to `schemas/` directory
7. Add schema validation to flatteners
8. Update tests to use new schema files
9. Add schema validation to CI pipeline

### Testing Requirements

```python
def test_chart_query_response_matches_schema():
    """Test that real API response matches expected schema."""
    with open("schemas/chart_query.schema.json") as f:
        schema = json.load(f)

    # Use real response captured from API
    with open("schemas/samples/chart_query.json") as f:
        response = json.load(f)

    # Should not raise ValidationError
    validate(instance=response, schema=schema)

def test_flattener_validates_input_schema():
    """Test that flattener rejects invalid input."""
    invalid_response = {"bad": "data"}

    with pytest.raises(ValidationError):
        flatten_chart_query(invalid_response)
```

### Files to Create/Modify

- `scripts/capture_api_responses.py` (create)
- `scripts/generate_schemas.py` (create)
- `schemas/chart_query.schema.json` (regenerate)
- `schemas/list_of_metrics.schema.json` (regenerate)
- `schemas/listings_section.schema.json` (regenerate)
- `schemas/parsed_chart_query.schema.json` (regenerate)
- `schemas/parsed_chart_summary.schema.json` (regenerate)
- `schemas/parsed_list_of_metrics.schema.json` (regenerate)
- `sync_airbnb/flatteners/insights.py` (add validation)
- `sync_airbnb/flatteners/listings.py` (add validation)
- `requirements.txt` (add genson, jsonschema)

### Dependencies

- `genson` - Schema generation from JSON samples
- `jsonschema` - Schema validation

### Related Issues

- Issue 9 (per-listing error recovery)
- Issue 19 (Pydantic validation)

---

## Issue 4: Hardcoded Airbnb API Key

**Priority:** P0 - CRITICAL
**Severity:** Security vulnerability
**Impact:** API key exposed in source code, git history, Docker images
**Status:** Open
**Estimated Effort:** 30 minutes

### Current State

Airbnb API key is hardcoded in source file:

```python
# sync_airbnb/network/http_headers.py:189
def build_headers(
    airbnb_cookie: str,
    x_client_version: str,
    x_airbnb_client_trace_id: str,
    user_agent: str,
) -> dict[str, str]:
    return {
        "Cookie": airbnb_cookie,
        "X-Airbnb-API-Key": "d306zoyjsyarp7ifhu67rjxn52tv0t20",  # HARDCODED!
        "X-Client-Version": x_client_version,
        ...
    }
```

### Security Risks

1. **Source Control Exposure**: API key visible in git history
2. **Docker Image Exposure**: API key baked into Docker images
3. **Log Exposure**: May appear in debug logs
4. **Developer Exposure**: All developers have access
5. **Rotation Impossible**: Cannot rotate key without code deploy

### Recommended Solution

Move to environment variable:

```python
# sync_airbnb/network/http_headers.py
import os

def build_headers(
    airbnb_cookie: str,
    x_client_version: str,
    x_airbnb_client_trace_id: str,
    user_agent: str,
) -> dict[str, str]:
    api_key = os.getenv("AIRBNB_API_KEY")
    if not api_key:
        raise ValueError("AIRBNB_API_KEY environment variable not set")

    return {
        "Cookie": airbnb_cookie,
        "X-Airbnb-API-Key": api_key,  # From environment
        "X-Client-Version": x_client_version,
        ...
    }
```

### Implementation Steps

1. Add `AIRBNB_API_KEY` to `.env` file
2. Update `build_headers()` to read from environment
3. Update `.env.example` with placeholder
4. Update README with new environment variable
5. Test locally to ensure it works
6. Update Docker Compose to pass environment variable
7. Update Kubernetes manifests (if applicable)

### File Changes

```bash
# .env
AIRBNB_API_KEY=d306zoyjsyarp7ifhu67rjxn52tv0t20

# .env.example
AIRBNB_API_KEY=your_airbnb_api_key_here

# sync_airbnb/network/http_headers.py
# (see solution above)

# docker-compose.yml
services:
  app:
    environment:
      - AIRBNB_API_KEY=${AIRBNB_API_KEY}
```

### Testing Requirements

```python
def test_build_headers_without_api_key_raises_error():
    """Test that missing API key raises ValueError."""
    # Remove env var
    os.environ.pop("AIRBNB_API_KEY", None)

    with pytest.raises(ValueError, match="AIRBNB_API_KEY"):
        build_headers(
            airbnb_cookie="test",
            x_client_version="1.0",
            x_airbnb_client_trace_id="test",
            user_agent="test",
        )

def test_build_headers_with_api_key_includes_header():
    """Test that API key is included in headers."""
    os.environ["AIRBNB_API_KEY"] = "test-key-123"

    headers = build_headers(...)

    assert headers["X-Airbnb-API-Key"] == "test-key-123"
```

### Files to Modify

- `sync_airbnb/network/http_headers.py`
- `.env`
- `.env.example`
- `docker-compose.yml`
- `README.md`
- `tests/network/test_http_headers.py` (create)

### Dependencies

- None

### Related Issues

- Issue 5 (.env file security)
- Issue 1 (API authentication)

---

## Issue 5: .env File Security Audit

**Priority:** P0 - CRITICAL
**Severity:** Security vulnerability
**Impact:** Credentials may be exposed in git history
**Status:** Open
**Estimated Effort:** 1-2 hours

### Current State

Git status shows `.env` file with modifications:

```bash
$ git status
modified:   .env
```

This suggests `.env` may have been committed to git history at some point.

### Security Risks

1. **Credential Exposure**: Airbnb cookies, database passwords, API keys in git history
2. **Public Repository**: If repo is public, credentials are public
3. **Cloned Repositories**: All forks and clones have full git history
4. **Audit Trail**: Even after deletion, credentials remain in history

### Investigation Steps

#### Step 1: Check if .env is in Git History

```bash
# Check if .env was ever committed
git log --all --full-history -- .env

# Check current .gitignore
cat .gitignore | grep "\.env"

# Search for .env content in all commits
git log --all -p -S "AIRBNB_COOKIE" --source --all

# Check for environment variables in all commits
git grep -i "database_url" $(git rev-list --all)
```

#### Step 2: Assess Exposure

If `.env` is in history:

1. **List all exposed credentials**:
   - DATABASE_URL (username, password, host)
   - AIRBNB_COOKIE
   - X_AIRBNB_CLIENT_TRACE_ID
   - API keys
   - Any other secrets

2. **Check repository visibility**:
   ```bash
   # Is repo public?
   git remote -v
   # Check on GitHub if applicable
   ```

3. **Check for forks and clones**:
   - GitHub: Check fork count
   - Check who has access

### Remediation Steps

#### If .env is in Git History

1. **Immediately rotate ALL credentials**:
   ```bash
   # Airbnb
   - Generate new cookie (re-login)
   - Generate new trace ID

   # Database
   - Change database password
   - Update DATABASE_URL

   # API Keys
   - Rotate Airbnb API key (if possible)
   - Rotate internal API keys
   ```

2. **Remove .env from git history**:
   ```bash
   # Option A: BFG Repo-Cleaner (recommended)
   # Install: brew install bfg
   bfg --delete-files .env
   git reflog expire --expire=now --all
   git gc --prune=now --aggressive

   # Option B: git-filter-branch (slower)
   git filter-branch --force --index-filter \
     "git rm --cached --ignore-unmatch .env" \
     --prune-empty --tag-name-filter cat -- --all
   ```

3. **Force push to all remotes**:
   ```bash
   git push --force --all
   git push --force --tags

   # Warn all collaborators to re-clone
   ```

4. **Verify .gitignore**:
   ```bash
   # Ensure .env is ignored
   echo ".env" >> .gitignore
   git add .gitignore
   git commit -m "Ensure .env is in .gitignore"
   ```

5. **Create .env.example template**:
   ```bash
   # .env.example (no real secrets)
   DATABASE_URL=postgresql://user:password@localhost:5432/dbname
   MODE=hybrid
   ACCOUNT_ID=your_account_id
   AIRBNB_COOKIE=your_cookie_here
   X_AIRBNB_CLIENT_TRACE_ID=your_trace_id
   X_CLIENT_VERSION=your_client_version
   USER_AGENT=your_user_agent
   LOG_LEVEL=INFO
   DEBUG=false
   AIRBNB_API_KEY=your_api_key_here
   API_KEY=your_internal_api_key
   ```

6. **Document the incident**:
   - When credentials were exposed
   - Which credentials were rotated
   - Actions taken to remediate

#### If .env is NOT in Git History

1. **Verify .gitignore is correct**:
   ```bash
   cat .gitignore | grep "\.env"
   # Should output: .env
   ```

2. **Ensure .env is never committed**:
   ```bash
   # Add to .gitignore if missing
   echo ".env" >> .gitignore

   # Remove from staging if present
   git rm --cached .env

   # Commit .gitignore update
   git add .gitignore
   git commit -m "Ensure .env is ignored"
   ```

3. **Create .env.example** (as above)

### Prevention Measures

1. **Pre-commit hooks**:
   ```bash
   # Install pre-commit
   pip install pre-commit

   # .pre-commit-config.yaml
   repos:
     - repo: https://github.com/pre-commit/pre-commit-hooks
       rev: v4.4.0
       hooks:
         - id: detect-private-key
         - id: check-added-large-files
         - id: check-merge-conflict
     - repo: https://github.com/Yelp/detect-secrets
       rev: v1.4.0
       hooks:
         - id: detect-secrets

   # Install hooks
   pre-commit install
   ```

2. **Secret scanning in CI**:
   ```yaml
   # .github/workflows/security.yml
   name: Secret Scanning
   on: [push, pull_request]
   jobs:
     scan:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v3
         - uses: trufflesecurity/trufflehog@main
           with:
             path: ./
             base: ${{ github.event.repository.default_branch }}
             head: HEAD
   ```

3. **Regular audits**:
   ```bash
   # Monthly audit script
   git log --all --full-history -- .env
   git log --all -p -S "password" --all
   ```

### Testing Requirements

After remediation:

```bash
# Verify .env not in history
git log --all --full-history -- .env
# Should return nothing

# Verify .env ignored
git check-ignore .env
# Should output: .env

# Verify .env.example exists
ls -la .env.example
# Should exist

# Try to commit .env (should fail)
git add .env
# Should warn "file is ignored by .gitignore"
```

### Files to Create/Modify

- `.gitignore` (ensure .env is present)
- `.env.example` (create template)
- `.pre-commit-config.yaml` (create)
- `docs/security-incident-response.md` (document process)

### Dependencies

- `pre-commit` (optional but recommended)
- `detect-secrets` (optional but recommended)
- `bfg` or `git-filter-branch` (if history needs cleaning)

### Related Issues

- Issue 4 (hardcoded API key)
- Issue 1 (API authentication)

---

## Summary

These 5 P0 issues represent critical blockers for production deployment. They expose the system to security vulnerabilities, prevent quality assurance, and risk data corruption.

**Priority Order:**
1. Issue 5 - .env security audit (IMMEDIATE - potential active exposure)
2. Issue 4 - Hardcoded API key (30 minutes - quick win)
3. Issue 2 - Failing tests (2-4 hours - enables QA)
4. Issue 1 - API authentication (4-8 hours - security essential)
5. Issue 3 - JSON schemas (4-6 hours - data quality)

**Total Effort:** 10-18 hours (~2-3 days for one developer)

**Blocking:** All P1/P2/P3 issues should wait until these are resolved.
