# Claude Code Instructions for sync-airbnb

**Purpose:** Instructions for future Claude Code sessions working on this project
**Last Updated:** October 21, 2025

---

## First Steps for New Sessions

### 1. Read These Documents First (in order)

1. **README.md** - Project overview and setup instructions
2. **docs/2025-10-context.md** - October 2025 refactoring session context (what was built)
3. **docs/ARCHITECTURE.md** - High-level system architecture
4. **docs/implementation-status.md** - Current state, known issues, production readiness
5. **CONTRIBUTING.md** - Code standards and development workflow

**Time to read:** ~30 minutes

**Why these?** Understanding the architecture and recent changes prevents duplicate work and misunderstandings.

---

### 2. Check Current Issues Status

Before starting ANY work, check:

1. **P0 Critical Issues** - `tasks/p0-critical.md` (5 issues, 10-18 hours)
2. **P1 High Priority** - `tasks/p1-high.md` (8 issues, 34-49 hours)
3. **P2 Medium Priority** - `tasks/p2-medium.md` (8 issues, 25-37 hours)
4. **P3 Low Priority** - `tasks/p3-low.md` (7 issues, 19-29 hours)

**Ask user which priority level to focus on** before implementing anything.

---

### 3. Understand Current State

```bash
# Check git status
git status

# Check which branch you're on
git branch

# See recent commits
git log --oneline -10

# Check if tests are passing
pytest --collect-only

# Check for import errors
python -c "import sync_airbnb"
```

---

## Project Overview (Quick Reference)

### What This Project Does

sync-airbnb extracts Airbnb insights data (metrics, conversions, visibility) via private GraphQL endpoints and stores it in a TimescaleDB database with multi-account support.

**Key Features:**
- Multi-account architecture (database-driven)
- RESTful API for account management
- Scheduled background jobs (daily sync at 5:00 UTC)
- Intelligent backfill (25 weeks first run, 1 week subsequent)
- Per-listing error recovery
- Docker containerization

**Tech Stack:**
- FastAPI, Uvicorn, SQLAlchemy, Alembic, APScheduler
- PostgreSQL + TimescaleDB
- Python 3.10+

---

## Architecture Patterns (Must Follow)

### 1. Layered Architecture

**ALWAYS** follow this call flow:

```
main.py → api/routes/ → services/ → (network/, payloads/, flatteners/, parsers/) → db/ → PostgreSQL
```

**NEVER:**
- Call `db/` directly from `api/routes/` (use `services/` layer)
- Put business logic in API routes
- Make HTTP calls outside `network/` layer
- Skip layers

### 2. Separation of Concerns

Each layer has ONE responsibility:

| Layer | Responsibility | Can Do | Cannot Do |
|-------|---------------|--------|-----------|
| `api/routes/` | HTTP endpoints | Validate requests, return responses | Business logic, DB calls |
| `services/` | Orchestration | Coordinate workflows, business logic | Parse HTTP responses |
| `network/` | HTTP communication | Make API requests, retries | Transform data, store in DB |
| `payloads/` | GraphQL builders | Build query payloads | Make HTTP calls |
| `flatteners/` | Transform responses | Flatten nested JSON | Make API calls |
| `parsers/` | Pivot data | Transform row format | Make API calls |
| `db/` | Database operations | Run SQL queries | Business logic |

### 3. Dependency Injection

**ALWAYS** pass dependencies as parameters:

```python
# GOOD
def save_metrics(engine: Engine, account_id: str, metrics: list[dict]):
    with engine.begin() as conn:
        ...

# BAD (global dependency)
def save_metrics(account_id: str, metrics: list[dict]):
    with global_engine.begin() as conn:  # Avoid this
        ...
```

**Exception:** `config.engine` is acceptable as module-level global.

---

## Common Tasks

### Task: Add a New API Endpoint

1. **Define Pydantic schema** in `sync_airbnb/schemas/`
2. **Create route** in `sync_airbnb/api/routes/`
3. **Implement service function** in `sync_airbnb/services/`
4. **Add database function** in `sync_airbnb/db/readers/` or `db/writers/`
5. **Write tests** in `tests/api/`
6. **Update OpenAPI docs** (add docstrings with examples)

