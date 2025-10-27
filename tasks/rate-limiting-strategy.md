# Rate Limiting & Request Optimization Strategy

**Status:** ✅ Option A Implemented (October 27, 2025)
**Last Updated:** October 27, 2025
**Owner:** Strategic decision, monitor and iterate based on cookie lifetime

---

## Problem Statement

**Symptom:** Cookie expiry every 1-2 days when running on Render
**Unknown:** Root cause - could be IP mismatch, request volume, or usage patterns
**Risk:** Premature optimization without understanding the real problem

---

## Current State

### Request Volume (Corrected Math - October 27, 2025)

**Per listing, per sync (actual calculation):**
- **First run (25 weeks back + 25 weeks forward = 355 days):**
  - ChartQuery (28-day windows): 355/28 = ~13 requests × 2 metrics = **26 requests**
  - ListOfMetricsQuery (7-day windows): 355/7 = ~51 requests × 2 metrics = **102 requests**
  - **Total: 128 requests per listing**

- **Incremental run (1 week back + 25 weeks forward = 182 days):**
  - ChartQuery (28-day windows): 182/28 = ~7 requests × 2 metrics = **14 requests**
  - ListOfMetricsQuery (7-day windows): 182/7 = ~26 requests × 2 metrics = **52 requests**
  - **Total: 66 requests per listing (48% reduction from first run)**

**For account with 7 listings:**
- First run: 896 requests
- Incremental run: 462 requests per day

**Note:** Previous calculations were based on database rows, not API requests. The above reflects actual API call counts.

### Current Rate Limiting (✅ Implemented October 27, 2025)

- ✅ **Exponential backoff retry** - 5 tries for network errors (via `@backoff.on_exception`)
- ✅ **429 detection** - Logs prominently: `RATE LIMIT HIT (429)` with Retry-After header
- ✅ **Inter-request delays** - 5-10 seconds between API requests (mimics human clicking)
- ✅ **Between-listing delays** - 15-30 seconds between listings (mimics human navigation)
- ✅ **Sequential processing** - No concurrent requests (single user, single tab pattern)

### API Calls Currently Made

**Metrics being polled:**
1. ChartQuery:
   - `("CONVERSION", ["conversion_rate"])`
   - `("CONVERSION", ["p3_impressions"])`

2. ListOfMetricsQuery:
   - `("CONVERSION", ["conversion_rate"])`
   - `("CONVERSION", ["p3_impressions"])`

**Database tables populated:**
- `chart_query` - Daily timeseries data
- `chart_summary` - Summary metrics per window
- `list_of_metrics` - Overview metrics per window

**Columns available but usage unknown:**
- conversion_rate (various types)
- p3_impressions (various types)
- search_conversion_rate
- listing_conversion_rate
- occupancy_rate

---

## Changes Already Made (Load Reduction)

### ✅ 1. Backfill Strategy (Completed Oct 2025)

**Old behavior:**
- Gathered 180 days back on **every run** from Render
- Result: 25+ weeks × 5 listings × 4 metrics = **500+ requests per run**

**New behavior:**
- First run: 25 weeks back
- Subsequent runs: 1 week incremental
- Result: **93% reduction in daily request volume**

### ✅ 2. Infrastructure Change (Pending Tomorrow)

**Old setup:**
- Cookie generated on Mac (home IP)
- Service running on Render (different IP)
- Possible: Airbnb flagging IP mismatch as suspicious

**New setup:**
- Cookie generated on Mac (home IP)
- Service running on Nook (same home IP)
- Expected: Looks like normal user accessing from consistent location

---

## Wait-and-See Strategy (Recommended Approach)

### Phase 1: Monitor Nook Deployment (1-2 weeks)

**Deploy to Nook (tomorrow) and monitor:**

**Metrics to track:**
- Cookie validity duration (currently 1-2 days)
- Any 429 errors in logs (now visible with ⚠️ logging)
- Sync success rate
- Any other HTTP errors

**Decision point:**
- ✅ **If cookies stay valid 7+ days** → Problem solved, no code changes needed
- ⚠️ **If cookies still expire every 1-2 days** → Proceed to Phase 2

**Estimated time:** 1-2 weeks of observation

---

### Phase 2: Data Exploration & Metric Cleanup (TBD)

**Build visualizations and analytics queries:**

**Activities:**
1. Create dashboards/charts using stored data
2. Develop SQL queries for business insights
3. Identify which metrics are actually valuable
4. Identify which API calls/tables are unused

**Decision point:**
- Remove unused API calls (could be 50% request reduction)
- Remove unused metrics from polling config
- Drop unused database tables

**Example unknowns:**
- Is ListOfMetricsQuery redundant with ChartQuery summary?
- Are we using both conversion_rate AND p3_impressions, or just one?
- What about search_conversion_rate, listing_conversion_rate, etc.?

