# P1 High Priority Issues - Major Reliability Concerns

**Status:** Should be resolved before production deployment
**Total Issues:** 8
**Estimated Effort:** 34-49 hours

---

## Issue 6: Type Safety Issues (20+ mypy errors)

**Priority:** P1 - HIGH
**Severity:** Code quality, maintainability
**Impact:** Runtime type errors, harder debugging, reduced IDE support
**Status:** Open
**Estimated Effort:** 4-6 hours

### Current State

Running mypy reveals 20+ type errors throughout the codebase:

```bash
$ mypy sync_airbnb/
sync_airbnb/db/writers/accounts.py:45: error: Incompatible return value type (got "Row[Any]", expected "Account")
sync_airbnb/services/insights.py:78: error: Argument 1 has incompatible type "dict[str, Any]"; expected "str"
sync_airbnb/utils/date_window.py:23: error: Missing return statement
sync_airbnb/api/routes/accounts.py:55: error: Incompatible types in assignment
...
Found 24 errors in 12 files
```

### Impact

Without proper type hints:

1. **Runtime errors**: Type mismatches only discovered at runtime
2. **Poor IDE support**: No autocomplete, go-to-definition, refactoring tools
3. **Harder code review**: Cannot verify type correctness without running code
4. **Regression risk**: Changes may break code in non-obvious ways

### Common Error Patterns

#### Pattern 1: Missing Return Type Annotations

```python
# BROKEN
def get_account(engine: Engine, account_id: str):
    with engine.connect() as conn:
        result = conn.execute(select(Account).where(...))
        row = result.fetchone()
        if row:
            return Account(**dict(row._mapping))
        return None

# FIXED
def get_account(engine: Engine, account_id: str) -> Account | None:
    with engine.connect() as conn:
        result = conn.execute(select(Account).where(...))
        row = result.fetchone()
        if row:
            return Account(**dict(row._mapping))
        return None
```

#### Pattern 2: Dict vs Typed Object Confusion

```python
# BROKEN
def process_metrics(data: dict) -> list[dict]:
    # What keys does 'data' have? Unknown!
    return [{"value": d["metric"]} for d in data["items"]]

# FIXED
from typing import TypedDict

class MetricData(TypedDict):
    items: list[dict[str, Any]]

def process_metrics(data: MetricData) -> list[dict[str, Any]]:
    return [{"value": d["metric"]} for d in data["items"]]
```

#### Pattern 3: SQLAlchemy Row Type Handling

```python
# BROKEN
def get_all_accounts(engine: Engine) -> list[Account]:
    with engine.connect() as conn:
        result = conn.execute(select(Account))
        return [Account(**dict(row._mapping)) for row in result]  # Type error

# FIXED
from sqlalchemy.engine import Row

def get_all_accounts(engine: Engine) -> list[Account]:
    with engine.connect() as conn:
        result = conn.execute(select(Account))
        rows: list[Row[Any]] = result.fetchall()
        return [Account(**dict(row._mapping)) for row in rows]
```

### Implementation Steps

1. **Enable mypy in CI**:
   ```yaml
   # .github/workflows/ci.yml
   - name: Type check with mypy
     run: |
       pip install mypy
       mypy sync_airbnb/ --strict
   ```

2. **Fix errors file by file**:
   ```bash
   # Start with most critical files
   mypy sync_airbnb/config.py
   mypy sync_airbnb/models/
   mypy sync_airbnb/schemas/
   mypy sync_airbnb/db/
   mypy sync_airbnb/services/
   mypy sync_airbnb/api/
   ```

3. **Add type stubs for third-party libraries**:
   ```bash
   pip install types-requests types-python-dotenv
   ```

4. **Configure mypy**:
   ```ini
   # mypy.ini
   [mypy]
   python_version = 3.10
   warn_return_any = True
   warn_unused_configs = True
   disallow_untyped_defs = True
   disallow_any_generics = True
   check_untyped_defs = True

   # Per-module overrides for gradual typing
   [mypy-tests.*]
   ignore_errors = True

   [mypy-alembic.*]
   ignore_errors = True
   ```

### Testing Requirements

```bash
# All files should pass mypy
mypy sync_airbnb/ --strict
# Expected: Success: no issues found in X source files
```

### Files to Modify

Most files in `sync_airbnb/` will need type hint improvements (estimated 40+ files).

### Dependencies

- `mypy` (already in dev-requirements.txt)
- `types-requests`
- `types-python-dotenv`

### Related Issues

- None

---

## Issue 7: No Observability for Background Jobs

**Priority:** P1 - HIGH
**Severity:** Operations, debugging
**Impact:** Cannot monitor sync progress, detect failures, or debug issues
**Status:** Open
**Estimated Effort:** 6-8 hours

### Current State

Manual sync returns 202 immediately with no way to check status:

```python
@router.post("/accounts/{account_id}/sync")
async def trigger_sync(account_id: str):
    thread = threading.Thread(target=run_insights_poller, args=(account,))
    thread.start()
    return {"message": "Sync initiated in background"}
    # User has NO way to check:
    # - Is sync still running?
    # - Did sync succeed or fail?
    # - How many listings completed?
    # - What errors occurred?
```

Scheduled syncs have same problem - no visibility into execution.

### Impact

Without job observability:

1. **Silent failures**: Sync fails, nobody knows
2. **No progress tracking**: User doesn't know if 5-minute sync is stuck or working
3. **Hard to debug**: Cannot see which listing failed or why
4. **No metrics**: Cannot track sync duration, success rate, error rate
5. **No alerting**: Cannot alert on-call when syncs fail

### Recommended Solution

Add `sync_jobs` table to track all sync executions:

#### Step 1: Create Sync Jobs Table

