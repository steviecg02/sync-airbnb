# Claude Instructions for sync-airbnb

**Purpose:** Constraints, standards, and reference documentation for AI assistants working on this project.

---

## What This Project Does

sync-airbnb extracts Airbnb insights data (metrics, conversions, visibility) via private GraphQL endpoints and stores it in a TimescaleDB database with multi-account support.

**Tech Stack:** FastAPI, Uvicorn, SQLAlchemy, Alembic, APScheduler, PostgreSQL + TimescaleDB, Prometheus, Python 3.10+

**Key Features:**
- Multi-account support with database-driven configuration
- FastAPI dependency injection pattern (`Depends(get_db_engine)`)
- Comprehensive Prometheus metrics (HTTP, DB, sync jobs, Airbnb API)
- Health endpoints (`/health`, `/health/ready`, `/metrics`)
- Validation helper functions for DRY code
- Per-listing error recovery
- Intelligent backfill (25 weeks first run, 1 week subsequent)

---

## Key Documentation

Read these to understand the project:

- **README.md** - Setup and quick start
- **docs/ARCHITECTURE.md** - System design and data flow
- **docs/codebase-standards-checklist.md** - Standards we adhere to (use for cross-repo consistency)
- **CONTRIBUTING.md** - Code standards and testing requirements
- **tasks/*.md** - Individual task files for remaining work

---

## Architecture Constraints (MUST FOLLOW)

### 1. Layered Architecture

**Call flow:**
```
main.py → api/routes/ → services/ → (network/, payloads/, flatteners/, parsers/) → db/ → PostgreSQL
```

**Each layer's responsibility:**

| Layer | Responsibility | Can Do | Cannot Do |
|-------|---------------|--------|-----------|
| `api/routes/` | HTTP endpoints | Validate requests, return responses | Business logic, DB calls |
| `services/` | Orchestration | Coordinate workflows, business logic | Parse HTTP responses |
| `network/` | HTTP communication | Make API requests, retries | Transform data, store in DB |
| `payloads/` | GraphQL builders | Build query payloads | Make HTTP calls |
| `flatteners/` | Transform responses | Flatten nested JSON | Make API calls |
| `parsers/` | Pivot data | Transform row format | Make API calls |
| `db/` | Database operations | Run SQL queries | Business logic |

**Never skip layers. Never call database directly from API routes.**

### 2. Dependency Injection

Pass dependencies as parameters:

```python
# GOOD
def save_metrics(engine: Engine, account_id: str, metrics: list[dict]):
    with engine.begin() as conn:
        ...

# BAD - avoid globals
def save_metrics(account_id: str, metrics: list[dict]):
    with global_engine.begin() as conn:  # Don't do this
        ...
```

**Exception:** `config.engine` is acceptable as module-level global.

---

## Code Standards (MUST FOLLOW)

### Security

- ❌ **Never hardcode secrets** - Use environment variables
- ❌ **Never commit .env files** - Add to .gitignore
- ✅ **Always validate inputs** - Use Pydantic field validators
- ✅ **Use API authentication** - All endpoints except `/health`

### Type Safety

- ✅ **Type annotate all functions** - Use mypy
- ✅ **Use `Type | None` not `Optional[Type]`** - Python 3.10+ syntax
- ✅ **Add None checks** - Before accessing optional values

### Error Handling

- ❌ **Never use bare `except:`** - Use specific exception types
- ✅ **Log with context** - Include account_id, listing_id, request_id
- ✅ **Per-item error recovery** - One failure doesn't break entire batch
- ✅ **Structured errors** - `{"error": {"code", "message", "details", "request_id"}}`

### Database

- ✅ **Connection pooling** - `pool_pre_ping=True`, `pool_recycle=3600`
- ✅ **Indexes on foreign keys** - And columns used in WHERE clauses
- ✅ **Soft delete** - Use `deleted_at` timestamp, don't hard delete user data
- ✅ **Test migrations** - Both upgrade and downgrade paths

### Datetime Handling

- ❌ **Never use `datetime.now()` or `datetime.utcnow()`**
- ✅ **Always use `utc_now()`** - From `sync_airbnb.utils.datetime_utils`
- ✅ **Always timezone-aware** - `datetime.now(timezone.utc)`
- ✅ **Always store in UTC** - Database columns use `DateTime(timezone=True)`

### Logging

- ❌ **Never use `print()`** - Use `logger.info/error/warning`
- ❌ **Never use emoji in logs** - Breaks JSON parsers
- ✅ **Include context** - account_id, listing_id, request_id
- ✅ **Log at appropriate level** - ERROR for failures, INFO for milestones

### API Design

- ✅ **OpenAPI documentation** - Comprehensive docs with examples
- ✅ **Paginate lists** - Default 50, max 100 items
- ✅ **Version URLs** - `/api/v1/...`
- ✅ **Request ID tracking** - Via middleware, in response headers

### Testing

- ✅ **Run before committing** - `pytest`, `mypy`, `ruff check`, `ruff format`
- ✅ **Mock external dependencies** - APIs, database in unit tests
- ✅ **Aim for >80% coverage** - >90% for core modules
- ✅ **Update imports after refactoring** - Use `sync_airbnb.*` package paths

### Threading

- ❌ **Never use `daemon=True` for data operations**
- ✅ **Implement graceful shutdown** - Signal handlers, thread tracking
- ✅ **Non-daemon threads** - Track in list, join with timeout on shutdown

---

## What NOT to Do

### File Creation

- ❌ **Don't create unnecessary files** - Especially documentation
- ❌ **Don't create README files in subdirectories**
- ❌ **Don't create example/template files**
- ✅ **Always prefer editing existing files** - Over creating new ones

### Emoji Usage

- ❌ **Don't add emoji to logs** - Breaks JSON log parsers
- ❌ **Don't add emoji to comments/docstrings**
- ✅ **Only use emoji if user explicitly requests**

### Architecture Violations

- ❌ **Don't call database from API routes** - Use services layer
- ❌ **Don't put business logic in HTTP client**
- ❌ **Don't skip the service layer**
- ❌ **Don't create multiple entry points** - Use `main.py` only

### Error Handling

- ❌ **Don't use bare `except:`** - Catches too much
- ❌ **Don't silence errors** - Always log, never `pass`
- ❌ **Don't lose context** - Include account_id, listing_id in logs

---

## Quick Reference

### Entry Point
- **Main:** `sync_airbnb/main.py`

### Configuration
- **Config:** `sync_airbnb/config.py`
- **Environment:** `.env` (not committed), `.env.example` (committed)

### API Routes
- **Accounts:** `sync_airbnb/api/routes/accounts.py`
- **Metrics:** `sync_airbnb/api/routes/metrics.py`
- **Health:** `sync_airbnb/api/routes/health.py`

### Services
- **Sync orchestration:** `sync_airbnb/services/insights.py`
- **Scheduler:** `sync_airbnb/services/scheduler.py`

### Database
- **Models:** `sync_airbnb/models/`
- **Readers:** `sync_airbnb/db/readers/`
- **Writers:** `sync_airbnb/db/writers/`
- **Migrations:** `alembic/versions/`

### Data Pipeline
- **HTTP client:** `sync_airbnb/network/http_client.py`
- **Payloads:** `sync_airbnb/payloads/insights.py`
- **Flatteners:** `sync_airbnb/flatteners/insights.py`
- **Parsers:** `sync_airbnb/parsers/insights.py`

### Utilities
- **Datetime:** `sync_airbnb/utils/datetime_utils.py`
- **Date windows:** `sync_airbnb/utils/date_window.py`
- **Airbnb sync:** `sync_airbnb/utils/airbnb_sync.py`

### New Modules (Added October 2025)
- **Dependencies:** `sync_airbnb/dependencies.py` - FastAPI dependency injection (e.g., `get_db_engine()`)
- **Validation Helpers:** `sync_airbnb/api/routes/_helpers.py` - DRY validation functions (`validate_account_exists`, `validate_date_range`)
- **Metrics:** `sync_airbnb/metrics.py` - Prometheus metric definitions (20+ metrics across all layers)

---

## Service Modes

Controlled by `MODE` environment variable:

- **admin** - API only (account management), no scheduler
- **worker** - Scheduler only (requires `ACCOUNT_ID`), no API
- **hybrid** - Both API and scheduler (for local dev)

---

## Testing Commands

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=sync_airbnb --cov-report=term-missing

# Type checking
mypy sync_airbnb/

# Linting
ruff check .

# Format code
ruff format .

# Run all checks
make test  # or pytest && mypy sync_airbnb/ && ruff check .
```

---

## Database Commands

```bash
# Create migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Show current revision
alembic current
```

---

## Git Workflow

```bash
# Check status
git status

# Create feature branch
git checkout -b feature/your-feature

# Commit with descriptive message
git commit -m "Add feature X

- Detailed change 1
- Detailed change 2

Fixes issue Y"
```

---

## Common Patterns

### Error Handling in Services

```python
def run_insights_poller(account: Account) -> dict:
    results = {"succeeded": 0, "failed": 0, "errors": []}

    for listing_id in listings:
        try:
            process_listing(listing_id)
            results["succeeded"] += 1
        except Exception as e:
            logger.error(
                f"Listing {listing_id} failed",
                extra={"listing_id": listing_id, "error": str(e)},
                exc_info=True
            )
            results["failed"] += 1
            results["errors"].append({"listing_id": listing_id, "error": str(e)})
            continue  # Don't break entire sync

    return results
```

### Database Transactions

```python
# Read (no transaction needed)
def get_account(engine: Engine, account_id: str) -> Account | None:
    with engine.connect() as conn:
        stmt = select(Account).where(Account.account_id == account_id)
        result = conn.execute(stmt)
        ...

# Write (use begin() for auto-commit)
def create_account(engine: Engine, account: AccountCreate) -> Account:
    with engine.begin() as conn:  # Auto-commits on success
        stmt = insert(Account).values(...)
        result = conn.execute(stmt)
        ...
```

### API Endpoints

```python
@router.post(
    "/resource",
    response_model=ResourceResponse,
    status_code=201,
    summary="Short description",
    description="Long description with examples",
    responses={
        201: {"description": "Success", "content": {"application/json": {"example": {...}}}},
        400: {"description": "Bad request", "content": {"application/json": {"example": {...}}}},
    },
)
async def create_resource(resource: ResourceCreate = Body(..., example={...})):
    """Create resource."""
    result = service_function(config.engine, resource)
    return ResourceResponse.model_validate(result)
```

---

## Files to Keep Updated

When making changes, update these if relevant:

- **ARCHITECTURE.md** - If architecture changes
- **codebase-standards-checklist.md** - If adding new standards
- **README.md** - If setup process changes
- **CLAUDE.md** (this file) - If constraints/patterns change

---

## Summary

- **Read:** ARCHITECTURE.md, codebase-standards-checklist.md
- **Follow:** Layered architecture, type safety, structured errors
- **Never:** Hardcode secrets, use bare except, skip layers, add emoji to logs
- **Always:** Test before commit, log with context, use timezone-aware datetimes
- **Ask:** If unclear on architecture or standards

When in doubt, ask the user before implementing!
