# sync-airbnb

A production-grade data pipeline for extracting, normalizing, and storing Airbnb insights via private GraphQL endpoints.

While the initial focus is on performance metrics (e.g. conversion rate, visibility, page views), the system is architected to support additional data types—such as reservations, payouts, listing content, guest messages, and reviews—via the same polling and ingestion framework.

Built for extensibility, testability, and deployment in modern environments like Render, Docker, or your own cron scheduler.

---

## ✅ What This Does

This system:

- Authenticates with Airbnb using session cookies and custom headers
- Pulls:
  - **Listing metadata** via `ListingsSectionQuery`
  - **Conversion metrics** via `ChartQuery` (e.g. impressions, conversion rate)
  - **Visibility metrics** via `ListOfMetricsQuery` (e.g. CTR, page views)
- Aligns query windows to **Sunday–Saturday weeks**
- Respects Airbnb's 180-day offset limit (+3-day adjustment)
- Normalizes raw JSON responses into structured rows
- Inserts data into a **Postgres + TimescaleDB schema**
- (Optional) Runs as a **daily cron job** in Docker

---

## 📁 Project Structure

```
sync_airbnb/
├── api/
│   └── routes/           # FastAPI REST endpoints (accounts, health, metrics)
├── services/             # Orchestration and business logic
├── db/
│   ├── readers/          # Database read operations
│   └── writers/          # Database write operations
├── models/               # SQLAlchemy ORM models
├── schemas/              # Pydantic validation schemas
├── network/              # HTTP client and Airbnb headers
├── payloads/             # GraphQL query builders
├── flatteners/           # Transform nested responses to flat rows
├── parsers/              # Pivot metrics from long to wide format
├── utils/                # Date windows, sync helpers, logging
├── dependencies.py       # FastAPI dependency injection
├── metrics.py            # Prometheus metrics definitions
├── config.py             # Environment configuration
└── main.py               # FastAPI application entry point

tests/                    # Unit and integration tests
alembic/                  # Database migrations
docs/                     # Architecture and reference documentation
tasks/                    # Implementation tasks and technical debt
```

---

## 🛠 How to Run

### Local Development

```bash
# Install dependencies
make venv
source venv/bin/activate

# Start PostgreSQL with TimescaleDB (with data persistence)
# If upgrading from old setup, remove old container first:
# docker stop sync_airbnb_db && docker rm sync_airbnb_db
docker-compose up -d postgres

# Run migrations
alembic upgrade head

# Create account in database (direct DB insert from .env)
python create_account.py

# Run the service with hot reload
uvicorn sync_airbnb.main:app --host 0.0.0.0 --port 8000 --reload
```

**Service Endpoints:**
- API Docs (Swagger): http://localhost:8000/docs
- API Docs (ReDoc): http://localhost:8000/redoc
- Health Check: http://localhost:8000/health
- Readiness Check: http://localhost:8000/health/ready
- Prometheus Metrics: http://localhost:8000/metrics
- Accounts API: http://localhost:8000/api/v1/accounts
- Postgres: localhost:5432

**Database Persistence:**
- Data stored in `pgdata` Docker volume (survives container restarts)
- To reset database: `docker-compose down -v` (removes volumes)

**Scheduler:**
- Runs daily at 5:00 UTC (1 AM EDT / 12 AM EST)
- First run: Backfills 25 weeks of data
- Subsequent runs: Fetches last 1 week
- Updates `last_sync_at` after successful sync

### Service Modes

Set `MODE` in `.env`:
- `MODE=hybrid` (default) - Runs API + scheduler (local dev)
- `MODE=admin` - Only account management API
- `MODE=worker` - Only scheduler (requires `ACCOUNT_ID`)

### Docker (Optional - for containerized dev environment)

```bash
# Start all services (postgres + app)
# Migrations and account creation run automatically via entrypoint.sh
docker-compose up -d

# View logs
docker-compose logs -f app
```

**Notes:**
- Hot reload enabled - code changes auto-restart the app
- `entrypoint.sh` runs migrations and creates account from env vars on startup (dev convenience)
- **Production deployment** uses different approach:
  - Admin API manages accounts (POST /api/v1/accounts)
  - Migrations run as separate K8s Job (not in worker pods)
  - Workers only read accounts, never create them

---

## 🧪 Tests

```bash
make test           # Run all tests
make lint           # Ruff lint
make format         # Black formatting
make clean          # Clear .pyc, .pytest_cache, .ruff_cache, etc
```

> Tests use mocking to avoid hitting the live Airbnb API.

---

## 🐳 Docker (e.g. for Render)

```Dockerfile
CMD ["python", "-m", "pollers.insights"]
```

---

## ✅ Multi-Account Support

The service now supports multiple Airbnb accounts with a container-per-customer architecture:

### Current Architecture
- **Account Management API**: CRUD operations for accounts
- **Worker Mode**: Each container syncs one account (`MODE=worker`, `ACCOUNT_ID=xxx`)
- **Hybrid Mode**: Combined API + scheduler for local dev (`MODE=hybrid`)
- **Intelligent Backfill**: First run fetches 25 weeks, subsequent runs fetch 1 week
- **Scheduled Sync**: Runs daily at 8 AM Eastern (12:00 UTC)
- **Database Schema**: All metrics tables have `account_id` foreign keys