```python
# sync_airbnb/models/sync_job.py
from sqlalchemy import Column, String, DateTime, Integer, Text, ForeignKey
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class SyncJob(Base):
    __tablename__ = "sync_jobs"
    __table_args__ = {"schema": "airbnb"}

    job_id = Column(String(36), primary_key=True)  # UUID
    account_id = Column(String(255), ForeignKey("airbnb.accounts.account_id"), nullable=False)
    status = Column(String(50), nullable=False)  # pending, running, succeeded, failed
    trigger = Column(String(50), nullable=False)  # manual, scheduled, startup
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    listings_total = Column(Integer, nullable=True)
    listings_completed = Column(Integer, nullable=True)
    listings_failed = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
```

#### Step 2: Update Service Layer

```python
# sync_airbnb/services/insights.py
import uuid
from datetime import datetime
from sync_airbnb.db.writers.sync_jobs import create_sync_job, update_sync_job

def run_insights_poller(account: Account, trigger: str = "manual") -> str:
    """Run insights poller with job tracking."""
    # Create job record
    job_id = str(uuid.uuid4())
    create_sync_job(
        engine,
        job_id=job_id,
        account_id=account.account_id,
        status="pending",
        trigger=trigger,
    )

    try:
        # Update to running
        update_sync_job(engine, job_id, status="running", started_at=datetime.utcnow())

        # Fetch listings
        listings = poller.fetch_listing_ids()
        update_sync_job(engine, job_id, listings_total=len(listings))

        # Track progress
        completed = 0
        failed = 0

        for listing_id, listing_name in listings.items():
            try:
                # Poll and insert
                ...
                completed += 1
                update_sync_job(engine, job_id, listings_completed=completed)
            except Exception as e:
                logger.error(f"Listing {listing_id} failed: {e}")
                failed += 1
                update_sync_job(engine, job_id, listings_failed=failed)
                # Continue to next listing

        # Mark success
        update_sync_job(
            engine,
            job_id,
            status="succeeded",
            completed_at=datetime.utcnow(),
        )

    except Exception as e:
        logger.error(f"Sync job {job_id} failed: {e}", exc_info=True)
        update_sync_job(
            engine,
            job_id,
            status="failed",
            completed_at=datetime.utcnow(),
            error_message=str(e),
        )
        raise

    return job_id
```

#### Step 3: Add Job Status API

```python
# sync_airbnb/api/routes/sync_jobs.py
from fastapi import APIRouter, HTTPException
from sync_airbnb.db.readers.sync_jobs import get_sync_job, list_sync_jobs

router = APIRouter()

@router.get("/sync-jobs/{job_id}")
async def get_job_status(job_id: str):
    """Get sync job status by ID."""
    job = get_sync_job(engine, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@router.get("/accounts/{account_id}/sync-jobs")
async def list_account_jobs(account_id: str, limit: int = 50):
    """List recent sync jobs for account."""
    jobs = list_sync_jobs(engine, account_id=account_id, limit=limit)
    return jobs

# Update manual sync to return job_id
@router.post("/accounts/{account_id}/sync")
async def trigger_sync(account_id: str):
    account = get_account(engine, account_id)
    if not account:
        raise HTTPException(status_code=404)

    # Start in background
    job_id = None
    def run_with_tracking():
        nonlocal job_id
        job_id = run_insights_poller(account, trigger="manual")

    thread = threading.Thread(target=run_with_tracking)
    thread.start()

    # Wait briefly for job_id to be created
    thread.join(timeout=1.0)

    return {
        "message": "Sync initiated",
        "job_id": job_id,
        "status_url": f"/api/v1/sync-jobs/{job_id}",
    }
```

### Alternative Solution: Use Celery

For production, consider replacing threads with Celery:

```python
# sync_airbnb/tasks.py
from celery import Celery

celery_app = Celery("sync_airbnb", broker="redis://localhost:6379")

@celery_app.task(bind=True)
def run_insights_sync(self, account_id: str, trigger: str = "manual"):
    """Celery task for insights sync with built-in tracking."""
    job_id = self.request.id
    account = get_account(engine, account_id)

    # Celery tracks state automatically
    self.update_state(state="PROGRESS", meta={"current": 0, "total": 100})

    # Run sync...
    ...
```

Benefits:
- Built-in job tracking and retries
- Better for horizontal scaling
- Visibility via Flower dashboard
- No threading issues

### Implementation Steps

1. Create migration for `sync_jobs` table
2. Create `SyncJob` model
3. Create `db/readers/sync_jobs.py` and `db/writers/sync_jobs.py`
4. Update `run_insights_poller()` to create and update jobs
5. Add sync jobs API routes
6. Update manual sync endpoint to return job_id
7. Add tests for job tracking
8. Update documentation

### Testing Requirements

```python
def test_manual_sync_creates_job_record():
    """Test that manual sync creates job in database."""
    response = client.post(f"/api/v1/accounts/{account_id}/sync")
    job_id = response.json()["job_id"]

    job = get_sync_job(engine, job_id)
    assert job.status == "pending"
    assert job.trigger == "manual"

def test_sync_job_tracks_progress():
    """Test that job record updates during sync."""
    job_id = run_insights_poller(account, trigger="manual")

    job = get_sync_job(engine, job_id)
    assert job.status == "succeeded"
    assert job.listings_completed > 0
    assert job.started_at is not None
    assert job.completed_at is not None

def test_get_job_status_endpoint():
    """Test GET /sync-jobs/{job_id}."""
    response = client.get(f"/api/v1/sync-jobs/{job_id}")
    assert response.status_code == 200
    assert response.json()["job_id"] == job_id
```

### Files to Create/Modify

- `sync_airbnb/models/sync_job.py` (create)
- `sync_airbnb/db/readers/sync_jobs.py` (create)
- `sync_airbnb/db/writers/sync_jobs.py` (create)
- `sync_airbnb/api/routes/sync_jobs.py` (create)
- `sync_airbnb/services/insights.py` (modify)
- `sync_airbnb/api/routes/accounts.py` (modify)
- `alembic/versions/...py` (create migration)
- `tests/api/test_sync_jobs.py` (create)

