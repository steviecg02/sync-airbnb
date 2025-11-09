# Cookie and Session Management Strategy

**Priority:** P0 - Critical (Blocks production viability)
**Status:** Phase 1 complete, monitoring in progress
**Last Updated:** November 9, 2025
**Owner:** Core infrastructure - must be solved before scaling

---

## Executive Summary

**The Problem:** Airbnb authentication cookies expire every 2 days, requiring manual credential refresh. This breaks the automated polling system and makes the service non-viable for customers.

**Root Cause (Current Hypothesis):** Replaying stale Akamai Bot Manager cookies (`ak_bmsc`, `bm_sv`) triggers anti-bot detection. These tokens are embedded in the full cookie string and expire based on behavioral patterns, not time.

**The Solution:** Multi-phase approach to test and implement solutions incrementally:
1. **Backend improvements** (preflight pattern + TLS fingerprinting) - Test first
2. **Chrome extension** (if backend alone doesn't solve it) - Automatic cookie refresh
3. **Multi-tenant architecture** (once cookies are stable) - Multiple accounts per service
4. **Kubernetes operator** (conditional) - Only if IP-per-account isolation needed

**Current Status:** Phase 1 implementation complete (November 9, 2025):
- ✅ Deployed on home IP (same as cookie source) - October 22, 2025
- ✅ Reduced request volume by 93% (incremental sync) - October 27, 2025
- ✅ Implemented rate limiting (5-10s between requests, 15-30s between listings) - October 27, 2025
- ✅ Implemented TLS fingerprinting via curl_cffi - November 9, 2025
- ✅ Implemented preflight pattern (fresh Akamai cookies before each sync) - November 9, 2025
- ✅ Fixed cookie parsing to use curl_cffi's get_list() method - November 9, 2025
- ✅ Successfully extracting 1-2 fresh Akamai cookies per preflight - November 9, 2025
- ✅ API calls succeeding with merged auth + Akamai cookies - November 9, 2025
- ⏳ **Monitoring cookie lifetime - need 7+ days to confirm success**

---

## Table of Contents

1. [Problem Statement](#problem-statement)
2. [Research Findings](#research-findings)
3. [Competitor Analysis](#competitor-analysis)
4. [Current Implementation](#current-implementation)
5. [Proposed Solutions](#proposed-solutions)
6. [Phased Implementation Plan](#phased-implementation-plan)
7. [Architecture Decisions](#architecture-decisions)
8. [Rate Limiting Strategy](#rate-limiting-strategy)
9. [Kubernetes Operator (Conditional)](#kubernetes-operator-conditional)
10. [Decision Log](#decision-log)

---

## Problem Statement

### Symptom
Airbnb authentication cookies expire every 1-2 days when running automated polling, requiring manual credential refresh via DevTools and `.env` file update.

### Impact
- **User Experience:** Manual cookie refresh every 2 days is unacceptable for production SaaS
- **Competitor Benchmark:** RankBreeze/IntelliHost users refresh "once or twice a year" via Chrome extension
- **Business Viability:** Cannot scale to multiple customers without solving this

### Unknown Variables
1. **Is IP address tied to cookie?** (Testing in progress on home IP)
2. **Is request volume the trigger?** (Reduced by 93%, still expires)
3. **Is TLS fingerprint the issue?** (Python `requests` vs Chrome browser)
4. **Are Akamai tokens the culprit?** (Most likely based on research)

### What We Know
- ✅ Same IP deployment (Nook at home) did NOT solve the issue
- ✅ Reduced request volume (93% reduction) did NOT solve the issue
- ✅ Rate limiting (5-10s delays) did NOT solve the issue
- ✅ Cookie has 9-month timestamp (`bev=1754402040` = August 2025) but still dies in 2 days
- ✅ Cookie contains Akamai Bot Manager tokens: `ak_bmsc`, `bm_sv`

---

## Research Findings

### ChatGPT Analysis of RankBreeze Extension

**Key Discovery:** RankBreeze Chrome extension (ID: `plkdnpjpnhhnmigmekaocdfokkmebdnm`) actively collects cookies from browser and POSTs them to backend server.

#### Extension Behavior (Confirmed via Code Analysis)

**From `backgroundIntegration.js`:**
```javascript
// Extension collects cookies when user clicks button on Airbnb page
fetch(`${API_URL}/api/v1/airbnb/cookies_update`, {
  method: 'POST',
  headers: {
    'Accept': 'application/json, text/plain, */*',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    user_id: userId,
    cookies: cookies,  // Array of {domain, cookie} objects
    user_agent: userAgent,
    activate: true
  })
})
```

**Trigger Mechanism:**
- **User-initiated:** Button click on Airbnb pages (NOT automatic `chrome.cookies.onChanged`)
- **On-demand:** When user visits `airbnb/connect` or `airbnb/index` pages
- **Manual but convenient:** User clicks extension button occasionally, not daily

**Post-Upload Behavior:**
```javascript
.then(res => {
  if (typeof res.accounts !== 'undefined') {
    // Extension DELETES local cookies after successful upload
    cookieDomains.forEach(function (domain) {
      removeCookiesForDomain(domain);
    });
  }
})
```

**Implications:**
- Backend stores cookies for server-side polling
- Users don't need to manually copy cookies from DevTools
- Refresh frequency determined by user's natural Airbnb visits (weeks/months)
- Extension removes local cookies after upload (security/hygiene)

---

### ChatGPT's Backend Speculation (Unconfirmed)

**ChatGPT suggested RankBreeze backend likely does:**

1. **Store minimal auth cookies only:**
   - `_airbed_session_id` - Core session identifier
   - `_aaj` - Short-lived JWT-like token
   - `_aat` - Additional auth token
   - `auth_jitney_session_id` - Jitney session (Airbnb's auth service)
   - Optionally: `hli`, `li`, `sticky_locale`, `country`, `_user_attributes`

2. **DO NOT store Akamai/analytics cookies:**
   - `bm_sv` - Bot Manager Sensor Value (expires quickly)
   - `ak_bmsc` - Akamai Bot Manager Session Cookie (expires quickly)
   - `muxData`, `_ga*`, `_gcl_*`, etc. - Analytics tracking

3. **Preflight pattern before each GraphQL request:**
   ```
   Before GraphQL call:
   1. GET https://www.airbnb.com/hosting/performance
      - Use stored User-Agent
      - NO old Akamai cookies
   2. Parse Set-Cookie headers from response
      - Extract fresh ak_bmsc, bm_sv
   3. Merge cookies:
      - Fresh Akamai cookies (from preflight)
      + Stored auth cookies (from database)
   4. Use merged cookie set for GraphQL request
   ```

4. **CSRF token management:**
   - Extract from preflight response (meta tag or response header)
   - Use for GraphQL requests

**Important Note:** This is ChatGPT's educated guess based on extension code analysis. We don't have direct evidence RankBreeze does preflight requests. However, the logic is sound:
- Explains why static cookies fail (stale Akamai tokens)
- Explains why their backend polling works (fresh Akamai tokens each run)
- Matches Akamai Bot Manager's known behavior

---

### Cookie Anatomy Analysis

**User provided two cookie snapshots:**

**Day 0 (initial capture):**
```
bev=1754402040_EANGVmYTkzYzA5Nz;
everest_cookie=1754402040.EANWY1NWZjNmUyYTFmMD.15kZ5SEgmga3lliLvendBaEoDkGfzm-Ef9ve4am73bk;
_airbed_session_id=039a37daa629fd0fc4c500c9d0a57388;
auth_jitney_session_id=d08859e4-cf64-4903-9211-2bbc51d6716f;
_aaj=28|2|soP8nEunkUIGTjHJWGrXMC8%2Baxi9n2c%2FW7pO5Y6gIXmGuCPenBPB8l9F6apNz95pGEER...;
_aat=0|CpWL4%2BsM%2FZF0DETjFxQ%2BhzY%2Bdn6hihRZDNVtT%2Fw%2F6zZ0uEkz...;
ak_bmsc=C2DCDA0B4BE3D3E8F826049147C74C60~000000000000000000000000000000~YAAQhcgwFys4bhuaAQAAZ9cyPx3u8CXzTkSqsaBJM4Ul5kGi4oR06tke+BT9Zz89nXHN...;
bm_sv=23F9E3FCC655006081ED5552A6B1F648~YAAQqyQPFw5gOzCaAQAAnDuBPx1hKjKnjLM+JNhviP2xDvpvVZp0k/HaiVcqTAAwWYinmhVuA1tt/vIYwVbTyjzimar4gywrmEOGCtyPrdVCqeK1LFkZc+ox1bhvRfYsngCuH6FchRlMoC7HOe5vaX+muq3xfzcyajo6Nx4PiNoHh2JjmGZpkv7PsZ9PQCg5f4auN7O8hQkXC4KmkiL6bcaJfniEotS1JYkpEIr2jNWBLwTK/uo5F0hUgX1e3d1ZqA==~1;
(+ many analytics cookies: _ga, _gcl_au, muxData, etc.)
```

**Day 1 (before expiry):**
- `ak_bmsc` changed: `55EBAA50F53308C643220E422C807E6A~...` (different hash)
- `bm_sv` changed: `CD5AE699543C1783887C6C46FA523C93~...` (different hash)
- `_aaj` changed: `28|2|eaZuDhrE76k1A%2FO7nvcE2DhCeGttxflw5OjokygeNYiCMkGpV9T%2By1E21zw%2BfDTbRsWHlN1Xc8Dr9O5pWc%2FFC9wLkML9%2FFxotVg12vrF5FkIt6lu3FNKFgaiXuohMwGW...` (rotated token)
- `tzo` changed: `-240` → `-300` (timezone, harmless)
- `jitney_client_session_id` changed (ephemeral session tracking)

**Analysis:**
- **Auth cookies** (`_airbed_session_id`, `_aat`, `auth_jitney_session_id`): Relatively stable
- **Rotating tokens** (`_aaj`): Change frequently (hours/days)
- **Akamai cookies** (`ak_bmsc`, `bm_sv`): Change every page load
- **Analytics cookies**: Constant churn, not needed for auth

**Conclusion:** Replaying the entire Day 0 cookie blob on Day 1+ means:
- Stale `ak_bmsc` and `bm_sv` (mismatched with server expectations)
- Possibly stale `_aaj` (if it rotated)
- Creates fingerprint mismatch → bot detection → session invalidation

---

## Competitor Analysis

### RankBreeze/IntelliHost User Experience

**Observed Behavior:**
- Users install Chrome extension
- Click "Connect" button occasionally when visiting Airbnb
- Credentials refresh automatically in background
- Users rarely prompted to re-authenticate (once or twice a year)

**How They Achieve This:**

1. **Chrome Extension** - Extracts cookies from user's active browser session
2. **Backend Storage** - Stores auth cookies (not Akamai tokens)
3. **Server-Side Polling** - Backend makes GraphQL requests using stored cookies
4. **Automatic Refresh** - When user visits Airbnb naturally, extension sends fresh cookies
5. **Graceful Degradation** - On 401/403, backend can retry with preflight or request fresh upload

**Key Insight:** They're NOT polling from the user's browser. They're:
- Extracting credentials from browser → Sending to backend → Backend does all polling
- This means IP address doesn't need to match (their backend likely uses different IPs)
- Fresh cookies matter more than IP consistency

---

## Current Implementation

### Cookie Management
**Current approach:**
1. User manually extracts cookie from Chrome DevTools
2. Paste entire cookie blob into `.env` file
3. Service uses same cookie blob for all requests
4. Cookie expires after 2 days
5. Repeat step 1-3

**Problems:**
- Manual process every 2 days
- Replays stale Akamai tokens
- No automatic refresh mechanism

### Request Pattern (After Oct 27, 2025 Improvements)

**Current rate limiting:**
- 5-10 seconds between API requests (mimics human clicking)
- 15-30 seconds between listings (mimics human navigation)
- Sequential processing (no concurrency)

**Request volume (per sync):**
- **First run:** 128 requests per listing (25 weeks back + 25 weeks forward)
- **Incremental:** 66 requests per listing (1 week back + 25 weeks forward)
- **7 listings:** 462 requests per day (incremental)

**Timing:**
- 7 listings: ~60 minutes per sync
- 50 listings: ~6.9 hours per sync
- 1,000 listings: ~5.7 days per sync (not viable)

### API Calls Made
```python
# ChartQuery (28-day windows)
("CONVERSION", ["conversion_rate"])
("CONVERSION", ["p3_impressions"])

# ListOfMetricsQuery (7-day windows)
("CONVERSION", ["conversion_rate"])
("CONVERSION", ["p3_impressions"])
```

### Headers Sent
**From `sync_airbnb/network/http_headers.py`:**
```python
{
    # Session + Auth
    "Cookie": airbnb_cookie,  # Full cookie blob including Akamai
    "X-Airbnb-API-Key": airbnb_api_key,
    "X-CSRF-Token": "",
    "X-CSRF-Without-Token": "1",

    # Client Context
    "X-Client-Version": x_client_version,
    "X-Client-Request-Id": "manual-dev",
    "X-Airbnb-Client-Trace-Id": x_airbnb_client_trace_id,
    "User-Agent": user_agent,

    # Internal Feature Flags
    "X-Airbnb-GraphQL-Platform": "web",
    "X-Airbnb-GraphQL-Platform-Client": "minimalist-niobe",
    "X-Airbnb-Supports-Airlock-V2": "true",
    "X-Niobe-Short-Circuited": "true",

    # Standard HTTP headers
    "Accept": "*/*",
    "Content-Type": "application/json",
}
```

**Missing browser headers:**
- `Origin: https://www.airbnb.com`
- `Referer: https://www.airbnb.com/hosting/performance`
- `Sec-Fetch-Site: same-origin`
- `Sec-Fetch-Mode: cors`
- `Sec-Fetch-Dest: empty`
- `Accept-Language: en-US,en;q=0.9`
- `Accept-Encoding: gzip, deflate, br`

### HTTP Client
**Current:** Python `requests` library
- Different TLS fingerprint than Chrome
- Missing browser-specific handshake details
- Potentially detectable by Akamai

**Location:** `sync_airbnb/network/http_client.py`

---

## Proposed Solutions

### Solution 1: Preflight Pattern (Backend Improvement)

**What:** Before each sync, make GET request to Airbnb to obtain fresh Akamai cookies, then merge with stored auth cookies.

**Implementation:**
```python
# Before sync run in services/insights.py
def get_fresh_akamai_cookies(user_agent: str) -> dict[str, str]:
    """
    Preflight request to get fresh Akamai bot manager cookies.
    """
    response = requests.get(
        "https://www.airbnb.com/hosting/performance",
        headers={"User-Agent": user_agent},
        allow_redirects=True
    )

    # Parse Set-Cookie headers
    akamai_cookies = {}
    for cookie in response.cookies:
        if cookie.name in ['ak_bmsc', 'bm_sv', 'bm_sz']:
            akamai_cookies[cookie.name] = cookie.value

    return akamai_cookies

def merge_cookies(auth_cookies: dict, akamai_cookies: dict) -> str:
    """
    Merge auth cookies from database with fresh Akamai cookies.
    """
    merged = {**auth_cookies, **akamai_cookies}
    return "; ".join(f"{k}={v}" for k, v in merged.items())

# In run_insights_poller()
akamai = get_fresh_akamai_cookies(account.user_agent)
auth_cookies = parse_stored_cookies(account.airbnb_cookie)  # Extract only auth cookies
merged_cookie = merge_cookies(auth_cookies, akamai)
headers = build_headers(airbnb_cookie=merged_cookie, ...)
```

**Pros:**
- Relatively simple implementation
- Addresses stale Akamai token issue directly
- No user interaction required
- Can test immediately (2-3 days for results)

**Cons:**
- Adds one extra HTTP request per sync
- Assumes preflight is what RankBreeze does (unconfirmed)
- Requires parsing cookie string into key/value pairs

**Test Criteria:**
- Deploy with preflight pattern
- Monitor cookie lifetime
- Success = cookie lasts >7 days

**Effort:** 4-6 hours

---

### Solution 2: TLS Fingerprinting (curl_cffi)

**What:** Replace Python `requests` library with `curl_cffi` which mimics Chrome's exact TLS handshake.

**Implementation:**
```python
# sync_airbnb/network/http_client.py
# Change this:
import requests

# To this:
from curl_cffi import requests

# That's it - drop-in replacement
```

**Why:** Python `requests` uses different TLS fingerprint than browsers:
- Different cipher suites
- Different TLS extension order
- Different ALPN negotiation
- Akamai can detect this mismatch

**Pros:**
- Extremely simple (one line change)
- Low risk
- Can test immediately with preflight pattern
- `curl_cffi` mimics Chrome exactly

**Cons:**
- New dependency (`pip install curl-cffi`)
- Might not solve the issue if problem is elsewhere

**Test Criteria:**
- Install `curl_cffi`
- Replace import
- Deploy
- Monitor cookie lifetime

**Effort:** 30 minutes

---

### Solution 3: Add Missing Browser Headers

**What:** Add standard browser headers that are currently missing.

**Implementation:**
```python
# sync_airbnb/network/http_headers.py
def build_headers(...):
    return {
        # ... existing headers ...

        # Add these:
        "Origin": "https://www.airbnb.com",
        "Referer": "https://www.airbnb.com/hosting/performance",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
    }
```

**Pros:**
- Simple addition
- Likely helpful regardless
- Makes requests more browser-like

**Cons:**
- If missing headers were the issue, requests would fail immediately (not after 2 days)
- Probably not the root cause

**Test Criteria:**
- Add headers
- Deploy
- Monitor cookie lifetime

**Effort:** 1 hour

---

### Solution 4: Chrome Extension (Cookie Auto-Refresh)

**What:** Build Chrome extension that automatically sends fresh cookies to backend when user visits Airbnb.

**Components:**

1. **Chrome Extension (Manifest V3)**
   ```json
   {
     "manifest_version": 3,
     "name": "Airbnb Sync - Cookie Connector",
     "version": "1.0.0",
     "permissions": ["cookies", "storage"],
     "host_permissions": ["https://*.airbnb.com/*"],
     "background": {
       "service_worker": "background.js"
     },
     "content_scripts": [{
       "matches": ["https://www.airbnb.com/hosting/*"],
       "js": ["content.js"]
     }]
   }
   ```

2. **Background Service Worker**
   ```javascript
   // background.js
   chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
     if (request.action === "send_cookies") {
       collectAndSendCookies(request.accountId);
     }
   });

   async function collectAndSendCookies(accountId) {
     // Get Airbnb cookies
     const cookies = await chrome.cookies.getAll({
       domain: ".airbnb.com"
     });

     // Filter to auth cookies only
     const authCookies = cookies.filter(c =>
       ['_airbed_session_id', '_aaj', '_aat',
        'auth_jitney_session_id', 'hli', 'li'].includes(c.name)
     );

     // Send to backend
     await fetch(`https://api.yourdomain.com/api/v1/accounts/${accountId}/cookies`, {
       method: 'POST',
       headers: {'Content-Type': 'application/json'},
       body: JSON.stringify({
         cookies: authCookies,
         user_agent: navigator.userAgent
       })
     });
   }
   ```

3. **Content Script (Inject Button)**
   ```javascript
   // content.js - Runs on Airbnb pages
   const button = document.createElement('button');
   button.textContent = 'Sync Credentials';
   button.onclick = () => {
     chrome.runtime.sendMessage({
       action: 'send_cookies',
       accountId: getUserAccountId() // From extension storage
     });
   };
   document.body.appendChild(button);
   ```

4. **Backend API Endpoint**
   ```python
   # sync_airbnb/api/routes/accounts.py
   @router.post(
       "/{account_id}/cookies",
       summary="Update account cookies from Chrome extension"
   )
   async def update_cookies_from_extension(
       account_id: str,
       cookies: CookieUpdate = Body(...),
       engine: Engine = Depends(get_db_engine)
   ):
       """
       Accept cookie update from Chrome extension.
       Store only auth cookies (not Akamai/analytics).
       """
       # Parse cookies array
       auth_cookies = {
           '_airbed_session_id': None,
           '_aaj': None,
           '_aat': None,
           'auth_jitney_session_id': None,
       }

       for cookie in cookies.cookies:
           if cookie.name in auth_cookies:
               auth_cookies[cookie.name] = cookie.value

       # Build cookie string (only auth cookies)
       cookie_string = "; ".join(
           f"{k}={v}" for k, v in auth_cookies.items() if v
       )

       # Update account
       update_account_credentials(
           engine,
           account_id,
           airbnb_cookie=cookie_string,
           user_agent=cookies.user_agent
       )

       return {"status": "updated", "account_id": account_id}
   ```

**Pros:**
- Matches RankBreeze/IntelliHost approach
- Users refresh naturally (when they visit Airbnb)
- No manual DevTools copying
- Automatic credential refresh

**Cons:**
- Significant development effort
- Requires Chrome Web Store submission (review process)
- Users must install extension
- More complex deployment

**Test Criteria:**
- User installs extension
- Clicks "Sync Credentials" button on Airbnb page
- Backend receives and stores auth cookies only
- Cookies last weeks/months

**Effort:** 16-24 hours (extension + backend API + testing)

---

### Solution 5: Cookie Parsing & Storage

**What:** Change how cookies are stored - parse into key/value pairs, store only auth cookies.

**Current:**
```python
# accounts table
airbnb_cookie = "full_cookie_blob_including_akamai_and_analytics..."
```

**Proposed:**
```python
# Store structured cookies
{
  "_airbed_session_id": "039a37daa629fd0fc4c500c9d0a57388",
  "_aaj": "28|2|soP8nEunkUIGTjHJWGrXMC8...",
  "_aat": "0|CpWL4%2BsM%2FZF0DETjFxQ%2BhzY...",
  "auth_jitney_session_id": "d08859e4-cf64-4903-9211-2bbc51d6716f"
}
```

**Implementation:**
- Add JSON column to accounts table: `auth_cookies_json`
- Helper function to parse cookie string
- Helper function to rebuild cookie string (merge with fresh Akamai)

**Pros:**
- Clean separation of auth vs ephemeral cookies
- Enables preflight pattern
- Better for debugging (see which cookies are stored)

**Cons:**
- Database schema change
- Migration required
- Breaking change for existing deployments

**Test Criteria:**
- Parse existing cookie strings
- Store auth cookies as JSON
- Reconstruct cookie string with preflight Akamai cookies
- Verify GraphQL requests succeed

**Effort:** 6-8 hours (including migration)

---

## Phased Implementation Plan

### Phase 1: Backend Improvements ✅ COMPLETE

**Goal:** Test if preflight + TLS fingerprinting solve cookie expiry without Chrome extension.

**Tasks:**
1. ✅ Install `curl_cffi`: `pip install curl-cffi`
2. ✅ Replace `import requests` with `from curl_cffi import requests` in `http_client.py`
3. ✅ Implement preflight function to get fresh Akamai cookies
4. ✅ Implement cookie parsing/merging logic
5. ✅ Add missing browser headers (Origin, Referer, Sec-Fetch-*)
6. ✅ Deploy to Nook (hybrid mode)
7. ✅ Fix cookie parsing bug (curl_cffi Headers.get_list() method)
8. ⏳ Monitor cookie lifetime for 1-2 weeks

**Implementation Details:**
- Created `sync_airbnb/network/preflight.py` with preflight request logic
- Created `sync_airbnb/utils/cookie_utils.py` for cookie parsing/merging
- Modified `sync_airbnb/services/insights.py` to call preflight before sync
- Added comprehensive logging to track cookie extraction and merging
- Fixed `parse_set_cookie_headers()` to properly use curl_cffi's `get_list()` method

**Current Results (November 9, 2025):**
- ✅ Preflight successfully extracting 1-2 Akamai cookies (`bm_sv`, occasionally `ak_bmsc`)
- ✅ Cookie merging working (9 auth cookies + 1 Akamai = 10 total)
- ✅ GraphQL API calls succeeding with merged cookies
- ✅ No auth errors observed in initial testing
- ⏳ Need 7+ days of monitoring to confirm cookie longevity

**Success Criteria:**
- Cookie lasts >7 days ⏳ Pending
- No 401/403 errors ✅ So far
- GraphQL requests succeed ✅ Yes
- Daily syncs complete successfully ✅ Yes

**Failure Criteria:**
- Cookie still expires in 2 days
- → Proceed to Phase 2 (Chrome extension)

**Actual Effort:** ~12 hours
**Timeline:** November 7-9, 2025

---

### Phase 2: Chrome Extension (IF PHASE 1 FAILS)

**Goal:** Build Chrome extension for automatic cookie refresh, matching RankBreeze approach.

**Tasks:**
1. Create extension manifest (Manifest V3)
2. Build background service worker (cookie collection)
3. Build content script (inject button on Airbnb pages)
4. Add backend API endpoint: `POST /accounts/{id}/cookies`
5. Implement cookie parsing and storage (auth cookies only)
6. Test locally with extension
7. Submit to Chrome Web Store
8. Document installation process for users

**Success Criteria:**
- Extension successfully extracts auth cookies
- Backend receives and stores cookies
- Users can click button to refresh
- Cookies persist weeks/months

**Effort:** 16-24 hours
**Timeline:** TBD (only if Phase 1 fails)

---

### Phase 3: Multi-Tenant Architecture (ONCE COOKIES ARE STABLE)

**Goal:** Support multiple accounts in single service deployment.

**Current State:**
- Service requires `ACCOUNT_ID` environment variable
- Scheduler runs for single account only
- Three modes: `admin`, `worker`, `hybrid`

**Proposed State:**
- Remove `ACCOUNT_ID` requirement
- Remove mode concept (single service does both)
- Scheduler iterates ALL active accounts
- API endpoints already support multi-account

**Tasks:**
1. Remove `ACCOUNT_ID` from required config
2. Update scheduler to query all active accounts
3. Remove mode switching logic
4. Update `services/scheduler.py` to loop through accounts
5. Add account-level rate limiting (prevent one account from blocking others)
6. Test with 2-3 accounts

**Success Criteria:**
- Service starts without `ACCOUNT_ID`
- Scheduler syncs all active accounts
- Each account runs independently
- Errors in one account don't affect others

**Effort:** 8-12 hours
**Timeline:** After Phase 1 or Phase 2 succeeds

---

### Phase 4: Rate Limiting Optimization (AS NEEDED FOR SCALE)

**Goal:** Improve sync performance for accounts with many listings (50-1,000+).

**Current Performance:**
- 7 listings: ~60 minutes (acceptable)
- 50 listings: ~6.9 hours (borderline)
- 1,000 listings: ~5.7 days (not viable)

**Options:**

**Option A: Keep Sequential (Current)**
- Works for small accounts (<20 listings)
- Safe, mimics single user
- No changes needed

**Option B: Limited Concurrency (Recommended for 50-200 listings)**
- Process N listings concurrently (N=5-10)
- Each listing still sequential (requests within listing)
- Mimics "multiple browser tabs" pattern
- Expected timing for 1,000 listings: ~14 hours

**Implementation:**
```python
# services/insights.py
import asyncio
from concurrent.futures import ThreadPoolExecutor

async def run_insights_poller_concurrent(
    account: Account,
    max_concurrent: int = 5
):
    listings = fetch_listing_ids()

    # Process listings in batches
    with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
        futures = []
        for listing_id in listings:
            future = executor.submit(
                process_single_listing,
                account, listing_id
            )
            futures.append(future)

            # Delay between starting listings
            await asyncio.sleep(random.uniform(15, 30))

        # Wait for all to complete
        for future in futures:
            future.result()
```

**Option C: Adaptive Concurrency**
- Start with N=1 (sequential)
- If no errors for 10 listings, increase to N=5
- If errors occur, decrease to N=1
- Auto-tune based on account size and error rate

**When to implement:**
- Only if Phase 3 (multi-tenant) is successful
- Only if customers have >50 listings
- Can be deployed incrementally per account

**Effort:** 12-16 hours
**Timeline:** TBD based on customer needs

---

### Phase 5: Kubernetes Operator (CONDITIONAL - ONLY IF NEEDED)

**Condition:** Only implement if:
1. IP-per-account isolation is required (evidence suggests it's NOT)
2. OR need strict resource isolation per account
3. OR pod-per-account deployment model is preferred for other reasons

**Current Assessment:** Likely NOT needed because:
- RankBreeze polls from their backend servers (different IPs than cookie source)
- Evidence suggests IP matching doesn't matter
- Multi-tenant service can handle multiple accounts efficiently

**If needed, see:** [Kubernetes Operator Details](#kubernetes-operator-conditional)

---

## Architecture Decisions

### Decision 1: Store Auth Cookies Only

**Decision:** Store parsed auth cookies separately from ephemeral Akamai/analytics cookies.

**Rationale:**
- Akamai tokens expire quickly and should not be persisted
- Auth cookies are the persistent credentials
- Enables preflight pattern (merge fresh Akamai + stored auth)
- Reduces storage size (80% of cookie blob is analytics junk)

**Implementation:**
- Add `auth_cookies_json` column to accounts table (JSONB)
- Store only: `_airbed_session_id`, `_aaj`, `_aat`, `auth_jitney_session_id`, `hli`, `li`
- Keep `airbnb_cookie` column for backward compatibility (can deprecate later)

**Migration Path:**
1. Add new column
2. Parse existing cookies and populate new column
3. Update code to use new column
4. After validation period, drop old column

---

### Decision 2: Preflight Before Each Sync (Not Every Request)

**Decision:** Run preflight GET request once per sync (not before every GraphQL request).

**Rationale:**
- Akamai cookies are valid for ~1 hour (estimated)
- One sync = 60-120 minutes with current rate limiting
- Single preflight per sync is sufficient
- Reduces HTTP request overhead

**Implementation:**
```python
# services/insights.py
def run_insights_poller(account: Account, ...):
    # Preflight ONCE at start of sync
    akamai_cookies = get_fresh_akamai_cookies(account.user_agent)
    auth_cookies = json.loads(account.auth_cookies_json)
    merged_cookie = merge_cookies(auth_cookies, akamai_cookies)

    headers = build_headers(airbnb_cookie=merged_cookie, ...)

    # Use same headers for all requests in this sync
    poller = AirbnbSync(headers=headers, ...)
    ...
```

**Future Optimization:**
If Akamai cookies expire mid-sync (detected via 403 response):
- Retry with fresh preflight
- Update merged cookie
- Continue sync

---

### Decision 3: Modes Removal Depends on Cookie Solution

**Conditional Decision:**

**If Phase 1 succeeds (backend fixes work):**
- ✅ Remove modes (`admin`, `worker`, `hybrid`)
- ✅ Single service handles both API and scheduling
- ✅ Implement multi-tenant (all accounts in one service)
- ❌ No Kubernetes operator needed

**If Phase 2 needed (Chrome extension required):**
- ⚠️ Keep modes temporarily
- ⚠️ Assess if IP-per-account matters after extension testing
- ⏸️ Decide on multi-tenant vs operator after data collection

**Rationale:**
- Don't remove modes until we know cookies work long-term
- If extension is needed, re-evaluate architecture
- Current hybrid mode works for testing both approaches

---

### Decision 4: TLS Fingerprinting via curl_cffi

**Decision:** Use `curl_cffi` instead of native `requests` library.

**Rationale:**
- Python `requests` has different TLS fingerprint than Chrome
- Akamai likely fingerprints TLS handshake
- `curl_cffi` is drop-in replacement that mimics Chrome exactly
- Low risk, high potential benefit

**Implementation:**
```python
# requirements.txt
curl-cffi>=0.6.0

# sync_airbnb/network/http_client.py
# from curl_cffi import requests  # Impersonate Chrome
from curl_cffi import requests

# Optional: Specify Chrome version
res = requests.post(url, json=json, headers=headers, impersonate="chrome110")
```

**Fallback:**
If `curl_cffi` causes issues, can easily revert to native `requests`.

---

## Rate Limiting Strategy

### Current Implementation (October 27, 2025)

**Pattern:** Single user, single browser tab (most conservative)

**Timing:**
- **Inter-request delay:** 5-10 seconds (mimics human clicking through UI)
- **Between-listing delay:** 15-30 seconds (mimics navigation between listings)
- **Sequential processing:** No concurrency

**Code Location:**
- `sync_airbnb/network/http_client.py:122-125` - Inter-request delay
- `sync_airbnb/services/insights.py` - Between-listing delay

**Performance:**
| Listings | First Sync | Incremental Sync |
|----------|------------|------------------|
| 7        | ~112 min   | ~60 min          |
| 50       | ~802 min   | ~413 min (6.9h)  |
| 1,000    | N/A        | ~8,250 min (5.7d)|

**Conclusion:** Works well for <20 listings. Needs optimization for larger accounts.

---

### Request Volume Analysis

**Per listing, per sync:**

**First run (25 weeks back + 25 weeks forward = 355 days):**
- ChartQuery (28-day windows): 355/28 = ~13 requests × 2 metrics = 26 requests
- ListOfMetricsQuery (7-day windows): 355/7 = ~51 requests × 2 metrics = 102 requests
- **Total: 128 requests per listing**

**Incremental run (1 week back + 25 weeks forward = 182 days):**
- ChartQuery: 182/28 = ~7 requests × 2 metrics = 14 requests
- ListOfMetricsQuery: 182/7 = ~26 requests × 2 metrics = 52 requests
- **Total: 66 requests per listing (48% reduction from first run)**

**Load reduction achieved:**
- Old behavior: 180 days back every run = 500+ requests per sync
- New behavior: 1 week incremental = 462 requests for 7 listings
- **Reduction: 93%** (but cookie still expires)

---

### Future Optimization Options

**Option B: Limited Concurrency (5-10 listings in parallel)**

**Pattern:** Multiple browser tabs (realistic for medium accounts)

**Implementation:**
```python
# Process 5 listings concurrently
max_concurrent = 5
with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
    # Submit all listing tasks
    futures = {
        executor.submit(process_listing, lid): lid
        for lid in listings
    }

    # Process as they complete
    for future in as_completed(futures):
        listing_id = futures[future]
        try:
            result = future.result()
        except Exception as e:
            logger.error(f"Listing {listing_id} failed: {e}")
```

**Expected Performance (1,000 listings):**
- Current: 5.7 days
- With concurrency=10: ~14 hours
- **Improvement: 90% faster**

**When to use:**
- After Phase 3 (multi-tenant) is stable
- For accounts with 50-200 listings
- If cookies are stable (no bot detection)

---

### Adaptive Rate Limiting

**Concept:** Adjust concurrency and delays based on response patterns.

**Triggers for slowdown:**
- 429 rate limit errors
- Slow response times (>2s average)
- 403 auth errors (potential bot detection)

**Implementation:**
```python
class AdaptiveRateLimiter:
    def __init__(self):
        self.concurrency = 1  # Start conservative
        self.error_count = 0
        self.success_count = 0

    def on_success(self):
        self.success_count += 1
        # After 10 successes, try increasing concurrency
        if self.success_count >= 10 and self.concurrency < 10:
            self.concurrency += 1
            self.success_count = 0

    def on_error(self, error_type):
        self.error_count += 1
        if error_type in ['429', '403']:
            # Immediately drop to single threaded
            self.concurrency = 1
            self.error_count = 0
```

**Pros:**
- Auto-tunes to Airbnb's rate limits
- Conservative by default
- Scales up when safe

**Cons:**
- More complex
- Harder to debug
- Need good monitoring

**When to use:**
- Phase 4 (if needed for scale)
- After collecting baseline performance data

---

### Monitoring & Alerts

**Metrics to track:**
```python
# Prometheus metrics (already implemented)
airbnb_api_requests_total{endpoint, status_code}
airbnb_api_request_duration_seconds{endpoint}
airbnb_api_retries_total{endpoint}
errors_total{error_type, component}
```

**Key alerts:**
- 429 rate limit errors (>5 per hour)
- 401/403 auth errors (>1 per day)
- Sync duration exceeding 2x baseline
- Cookie age exceeding 7 days

**Log monitoring:**
```bash
# Watch for rate limit hits
docker logs -f sync_airbnb | grep "RATE LIMIT HIT"

# Watch for auth errors
docker logs -f sync_airbnb | grep "Auth error"

# Monitor sync performance
docker logs -f sync_airbnb | grep "Sync completed"
```

---

## Kubernetes Operator (Conditional)

**Status:** Design complete, implementation on hold pending Phase 1-3 results.

**Condition:** Only implement if:
1. IP-per-account isolation is required (evidence suggests it's NOT)
2. OR need strict resource isolation per account
3. OR pod-per-account preferred for operational reasons

**Current Assessment:** Likely NOT needed because:
- RankBreeze backend polling works from different IPs
- Multi-tenant service can handle multiple accounts
- No evidence of IP-based cookie binding

### Architecture (If Needed)

**Components:**

**1. Admin API (MODE=admin)**
- Manages accounts via REST API
- NO Kubernetes API access (security boundary)
- Runs as single deployment

**2. Kubernetes Operator**
- Watches `accounts` table for `is_active=true`
- Creates worker Deployment per account
- Sets `ACCOUNT_ID` and `MODE=worker` environment variables
- Scoped RBAC (deployment CRUD only)
- Written in Python (kopf) or Go (kubebuilder)

**3. Worker Pods (auto-created)**
- One pod per account
- Startup sync if `last_sync_at` is NULL (25 week backfill)
- Scheduler runs daily syncs
- Self-contained, no cross-pod communication

### Benefits

**If IP isolation matters:**
- Each pod can have dedicated egress IP
- Rotate IPs per account
- Isolate from shared IP reputation

**Resource isolation:**
- Account A's heavy sync doesn't affect Account B
- Per-account resource limits
- Easier to debug performance issues

**Operational:**
- Independently scale/restart per account
- Rolling updates per account
- Blast radius contained

### Implementation

**Operator Logic (Python/kopf):**
```python
import kopf
from sqlalchemy import create_engine, select
from models import Account

@kopf.on.timer('', interval=30.0)
def reconcile_accounts(**kwargs):
    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        # Get active accounts
        active = conn.execute(
            select(Account).where(Account.is_active == True)
        ).fetchall()

        # Get existing deployments
        existing = get_k8s_deployments()

        # Create missing deployments
        for account in active:
            if account.account_id not in existing:
                create_worker_deployment(account)

        # Delete inactive deployments
        for account_id in existing:
            if account_id not in [a.account_id for a in active]:
                delete_worker_deployment(account_id)
```

**Worker Deployment Template:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sync-airbnb-worker-{{ account_id }}
  namespace: sync-airbnb
  labels:
    app: sync-airbnb-worker
    account-id: "{{ account_id }}"
spec:
  replicas: 1
  selector:
    matchLabels:
      app: sync-airbnb-worker
      account-id: "{{ account_id }}"
  template:
    spec:
      containers:
      - name: worker
        image: sync-airbnb:latest
        env:
        - name: MODE
          value: "worker"
        - name: ACCOUNT_ID
          value: "{{ account_id }}"
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: sync-airbnb-db
              key: url
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
```

**RBAC:**
```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: sync-airbnb-operator
  namespace: sync-airbnb
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: sync-airbnb-operator
  namespace: sync-airbnb
rules:
- apiGroups: ["apps"]
  resources: ["deployments"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list", "watch"]
```

### Migration Strategy (If Implemented)

1. **Migrations as Kubernetes Job**
   - Run before operator starts
   - Avoids race conditions with multiple pods
   - Faster pod startup (no migration wait)

2. **Gradual Rollout**
   - Start with 1-2 test accounts
   - Monitor for issues
   - Scale to all accounts

3. **Fallback Plan**
   - Keep multi-tenant service as backup
   - Can switch back if operator causes issues

### Open Questions

1. **Credential Updates:** How to trigger pod restart when cookies change?
   - Option A: Operator detects `updated_at` change, recreates pod
   - Option B: Worker polls database periodically
   - **Decision:** Option A (operator-driven)

2. **Pod Naming:** Use account_id or hash?
   - Current: `sync-airbnb-worker-{{ account_id }}`
   - Concern: Account IDs might have special characters
   - **Decision:** Hash account_id for k8s compatibility

3. **Resource Limits:** CPU/memory per pod?
   - Need profiling data from 25-week backfill
   - Current estimate: 512Mi-1Gi memory, 250m-500m CPU
   - **Decision:** Start conservative, tune based on metrics

### Effort

**If needed:**
- Operator development: 12-16 hours
- RBAC setup: 2-4 hours
- Testing: 4-6 hours
- Documentation: 2-3 hours
- **Total: 20-30 hours**

**Recommendation:** Defer until Phase 3 is complete and we have evidence IP isolation is required.

---

## Decision Log

| Date | Decision | Rationale | Outcome |
|------|----------|-----------|---------|
| Oct 2025 | Reduced backfill to 25 weeks first run, 1 week incremental | 93% reduction in request volume | ✅ Implemented, but cookie still expires |
| Oct 22, 2025 | Deploy to Nook (home IP, same as cookie source) | Eliminate IP mismatch as potential cause | ✅ Deployed, cookie still expires after 2 days |
| Oct 22, 2025 | Add 429 error logging | Make rate limits visible | ✅ Implemented |
| Oct 27, 2025 | Fix incremental sync bug | Was using 25 weeks instead of 1 week | ✅ Fixed |
| Oct 27, 2025 | Implement rate limiting (5-10s between requests, 15-30s between listings) | Test if request volume/timing is the issue | ✅ Implemented, cookie still expires |
| Nov 7, 2025 | Research RankBreeze extension behavior | Understand competitor approach | ✅ Complete - they use extension + backend polling |
| Nov 7-9, 2025 | **Implement preflight + TLS fingerprinting (Phase 1)** | Test backend improvements before building extension | ✅ Implemented - monitoring results |
| Nov 9, 2025 | Fix curl_cffi Headers parsing bug | parse_set_cookie_headers() wasn't using get_list() method | ✅ Fixed - preflight now extracts Akamai cookies |
| Nov 9, 2025 | Add comprehensive cookie logging | Track preflight, extraction, merging for debugging | ✅ Implemented |
| TBD | Phase 2: Chrome extension (if Phase 1 fails) | Match competitor UX if backend alone doesn't work | On hold - awaiting Phase 1 monitoring results |
| TBD | Phase 3: Multi-tenant architecture | Once cookies are stable, support multiple accounts | Planned after Phase 1 success |
| TBD | Phase 4: Rate limiting optimization | Only if needed for accounts with 50+ listings | Not started |
| TBD | Kubernetes operator decision | Only if IP isolation or resource isolation required | On hold |

---

## Testing Results

### Test 1: Home IP Deployment (October 22-27, 2025)

**Hypothesis:** IP mismatch is causing cookie expiry.

**Test:**
- Cookie generated on Mac (home IP: Nook)
- Service deployed on Nook (same home IP)
- Expected: Cookie lasts longer due to IP consistency

**Result:** ❌ FAILED
- Cookie still expires after 2 days
- Same behavior as Render deployment
- **Conclusion:** IP matching alone does NOT solve the problem

### Test 2: Incremental Sync + Rate Limiting (October 27, 2025)

**Hypothesis:** Request volume and timing are causing cookie expiry.

**Test:**
- Reduced requests by 93% (1 week incremental vs 25 weeks every run)
- Added 5-10s delays between requests
- Added 15-30s delays between listings
- Sequential processing (no concurrency)

**Result:** ❌ FAILED
- Cookie still expires after 2 days
- Request volume reduction did not help
- Rate limiting did not help
- **Conclusion:** Request volume/timing alone do NOT solve the problem

### Test 3: Preflight + TLS Fingerprinting (November 7-9, 2025)

**Hypothesis:** Stale Akamai cookies and TLS fingerprint mismatch are causing expiry.

**Test Implementation:**
- ✅ Switched to `curl_cffi` with Chrome 110 impersonation for TLS fingerprint
- ✅ Implemented preflight GET to `https://www.airbnb.com/` before each sync
- ✅ Parse Set-Cookie headers using curl_cffi's `get_list()` method
- ✅ Extract fresh Akamai cookies (`bm_sv`, `ak_bmsc`) from preflight response
- ✅ Merge fresh Akamai cookies with stored auth cookies (9 auth + 1-2 Akamai)
- ✅ Add comprehensive logging to track cookie extraction and merging

**Initial Results (November 9, 2025):**
- ✅ Preflight successfully obtaining 1-2 fresh Akamai cookies per sync
- ✅ Cookie merging working correctly (10 total cookies: 9 auth + 1 Akamai)
- ✅ GraphQL API calls succeeding without auth errors
- ✅ Sync proceeding through all listings successfully
- ⏳ **Cookie lifetime monitoring in progress - need 7+ days to confirm success**

**Example from logs:**
```
[PREFLIGHT] Requesting fresh Akamai cookies from Airbnb homepage...
[COOKIES] Using 9 auth cookies: ['_airbed_session_id', '_pt', 'hli', ...]
Preflight request successful, obtained 1 Akamai cookies
[PREFLIGHT] bm_sv=7E017A61B0ABF98A59EB...
[PREFLIGHT] Received 1 fresh Akamai cookies: ['bm_sv']
[COOKIES] Merged cookie string has 10 total cookies (auth: 9, akamai: 1)
[API_CALL] ListingsSectionQuery
[Processing 7 listings for account 310316675]
[API_CALL] ChartQuery|Listing_745515258634591476|...
```

**Next Steps:**
- Monitor daily syncs for 7-14 days
- Check for any auth failures or cookie expiry
- If successful (>7 days), proceed to Phase 3 (multi-tenant)
- If failed (<3 days), proceed to Phase 2 (Chrome extension)

**Timeline:** Deployed Nov 9, monitoring until Nov 16-23

---

## Next Steps

### Immediate (November 9-23, 2025)

1. **✅ Phase 1 Implementation Complete:**
   - ✅ Install `curl-cffi`
   - ✅ Replace `requests` library
   - ✅ Implement preflight function
   - ✅ Implement cookie parsing/merging
   - ✅ Fix curl_cffi Headers parsing bug
   - ✅ Add comprehensive cookie logging
   - ✅ Deploy to Nook (hybrid mode)
   - ✅ All tests passing, GitHub Actions passing

2. **⏳ Monitoring in Progress:**
   - ⏳ Track cookie lifetime daily (target: 7+ days)
   - ⏳ Watch for 401/403 errors (none so far)
   - ⏳ Monitor sync success rate (100% so far)
   - ⏳ Check logs for preflight issues (working correctly)

3. **✅ Documentation:**
   - ✅ Updated this file with Phase 1 implementation details
   - ✅ Recorded decisions in Decision Log
   - ⏳ Will update with final results after monitoring period

### Short-Term (Next 2 Weeks)

**If Phase 1 succeeds (cookie lasts >7 days):**
- ✅ Proceed to Phase 3 (multi-tenant)
- ✅ Remove mode switching
- ✅ Update scheduler for all accounts
- ❌ Skip Phase 2 (Chrome extension not needed)
- ❌ Skip Kubernetes operator (not needed)

**If Phase 1 fails (cookie still expires in 2 days):**
- ⚠️ Proceed to Phase 2 (Chrome extension)
- ⚠️ Build extension components
- ⚠️ Add backend API endpoint
- ⏸️ Re-evaluate architecture after extension testing

### Long-Term (After Cookie Stability)

**Once cookies are stable:**
1. Implement multi-tenant (Phase 3)
2. Assess need for rate limiting optimization (Phase 4)
3. Assess need for Kubernetes operator (probably not needed)
4. Scale to multiple customers

---

## Open Questions

1. **Does preflight pattern actually help?**
   - Will know after Phase 1 testing (1-2 weeks)
   - RankBreeze likely does this, but not confirmed

2. **Is TLS fingerprint a factor?**
   - Testing `curl_cffi` vs native `requests`
   - Will know after Phase 1

3. **Do we need Chrome extension?**
   - Only if Phase 1 fails
   - Would match competitor approach

4. **Is IP-per-account needed?**
   - Evidence suggests NO (RankBreeze polls from backend)
   - Kubernetes operator likely not needed

5. **How many concurrent listings can we safely process?**
   - Need data from customers with 50+ listings
   - Will test after cookies are stable

---

## References

- **RankBreeze Extension Analysis:** ChatGPT-Airbnb Poller overview.md
- **Rate Limiting Details:** tasks/rate-limiting-strategy.md (deprecated, merged into this doc)
- **Kubernetes Operator:** tasks/kubernetes-operator.md (deprecated, merged into this doc)
- **Akamai Bot Manager:** https://www.akamai.com/products/bot-manager
- **curl_cffi:** https://github.com/yifeikong/curl_cffi

---

## Acceptance Criteria

**Phase 1 Success:**
- [ ] Cookie lasts >7 days without manual refresh
- [ ] Daily syncs complete successfully
- [ ] No 401/403 authentication errors
- [ ] GraphQL requests succeed with merged cookies
- [ ] Preflight pattern working correctly

**Phase 2 Success (if needed):**
- [ ] Chrome extension extracts cookies
- [ ] Backend receives and stores auth cookies only
- [ ] Users can refresh via extension button
- [ ] Cookies persist weeks/months
- [ ] Extension submitted to Chrome Web Store

**Phase 3 Success:**
- [ ] Service runs multiple accounts simultaneously
- [ ] No `ACCOUNT_ID` environment variable required
- [ ] Scheduler syncs all active accounts
- [ ] Errors in one account don't affect others
- [ ] Can scale to 10+ accounts

**Phase 4 Success (if needed):**
- [ ] Accounts with 50+ listings sync in <8 hours
- [ ] Concurrent processing works without bot detection
- [ ] Adaptive rate limiting prevents 429 errors
- [ ] System handles 1,000+ listings per account

---

## Notes

- **Don't optimize prematurely:** Test one solution at a time
- **Data-driven decisions:** Wait for Phase 1 results before building extension
- **Competitor research is valuable:** But their backend implementation is speculation
- **IP doesn't seem to matter:** Evidence points to cookie freshness, not IP matching
- **Kubernetes operator likely not needed:** Multi-tenant service should suffice
- **Keep it simple:** Start with backend fixes, add complexity only if needed

---

**Last Updated:** November 9, 2025
**Next Review:** After Phase 1 monitoring completes (November 16-23, 2025)
