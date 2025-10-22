# sync-airbnb Architecture

**Version:** 1.0.0
**Last Updated:** October 21, 2025

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Component Architecture](#component-architecture)
3. [Multi-Account Architecture](#multi-account-architecture)
4. [Service Modes](#service-modes)
5. [Data Flow](#data-flow)
6. [Scheduler Design](#scheduler-design)
7. [Database Schema](#database-schema)
8. [Production Deployment (K8s Operator Pattern)](#production-deployment-k8s-operator-pattern)
9. [Key Design Decisions](#key-design-decisions)
10. [Security Considerations](#security-considerations)
11. [Scalability Considerations](#scalability-considerations)

---

## System Overview

sync-airbnb is a production-grade data pipeline for extracting, normalizing, and storing Airbnb insights data via private GraphQL endpoints. The system supports multiple Airbnb accounts with container-per-account architecture for horizontal scalability.

### Core Capabilities

- **Multi-account support**: Manage multiple Airbnb accounts independently
- **Intelligent backfill**: First run fetches 25 weeks, subsequent runs fetch 1 week
- **Scheduled syncs**: Daily automatic sync at 5:00 UTC
- **Per-listing error recovery**: One listing failure doesn't break entire sync
- **TimescaleDB storage**: Efficient time-series data storage with automatic partitioning
- **RESTful API**: Full CRUD operations for account management

### Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Web Framework** | FastAPI | REST API endpoints |
| **ASGI Server** | Uvicorn | Production web server |
| **Database** | PostgreSQL + TimescaleDB | Time-series data storage |
| **ORM/Query Builder** | SQLAlchemy 2.0 | Database abstraction |
| **Migrations** | Alembic | Schema versioning |
| **Scheduler** | APScheduler | Background job scheduling |
| **HTTP Client** | Requests | Airbnb API communication |
| **Containerization** | Docker | Deployment packaging |

---

## Component Architecture

### Layered Architecture

The system follows a strict layered architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────┐
│                         main.py                              │
│                    (FastAPI Application)                     │
└─────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      api/routes/                             │
│            (HTTP Endpoints, Request/Response)                │
└─────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      services/                               │
│            (Orchestration, Business Logic)                   │
└─────────────────────────────────────────────────────────────┘
                              ▼
┌───────────────┬──────────────┬──────────────┬───────────────┐
│   network/    │  payloads/   │ flatteners/  │   parsers/    │
│ (HTTP Client) │  (GraphQL)   │ (Transform)  │  (Pivoting)   │
└───────────────┴──────────────┴──────────────┴───────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                          db/                                 │
│                 (Database Operations)                        │
│         ┌──────────────┬──────────────────┐                 │
│         │  readers/    │    writers/      │                 │
│         │  (SELECT)    │  (INSERT/UPDATE) │                 │
│         └──────────────┴──────────────────┘                 │
└─────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              PostgreSQL + TimescaleDB                        │
└─────────────────────────────────────────────────────────────┘
```

### Layer Responsibilities

#### 1. API Layer (`api/routes/`)

**Purpose:** HTTP endpoint definitions, request/response handling

**Responsibilities:**
- Define REST endpoints
- Validate request payloads (Pydantic)
- Return formatted responses
- Handle HTTP errors

**Does NOT:**
- Contain business logic
- Make database calls directly
- Make HTTP calls to external APIs

**Example:**
```python
@router.post("/accounts", status_code=201)
async def create_account(account: AccountCreate):
    """Create account - delegates to service layer."""
    result = create_or_update_account(engine, account)
    return result
```

#### 2. Service Layer (`services/`)

**Purpose:** Orchestration of complex workflows

**Responsibilities:**
- Coordinate multiple operations
- Implement business logic
- Handle cross-cutting concerns (transactions, error recovery)
- Call other layers to complete workflows

**Does NOT:**
- Handle HTTP requests/responses
- Construct SQL queries
- Parse external API responses

**Example:**
```python
def run_insights_poller(account: Account) -> None:
    """Orchestrate full insights sync workflow."""
    # 1. Build headers
    headers = build_headers(account.airbnb_cookie, ...)

    # 2. Create HTTP client
    poller = AirbnbSync(headers=headers)

    # 3. Fetch listings
    listings = poller.fetch_listing_ids()

    # 4. For each listing: poll → flatten → parse → insert
    for listing_id in listings:
        # Poll
        poller.poll_range_and_flatten(listing_id, ...)

        # Parse
        parsed = poller.parse_all()

        # Insert
        insert_chart_query_rows(engine, parsed["chart_query"])

    # 5. Update sync timestamp
    update_last_sync(engine, account.account_id)
```

#### 3. Network Layer (`network/`)

**Purpose:** HTTP communication with external APIs

**Responsibilities:**
- Make HTTP requests
- Handle retries and timeouts
- Build request headers
- Parse HTTP responses

**Does NOT:**
- Understand business logic
- Store data in database
- Transform data structures

#### 4. Payload Layer (`payloads/`)

**Purpose:** Build GraphQL query payloads

**Responsibilities:**
- Construct GraphQL queries
- Parameterize queries with variables
- Return query as dictionary

#### 5. Flattener Layer (`flatteners/`)

**Purpose:** Transform nested API responses into flat rows

**Responsibilities:**
- Extract data from GraphQL responses
- Flatten nested structures
- Map API fields to database columns

#### 6. Parser Layer (`parsers/`)

**Purpose:** Pivot metrics from long to wide format

**Responsibilities:**
- Group metrics by listing/date
- Pivot metric_name/metric_value into columns
- Prepare data for database insertion

#### 7. Database Layer (`db/`)

**Purpose:** All database operations

**Separated into:**
- `readers/` - SELECT queries only
- `writers/` - INSERT/UPDATE/DELETE queries only

**Responsibilities:**
- Execute SQL queries
- Handle transactions
- Map database rows to models

**Does NOT:**
- Contain business logic
- Make HTTP calls
- Transform data (except DB ↔ model mapping)

---

## Multi-Account Architecture

### Database-Driven Configuration

Accounts are stored in database (not environment variables):

```
┌───────────────────────────────────────────────────────────┐
│                    accounts table                         │
├───────────────────────────────────────────────────────────┤
│  account_id (PK)                                          │
│  airbnb_cookie (encrypted credential)                     │
│  x_airbnb_client_trace_id                                 │
│  x_client_version                                         │
│  user_agent                                               │
│  is_active (enable/disable account)                       │
│  last_sync_at (track sync history)                        │
│  customer_id (optional external reference)                │
│  created_at, updated_at                                   │
└───────────────────────────────────────────────────────────┘
                        ▼
┌───────────────────────────────────────────────────────────┐
│              Metrics Tables (all have FK)                 │
├───────────────────────────────────────────────────────────┤
│  chart_query.account_id → accounts.account_id             │
│  chart_summary.account_id → accounts.account_id           │
│  list_of_metrics.account_id → accounts.account_id         │
└───────────────────────────────────────────────────────────┘
```

### Container-Per-Account Pattern

Each account runs in its own container (worker pod):

```
┌──────────────────────────────────────────────────────────────┐
│                     PostgreSQL Database                      │
│  ┌────────────┬────────────┬────────────┬────────────┐      │
│  │ Account 1  │ Account 2  │ Account 3  │ Account 4  │      │
│  └────────────┴────────────┴────────────┴────────────┘      │
└──────────────────────────────────────────────────────────────┘
        ▲              ▲              ▲              ▲
        │              │              │              │
┌───────┴───┐  ┌───────┴───┐  ┌───────┴───┐  ┌───────┴───┐
│ Worker 1  │  │ Worker 2  │  │ Worker 3  │  │ Worker 4  │
│ MODE=     │  │ MODE=     │  │ MODE=     │  │ MODE=     │
│ worker    │  │ worker    │  │ worker    │  │ worker    │
│ ACCOUNT_  │  │ ACCOUNT_  │  │ ACCOUNT_  │  │ ACCOUNT_  │
│ ID=123    │  │ ID=456    │  │ ID=789    │  │ ID=012    │
└───────────┘  └───────────┘  └───────────┘  └───────────┘
```

**Benefits:**
- **Isolation**: One account failure doesn't affect others
- **Scaling**: Add capacity by adding workers
- **Resource limits**: Per-account CPU/memory limits
- **Independent schedules**: Different sync times per account
- **Simpler code**: No multi-threading complexity

**Drawbacks:**
- More containers to manage
- Slightly higher resource overhead
- Requires orchestration (Kubernetes operator)

---

## Service Modes

The application supports three deployment modes via `MODE` environment variable:

### Mode 1: Admin (`MODE=admin`)

**Purpose:** Account management API only

**Use Case:** Dedicated admin service for customer-facing API

**What Runs:**
- FastAPI application
- Account CRUD endpoints
- Health check endpoint

**What Does NOT Run:**
- Scheduler
- Background sync jobs

**Environment Variables:**
```bash
MODE=admin
DATABASE_URL=postgresql://...
API_KEY=secret  # For authentication
```

**Kubernetes Deployment:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sync-airbnb-admin
spec:
  replicas: 2  # Can scale horizontally
  template:
    spec:
      containers:
        - name: admin
          env:
            - name: MODE
              value: "admin"
```

---

### Mode 2: Worker (`MODE=worker`)

**Purpose:** Background sync for single account

**Use Case:** One worker per customer account

**What Runs:**
- Scheduler (daily sync at 5:00 UTC)
- Startup sync (if first run)
- Health check endpoint (for readiness probe)

**What Does NOT Run:**
- Account management API

**Environment Variables:**
```bash
MODE=worker
ACCOUNT_ID=310316675  # REQUIRED
DATABASE_URL=postgresql://...
```

**Kubernetes Deployment:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sync-airbnb-worker-310316675
spec:
  replicas: 1  # Should NOT scale (one per account)
  template:
    spec:
      containers:
        - name: worker
          env:
            - name: MODE
              value: "worker"
            - name: ACCOUNT_ID
              value: "310316675"
```

---

### Mode 3: Hybrid (`MODE=hybrid`)

**Purpose:** All-in-one for local development

**Use Case:** Local development, single-account deployments

**What Runs:**
- Account management API
- Scheduler
- Background sync jobs

**Environment Variables:**
```bash
MODE=hybrid  # Default if not specified
ACCOUNT_ID=310316675  # Required for scheduler
DATABASE_URL=postgresql://...
```

**Usage:**
```bash
# Local development
uvicorn sync_airbnb.main:app --reload
```

**NOT recommended for production** (use separate admin + workers).

---

## Data Flow

### Sync Workflow (End-to-End)

```
┌─────────────────────────────────────────────────────────────┐
│ 1. TRIGGER                                                  │
├─────────────────────────────────────────────────────────────┤
│  • Scheduled (5:00 UTC daily)                               │
│  • Manual (POST /api/v1/accounts/{id}/sync)                 │
│  • Startup (first run only)                                 │
└─────────────────────────────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. SERVICE LAYER (services/insights.py)                    │
├─────────────────────────────────────────────────────────────┤
│  • Get account from database                                │
│  • Determine date window (25 weeks or 1 week)               │
│  • Build HTTP headers from account credentials              │
│  • Create AirbnbSync poller instance                        │
└─────────────────────────────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. FETCH LISTINGS (network/http_client.py)                 │
├─────────────────────────────────────────────────────────────┤
│  • Build GraphQL payload (ListingsSectionQuery)             │
│  • POST to Airbnb API                                       │
│  • Parse response → {listing_id: listing_name}              │
└─────────────────────────────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. FOR EACH LISTING (per-listing error recovery)           │
├─────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────────────┐ │
│  │ 4a. POLL METRICS                                      │ │
│  ├───────────────────────────────────────────────────────┤ │
│  │  • Build GraphQL payloads (ChartQuery, ListOfMetrics) │ │
│  │  • POST to Airbnb API (one request per query type)    │ │
│  │  • Store raw responses in memory                      │ │
│  └───────────────────────────────────────────────────────┘ │
│                        ▼                                    │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ 4b. FLATTEN RESPONSES (flatteners/insights.py)        │ │
│  ├───────────────────────────────────────────────────────┤ │
│  │  • Extract data from nested GraphQL structure         │ │
│  │  • Flatten to list of dictionaries                    │ │
│  │  • Map API fields to database columns                 │ │
│  └───────────────────────────────────────────────────────┘ │
│                        ▼                                    │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ 4c. PARSE METRICS (parsers/insights.py)               │ │
│  ├───────────────────────────────────────────────────────┤ │
│  │  • Group by listing + date/window                     │ │
│  │  • Pivot metric_name/value into columns              │ │
│  │  • Add account_id to all rows                         │ │
│  └───────────────────────────────────────────────────────┘ │
│                        ▼                                    │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ 4d. INSERT TO DATABASE (db/writers/insights.py)       │ │
│  ├───────────────────────────────────────────────────────┤ │
│  │  • Upsert chart_query rows                            │ │
│  │  • Upsert chart_summary rows                          │ │
│  │  • Upsert list_of_metrics rows                        │ │
│  │  • Commit transaction                                 │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  IF ERROR: Log error, continue to next listing             │
└─────────────────────────────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. UPDATE LAST_SYNC_AT                                      │
├─────────────────────────────────────────────────────────────┤
│  • Update accounts.last_sync_at = NOW()                     │
│  • Used to determine first run vs subsequent runs           │
└─────────────────────────────────────────────────────────────┘
```

### Upsert Logic

All metrics tables use upsert (INSERT ... ON CONFLICT UPDATE):

```python
stmt = insert(ChartQuery).values(rows)
stmt = stmt.on_conflict_do_update(
    constraint="uq_chart_query_listing_metric_date",
    set_={c.name: c for c in stmt.excluded}
)
conn.execute(stmt)
```

**Unique Constraints:**
- `chart_query`: `(account_id, listing_id, metric_date, time)`
- `chart_summary`: `(account_id, listing_id, window_start, time)`
- `list_of_metrics`: `(account_id, listing_id, window_start, time)`

**Why `time` in constraint?**
- Tracks metric changes over multiple scrapes
- Allows "as-of" queries (what did metrics look like on specific scrape date)
- Required for TimescaleDB hypertables

---

## Scheduler Design

### APScheduler Configuration

```python
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = BackgroundScheduler(timezone="UTC")

scheduler.add_job(
    func=scheduled_sync_job,
    trigger=CronTrigger(hour=5, minute=0, timezone="UTC"),
    id="daily_sync",
    replace_existing=True,
)

scheduler.start()
```

### Schedule

**Daily at 5:00 UTC**
- 1:00 AM EDT (summer)
- 12:00 AM EST (winter)

**Why 5:00 UTC?**
- Catches overnight metric updates from Airbnb
- Low-traffic time for API
- Before business hours in US timezones

### Startup Sync Logic

On worker startup, check if this is first run:

```python
def run_sync_on_startup():
    """Run sync on startup if this is first sync for account."""
    account = get_account(engine, ACCOUNT_ID)

    # Check if first run
    if account and account.is_active and account.last_sync_at is None:
        logger.info("First sync for account, running startup sync...")

        # Run in background thread (non-blocking)
        thread = threading.Thread(
            target=run_insights_poller,
            args=(account,),
            daemon=True,
        )
        thread.start()

    else:
        logger.info("Not first run, waiting for scheduled sync")
```

**First Run Behavior:**
- `last_sync_at = NULL` → Fetch 25 weeks (backfill)
- `last_sync_at = <timestamp>` → Fetch 1 week (incremental)

### Date Window Calculation

```python
def get_poll_window(is_first_run: bool, today: date) -> tuple[date, date]:
    """Calculate date window for polling."""
    if is_first_run:
        # First run: 25 weeks lookback
        start = get_previous_sunday(today) - timedelta(weeks=25)
    else:
        # Subsequent runs: 1 week lookback
        start = get_previous_sunday(today) - timedelta(weeks=1)

    # Always include future weeks for booking data
    end = get_next_saturday(today) + timedelta(weeks=5)

    return (start, end)
```

**Key Points:**
- All windows align to Sunday-Saturday (Airbnb's weekly boundary)
- Always fetches future weeks (booking data)
- Uses +3 offset for Airbnb API quirk (Sunday = offset 3)

---

## Database Schema

### Schema: `airbnb`

All tables in dedicated schema for namespace isolation.

### Hypertables (TimescaleDB)

Three metrics tables are hypertables (time-series optimized):

```sql
SELECT create_hypertable('airbnb.chart_query', 'time', if_not_exists => TRUE);
SELECT create_hypertable('airbnb.chart_summary', 'time', if_not_exists => TRUE);
SELECT create_hypertable('airbnb.list_of_metrics', 'time', if_not_exists => TRUE);
```

**Benefits:**
- Automatic partitioning by time
- Faster time-range queries
- Compression policies (optional)
- Retention policies (optional)

### Table: `accounts`

```sql
CREATE TABLE airbnb.accounts (
    account_id VARCHAR(255) PRIMARY KEY,
    customer_id VARCHAR(255),  -- Optional external reference
    airbnb_cookie TEXT NOT NULL,
    x_airbnb_client_trace_id VARCHAR(255) NOT NULL,
    x_client_version VARCHAR(255) NOT NULL,
    user_agent TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_sync_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_accounts_is_active ON airbnb.accounts(is_active);
CREATE INDEX idx_accounts_customer_id ON airbnb.accounts(customer_id);
```

### Table: `chart_query`

```sql
CREATE TABLE airbnb.chart_query (
    account_id VARCHAR(255) NOT NULL REFERENCES airbnb.accounts(account_id),
    airbnb_listing_id VARCHAR(255) NOT NULL,
    metric_date DATE NOT NULL,
    time TIMESTAMP NOT NULL,  -- Scrape timestamp
    -- Metrics (wide format)
    p3_impressions_total BIGINT,
    p3_impressions_search BIGINT,
    conversion_rate DOUBLE PRECISION,
    booking_value DOUBLE PRECISION,
    -- ... 20+ other metrics
    CONSTRAINT uq_chart_query_listing_metric_date
        UNIQUE (account_id, airbnb_listing_id, metric_date, time)
);

CREATE INDEX idx_chart_query_account_listing
    ON airbnb.chart_query(account_id, airbnb_listing_id);
```

### Table: `chart_summary`

Weekly summary metrics (conversion, booking value, etc.):

```sql
CREATE TABLE airbnb.chart_summary (
    account_id VARCHAR(255) NOT NULL,
    airbnb_listing_id VARCHAR(255) NOT NULL,
    window_start DATE NOT NULL,
    time TIMESTAMP NOT NULL,
    -- Metrics
    total_conversions BIGINT,
    total_booking_value DOUBLE PRECISION,
    conversion_rate DOUBLE PRECISION,
    CONSTRAINT uq_chart_summary_listing_window
        UNIQUE (account_id, airbnb_listing_id, window_start, time)
);
```

### Table: `list_of_metrics`

Visibility and engagement metrics:

```sql
CREATE TABLE airbnb.list_of_metrics (
    account_id VARCHAR(255) NOT NULL,
    airbnb_listing_id VARCHAR(255) NOT NULL,
    window_start DATE NOT NULL,
    time TIMESTAMP NOT NULL,
    -- Metrics
    page_views BIGINT,
    click_through_rate DOUBLE PRECISION,
    search_impressions BIGINT,
    CONSTRAINT uq_list_of_metrics_listing_window
        UNIQUE (account_id, airbnb_listing_id, window_start, time)
);
```

---

## Production Deployment (K8s Operator Pattern)

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Admin API (MODE=admin)                  │
│  • Manages accounts via REST API                            │
│  • Creates account records in database                      │
│  • NO Kubernetes API access (security)                      │
└─────────────────────────────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                 PostgreSQL Database                         │
│  ┌────────────────────────────────────────────┐             │
│  │         accounts table                     │             │
│  │  account_id | is_active | credentials      │             │
│  └────────────────────────────────────────────┘             │
└─────────────────────────────────────────────────────────────┘
                          ▼ (watches)
┌─────────────────────────────────────────────────────────────┐
│              Kubernetes Operator (separate service)         │
│  • Watches accounts table (SELECT WHERE is_active = true)   │
│  • Validates account credentials                            │
│  • Creates worker Deployment per account                    │
│  • Scoped ServiceAccount (deployment CRUD only)             │
│  • Handles updates, scaling, cleanup                        │
└─────────────────────────────────────────────────────────────┘
                          ▼ (creates)
┌─────────────────────────────────────────────────────────────┐
│                Worker Pods (auto-created)                   │
│  ┌──────────────┬──────────────┬──────────────┐            │
│  │ Worker 1     │ Worker 2     │ Worker 3     │            │
│  │ MODE=worker  │ MODE=worker  │ MODE=worker  │            │
│  │ ACCOUNT_ID=1 │ ACCOUNT_ID=2 │ ACCOUNT_ID=3 │            │
│  └──────────────┴──────────────┴──────────────┘            │
└─────────────────────────────────────────────────────────────┘
```

### Component: Admin API

**Deployment:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sync-airbnb-admin
spec:
  replicas: 2  # Can scale
  template:
    spec:
      containers:
        - name: admin
          image: sync-airbnb:latest
          env:
            - name: MODE
              value: "admin"
            - name: API_KEY
              valueFrom:
                secretKeyRef:
                  name: sync-airbnb-secrets
                  key: api-key
```

### Component: Kubernetes Operator

**Responsibilities:**
1. Watch `accounts` table every 60 seconds
2. For each `is_active = true` account:
   - Check if worker Deployment exists
   - If not, validate credentials and create Deployment
   - If exists, ensure it's healthy
3. For inactive accounts, delete worker Deployment

**Implementation (Python pseudocode):**
```python
from kubernetes import client, config

config.load_in_cluster_config()
k8s_apps = client.AppsV1Api()

def reconcile_workers():
    """Reconcile worker pods with active accounts."""
    # Get active accounts from database
    active_accounts = get_active_accounts(engine)

    for account in active_accounts:
        deployment_name = f"sync-airbnb-worker-{account.account_id}"

        # Check if Deployment exists
        try:
            k8s_apps.read_namespaced_deployment(
                name=deployment_name,
                namespace="default",
            )
            # Exists, check health
            logger.info(f"Worker {deployment_name} exists")

        except ApiException as e:
            if e.status == 404:
                # Doesn't exist, create it
                logger.info(f"Creating worker {deployment_name}")

                # Validate credentials first
                if not validate_account_credentials(account):
                    logger.error(f"Account {account.account_id} has invalid credentials")
                    continue

                # Create Deployment
                deployment = create_worker_deployment(account)
                k8s_apps.create_namespaced_deployment(
                    namespace="default",
                    body=deployment,
                )

    # Clean up workers for inactive accounts
    cleanup_inactive_workers(engine, k8s_apps)

# Run every 60 seconds
while True:
    reconcile_workers()
    time.sleep(60)
```

**ServiceAccount (Scoped Permissions):**
```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: sync-airbnb-operator
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: sync-airbnb-operator
rules:
  - apiGroups: ["apps"]
    resources: ["deployments"]
    verbs: ["get", "list", "create", "update", "delete"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: sync-airbnb-operator
subjects:
  - kind: ServiceAccount
    name: sync-airbnb-operator
roleRef:
  kind: Role
  name: sync-airbnb-operator
  apiGroup: rbac.authorization.k8s.io
```

### Component: Worker Pods

**Created dynamically by operator:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sync-airbnb-worker-310316675
  labels:
    app: sync-airbnb
    component: worker
    account_id: "310316675"
spec:
  replicas: 1  # One per account
  selector:
    matchLabels:
      app: sync-airbnb
      account_id: "310316675"
  template:
    metadata:
      labels:
        app: sync-airbnb
        account_id: "310316675"
    spec:
      containers:
        - name: worker
          image: sync-airbnb:latest
          env:
            - name: MODE
              value: "worker"
            - name: ACCOUNT_ID
              value: "310316675"
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: sync-airbnb-secrets
                  key: database-url
          resources:
            requests:
              cpu: 500m
              memory: 512Mi
            limits:
              cpu: 1000m
              memory: 1Gi
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 10
      terminationGracePeriodSeconds: 600  # 10 min for graceful shutdown
```

### Security Benefits

1. **Least Privilege**: Admin API has NO Kubernetes access
2. **Credential Validation**: Operator validates before creating pods
3. **Audit Trail**: All pod creations logged
4. **Isolation**: Operator breach ≠ cluster admin
5. **Database as Source of Truth**: Can't create pods without DB record

---

## Key Design Decisions

### 1. Container-Per-Account vs Multi-Account Workers

**Decision:** Container-per-account

**Rationale:**
- Simpler code (no multi-threading)
- Better isolation (one account failure doesn't affect others)
- Easier to scale (add workers, not increase thread pool)
- Resource limits per account

**Trade-off:** More containers to manage

---

### 2. SQLAlchemy Core vs ORM for Metrics

**Decision:** Use SQLAlchemy Core for bulk inserts

**Rationale:**
- Time-series data involves 100s-1000s of rows per insert
- ORM has overhead for large batches
- Core's `insert().values(list[dict])` is more efficient

**Exception:** Account table uses ORM (small, CRUD operations)

---

### 3. TimescaleDB vs Plain PostgreSQL

**Decision:** Use TimescaleDB with hypertables

**Rationale:**
- Metrics are time-series data
- Automatic partitioning by time
- Better query performance for time-range queries
- Compression and retention policies available

---

### 4. Unique Constraints Include `time` Column

**Decision:** Include scrape timestamp in unique constraints

**Rationale:**
- Tracks metric changes over multiple scrapes
- Allows "as-of" queries
- Required for TimescaleDB compatibility

**Trade-off:** More storage (duplicates if metrics unchanged)

---

### 5. Background Threads vs Async

**Decision:** Use threads for background sync

**Rationale:**
- FastAPI uses async, but Airbnb polling is synchronous
- Threading avoids mixing sync/async code
- Simpler error handling
- Daemon threads clean up automatically

**Trade-off:** Not as efficient as true async

---

### 6. Database is Source of Truth

**Decision:** All account config in database, not environment

**Rationale:**
- Dynamic account management (no redeploy)
- Supports operator pattern
- Audit trail of changes
- Multi-tenancy support

---

### 7. Scheduler Uses UTC

**Decision:** Fixed 5:00 UTC, not dynamic timezone

**Rationale:**
- Avoids DST complexity
- Predictable in logs
- Standard practice for distributed systems

**Trade-off:** Time shifts by 1 hour during DST

---

## Security Considerations

### Credential Storage

**Current:** Plain text in database
**TODO:** Encrypt credentials at rest

```python
from cryptography.fernet import Fernet

def encrypt_cookie(cookie: str, key: bytes) -> str:
    f = Fernet(key)
    return f.encrypt(cookie.encode()).decode()

def decrypt_cookie(encrypted: str, key: bytes) -> str:
    f = Fernet(key)
    return f.decrypt(encrypted.encode()).decode()
```

### API Authentication

**Current:** None (P0 issue)
**TODO:** API key or OAuth2

### Network Security

**Production Requirements:**
- TLS for all external communication
- mTLS for service-to-service
- Network policies in Kubernetes

---

## Scalability Considerations

### Horizontal Scaling

**Admin API:** Can scale to N replicas (stateless)

**Workers:** One per account (do NOT scale)

**Database:** Connection pool per worker
- Formula: `pool_size = (num_workers * 2) + 1`
- Ensure DB `max_connections` > total pool

### Performance Bottlenecks

1. **Airbnb API rate limits** (10 req/sec recommended)
2. **Database write throughput** (TimescaleDB helps)
3. **Memory** (parsing large GraphQL responses)

### Optimization Strategies

1. **Batch inserts** (already implemented)
2. **Parallel listing processing** (future: async)
3. **Redis cache** for listings lookup (future)
4. **TimescaleDB compression** (reduce storage)

---

## Conclusion

sync-airbnb is architected for production scale with:
- Clear separation of concerns (layered architecture)
- Multi-account support (database-driven config)
- Horizontal scalability (container-per-account)
- Operational excellence (Kubernetes operator pattern)

The system is ready for small-scale production with P0 issues resolved. For large-scale production (100+ accounts), implement:
- Kubernetes operator
- Credential encryption
- API authentication
- Observability stack (Prometheus, Grafana)
- Advanced TimescaleDB features (compression, retention)