### Dependencies

- None (uses existing stack)
- Optional: Celery + Redis (for production)

### Related Issues

- Issue 8 (thread safety)
- Issue 9 (per-listing error recovery)

---

## Issue 8: Thread Safety Issues (Daemon Threads)

**Priority:** P1 - HIGH
**Severity:** Data corruption risk
**Impact:** Database transactions can be killed mid-write on process shutdown
**Status:** Open
**Estimated Effort:** 4-6 hours

### Current State

Startup sync and manual sync use daemon threads that don't block process exit:

```python
# sync_airbnb/services/scheduler.py
def run_sync_on_startup():
    account = get_account(config.engine, config.ACCOUNT_ID)
    if account and account.is_active and account.last_sync_at is None:
        thread = threading.Thread(
            target=run_insights_poller,
            args=(account,),
            daemon=True  # <-- PROBLEM: Killed on exit even mid-transaction
        )
        thread.start()
```

### Problem

Daemon threads are forcefully killed when main process exits, even if:
- Writing to database
- In middle of transaction
- Holding locks

**Result:** Partial writes, corrupted data, inconsistent state.

### Example Failure Scenario

```python
# Thread 1 (daemon) is syncing
for listing in listings:
    # Writing listing 1... SUCCESS
    # Writing listing 2... (IN PROGRESS)
    #   ↓
    # Main process receives SIGTERM (deploy, scale-down, etc.)
    #   ↓
    # Python kills daemon thread immediately
    #   ↓
    # Listing 2 partially written (some rows yes, some rows no)
    #   ↓
    # DATA CORRUPTION
```

### Recommended Solution: Graceful Shutdown

Use non-daemon threads with shutdown signal handling:

```python
# sync_airbnb/services/scheduler.py
import signal
import threading
from typing import List

# Track active sync threads
active_threads: List[threading.Thread] = []
shutdown_event = threading.Event()

def run_sync_on_startup():
    """Run startup sync with graceful shutdown support."""
    account = get_account(config.engine, config.ACCOUNT_ID)
    if account and account.is_active and account.last_sync_at is None:
        # Non-daemon thread (blocks shutdown)
        thread = threading.Thread(
            target=run_insights_poller_with_shutdown_check,
            args=(account, shutdown_event),
            daemon=False  # <-- FIX: Block shutdown until complete
        )
        active_threads.append(thread)
        thread.start()

def run_insights_poller_with_shutdown_check(account: Account, shutdown_event: threading.Event):
    """Run poller with periodic shutdown checks."""
    try:
        poller = AirbnbSync(...)
        listings = poller.fetch_listing_ids()

        for listing_id in listings:
            # Check for shutdown signal before each listing
            if shutdown_event.is_set():
                logger.warning(f"Shutdown requested, stopping sync at listing {listing_id}")
                return

            # Process listing (atomic per-listing)
            try:
                process_single_listing(listing_id, poller, account)
            except Exception as e:
                logger.error(f"Listing {listing_id} failed: {e}")
                continue

        update_last_sync(engine, account.account_id)
    finally:
        active_threads.remove(threading.current_thread())

def handle_shutdown_signal(signum, frame):
    """Handle SIGTERM/SIGINT gracefully."""
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_event.set()

    # Wait for threads to finish (with timeout)
    for thread in active_threads:
        logger.info(f"Waiting for thread {thread.name} to complete...")
        thread.join(timeout=300)  # 5 minute max wait

        if thread.is_alive():
            logger.error(f"Thread {thread.name} did not complete in time")

    logger.info("Graceful shutdown complete")
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGTERM, handle_shutdown_signal)
signal.signal(signal.SIGINT, handle_shutdown_signal)
```

### Alternative Solution: Use Celery

Celery handles this automatically:

```python
# sync_airbnb/tasks.py
from celery import Celery
from celery.signals import worker_shutdown

celery_app = Celery("sync_airbnb", broker="redis://localhost:6379")

@celery_app.task(bind=True)
def run_insights_sync(self, account_id: str):
    """Celery task with automatic graceful shutdown."""
    # Celery handles SIGTERM gracefully:
    # 1. Stops accepting new tasks
    # 2. Waits for running tasks to complete
    # 3. Respects soft_time_limit and time_limit
    ...

@worker_shutdown.connect
def handle_worker_shutdown(sender, **kwargs):
    logger.info("Celery worker shutting down...")
```

### Kubernetes Graceful Shutdown

Update deployment to allow time for graceful shutdown:

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      terminationGracePeriodSeconds: 600  # 10 minutes for sync to complete
      containers:
        - name: sync-worker
          lifecycle:
            preStop:
              exec:
                command: ["/bin/sh", "-c", "sleep 10"]  # Give app time to receive signal
```

### Implementation Steps

1. Add shutdown signal handlers to `scheduler.py`
2. Change daemon threads to non-daemon
3. Add shutdown_event checks in sync loop
4. Track active threads in global list
5. Add graceful shutdown tests
6. Update Docker entrypoint to forward signals
7. Update Kubernetes deployment with terminationGracePeriodSeconds
8. Document shutdown behavior

### Testing Requirements

```python
import signal
import time
from threading import Thread

def test_graceful_shutdown_waits_for_sync():
    """Test that SIGTERM waits for sync to complete."""
    # Start sync in background
    thread = Thread(target=run_insights_poller, args=(account,))
    thread.start()

    # Wait for sync to start processing
    time.sleep(2)

    # Send SIGTERM
    os.kill(os.getpid(), signal.SIGTERM)

    # Thread should complete (not killed)
    thread.join(timeout=10)
    assert not thread.is_alive()

    # Verify data integrity
    job = get_last_sync_job(engine, account.account_id)
    assert job.status in ("succeeded", "failed")  # Not "running"

