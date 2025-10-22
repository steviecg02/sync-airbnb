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
.
├── pollers/              # Entry points (main.py) and orchestration logic
├── services/             # Role-specific orchestration (e.g. insights poller)
├── utils/                # Date logic, logging, sync helpers
├── network/              # HTTP client and Airbnb headers
├── payloads/             # GraphQL query payload builders
├── flatteners/           # Converts raw Airbnb responses into clean rows
├── db/                   # SQLAlchemy models + inserts
├── schemas/              # JSON schema validation (in progress)
├── tests/                # Unit + integration tests
├── config.py             # Central settings: DB URL, log level, dry run
├── Dockerfile            # Image for deployment
├── Makefile              # Developer commands
└── requirements.txt      # Python dependencies
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
- Health: http://localhost:8000/health
- API Docs: http://localhost:8000/docs
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
