# Task: API Authentication

**Priority:** P0 - CRITICAL (Blocking Production)
**Estimated Effort:** 4-8 hours
**Status:** Not Started

---

## Problem

All API endpoints are completely open with zero authentication. Anyone can:
- Create/delete accounts (including credentials)
- Trigger expensive sync operations (DoS vector)
- Access all metrics data
- List all accounts with sensitive data

---

## Solution

Implement API key authentication using FastAPI's security utilities.

### Implementation Steps

1. **Create security module** (`sync_airbnb/api/security.py`):
   ```python
   from fastapi import Security, HTTPException, status
   from fastapi.security.api_key import APIKeyHeader
   import os

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
   ```

2. **Apply to all routes** (except `/health`):
   ```python
   @router.post("/accounts", dependencies=[Security(verify_api_key)])
   async def create_account(account: AccountCreate):
       ...
   ```

3. **Add to environment**:
   - Add `API_KEY` to `.env`
   - Add `API_KEY=your_api_key_here` to `.env.example`
   - Update `docker-compose.yml` to pass `API_KEY` env var

4. **Update documentation**:
   - Add authentication section to README.md
   - Update OpenAPI docs to show API key requirement
   - Document in all endpoint descriptions

5. **Write tests** (`tests/api/test_authentication.py`):
   - Test without API key (should 403)
   - Test with invalid API key (should 403)
   - Test with valid API key (should succeed)
   - Test health check works without API key

---

## Files to Create/Modify

- `sync_airbnb/api/security.py` (create)
- `sync_airbnb/api/routes/accounts.py` (add Security dependency)
- `sync_airbnb/api/routes/metrics.py` (add Security dependency)
- `.env` (add API_KEY)
- `.env.example` (add API_KEY placeholder)
- `docker-compose.yml` (add API_KEY env var)
- `README.md` (document authentication)
- `tests/api/test_authentication.py` (create)

---

## Acceptance Criteria

- [ ] All endpoints except `/health` require API key
- [ ] Invalid/missing API key returns 403 Forbidden
- [ ] Valid API key allows access
- [ ] API key stored in environment variable
- [ ] Tests pass for all auth scenarios
- [ ] Documentation updated
- [ ] OpenAPI docs show security requirement

---

## Notes

- Keep health check public (no auth) for load balancer health checks
- Use `X-API-Key` header (standard convention)
- Generate strong random API keys (64+ characters)
- Consider rotating API keys periodically
- For future: consider OAuth2 for user-facing features