def test_shutdown_event_stops_new_listings():
    """Test that shutdown event stops processing new listings."""
    shutdown_event = threading.Event()

    # Start sync
    thread = Thread(
        target=run_insights_poller_with_shutdown_check,
        args=(account, shutdown_event),
    )
    thread.start()

    # Trigger shutdown after 2 seconds
    time.sleep(2)
    shutdown_event.set()

    # Thread should stop gracefully
    thread.join(timeout=10)
    assert not thread.is_alive()
```

### Files to Modify

- `sync_airbnb/services/scheduler.py`
- `sync_airbnb/services/insights.py`
- `sync_airbnb/api/routes/accounts.py` (manual sync)
- `k8s/deployment.yaml` (if exists)
- `tests/services/test_graceful_shutdown.py` (create)

### Dependencies

- None (uses built-in signal handling)

### Related Issues

- Issue 7 (job observability)
- Issue 9 (per-listing error recovery)

---

## Issue 9: Per-Listing Error Recovery Incomplete

**Priority:** P1 - HIGH
**Severity:** Data loss, silent failures
**Impact:** One listing failure breaks entire sync, remaining listings not processed
**Status:** Open
**Estimated Effort:** 2-3 hours

### Current State

Service layer inserts after each listing (good), but has no error handling:

```python
# sync_airbnb/services/insights.py
for listing_id, listing_name in sorted(listings.items()):
    # If this raises, loop breaks and remaining listings are skipped
    poller.poll_range_and_flatten(listing_id, start_date, end_date, metrics)

    parsed_chunks = poller.parse_all()

    # Add account_id
    for row in parsed_chunks["chart_query"]:
        row["account_id"] = account.account_id

    # If database insert fails, loop breaks
    insert_chart_query_rows(engine, parsed_chunks["chart_query"])
    insert_chart_summary_rows(engine, parsed_chunks["chart_summary"])
    insert_list_of_metrics_rows(engine, parsed_chunks["list_of_metrics"])

    poller._parsed_chunks.clear()
```

### Problem

If listing 5 out of 20 fails:
- Listings 1-4: Saved ✓
- Listing 5: Failed ✗
- Listings 6-20: **NOT PROCESSED** ✗

User has no idea which listings succeeded and which failed.

### Recommended Solution

Add try/except around each listing with detailed error logging:

```python
# sync_airbnb/services/insights.py
from typing import List, Dict

def run_insights_poller(account: Account, scrape_day: date | None = None) -> Dict[str, any]:
    """Run insights poller with per-listing error recovery."""
    # ... setup code ...

    results = {
        "total_listings": len(listings),
        "succeeded": 0,
        "failed": 0,
        "errors": [],
    }

    for listing_id, listing_name in sorted(listings.items()):
        try:
            logger.info(f"Processing listing {listing_id} ({listing_name})...")

            # Poll all queries for this listing
            for query_type, metrics in METRIC_QUERIES.items():
                poller.poll_range_and_flatten(
                    listing_id=listing_id,
                    start_date=window_start,
                    end_date=window_end,
                    metrics=metrics,
                )

            # Parse and add account_id
            parsed_chunks = poller.parse_all()
            for row in parsed_chunks["chart_query"]:
                row["account_id"] = account.account_id
            for row in parsed_chunks["chart_summary"]:
                row["account_id"] = account.account_id
            for row in parsed_chunks["list_of_metrics"]:
                row["account_id"] = account.account_id

            # Insert to database
            insert_chart_query_rows(engine, parsed_chunks["chart_query"])
            insert_chart_summary_rows(engine, parsed_chunks["chart_summary"])
            insert_list_of_metrics_rows(engine, parsed_chunks["list_of_metrics"])

            results["succeeded"] += 1
            logger.info(f"✓ Listing {listing_id} completed successfully")

        except Exception as e:
            results["failed"] += 1
            error_detail = {
                "listing_id": listing_id,
                "listing_name": listing_name,
                "error": str(e),
                "error_type": type(e).__name__,
            }
            results["errors"].append(error_detail)

            logger.error(
                f"✗ Listing {listing_id} ({listing_name}) failed",
                extra=error_detail,
                exc_info=True,
            )

            # Continue to next listing
            continue

        finally:
            # Always clear chunks to prevent memory leak
            poller._parsed_chunks.clear()

    # Log summary
    logger.info(
        f"Sync completed: {results['succeeded']}/{results['total_listings']} listings succeeded, "
        f"{results['failed']} failed"
    )

    # Update last_sync_at only if at least one listing succeeded
    if results["succeeded"] > 0:
        update_last_sync(engine, account.account_id)

    # Raise if ALL listings failed
    if results["failed"] == results["total_listings"]:
        raise RuntimeError(
            f"All {results['total_listings']} listings failed. "
            f"First error: {results['errors'][0]['error']}"
        )

    return results
```

### Enhanced: Store Errors in Database

Track listing-level errors in sync_jobs table:

```python
# sync_airbnb/models/sync_job.py
class SyncJob(Base):
    # ... existing fields ...
    listing_errors = Column(JSON, nullable=True)  # List of error details

# In run_insights_poller
update_sync_job(
    engine,
    job_id,
    status="succeeded" if results["failed"] == 0 else "partial",
    listing_errors=results["errors"],
)
```

### Implementation Steps

1. Add try/except around listing loop in `run_insights_poller()`
2. Track succeeded/failed counts
3. Log detailed error info for each failure
4. Continue to next listing after error
5. Update last_sync_at only if at least one listing succeeded
6. Raise error only if ALL listings failed
7. Add tests for partial success scenarios
8. Update sync_jobs table to store listing errors (optional)

### Testing Requirements

```python
from unittest.mock import patch, Mock