**Estimated time:** 2-4 weeks (depends on visualization work)

---

### Phase 3: Forecast Window Optimization (TBD)

**Determine Airbnb's actual data availability:**

**Question:** How far forward does Airbnb populate metrics?
- Hypothesis: Only 3 months forward (12 weeks)
- Current config: Not explicitly limited (uses LOOKAHEAD_WEEKS = TBD)

**Test approach:**
1. Query Airbnb API for dates 3, 6, 9, 12 months in future
2. Check which dates return actual data vs empty/null
3. Adjust LOOKAHEAD_WEEKS config accordingly

**Decision point:**
- If 3 months: Reduce forecast window by 50%
- If 6 months: Keep current config

**Config change location:**
```python
# sync_airbnb/config.py
LOOKAHEAD_WEEKS = 12  # Adjust based on testing
```

**Estimated time:** 1-2 days of testing

---

### Phase 4: Rate Limiting Implementation (If Still Needed)

**Only pursue if Phases 1-3 don't solve cookie expiry issue.**

#### Option A: Gentle Inter-Request Delay (Simulate Human)

Add small delay between requests to mimic human UI usage:

```python
# sync_airbnb/network/http_client.py
import time

def post_with_retry(...):
    # Make request
    res = requests.post(...)

    # Small delay after successful request (simulate human)
    time.sleep(random.uniform(0.5, 1.5))  # 0.5-1.5 seconds

    return data
```

**Pros:**
- Simple, non-invasive
- Mimics real user behavior
- No complex logic

**Cons:**
- Slows down syncs (20 requests × 1s = +20 seconds per sync)
- Arbitrary delay, not based on real limits

#### Option B: Adaptive Throttling (Smart)

Monitor response times and back off if things slow down:

```python
# Track request times
request_times = []

def post_with_retry(...):
    start = time.time()
    res = requests.post(...)
    duration = time.time() - start

    request_times.append(duration)

    # If last 10 requests are getting slower, back off
    if len(request_times) >= 10:
        avg_duration = sum(request_times[-10:]) / 10
        if avg_duration > 2.0:  # Responses taking >2s
            time.sleep(2.0)  # Slow down

    return data
```

**Pros:**
- Adaptive to actual API behavior
- Only slows down when needed

**Cons:**
- More complex
- Requires tuning thresholds

#### Option C: Respect Retry-After Header (Best Practice)

Already implemented for 429 errors. Backoff library will:
1. Catch 429 RequestException
2. Wait (exponential backoff)
3. Retry up to 5 times

**Current implementation:**
```python
@backoff.on_exception(
    backoff.expo,
    (requests.exceptions.RequestException,),
    max_tries=5,
    jitter=None,
)
def post_with_retry(...):
    # 429 now raises RequestException, triggering retry
    if res.status_code == 429:
        retry_after = res.headers.get("Retry-After", "unknown")
        raise requests.exceptions.RequestException(...)
```

**Note:** This doesn't respect Retry-After header value yet. Could enhance:

```python
@backoff.on_exception(
    backoff.expo,
    (requests.exceptions.RequestException,),
    max_tries=5,
)
def post_with_retry(...):
    if res.status_code == 429:
        retry_after = res.headers.get("Retry-After")
        if retry_after:
            time.sleep(int(retry_after))
        raise requests.exceptions.RequestException(...)
```

#### Recommendation for Phase 4

**If we reach this phase:**
1. Start with Option A (simple delay) - 0.5-1s between requests
2. Monitor for 1 week
3. If still issues, add Option C (respect Retry-After)
4. If still issues, consider Option B (adaptive)

---

## Future Polling Needs (Unknown)

**Potential future features:**

### High-Frequency Polling
- **Messages:** Every 5 minutes = 288 requests/day
- **Reservations:** TBD (daily? hourly?)
- **Payouts:** TBD (weekly? monthly?)

### Considerations
- Different endpoints = different rate limits
- High-frequency polling needs different strategy (websockets? webhooks?)
- May need separate worker processes with different configs

**Decision:** Defer until requirements are clear

---

## Monitoring & Alerts

### What to Watch For

**In logs (now visible with Oct 22 fix):**
```
⚠️  RATE LIMIT HIT (429) - Context: ChartQuery|listing_123, Retry-After: 60s
```

**Metrics to track:**
- Cookie lifetime (days)
- 429 error count per day
- Sync duration (should be consistent)
- Failed listings per sync

### Where to Check

**Docker logs:**
```bash
docker-compose logs -f app | grep -i "rate limit\|429\|cookie\|auth"
```

**Log files (if configured):**
```bash
tail -f /var/log/sync_airbnb/app.log | grep "⚠️"
```

---

