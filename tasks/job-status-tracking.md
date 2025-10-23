# Task: Job Status Tracking

**Priority:** P1 - HIGH
**Estimated Effort:** 3-4 hours
**Status:** Not Started

---

## Problem

No visibility into sync job status:
- Cannot tell if sync is running, completed, or failed
- No progress tracking for long-running syncs
- Cannot debug failed syncs (no error details)
- Manual sync endpoint returns immediately but no way to check status
- Scheduled jobs have no audit trail

---

## Solution

Create `sync_jobs` table to track all sync operations with status, progress, and error details.

### Implementation Steps

1. **Create database migration** (`alembic revision -m "add sync_jobs table"`):
   ```python
   def upgrade():
       op.create_table(
           'sync_jobs',
           sa.Column('job_id', sa.String(36), primary_key=True),
           sa.Column('account_id', sa.String(255), nullable=False),
           sa.Column('job_type', sa.String(50), nullable=False),  # 'manual', 'scheduled', 'startup'
           sa.Column('status', sa.String(50), nullable=False),  # 'running', 'completed', 'failed'
           sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
           sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
           sa.Column('total_listings', sa.Integer(), nullable=True),
           sa.Column('succeeded_listings', sa.Integer(), nullable=True),
           sa.Column('failed_listings', sa.Integer(), nullable=True),
           sa.Column('error_message', sa.Text(), nullable=True),
           sa.Column('error_details', sa.JSON(), nullable=True),
           sa.ForeignKeyConstraint(['account_id'], ['airbnb.accounts.account_id']),
           schema='airbnb'
       )
       op.create_index('idx_sync_jobs_account', 'sync_jobs', ['account_id'], schema='airbnb')
       op.create_index('idx_sync_jobs_status', 'sync_jobs', ['status'], schema='airbnb')
       op.create_index('idx_sync_jobs_started_at', 'sync_jobs', ['started_at'], schema='airbnb')
   ```

2. **Create SQLAlchemy model** (`sync_airbnb/models/sync_job.py`):
   ```python
   class SyncJob(Base):
       __tablename__ = "sync_jobs"
       __table_args__ = {"schema": "airbnb"}

       job_id = Column(String(36), primary_key=True)
       account_id = Column(String(255), ForeignKey("airbnb.accounts.account_id"))
       job_type = Column(String(50), nullable=False)
       status = Column(String(50), nullable=False)
       started_at = Column(DateTime(timezone=True), nullable=False)
       completed_at = Column(DateTime(timezone=True), nullable=True)
       total_listings = Column(Integer, nullable=True)
       succeeded_listings = Column(Integer, nullable=True)
       failed_listings = Column(Integer, nullable=True)
       error_message = Column(Text, nullable=True)
       error_details = Column(JSON, nullable=True)
   ```

3. **Create database functions** (`sync_airbnb/db/writers/sync_jobs.py`):
   ```python
   def create_sync_job(engine: Engine, account_id: str, job_type: str) -> str:
       """Create new sync job and return job_id."""
       job_id = str(uuid.uuid4())
       # Insert job with status='running'
       return job_id

   def update_sync_job_progress(engine: Engine, job_id: str, total: int, succeeded: int, failed: int):
       """Update job progress."""
       # Update counts

   def complete_sync_job(engine: Engine, job_id: str, results: dict):
       """Mark job as completed with results."""
       # Set status='completed', completed_at, final counts

   def fail_sync_job(engine: Engine, job_id: str, error: str, details: dict):
       """Mark job as failed with error details."""
       # Set status='failed', completed_at, error_message, error_details
   ```

4. **Update insights service** (`sync_airbnb/services/insights.py`):
   ```python
   def run_insights_poller(account: Account, job_type: str = "manual") -> dict:
       # Create job at start
       job_id = create_sync_job(engine, account.account_id, job_type)

       try:
           results = {"total": 0, "succeeded": 0, "failed": 0, "errors": []}

           # Process listings...
           for listing in listings:
               try:
                   # Process listing
                   results["succeeded"] += 1
               except Exception as e:
                   results["failed"] += 1
                   results["errors"].append(...)

           # Mark job as completed
           complete_sync_job(engine, job_id, results)
           return results

       except Exception as e:
           # Mark job as failed
           fail_sync_job(engine, job_id, str(e), {"traceback": ...})
           raise
   ```

5. **Create API endpoints** (`sync_airbnb/api/routes/sync_jobs.py`):
   ```python
   @router.get("/sync-jobs/{job_id}")
   async def get_sync_job(job_id: str):
       """Get sync job status."""
       job = get_sync_job_by_id(engine, job_id)
       if not job:
           raise HTTPException(status_code=404)
       return job

   @router.get("/accounts/{account_id}/sync-jobs")
   async def list_sync_jobs(account_id: str, limit: int = 50, offset: int = 0):
       """List sync jobs for account."""
       jobs = get_sync_jobs_by_account(engine, account_id, limit, offset)
       return jobs
   ```

6. **Update manual sync endpoint** (return job_id):
   ```python
   @router.post("/accounts/{account_id}/sync")
   async def trigger_sync(account_id: str):
       # Start sync in background thread
       job_id = start_sync_job(account)
       return {"message": "Sync initiated", "job_id": job_id}
   ```

7. **Create Pydantic schemas** (`sync_airbnb/schemas/sync_job.py`):
   ```python
   class SyncJobResponse(BaseModel):
       job_id: str
       account_id: str
       job_type: str
       status: str
       started_at: datetime
       completed_at: datetime | None
       total_listings: int | None
       succeeded_listings: int | None
       failed_listings: int | None
       error_message: str | None
       error_details: dict | None
   ```

---

## Files to Create/Modify

- `alembic/versions/xxx_add_sync_jobs_table.py` (create migration)
- `sync_airbnb/models/sync_job.py` (create)
- `sync_airbnb/db/writers/sync_jobs.py` (create)
- `sync_airbnb/db/readers/sync_jobs.py` (create)
- `sync_airbnb/schemas/sync_job.py` (create)
- `sync_airbnb/api/routes/sync_jobs.py` (create)
- `sync_airbnb/services/insights.py` (update to create/update jobs)
- `sync_airbnb/services/scheduler.py` (update to pass job_type='scheduled')
- `sync_airbnb/main.py` (register sync_jobs router)
- `tests/db/test_sync_jobs.py` (create)
- `tests/api/test_sync_jobs.py` (create)

---

## Acceptance Criteria

- [ ] sync_jobs table created with all fields
- [ ] Job created when sync starts
- [ ] Job updated with progress during sync
- [ ] Job marked completed/failed when sync finishes
- [ ] GET /sync-jobs/{job_id} returns job status
- [ ] GET /accounts/{account_id}/sync-jobs lists jobs
- [ ] POST /accounts/{account_id}/sync returns job_id
- [ ] Error details stored in JSON column
- [ ] Tests pass for all scenarios
- [ ] OpenAPI docs updated

---

## Benefits

- **Monitoring**: See which syncs are running/completed
- **Debugging**: Access error messages and details for failed syncs
- **Audit Trail**: Track all sync operations over time
- **Progress**: Know how many listings processed
- **Async Status**: Check status of manual sync after triggering

---

## Future Enhancements

- Real-time progress updates (WebSocket)
- Retry failed jobs
- Job cancellation
- Job scheduling UI
- Prometheus metrics from job data