def test_one_listing_fails_others_continue():
    """Test that one listing failure doesn't stop others."""
    # Mock fetch_listing_ids to return 3 listings
    with patch.object(poller, "fetch_listing_ids") as mock_fetch:
        mock_fetch.return_value = {
            "123": "Listing 1",
            "456": "Listing 2",  # This will fail
            "789": "Listing 3",
        }

        # Mock poll_range_and_flatten to fail on listing 456
        original_poll = poller.poll_range_and_flatten
        def mock_poll(listing_id, *args, **kwargs):
            if listing_id == "456":
                raise ValueError("API error for listing 456")
            return original_poll(listing_id, *args, **kwargs)

        with patch.object(poller, "poll_range_and_flatten", side_effect=mock_poll):
            results = run_insights_poller(account)

            # Should process all 3 listings
            assert results["total_listings"] == 3
            assert results["succeeded"] == 2
            assert results["failed"] == 1
            assert len(results["errors"]) == 1
            assert results["errors"][0]["listing_id"] == "456"

            # Verify listings 123 and 789 were inserted
            rows = get_chart_query_rows(engine, account.account_id)
            listing_ids = {row["airbnb_listing_id"] for row in rows}
            assert "123" in listing_ids
            assert "789" in listing_ids
            assert "456" not in listing_ids

def test_all_listings_fail_raises_error():
    """Test that all listings failing raises RuntimeError."""
    with patch.object(poller, "poll_range_and_flatten", side_effect=ValueError("API down")):
        with pytest.raises(RuntimeError, match="All .* listings failed"):
            run_insights_poller(account)