## Implementation Details (October 27, 2025)

### Option A: Single User, Single Tab (IMPLEMENTED)

**Pattern:** Mimics one human using one browser tab, clicking through metrics sequentially.

**Implementation:**
- **Location:** `sync_airbnb/network/http_client.py` - `post_with_retry()` function
- **Between requests:** `time.sleep(random.uniform(5, 10))` - mimics human clicking through charts
- **Between listings:** `time.sleep(random.uniform(15, 30))` in `run_insights_poller()` - mimics navigation

**Expected Timing:**
- **7 listings, first sync:** 896 requests × 7.5s avg + 6 × 22.5s = ~112 minutes (vs 10 min without rate limiting)
- **7 listings, incremental:** 462 requests × 7.5s avg + 6 × 22.5s = ~60 minutes
- **50 listings, incremental:** 3,300 requests × 7.5s + 49 × 22.5s = ~413 minutes (6.9h)
- **1,000 listings, incremental:** 66,000 requests × 7.5s + 999 × 22.5s = ~8,250 minutes (137.5h = 5.7 days)

**Scalability:** Works well for small-medium accounts (<50 listings). Not practical for 1,000+ listings.

---

### Future Options (Not Implemented Yet)

#### Option B: Single User, Multiple Tabs (10 tabs)
- **Concurrency:** 10 listings processed in parallel
- **Pattern:** Like opening 10 browser tabs and clicking through each
- **Timing for 1,000 listings:** ~13.8 hours (vs 5.7 days for Option A)
- **When to use:** If Option A solves cookie issues and need to scale to 100-1,000 listings

#### Option C: Property Management Team (10 people, 1 tab each)
- **Concurrency:** 10 workers, each with navigation delays between listings
- **Pattern:** Like 10 employees each checking their assigned listings
- **Timing for 1,000 listings:** ~14.8 hours
- **When to use:** More realistic pattern than Option B, similar performance

#### Option D: Large PM Company (10 people, 10 tabs each)
- **Concurrency:** 100 listings processed simultaneously
- **Pattern:** Enterprise-scale property management
- **Timing for 1,000 listings:** ~1.4 hours
- **When to use:** Only if desperate for speed and willing to risk looking suspicious

**Recommendation:** Start with Option A, monitor cookie lifetime. If cookie lasts 7+ days and need to scale, implement Option B or C with adaptive concurrency based on listing count.

---

## Decision Log

| Date | Decision | Rationale | Outcome |
|------|----------|-----------|---------|
| Oct 2025 | Reduced backfill to 25 weeks first run, 1 week incremental | 93% reduction in daily requests (was broken, showed 0% until Oct 27 fix) | ✅ Fixed Oct 27 |
| Oct 22, 2025 | Added 429 error logging | Make rate limits visible if they occur | ✅ In place |
| Oct 22, 2025 | Deploy to Nook at home (same IP as cookie source) | Eliminate IP mismatch as potential cause | ✅ Deployed |
| Oct 27, 2025 | **Fixed incremental sync bug** | Was using 25 weeks lookback instead of 1 week - incremental syncs were identical to first sync | ✅ Fixed |
| Oct 27, 2025 | **Implemented Option A rate limiting** | 5-10s between requests, 15-30s between listings - simplest approach to test if volume is the issue | ✅ Implemented |
| TBD | Phase 2: Remove unused metrics/API calls | TBD - need data exploration first | Not started |
| TBD | Phase 3: Limit forecast window (25 weeks → 4-8 weeks) | TBD - need to test Airbnb's data availability | Not started |
| TBD | Option B/C: Implement concurrency for large accounts | Only if Option A works and need to scale | Not started |

---

## Action Items

**Immediate (Oct 22, 2025):**
- ✅ Add 429 error logging (completed)
- ⏳ Deploy to Nook (tomorrow)
- ⏳ Monitor cookie lifetime for 1-2 weeks

**Short-term (Next 2-4 weeks):**
- Build visualizations to understand metric value
- Identify unused API calls/metrics
- Test Airbnb forecast data availability (3 vs 6 months)

**Long-term (If needed):**
- Implement rate limiting (Phase 4 options)
- Design polling strategy for future features (messages, reservations, payouts)

---

## Notes

- **Don't optimize prematurely** - Cookie expiry might already be solved by Nook + reduced backfill
- **429 errors were possibly hidden** - Before Oct 22 fix, they could have been logged as "Invalid JSON response"
- **Data-driven decisions** - Wait for visualization work to know which metrics matter
- **One change at a time** - If we make 10 changes, we won't know what fixed it

---

## Related Issues

- P1-10: Add rate limiting (tasks/p1-high.md) - Deferred pending this strategy
- Implementation status: docs/implementation-status.md
- Architecture: docs/ARCHITECTURE.md