### Production Deployment (Kubernetes Operator Pattern)

**Future implementation** will use a Kubernetes Operator for automated worker pod management:

1. **Admin API** (`MODE=admin`):
   - Manages accounts via REST API
   - Creates account records in database
   - NO direct Kubernetes API access (security)

2. **Kubernetes Operator** (separate service):
   - Watches `accounts` table for `is_active=true`
   - **Validates account credentials** before pod creation
   - Creates worker Deployment with `ACCOUNT_ID` and `MODE=worker`
   - Scoped ServiceAccount (only deployment CRUD permissions)
   - Handles scaling, updates, and cleanup

3. **Worker Pods** (auto-created):
   - Start with `ACCOUNT_ID` from environment
   - Startup sync runs in **background thread** (non-blocking)
   - Check `last_sync_at` on startup: If NULL, run immediate sync (backfill)
   - Configure scheduler for daily syncs
   - Self-contained, no cross-pod communication

**Readiness Probe Configuration:**
Worker pods run startup sync in background to avoid blocking the main process. Configure readiness probe to ensure pod is ready for scheduled syncs:

```yaml
readinessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 10
  timeoutSeconds: 5
  successThreshold: 1
  failureThreshold: 3
```

**Future Enhancement:** Add sync status to `/health` endpoint to check if initial sync is complete:
```json
{
  "status": "healthy",
  "mode": "worker",
  "account_id": "310316675",
  "initial_sync_complete": true
}
```

**Security Benefits:**
- Admin API breach ≠ cluster breach
- Database is single source of truth
- Operator has minimal, scoped permissions
- Account validation before resource creation
- Audit trail of all pod creations

---

## 🔌 API Endpoints

The service exposes a RESTful API for account management and metrics access:

### Account Management

- **`POST /api/v1/accounts`** - Create or update an account
- **`GET /api/v1/accounts`** - List all accounts (non-deleted)
- **`GET /api/v1/accounts/{account_id}`** - Get single account details
- **`PATCH /api/v1/accounts/{account_id}`** - Update account credentials or settings
- **`DELETE /api/v1/accounts/{account_id}`** - Soft delete account (sets `deleted_at`)
- **`POST /api/v1/accounts/{account_id}/restore`** - Restore soft-deleted account
- **`POST /api/v1/accounts/{account_id}/sync`** - Trigger manual sync for account

### Metrics

- **`GET /api/v1/accounts/{account_id}/metrics/export`** - Export metrics in CSV/JSON format
  - Query parameters: `start_date`, `end_date`, `format` (csv|json)

### Health & Monitoring

- **`GET /health`** - Basic health check (always returns 200)
- **`GET /health/ready`** - Readiness check with database connectivity test
- **`GET /metrics`** - Prometheus metrics endpoint

### Documentation

- **`GET /docs`** - Interactive API documentation (Swagger UI)
- **`GET /redoc`** - Alternative API documentation (ReDoc)

All endpoints return JSON except `/metrics` (Prometheus text format) and `/metrics/export` (CSV/JSON based on query param).

---

## 📊 Observability & Monitoring

The service includes comprehensive Prometheus metrics for monitoring and observability:

### Metrics Endpoints

- **`GET /metrics`** - Prometheus metrics in text format
- **`GET /health`** - Basic health check (always returns 200)
- **`GET /health/ready`** - Readiness check with database connectivity test

### Instrumented Components

**HTTP Metrics:**
- Request counts by method, endpoint, and status code
- Request duration histograms
- API error rates

**Database Metrics:**
- Query duration by operation and table
- Active connections gauge
- Query counts and error rates
- Metrics insert operations (rows/sec, duration)

**Sync Job Metrics:**
- Total sync jobs by account and trigger type (manual, scheduled, startup)
- Sync job duration histograms by status (success, partial_failure)
- Active sync jobs gauge
- Listings processed (success/failure counts per account)

**Airbnb API Metrics:**
- Request duration by endpoint
- Request counts by endpoint and status code
- Retry attempts by endpoint
- Rate limit hits

**Error Tracking:**
- Total errors by type and component (api, db, sync, network)
- Auth errors, network errors, database errors

### Prometheus Configuration Example

```yaml
scrape_configs:
  - job_name: 'sync-airbnb'
    static_configs:
      - targets: ['sync-airbnb:8000']
    metrics_path: '/metrics'
    scrape_interval: 15s
```

### Dependency Injection Pattern

All API routes use FastAPI dependency injection for better testability:

```python
from fastapi import Depends
from sync_airbnb.dependencies import get_db_engine

@router.get("/accounts")
async def list_accounts(engine: Engine = Depends(get_db_engine)):
    accounts = get_all_accounts(engine)
    return accounts
```

---

## ⚠️ Still In Progress

- [ ] JSON Schema validation for all flattener outputs
- [ ] Proper dry-run guard in services (used for CI or first-time testing)

---

## 🧠 Dev Notes

- All Airbnb GraphQL metrics use +3 day offset for `relativeDsStart` and `relativeDsEnd`
- `ChartQuery` = weekly windows (28 days)
- `ListOfMetricsQuery` = daily snapshots (7-day lookback to 180-day forward)
- Use `AirbnbSync.parse_all()` to get 3 tables:
  - `chart_query`
  - `chart_summary`
  - `list_of_metrics`