def test_last_sync_updated_on_partial_success():
    """Test that last_sync_at is updated even if some listings fail."""
    # Mock one failure
    original_poll = poller.poll_range_and_flatten
    call_count = 0
    def mock_poll(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise ValueError("Simulated failure")
        return original_poll(*args, **kwargs)

    with patch.object(poller, "poll_range_and_flatten", side_effect=mock_poll):
        run_insights_poller(account)

        # last_sync_at should still be updated
        updated_account = get_account(engine, account.account_id)
        assert updated_account.last_sync_at is not None
```

### Files to Modify

- `sync_airbnb/services/insights.py`
- `sync_airbnb/models/sync_job.py` (optional, for error storage)
- `tests/services/test_insights.py`

### Dependencies

- None

### Related Issues

- Issue 7 (job observability)
- Issue 8 (thread safety)

---

## Issue 10: No Rate Limiting

**Priority:** P1 - HIGH
**Severity:** Service stability, API abuse
**Impact:** Could hit Airbnb API rate limits, get IP banned, cause service outage
**Status:** Open
**Estimated Effort:** 4-6 hours

### Current State

HTTP client makes unlimited requests with no rate limiting:

```python
# sync_airbnb/network/http_client.py
def make_request(url: str, payload: dict, headers: dict) -> dict:
    response = requests.post(url, json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()
    # No rate limiting, no backoff, no circuit breaker
```

### Risks

1. **IP ban**: Airbnb may ban IP for excessive requests
2. **429 errors**: Hit rate limit, sync fails
3. **Cost**: Pay for retries on 429s
4. **Service degradation**: Slow responses when rate limited

### Recommended Solution

Implement token bucket rate limiter with exponential backoff:

```python
# sync_airbnb/network/rate_limiter.py
import time
from threading import Lock
from typing import Optional

class TokenBucketRateLimiter:
    """Thread-safe token bucket rate limiter."""

    def __init__(self, rate: float, capacity: float):
        """
        Initialize rate limiter.

        Args:
            rate: Tokens per second (e.g., 10 = 10 requests/sec)
            capacity: Max burst size (e.g., 20 = can burst up to 20 requests)
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.time()
        self.lock = Lock()

    def acquire(self, timeout: Optional[float] = None) -> bool:
        """
        Acquire a token, blocking if necessary.

        Args:
            timeout: Max seconds to wait for token (None = wait forever)

        Returns:
            True if token acquired, False if timeout
        """
        start = time.time()

        while True:
            with self.lock:
                now = time.time()
                elapsed = now - self.last_update

                # Add tokens based on elapsed time
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
                self.last_update = now

                # If token available, consume it
                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return True

            # Check timeout
            if timeout is not None and (time.time() - start) >= timeout:
                return False

            # Wait before retry
            time.sleep(0.1)

# sync_airbnb/network/http_client.py
import os
import time
import logging
from requests.exceptions import HTTPError

logger = logging.getLogger(__name__)

# Global rate limiter (shared across all requests)
# 10 requests/sec with burst of 20
RATE_LIMITER = TokenBucketRateLimiter(
    rate=float(os.getenv("AIRBNB_API_RATE_LIMIT", "10")),
    capacity=float(os.getenv("AIRBNB_API_BURST_LIMIT", "20")),
)

def make_request_with_rate_limit(
    url: str,
    payload: dict,
    headers: dict,
    max_retries: int = 3,
) -> dict:
    """Make HTTP request with rate limiting and exponential backoff."""

    for attempt in range(max_retries):
        # Acquire rate limit token (blocks if needed)
        if not RATE_LIMITER.acquire(timeout=60):
            raise TimeoutError("Rate limiter timeout after 60 seconds")

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()

        except HTTPError as e:
            if e.response.status_code == 429:
                # Rate limited - use Retry-After header if present
                retry_after = int(e.response.headers.get("Retry-After", 60))
                logger.warning(
                    f"Rate limited (429), waiting {retry_after}s before retry {attempt + 1}/{max_retries}"
                )
                time.sleep(retry_after)
                continue

            elif e.response.status_code >= 500:
                # Server error - exponential backoff
                wait_time = 2 ** attempt  # 1s, 2s, 4s
                logger.warning(
                    f"Server error ({e.response.status_code}), "
                    f"waiting {wait_time}s before retry {attempt + 1}/{max_retries}"
                )
                time.sleep(wait_time)
                continue

            else:
                # Client error (4xx) - don't retry
                raise

        except Exception as e:
            logger.error(f"Request failed: {e}", exc_info=True)
            raise

    raise RuntimeError(f"Max retries ({max_retries}) exceeded")
```

### Alternative Solution: Use slowapi

FastAPI middleware for rate limiting:

```python
# requirements.txt
slowapi==0.1.9

# sync_airbnb/main.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Apply to endpoints
@app.post("/api/v1/accounts/{account_id}/sync")
@limiter.limit("10/minute")  # Max 10 manual syncs per minute per IP
async def trigger_sync(request: Request, account_id: str):
    ...
```

### Implementation Steps

1. Create `TokenBucketRateLimiter` class in `network/rate_limiter.py`
2. Add rate limiter to `http_client.py`
3. Add environment variables for rate/burst limits
4. Implement exponential backoff for 429 and 5xx errors
5. Respect `Retry-After` header from Airbnb
6. Add tests for rate limiting behavior
7. Add metrics for rate limit hits
8. Document rate limit configuration

### Testing Requirements

```python
import time
from sync_airbnb.network.rate_limiter import TokenBucketRateLimiter

def test_rate_limiter_allows_burst():
    """Test that rate limiter allows burst up to capacity."""
    limiter = TokenBucketRateLimiter(rate=10, capacity=20)

    # Should allow 20 rapid requests (burst)
    start = time.time()
    for _ in range(20):
        assert limiter.acquire(timeout=1)
    elapsed = time.time() - start

    # Should complete in < 1 second (no throttling)
    assert elapsed < 1.0

def test_rate_limiter_throttles_after_burst():
    """Test that rate limiter throttles after burst."""
    limiter = TokenBucketRateLimiter(rate=10, capacity=20)

    # Consume burst
    for _ in range(20):
        limiter.acquire()

    # 21st request should block
    start = time.time()
    limiter.acquire(timeout=0.5)
    elapsed = time.time() - start

    # Should have waited ~0.1 seconds (1/10 rate)
    assert elapsed >= 0.05

def test_http_client_retries_on_429():
    """Test that HTTP client retries on 429 with backoff."""
    mock_response = Mock()
    mock_response.status_code = 429
    mock_response.headers = {"Retry-After": "1"}

    with patch("requests.post") as mock_post:
        # First 2 attempts: 429, third: success
        mock_post.side_effect = [
            HTTPError(response=mock_response),
            HTTPError(response=mock_response),
            Mock(status_code=200, json=lambda: {"data": "success"}),
        ]

        result = make_request_with_rate_limit("https://api.airbnb.com", {}, {})

        assert result == {"data": "success"}
        assert mock_post.call_count == 3
```

### Files to Create/Modify

- `sync_airbnb/network/rate_limiter.py` (create)
- `sync_airbnb/network/http_client.py` (modify)
- `.env` (add AIRBNB_API_RATE_LIMIT, AIRBNB_API_BURST_LIMIT)
- `tests/network/test_rate_limiter.py` (create)
- `tests/network/test_http_client.py` (add rate limit tests)

### Dependencies

- None (pure Python implementation)
- Optional: `slowapi` (for API endpoint rate limiting)

### Related Issues

- Issue 12 (account validation)

---

## Issue 11: Stale Poller Entry Point

**Priority:** P1 - HIGH
**Severity:** Confusion, incorrect deployment
**Impact:** Old entry point may be used by accident, bypassing new architecture
**Status:** Open
**Estimated Effort:** 1-2 hours

### Current State

Git status shows old poller files were deleted but may be referenced in docs:

```bash
$ git status
D pollers/__init__.py
D pollers/insights.py
```

README and Dockerfile may still reference old entry point:

```dockerfile
# Dockerfile (old)
CMD ["python", "-m", "pollers.insights"]
```

### Problem

1. **Stale documentation**: Developers follow old instructions
2. **Incorrect deployment**: Dockerfile uses wrong command
3. **Confusion**: Two entry points (old poller, new FastAPI)

### Recommended Solution

Complete the migration to new entry point:

#### Step 1: Update Dockerfile

```dockerfile
# Dockerfile - BEFORE
CMD ["python", "-m", "pollers.insights"]

# Dockerfile - AFTER
CMD ["uvicorn", "sync_airbnb.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### Step 2: Update README

Search for `pollers` references and update:

```markdown
# README.md - BEFORE
Run the poller:
python -m pollers.insights

# README.md - AFTER
Run the service:
uvicorn sync_airbnb.main:app --host 0.0.0.0 --port 8000 --reload
```

#### Step 3: Update Docker Compose

```yaml
# docker-compose.yml - BEFORE
services:
  app:
    command: python -m pollers.insights

# docker-compose.yml - AFTER
services:
  app:
    command: uvicorn sync_airbnb.main:app --host 0.0.0.0 --port 8000 --reload
```

#### Step 4: Remove Old References

```bash
# Search for all references to old entry point
grep -r "pollers" . --exclude-dir=.git --exclude-dir=venv

# Common locations:
# - README.md
# - Dockerfile
# - docker-compose.yml
# - docs/
# - Makefile
# - CI/CD configs (.github/workflows/, .gitlab-ci.yml, etc.)
```

### Implementation Steps

1. Search for all references to `pollers` module
2. Update Dockerfile CMD
3. Update docker-compose.yml command
4. Update README instructions
5. Update any CI/CD configurations
6. Test Docker build and run
7. Update deployment documentation
8. Remove old poller directory if still present

### Testing Requirements

```bash
# Verify Docker image uses correct entry point
docker build -t sync-airbnb .
docker run -p 8000:8000 sync-airbnb
# Should start FastAPI, not old poller

# Verify health endpoint works
curl http://localhost:8000/health
# Should return 200 OK

# Verify API docs load
curl http://localhost:8000/docs
# Should return OpenAPI docs
```

### Files to Modify

- `Dockerfile`
- `docker-compose.yml`
- `README.md`
- `docs/2025-10-context.md`
- `.github/workflows/*.yml` (if exists)
- `Makefile` (if has run commands)

### Dependencies

- None

### Related Issues

- None

---

## Issue 12: No Account Validation

**Priority:** P1 - HIGH
**Severity:** Data quality, user experience
**Impact:** Invalid credentials stored in database, silent sync failures
**Status:** Open
**Estimated Effort:** 3-4 hours

### Current State

Account creation endpoint accepts credentials without validation:

```python
@router.post("/accounts", status_code=201)
async def create_account(account: AccountCreate):
    # NO validation that credentials work
    result = create_or_update_account(engine, account)
    return result
```

User doesn't know if credentials are valid until first sync fails (hours later).

### Problem

1. **Silent failures**: User creates account, sync fails silently
2. **Wasted resources**: Sync runs with invalid credentials, wastes time
3. **Poor UX**: User doesn't know credentials are wrong until much later
4. **Debugging difficulty**: "Why isn't my account syncing?" (credentials expired)

### Recommended Solution

Validate credentials by making test API call on account creation:

```python
# sync_airbnb/services/account_validation.py
import logging
from datetime import date
from sync_airbnb.network.http_headers import build_headers
from sync_airbnb.utils.airbnb_sync import AirbnbSync
from sync_airbnb.schemas.account import AccountCreate

logger = logging.getLogger(__name__)

class AccountValidationError(Exception):
    """Raised when account credentials are invalid."""
    pass

def validate_account_credentials(account: AccountCreate) -> dict[str, any]:
    """
    Validate account credentials by making test API call.

    Args:
        account: Account data to validate

    Returns:
        Validation result with details

    Raises:
        AccountValidationError: If credentials are invalid
    """
    try:
        # Build headers from account
        headers = build_headers(
            airbnb_cookie=account.airbnb_cookie,
            x_client_version=account.x_client_version,
            x_airbnb_client_trace_id=account.x_airbnb_client_trace_id,
            user_agent=account.user_agent,
        )

        # Create poller with account headers
        poller = AirbnbSync(scrape_day=date.today(), headers=headers)

        # Try to fetch listings (lightweight API call)
        logger.info(f"Validating credentials for account {account.account_id}...")
        listings = poller.fetch_listing_ids()

        if not listings:
            logger.warning(f"Account {account.account_id} has no listings")
            return {
                "valid": True,
                "listing_count": 0,
                "warning": "Account has no listings",
            }

        logger.info(f"Account {account.account_id} validated: {len(listings)} listings found")
        return {
            "valid": True,
            "listing_count": len(listings),
            "listings": list(listings.keys())[:5],  # First 5 for preview
        }

    except Exception as e:
        logger.error(f"Account validation failed: {e}", exc_info=True)
        raise AccountValidationError(
            f"Invalid credentials: {str(e)}"
        ) from e

# sync_airbnb/api/routes/accounts.py
from sync_airbnb.services.account_validation import validate_account_credentials, AccountValidationError

@router.post("/accounts", status_code=201)
async def create_account(account: AccountCreate):
    """Create account with credential validation."""
    try:
        # Validate credentials before saving
        validation_result = validate_account_credentials(account)

        # Save to database
        result = create_or_update_account(engine, account)

        # Return account with validation info
        return {
            **result.dict(),
            "validation": validation_result,
        }

    except AccountValidationError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid account credentials: {str(e)}",
        )
```

### Optional: Skip Validation Flag

Allow skipping validation for automated processes:

```python
class AccountCreate(BaseModel):
    account_id: str
    airbnb_cookie: str
    # ... other fields ...
    skip_validation: bool = False  # Optional flag

@router.post("/accounts", status_code=201)
async def create_account(account: AccountCreate):
    if not account.skip_validation:
        validation_result = validate_account_credentials(account)
    else:
        validation_result = {"valid": "skipped"}
    # ...
```

### Implementation Steps

1. Create `sync_airbnb/services/account_validation.py`
2. Add `validate_account_credentials()` function
3. Update `create_account()` endpoint to validate
4. Add `AccountValidationError` exception
5. Update `AccountCreate` schema with optional `skip_validation`
6. Add tests for validation (valid, invalid, no listings)
7. Update API documentation
8. Add validation info to account response

### Testing Requirements

```python
from sync_airbnb.services.account_validation import validate_account_credentials, AccountValidationError

def test_validate_account_with_valid_credentials():
    """Test validation succeeds with valid credentials."""
    account = AccountCreate(
        account_id="123",
        airbnb_cookie="valid_cookie",
        # ... other fields ...
    )

    with patch.object(AirbnbSync, "fetch_listing_ids") as mock_fetch:
        mock_fetch.return_value = {"456": "Test Listing"}

        result = validate_account_credentials(account)

        assert result["valid"] is True
        assert result["listing_count"] == 1

def test_validate_account_with_invalid_credentials():
    """Test validation fails with invalid credentials."""
    account = AccountCreate(
        account_id="123",
        airbnb_cookie="invalid_cookie",
        # ... other fields ...
    )

    with patch.object(AirbnbSync, "fetch_listing_ids", side_effect=HTTPError("401 Unauthorized")):
        with pytest.raises(AccountValidationError, match="Invalid credentials"):
            validate_account_credentials(account)

def test_create_account_with_validation():
    """Test POST /accounts validates credentials."""
    with patch("sync_airbnb.services.account_validation.validate_account_credentials") as mock_validate:
        mock_validate.return_value = {"valid": True, "listing_count": 5}

        response = client.post("/api/v1/accounts", json={...})

        assert response.status_code == 201
        assert response.json()["validation"]["valid"] is True
        mock_validate.assert_called_once()

def test_create_account_with_invalid_credentials_returns_400():
    """Test POST /accounts returns 400 for invalid credentials."""
    with patch("sync_airbnb.services.account_validation.validate_account_credentials") as mock_validate:
        mock_validate.side_effect = AccountValidationError("Invalid cookie")

        response = client.post("/api/v1/accounts", json={...})

        assert response.status_code == 400
        assert "Invalid account credentials" in response.json()["detail"]
```

### Files to Create/Modify

- `sync_airbnb/services/account_validation.py` (create)
- `sync_airbnb/api/routes/accounts.py` (modify)
- `sync_airbnb/schemas/account.py` (add skip_validation field)
- `tests/services/test_account_validation.py` (create)
- `tests/api/test_accounts.py` (add validation tests)

### Dependencies

- None (uses existing AirbnbSync)

### Related Issues

- Issue 10 (rate limiting - validation makes API call)

---

## Issue 13: Missing Index Consistency

**Priority:** P1 - HIGH
**Severity:** Performance
**Impact:** Slow queries on large datasets (>1M rows)
**Status:** Open
**Estimated Effort:** 2-3 hours

### Current State

Migration creates some indexes but missing key ones:

```sql
-- Existing indexes (from migration)
CREATE INDEX idx_chart_query_account_listing ON airbnb.chart_query(account_id, airbnb_listing_id);
CREATE INDEX idx_chart_summary_account_listing ON airbnb.chart_summary(account_id, airbnb_listing_id);
```

Missing indexes for common query patterns:

1. **Filter by active accounts**: `SELECT * FROM accounts WHERE is_active = true`
2. **Filter by customer**: `SELECT * FROM accounts WHERE customer_id = ?`
3. **Date range queries**: `SELECT * FROM chart_query WHERE metric_date BETWEEN ? AND ?`
4. **Recent syncs**: `SELECT * FROM accounts ORDER BY last_sync_at DESC`

### Impact

Without proper indexes:
- List accounts by customer: Table scan (slow with 1000+ accounts)
- Active accounts query: Table scan
- Date range queries: Sequential scan on time-series data
- Dashboard queries: Timeout on large datasets

### Recommended Solution

Add missing indexes via Alembic migration:

```python
# alembic/versions/xxx_add_missing_indexes.py
def upgrade() -> None:
    # Accounts table indexes
    op.create_index(
        "idx_accounts_is_active",
        "accounts",
        ["is_active"],
        schema="airbnb",
    )

    op.create_index(
        "idx_accounts_customer_id",
        "accounts",
        ["customer_id"],
        schema="airbnb",
    )

    op.create_index(
        "idx_accounts_last_sync_at",
        "accounts",
        ["last_sync_at"],
        schema="airbnb",
    )

    # Metrics table indexes for date range queries
    op.create_index(
        "idx_chart_query_metric_date",
        "chart_query",
        ["metric_date"],
        schema="airbnb",
    )

    op.create_index(
        "idx_chart_summary_window_start",
        "chart_summary",
        ["window_start"],
        schema="airbnb",
    )

    op.create_index(
        "idx_list_of_metrics_window_start",
        "list_of_metrics",
        ["window_start"],
        schema="airbnb",
    )

    # Composite index for common query pattern (account + date range)
    op.create_index(
        "idx_chart_query_account_date",
        "chart_query",
        ["account_id", "metric_date"],
        schema="airbnb",
    )

def downgrade() -> None:
    op.drop_index("idx_chart_query_account_date", schema="airbnb")
    op.drop_index("idx_list_of_metrics_window_start", schema="airbnb")
    op.drop_index("idx_chart_summary_window_start", schema="airbnb")
    op.drop_index("idx_chart_query_metric_date", schema="airbnb")
    op.drop_index("idx_accounts_last_sync_at", schema="airbnb")
    op.drop_index("idx_accounts_customer_id", schema="airbnb")
    op.drop_index("idx_accounts_is_active", schema="airbnb")
```

### Performance Impact

Before indexes:
```sql
EXPLAIN SELECT * FROM accounts WHERE is_active = true;
-- Seq Scan on accounts (cost=0.00..35.50 rows=10)
```

After indexes:
```sql
EXPLAIN SELECT * FROM accounts WHERE is_active = true;
-- Index Scan using idx_accounts_is_active (cost=0.15..8.17 rows=10)
```

### Implementation Steps

1. Analyze common query patterns in application code
2. Create migration with missing indexes
3. Test migration on development database
4. Measure query performance before/after with EXPLAIN ANALYZE
5. Apply migration to production during low-traffic window
6. Monitor query performance after deployment
7. Document index strategy

### Testing Requirements

```sql
-- Test that indexes are created
SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'airbnb'
ORDER BY indexname;

-- Should include:
-- idx_accounts_is_active
-- idx_accounts_customer_id
-- idx_accounts_last_sync_at
-- idx_chart_query_metric_date
-- idx_chart_summary_window_start
-- idx_list_of_metrics_window_start
-- idx_chart_query_account_date

-- Test query performance
EXPLAIN ANALYZE
SELECT * FROM airbnb.accounts WHERE is_active = true;
-- Should use Index Scan, not Seq Scan

EXPLAIN ANALYZE
SELECT * FROM airbnb.chart_query
WHERE account_id = '123' AND metric_date BETWEEN '2025-01-01' AND '2025-12-31';
-- Should use idx_chart_query_account_date
```

### Files to Create

- `alembic/versions/xxx_add_missing_indexes.py` (migration)

### Dependencies

- None

### Related Issues

- None

---

## Summary

These 8 P1 issues represent major reliability and operational concerns that should be resolved before production deployment.

**Priority Order:**
1. Issue 8 - Thread safety (data corruption risk)
2. Issue 9 - Per-listing error recovery (data loss risk)
3. Issue 10 - Rate limiting (service stability)
4. Issue 12 - Account validation (user experience)
5. Issue 7 - Job observability (operations)
6. Issue 6 - Type safety (code quality)
7. Issue 13 - Missing indexes (performance)
8. Issue 11 - Stale entry point (confusion)

**Total Effort:** 34-49 hours (~5-7 days for one developer)

**Dependencies:** Should complete P0 issues first (especially authentication and failing tests).