**Example:**
```python
# 1. Schema (sync_airbnb/schemas/sync_job.py)
class SyncJobResponse(BaseModel):
    job_id: str
    status: str
    account_id: str

# 2. Route (sync_airbnb/api/routes/sync_jobs.py)
@router.get("/sync-jobs/{job_id}", response_model=SyncJobResponse)
async def get_sync_job(job_id: str):
    """Get sync job status."""
    job = get_sync_job_by_id(engine, job_id)
    if not job:
        raise HTTPException(status_code=404)
    return job

# 3. Service function (if needed for complex logic)
# 4. Database function (sync_airbnb/db/readers/sync_jobs.py)
def get_sync_job_by_id(engine: Engine, job_id: str) -> SyncJob | None:
    with engine.connect() as conn:
        stmt = select(SyncJob).where(SyncJob.job_id == job_id)
        result = conn.execute(stmt)
        row = result.fetchone()
        if row:
            return SyncJob(**dict(row._mapping))
        return None

# 5. Test (tests/api/test_sync_jobs.py)
def test_get_sync_job_returns_job():
    response = client.get(f"/api/v1/sync-jobs/{job_id}")
    assert response.status_code == 200
```

---

### Task: Add a New Database Table

1. **Create SQLAlchemy model** in `sync_airbnb/models/`
2. **Generate migration** with `alembic revision --autogenerate -m "description"`
3. **Review migration** (check types, indexes, constraints)
4. **Add TimescaleDB hypertable** if time-series (manually in migration)
5. **Apply migration** with `alembic upgrade head`
6. **Test rollback** with `alembic downgrade -1` then `alembic upgrade head`
7. **Create reader/writer functions** in `sync_airbnb/db/`

**Example:**
```python
# 1. Model (sync_airbnb/models/sync_job.py)
from sqlalchemy import Column, String, DateTime, Integer
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class SyncJob(Base):
    __tablename__ = "sync_jobs"
    __table_args__ = {"schema": "airbnb"}

    job_id = Column(String(36), primary_key=True)
    account_id = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False)
    created_at = Column(DateTime, nullable=False)

# 2. Generate migration
# $ alembic revision --autogenerate -m "add sync_jobs table"

# 3. Review migration (alembic/versions/xxx_add_sync_jobs_table.py)
def upgrade() -> None:
    op.create_table(
        'sync_jobs',
        sa.Column('job_id', sa.String(36), nullable=False),
        sa.Column('account_id', sa.String(255), nullable=False),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('job_id'),
        schema='airbnb'
    )

    # 4. Add indexes (manual)
    op.create_index('idx_sync_jobs_account', 'sync_jobs', ['account_id'], schema='airbnb')

# 5. Apply
# $ alembic upgrade head

# 6. Test rollback
# $ alembic downgrade -1
# $ alembic upgrade head
```

---

### Task: Fix Failing Tests

**Current state:** 15 tests failing due to import path refactoring.

**Steps:**
1. Run `pytest -v` to see failures
2. Fix import paths in test files:
   ```python
   # OLD (broken)
   from network.http_client import make_request
   @patch("network.http_client.requests.post")

   # NEW (correct)
   from sync_airbnb.network.http_client import make_request
   @patch("sync_airbnb.network.http_client.requests.post")
   ```
3. Run tests again: `pytest -v`
4. If still failing, check for missing fixtures or mock paths

**See:** `tasks/p0-critical.md` Issue 2 for details.

---

### Task: Add New Metric to Sync

1. **Identify GraphQL query** (ChartQuery or ListOfMetricsQuery)
2. **Add metric to METRIC_QUERIES** in `sync_airbnb/services/insights.py`
3. **Update flattener** in `sync_airbnb/flatteners/insights.py`
4. **Update parser** in `sync_airbnb/parsers/insights.py`
5. **Add database column** via Alembic migration
6. **Update tests** in `tests/flatteners/` and `tests/parsers/`

---

## Testing Requirements

### Before ANY commit:

```bash
# 1. Run tests
pytest

# 2. Check coverage (should be >80%)
pytest --cov=sync_airbnb --cov-report=term-missing

# 3. Type checking
mypy sync_airbnb/

# 4. Linting
ruff check .

# 5. Format code
ruff format .
```

### Test Standards

- **Unit tests:** Mock all external dependencies (API calls, DB)
- **Integration tests:** Real database (test schema), mocked APIs
- **Test naming:** `test_<function>_<scenario>_<expected>`
- **Coverage:** >80% overall, >90% for core modules

