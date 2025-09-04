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

```bash
# 1. Install dependencies
make install-dev

# 2. Set required environment variables in .env
cp .env.example .env

# 3. Run the poller
python -m pollers.insights
```

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

## ⚠️ Still In Progress

- [ ] JSON Schema validation for all flattener outputs
- [ ] OpenAPI documentation for upcoming API service
- [ ] Proper dry-run guard in services (used for CI or first-time testing)
- [ ] First-run detection (e.g. when to backfill vs increment)
- [ ] Multi-account support (via host_id or external config)

---

## 🧠 Dev Notes

- All Airbnb GraphQL metrics use +3 day offset for `relativeDsStart` and `relativeDsEnd`
- `ChartQuery` = weekly windows (28 days)
- `ListOfMetricsQuery` = daily snapshots (7-day lookback to 180-day forward)
- Use `AirbnbSync.parse_all()` to get 3 tables:
  - `chart_query`
  - `chart_summary`
  - `list_of_metrics`
