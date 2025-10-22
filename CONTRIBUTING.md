# Contributing to sync-airbnb

This document defines code standards, architecture patterns, and development workflow for the sync-airbnb project.

---

## Table of Contents

1. [Development Environment Setup](#development-environment-setup)
2. [Code Standards](#code-standards)
3. [Architecture Patterns](#architecture-patterns)
4. [Testing Requirements](#testing-requirements)
5. [Development Workflow](#development-workflow)
6. [Database Migrations](#database-migrations)
7. [Make Commands Reference](#make-commands-reference)

---

## Development Environment Setup

### Prerequisites

- Python 3.10+
- Docker and Docker Compose
- PostgreSQL client (optional, for direct DB access)
- Git

### Initial Setup

#### Local Development
```bash
# 1. Clone repository
git clone https://github.com/yourusername/sync-airbnb.git
cd sync-airbnb

# 2. Create virtual environment
make venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy environment template
cp .env.example .env
# Edit .env with your credentials

# 5. Start PostgreSQL (with data persistence)
docker-compose up -d postgres

# 6. Run migrations
alembic upgrade head

# 7. Create account
python create_account.py

# 8. Run service
uvicorn sync_airbnb.main:app --host 0.0.0.0 --port 8000 --reload
```

#### Docker Development
```bash
# 1. Copy environment template
cp .env.example .env
# Edit .env with your credentials

# 2. Start all services (migrations + account creation automatic)
docker-compose up -d

# 3. View logs
docker-compose logs -f app

# 4. Access service
open http://localhost:8000/docs
```

### Environment Variables

Required in `.env` file:

```bash
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres

# Service Mode
MODE=hybrid                    # admin | worker | hybrid
ACCOUNT_ID=<your_account_id>   # Required for worker/hybrid modes

# Airbnb API Credentials (for worker/hybrid modes)
AIRBNB_COOKIE=<long cookie string>
X_AIRBNB_CLIENT_TRACE_ID=<uuid>
X_CLIENT_VERSION=<version>
USER_AGENT=Mozilla/5.0...

# Optional
LOG_LEVEL=INFO                 # DEBUG | INFO | WARNING | ERROR
DEBUG=false                    # Enable debug output
```

---

## Code Standards

### Type Hints (Required)

All functions **must** have complete type hints for parameters and return types.

```python
from __future__ import annotations  # Use for clean syntax
from typing import Any

# Good - complete type hints
def fetch_metrics(
    endpoint: str,
    account_id: str,
    days: int = 180
) -> list[dict[str, Any]]:
    """Fetch metrics from Airbnb GraphQL API."""
    ...

# Bad - missing type hints
def fetch_metrics(endpoint, account_id, days=180):
    ...
```

**Exceptions:**
- Test functions (type hints optional but encouraged)
- Private helper functions with obvious types

### Docstrings (Required - Google Style)

All **public** functions and classes need docstrings. Use Google style formatting.

```python
def process_metrics(
    raw_data: list[dict],
    customer_id: str | None = None
) -> list[dict]:
    """
    Process raw Airbnb metrics into structured format.

    Args:
        raw_data: Raw metrics from GraphQL API
        customer_id: Optional customer identifier for multi-tenant tagging

    Returns:
        List of normalized metric dictionaries ready for insertion

    Raises:
        ValueError: If raw_data is empty or malformed

    Example:
        >>> raw = [{"date": "2025-01-01", "value": 100}]
        >>> process_metrics(raw, "cust_123")
        [{"date": "2025-01-01", "value": 100, "customer_id": "cust_123"}]
    """
    if not raw_data:
        raise ValueError("raw_data cannot be empty")
    ...
```

**Required Sections:**
- Description (first line + optional detailed explanation)
- `Args:` - All parameters with descriptions
- `Returns:` - Return value description
- `Raises:` (if applicable) - Exceptions that can be raised
- `Example:` (optional) - Usage example with expected output

### Code Formatting

Use `ruff format` for automatic formatting:

```bash
# Format all files
ruff format .

# Check formatting without modifying
ruff format --check .
```

**Style Rules:**
- Line length: 100 characters (configured in pyproject.toml)
- Indentation: 4 spaces (never tabs)
- Quotes: Double quotes preferred
- Trailing commas: Required in multi-line collections

### Function Design

#### Single Responsibility Principle

Each function should do **ONE** thing. If your function name contains "and", it's likely doing too much.

```python
# Good - single responsibility
def fetch_listings(headers: dict[str, str]) -> dict[str, str]:
    """Fetch listing IDs from Airbnb API."""
    ...

def process_listings(listings: dict[str, str]) -> list[dict]:
    """Transform listing data into database format."""
    ...

# Bad - multiple responsibilities
def fetch_and_process_listings(headers: dict[str, str]) -> list[dict]:
    """Fetch listings from API and transform to database format."""
    # Doing too much!
    ...
```

#### Complexity Limits

- **Cyclomatic complexity:** < 10 (ruff will check)
- **Function length:** < 50 lines (if longer, refactor into smaller functions)
- **Nesting depth:** Max 3 levels (use early returns to reduce nesting)

```python
# Good - low nesting, early returns
def process_metric(data: dict) -> dict | None:
    if not data:
        return None

    if "value" not in data:
        logger.warning("Missing value field")
        return None

    if not validate(data):
        logger.error("Validation failed")
        return None

    return normalize_metric(data)

# Bad - deep nesting
def process_metric(data: dict) -> dict | None:
    if data:
        if "value" in data:
            if validate(data):
                return normalize_metric(data)
            else:
                logger.error("Validation failed")
        else:
            logger.warning("Missing value field")
    return None
```

### Error Handling

Always catch **specific exceptions**, never bare `except:`.

```python
import requests
import logging

logger = logging.getLogger(__name__)

# Good - specific exceptions, logging, re-raise
def fetch_data(endpoint: str) -> dict:
    try:
        response = requests.get(endpoint, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.Timeout as e:
        logger.error("API timeout", extra={"endpoint": endpoint, "error": str(e)})
        raise
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            logger.warning("Resource not found", extra={"endpoint": endpoint})
            return {}
        logger.error("HTTP error", extra={"endpoint": endpoint, "status": e.response.status_code})
        raise
    except Exception as e:
        logger.error("Unexpected error", extra={"endpoint": endpoint, "error": str(e)}, exc_info=True)
        raise

# Bad - bare except, silent failure
def fetch_data(endpoint: str) -> dict:
    try:
        response = requests.get(endpoint)
        return response.json()
    except:  # Don't do this
        pass  # Or this
```

**Rules:**
- Catch specific exceptions (ValueError, HTTPError, etc.)
- Log errors with context (endpoint, account_id, etc.)
- Use `exc_info=True` for tracebacks in ERROR logs
- Never silently swallow exceptions
- Re-raise if you can't handle the error

### Logging Standards

Use Python `logging` module. **Never use `print()` in production code.**

```python
import logging

logger = logging.getLogger(__name__)

# Good - structured logging with context
logger.info(
    "Sync completed",
    extra={
        "account_id": account_id,
        "records": len(metrics),
        "duration_seconds": elapsed,
    }
)

# Log errors with full context
logger.error(
    "Sync failed",
    extra={
        "account_id": account_id,
        "endpoint": endpoint,
        "error": str(e),
    },
    exc_info=True  # Include traceback
)

# Bad - print statements
print(f"Sync completed for {account_id}")  # Don't do this
```

**Log Levels:**
- `DEBUG` - Detailed information for diagnosing problems
- `INFO` - General informational messages (sync started/completed, etc.)
- `WARNING` - Something unexpected but not an error (missing optional field, etc.)
- `ERROR` - Error occurred but application can continue
- `CRITICAL` - Serious error, application may not be able to continue

**Note:** Avoid emojis in production logs (breaks JSON parsers and log aggregation tools).

---

## Architecture Patterns

### Layered Structure

The codebase follows a strict layered architecture:

```
sync_airbnb/
├── main.py                    # Entry point (FastAPI app)
├── api/
│   └── routes/                # REST API endpoints
├── services/
│   └── insights.py            # Orchestration layer (coordinates other layers)
├── network/
│   ├── http_client.py         # HTTP requests with retries
│   └── http_headers.py        # Header construction
├── payloads/
│   └── insights.py            # GraphQL payload builders
├── flatteners/
│   └── insights.py            # Transform GraphQL responses
├── parsers/
│   └── insights.py            # Pivot metrics into wide format
├── db/
│   ├── readers/               # Database read operations
│   └── writers/               # Database write operations
├── models/                    # SQLAlchemy ORM models
├── schemas/                   # Pydantic schemas (API contracts)
└── utils/                     # Shared utilities
```

### Call Flow

```
main.py (FastAPI app)
  ↓
services/insights.py           # Orchestration
  ↓
network/http_client.py         # Fetch data from Airbnb
  ↓
flatteners/insights.py         # Transform GraphQL response
  ↓
parsers/insights.py            # Pivot into wide format
  ↓
db/writers/insights.py         # Insert to database
```

**Rules:**
- `main.py` is the ONLY entry point
- `services/` orchestrates all other layers
- Each layer has ONE responsibility
- Never skip layers (e.g., don't call `db/` directly from `main.py`)

### Separation of Concerns

Each module has a **single, well-defined responsibility**:

| Layer | Responsibility | What It Does | What It Doesn't Do |
|-------|---------------|--------------|-------------------|
| **services/** | Orchestration | Coordinates other layers, handles business logic | No HTTP calls, no SQL |
| **network/** | HTTP communication | Makes API requests, retries, timeout handling | No data transformation, no DB access |
| **payloads/** | Request construction | Builds GraphQL payloads | No API calls |
| **flatteners/** | Response transformation | Extracts data from GraphQL responses | No API calls, no DB access |
| **parsers/** | Data pivoting | Transforms rows into wide format | No API calls, no DB access |
| **db/** | Data persistence | Reads/writes to database | No HTTP calls, no data transformation |

**Example - Good Separation:**
```python
# services/insights.py (orchestration)
def run_insights_poller(account: Account) -> None:
    headers = build_headers(account.airbnb_cookie, ...)  # network layer
    poller = AirbnbSync(headers=headers)                 # network layer
    listings = poller.fetch_listing_ids()                 # network layer

    for listing_id in listings:
        poller.poll_range_and_flatten(listing_id, ...)   # network + flatteners
        parsed = poller.parse_all()                       # parsers

        insert_chart_query_rows(engine, parsed["chart_query"])  # db layer

    update_last_sync(engine, account.account_id)        # db layer
```

### Dependency Injection

Pass dependencies as function parameters, don't use globals.

```python
# Good - dependencies injected
def save_metrics(engine: Engine, account_id: str, metrics: list[dict]) -> None:
    with engine.begin() as conn:
        stmt = insert(Metrics).values(metrics)
        conn.execute(stmt)

# Bad - global dependency
global_engine = create_engine(DATABASE_URL)

def save_metrics(account_id: str, metrics: list[dict]) -> None:
    with global_engine.begin() as conn:  # Avoid this
        ...
```

**Exceptions:**
- `config.engine` is a module-level global (acceptable - configuration)
- Constants (LOOKBACK_WEEKS, MAX_LOOKBACK_DAYS, etc.)

### Multi-Account Patterns

#### Account Management

All metrics tables have an `account_id` foreign key:

```python
# Always add account_id to metric rows
for row in parsed_chunks["chart_query"]:
    row["account_id"] = account.account_id

insert_chart_query_rows(engine, parsed_chunks["chart_query"])
```

#### Dynamic Headers

Build headers from account credentials:

```python
from sync_airbnb.network.http_headers import build_headers

headers = build_headers(
    airbnb_cookie=account.airbnb_cookie,
    x_client_version=account.x_client_version,
    x_airbnb_client_trace_id=account.x_airbnb_client_trace_id,
    user_agent=account.user_agent,
)

poller = AirbnbSync(scrape_day=date.today(), headers=headers)
```

#### First-Run Detection

Check `last_sync_at` to determine backfill window:

```python
is_first_run = account.last_sync_at is None
window_start, window_end = get_poll_window(is_first_run=is_first_run, today=scrape_day)
```

---

## Testing Requirements

### Coverage Standards

**Minimum Coverage:**
- Overall: 80%
- Core modules (services/, db/): 90%
- API routes: 80%

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=sync_airbnb --cov-report=html

# Run specific module
pytest tests/services/

# Run with specific marker
pytest -m unit
pytest -m integration
```

### Test Organization

Use pytest markers to categorize tests:

```python
import pytest

@pytest.mark.unit
def test_fetch_listings_success(mock_requests):
    """Test successful listing fetch."""
    # Fast, isolated, all dependencies mocked
    ...

@pytest.mark.integration
def test_insert_metrics_with_real_db(test_engine):
    """Test metric insertion with real database."""
    # Real DB (test schema), mocked external APIs
    ...

@pytest.mark.e2e
def test_full_sync_workflow():
    """Test complete sync workflow end-to-end."""
    # Full workflow, minimal mocking
    ...
```

### Writing Tests

#### Test Naming

Use descriptive names following pattern: `test_<function>_<scenario>_<expected>`

```python
# Good - descriptive names
def test_fetch_metrics_when_api_timeout_then_retry():
    ...

def test_process_metrics_with_empty_list_returns_empty():
    ...

# Bad - vague names
def test_fetch():
    ...

def test_error():
    ...
```

#### Test Structure (Arrange-Act-Assert)

```python
def test_insert_chart_query_with_duplicate_then_upsert():
    # Arrange - set up test data
    engine = create_test_engine()
    rows = [
        {"account_id": "123", "listing_id": "456", "metric_date": date(2025, 1, 1), ...}
    ]

    # Act - execute function under test
    insert_chart_query_rows(engine, rows)
    insert_chart_query_rows(engine, rows)  # Duplicate insert

    # Assert - verify expected outcome
    with engine.connect() as conn:
        result = conn.execute(select(ChartQuery)).fetchall()
        assert len(result) == 1  # Upsert, not duplicate
```

#### Test Happy Path AND Error Cases

```python
# Test successful case
def test_fetch_listings_success():
    mock_response = Mock()
    mock_response.json.return_value = {"listings": [...]}
    with patch("requests.post", return_value=mock_response):
        result = fetch_listings()
        assert len(result) > 0

# Test error case
def test_fetch_listings_when_timeout_then_retry():
    with patch("requests.post", side_effect=requests.Timeout):
        with pytest.raises(requests.Timeout):
            fetch_listings()
```

### Test Fixtures

Use pytest fixtures for common setup:

```python
import pytest
from sqlalchemy import create_engine

@pytest.fixture
def test_engine():
    """Create test database engine."""
    engine = create_engine("postgresql://localhost/test_db")
    # Setup schema
    yield engine
    # Teardown
    engine.dispose()

@pytest.fixture
def sample_account():
    """Create sample account for testing."""
    return Account(
        account_id="123",
        airbnb_cookie="test_cookie",
        is_active=True,
        last_sync_at=None,
    )

# Use in tests
def test_sync_with_account(test_engine, sample_account):
    run_insights_poller(sample_account)
    # ... assertions
```

---

## Development Workflow

### Starting a Feature

1. **Create a branch**
   ```bash
   git checkout -b feature/add-reservations-sync
   ```

2. **Plan the implementation**
   - Identify which layers need changes
   - Sketch out function signatures
   - Consider testing approach

3. **Write tests first** (optional but recommended)
   ```python
   # tests/services/test_reservations.py
   def test_sync_reservations_success():
       # Arrange, Act, Assert
       ...
   ```

4. **Implement the feature**
   - Follow architecture patterns
   - Add type hints and docstrings
   - Handle errors appropriately

5. **Run tests and type checking**
   ```bash
   pytest
   mypy sync_airbnb/
   ruff check .
   ```

6. **Commit with descriptive message**
   ```bash
   git commit -m "Add reservations sync poller

   - Implement ReservationsPoller in services/
   - Add GraphQL payload builder for reservations
   - Add flattener and parser for reservation data
   - Add database writer for reservations table
   - Tests included with 90% coverage"
   ```

### Pull Request Requirements

Before submitting a PR, ensure:

- [ ] All tests pass (`pytest`)
- [ ] Coverage maintained or improved (`pytest --cov`)
- [ ] Type checking passes (`mypy sync_airbnb/`)
- [ ] Linting passes (`ruff check .`)
- [ ] Code formatted (`ruff format .`)
- [ ] All functions have type hints
- [ ] All public functions have docstrings
- [ ] New features have tests (90% coverage)
- [ ] No print statements in production code
- [ ] Error handling follows standards

### Commit Message Format

Use conventional commits format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat:` - New feature
- `fix:` - Bug fix
- `refactor:` - Code refactoring (no functional changes)
- `test:` - Adding or updating tests
- `docs:` - Documentation changes
- `chore:` - Maintenance tasks (dependencies, config, etc.)

**Examples:**
```
feat(api): add account deletion endpoint

Implement DELETE /api/v1/accounts/{account_id} endpoint with
soft delete support. Foreign key constraints prevent deletion
if metrics exist.

Closes #42

---

fix(scheduler): correct UTC timezone handling

Scheduler was using system timezone instead of explicit UTC,
causing jobs to run at wrong times. Added timezone='UTC'
parameter to APScheduler job configuration.

Fixes #38
```

---

## Database Migrations

### Creating Migrations

**ALWAYS use autogenerate, NEVER write migrations manually.**

```bash
# 1. Make changes to models (sync_airbnb/models/)
# 2. Generate migration
alembic revision --autogenerate -m "add reservations table"

# 3. Review generated file
# Check: alembic/versions/<hash>_add_reservations_table.py

# 4. Apply migration
alembic upgrade head

# 5. Test downgrade (optional but recommended)
alembic downgrade -1
alembic upgrade head
```

### Migration Best Practices

1. **One logical change per migration**
   - Don't mix schema changes and data migrations
   - Keep migrations small and focused

2. **Review autogenerated migrations**
   - Check column types (String vs Text)
   - Verify indexes are created
   - Ensure constraints are correct

3. **Test migrations**
   ```bash
   # Test upgrade
   alembic upgrade head

   # Test downgrade
   alembic downgrade base
   alembic upgrade head
   ```

4. **Add TimescaleDB hypertables manually**
   Alembic doesn't auto-detect hypertables - add them manually:
   ```python
   def upgrade() -> None:
       # Autogenerated table creation
       op.create_table('reservations', ...)

       # Manually add hypertable
       op.execute("SELECT create_hypertable('airbnb.reservations', 'time', if_not_exists => TRUE)")
   ```

### TimescaleDB Considerations

- **Hypertables require `time` column** - Use DATE or TIMESTAMP type
- **Unique constraints must include `time`** - Required for TimescaleDB partitioning
- **Compression policies** - Add for tables > 90 days old (optional)
- **Retention policies** - Add to drop old data automatically (optional)

Example:
```python
# In migration after hypertable creation
op.execute("SELECT add_retention_policy('airbnb.metrics', INTERVAL '2 years')")
op.execute("SELECT add_compression_policy('airbnb.metrics', INTERVAL '90 days')")
```

---

## Make Commands Reference

```bash
# Setup
make venv              # Create virtual environment
make install           # Install dependencies
make dev-setup         # Full development setup (venv + install + pre-commit)

# Code Quality
make format            # Format code with ruff
make lint              # Run linting checks
make type-check        # Run mypy type checking
make test              # Run all tests
make test-cov          # Run tests with coverage report

# Database
make migrate           # Run pending migrations (alembic upgrade head)
make migrate-down      # Rollback last migration (alembic downgrade -1)
make migrate-create    # Create new migration (prompts for message)

# Docker
make docker-build      # Build Docker image
make docker-up         # Start all services (docker-compose up -d)
make docker-down       # Stop all services (docker-compose down)
make docker-logs       # View application logs (docker-compose logs -f app)

# Cleanup
make clean             # Remove cache files, virtual environment
make clean-db          # Stop containers and remove database volume
```

---

## Troubleshooting

### Import Errors in Tests

**Problem:** `ModuleNotFoundError: No module named 'sync_airbnb'`

**Solution:** Install package in editable mode:
```bash
pip install -e .
```

### Database Connection Refused

**Problem:** `Connection refused` when connecting to database

**Solution:**
1. Check Docker container is running: `docker ps`
2. Start database: `docker-compose up -d postgres`
3. Verify DATABASE_URL in .env matches container settings

### Tests Failing with Import Errors

**Problem:** Tests use incorrect import paths (e.g., `patch("network.http_client...")`)

**Solution:** Use full import path with package prefix:
```python
# Bad
@patch("network.http_client.requests.post")

# Good
@patch("sync_airbnb.network.http_client.requests.post")
```

### Type Checking Errors

**Problem:** `mypy` reports type errors

**Solution:**
1. Add type hints to function signatures
2. Use `from __future__ import annotations` for clean syntax
3. Add `# type: ignore` comments only as last resort (with explanation)

### Alembic Can't Detect Model Changes

**Problem:** `alembic revision --autogenerate` generates empty migration

**Solution:**
1. Ensure models import in `alembic/env.py`
2. Check `target_metadata` is set correctly
3. Verify model uses correct schema (`__table_args__ = {"schema": "airbnb"}`)

---

## Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [TimescaleDB Documentation](https://docs.timescale.com/)
- [APScheduler Documentation](https://apscheduler.readthedocs.io/)
- [Pytest Documentation](https://docs.pytest.org/)
- [Ruff Documentation](https://docs.astral.sh/ruff/)

---

## Questions?

If you have questions about these standards or need clarification:
1. Check existing code for examples
2. Review [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for high-level patterns
3. Check [docs/implementation-status.md](docs/implementation-status.md) for current state
4. Review [docs/2025-10-context.md](docs/2025-10-context.md) for recent changes
5. Open a GitHub issue for discussion