**Example:**
```python
def test_create_account_with_valid_data_returns_201():
    """Test creating account with valid credentials."""
    response = client.post("/api/v1/accounts", json={...})
    assert response.status_code == 201
    assert response.json()["account_id"] == "123"

def test_create_account_with_invalid_cookie_returns_400():
    """Test creating account with invalid credentials fails."""
    response = client.post("/api/v1/accounts", json={...})
    assert response.status_code == 400
```

---

## What NOT to Do

### 1. DO NOT Create Unnecessary Files

- **DO NOT** create documentation files unless explicitly requested
- **DO NOT** create README files in subdirectories
- **DO NOT** create example files or templates
- **ALWAYS** prefer editing existing files over creating new ones

### 2. DO NOT Use Emojis

- **DO NOT** add emojis to logs (breaks JSON parsers)
- **DO NOT** add emojis to comments or docstrings
- **ONLY** use emojis if user explicitly requests them

See `tasks/p2-medium.md` Issue 14 for details.

### 3. DO NOT Hardcode Secrets

- **DO NOT** hardcode API keys, passwords, tokens
- **ALWAYS** use environment variables
- **ALWAYS** add to `.env.example` with placeholder values

See `tasks/p0-critical.md` Issues 4 and 5 for details.

### 4. DO NOT Skip Authentication

- **DO NOT** create endpoints without authentication
- **ALWAYS** add `Security(verify_api_key)` dependency
- **Exception:** Health check endpoint can be public

See `tasks/p0-critical.md` Issue 1 for details.

### 5. DO NOT Use Print Statements

- **DO NOT** use `print()` in production code
- **ALWAYS** use `logger.info()`, `logger.error()`, etc.
- **ALWAYS** include context in logs (account_id, request_id, etc.)

### 6. DO NOT Break Layered Architecture

- **DO NOT** call database directly from API routes
- **DO NOT** put business logic in HTTP client
- **DO NOT** skip the service layer
- **ALWAYS** follow: `api → services → (network/flatteners/parsers) → db`

### 7. DO NOT Use Bare Except

```python
# BAD
try:
    do_something()
except:  # NEVER do this
    pass

# GOOD
try:
    do_something()
except ValueError as e:
    logger.error(f"Invalid value: {e}", exc_info=True)
    raise
```

### 8. DO NOT Create Multiple Entry Points

- **DO NOT** create standalone scripts that bypass `main.py`
- **ALWAYS** use `uvicorn sync_airbnb.main:app` as entry point
- **Exception:** Migration scripts, one-off admin tools

See `tasks/p1-high.md` Issue 11 for details.

---

## Development Workflow

### Starting Work

1. **Read relevant documentation** (ARCHITECTURE.md, implementation-status.md)
2. **Check current branch:** `git branch`
3. **Pull latest:** `git pull origin main`
4. **Create feature branch:** `git checkout -b feature/your-feature`
5. **Set up environment:**
   ```bash
   make venv
   source venv/bin/activate
   docker-compose up -d postgres
   alembic upgrade head
   python create_account.py
   ```

### Making Changes

1. **Write tests first** (optional but recommended)
2. **Implement feature** following architecture patterns
3. **Run tests:** `pytest`
4. **Check types:** `mypy sync_airbnb/`
5. **Lint:** `ruff check .`
6. **Format:** `ruff format .`

### Committing

1. **Stage changes:** `git add .`
2. **Commit with descriptive message:**
   ```bash
   git commit -m "Add job status tracking API

   - Create sync_jobs table with status tracking
   - Add GET /api/v1/sync-jobs/{job_id} endpoint
   - Update run_insights_poller to create/update jobs
   - Add tests for job tracking (90% coverage)

   Fixes P1 Issue 7"
   ```

### Testing Locally

```bash
# Start service
uvicorn sync_airbnb.main:app --reload

# Test health check
curl http://localhost:8000/health

# Test API
curl http://localhost:8000/api/v1/accounts

# Trigger manual sync
curl -X POST http://localhost:8000/api/v1/accounts/123/sync

# Check logs
docker-compose logs -f app
```

---

## Production Readiness Checklist

Before deploying to production, ensure:

### Security
- [ ] API authentication implemented (P0-1)
- [ ] Secrets moved to environment variables (P0-4)
- [ ] .env file removed from git history (P0-5)
- [ ] Input validation on all endpoints
- [ ] HTTPS enforced

### Reliability
- [ ] All tests passing (P0-2)
- [ ] JSON schema validation (P0-3)
- [ ] Graceful shutdown implemented (P1-8)
- [ ] Per-listing error recovery (P1-9)
- [ ] Rate limiting configured (P1-10)

### Observability
- [ ] Job status tracking (P1-7)
- [ ] Structured logging (no emojis)
- [ ] Request ID tracking (P2-18)
- [ ] Metrics instrumentation
- [ ] Health check verifies DB and scheduler

### Performance
- [ ] Database connection pool tuned (P2-15)
- [ ] Missing indexes added (P1-13)
- [ ] Query performance tested

---

## Common Questions

### Q: How do I run the service locally?

```bash
# Option 1: Direct (for development)
make venv
source venv/bin/activate
docker-compose up -d postgres
alembic upgrade head
python create_account.py
uvicorn sync_airbnb.main:app --reload

# Option 2: Docker (for testing containerization)
docker-compose up -d
docker-compose logs -f app
```

### Q: How do I create a new database migration?

```bash
# 1. Modify model in sync_airbnb/models/
# 2. Generate migration (ALWAYS use autogenerate)
alembic revision --autogenerate -m "add sync_jobs table"

# 3. Review generated file in alembic/versions/
# 4. Apply migration
alembic upgrade head

# 5. Test rollback
alembic downgrade -1
alembic upgrade head
```

### Q: How do I add a new API endpoint?

See "Common Tasks" → "Add a New API Endpoint" above.

### Q: Where should business logic go?

**Services layer** (`sync_airbnb/services/`).

API routes should be thin and delegate to services.

### Q: How do I test my changes?

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/api/test_accounts.py

# Run specific test
pytest tests/api/test_accounts.py::test_create_account

# Run with coverage
pytest --cov=sync_airbnb --cov-report=html
```

### Q: What's the difference between MODE=admin, worker, and hybrid?

- **admin**: Only runs account management API (no scheduler)
- **worker**: Only runs scheduler for single account (requires ACCOUNT_ID)
- **hybrid**: Runs both API and scheduler (for local dev)

See `docs/ARCHITECTURE.md` → "Service Modes" for details.

### Q: How do I handle errors in the service layer?

```python
import logging

logger = logging.getLogger(__name__)

def run_insights_poller(account: Account) -> dict:
    """Run insights sync with error handling."""
    results = {"succeeded": 0, "failed": 0, "errors": []}

    for listing_id in listings:
        try:
            # Process listing
            process_listing(listing_id)
            results["succeeded"] += 1

        except Exception as e:
            # Log error with context
            logger.error(
                f"Listing {listing_id} failed",
                extra={"listing_id": listing_id, "error": str(e)},
                exc_info=True
            )
            results["failed"] += 1
            results["errors"].append({
                "listing_id": listing_id,
                "error": str(e)
            })
            # Continue to next listing
            continue

    return results
```

---

## Quick Reference Links

- **Main entry point:** `sync_airbnb/main.py`
- **Configuration:** `sync_airbnb/config.py`
- **Account CRUD:** `sync_airbnb/api/routes/accounts.py`
- **Sync orchestration:** `sync_airbnb/services/insights.py`
- **Scheduler:** `sync_airbnb/services/scheduler.py`
- **Database models:** `sync_airbnb/models/`
- **Database operations:** `sync_airbnb/db/readers/`, `sync_airbnb/db/writers/`
- **Migrations:** `alembic/versions/`

---

## Summary

When starting a new session:

1. ✅ Read documentation first (README, ARCHITECTURE, implementation-status)
2. ✅ Check current issues (tasks/p0-critical.md, p1-high.md, etc.)
3. ✅ Ask user which priority to focus on
4. ✅ Follow layered architecture strictly
5. ✅ Write tests for all changes
6. ✅ Do NOT create unnecessary files
7. ✅ Do NOT use emojis
8. ✅ Do NOT hardcode secrets
9. ✅ Do NOT skip authentication

**When in doubt, ask the user before implementing anything.**

Good luck! 🚀 (okay, emojis in CLAUDE.md are fine 😉)
