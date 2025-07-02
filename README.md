# Airbnb Metrics Poller

A modular pipeline for polling Airbnb's internal GraphQL API to collect listing performance metrics — cleanly structured for maintainability, testing, and future expansion.

---

## 🔧 What It Does

This project:

- Fetches your Airbnb listing IDs
- Pulls **search + booking metrics** (e.g. conversion rate, impressions) from Airbnb's private APIs
- Supports both `ListOfMetricsQuery` and `ChartQuery`
- Normalizes the results into structured rows
- (Coming soon) Inserts into a Postgres database

---

## 📁 Project Structure

```
.
├── main.py              # Orchestration entrypoint
├── config.py            # Env vars, API headers, scrape day logic
├── utils/               # Logger setup, small helpers
├── pollers/             # Calls Airbnb APIs (listings, metrics)
├── payloads/            # GraphQL query builders
├── flatteners/          # Extracts data from Airbnb JSON into clean rows
├── db/                  # [WIP] Postgres schema & inserts
└── tests/               # [Optional] Unit tests
```

---

## 🚀 Getting Started

1. **Install dependencies**

```bash
pip install -r requirements.txt
```

2. **Create a `.env` file** (only if not running in production)

```
AIRBNB_COOKIE=your_session_cookie
X_CLIENT_VERSION=...
X_CLIENT_REQUEST_ID=...
X_AIRBNB_CLIENT_TRACE_ID=...
```

3. **Run the poller**

```bash
python main.py
```

---

## ⚙️ Configuration

| Variable             | Purpose                                |
|----------------------|----------------------------------------|
| `.env` present       | Automatically sets `LOG_LEVEL=DEBUG`   |
| `ENV=production`     | Skips `.env` loading                   |
| `TEST_LISTING_ID`    | (optional) Poll a single listing       |
| `LIMIT`              | (optional) Limit number of listings    |

---

## 🧠 Architecture Principles

- No hardcoded offsets — everything aligns to Airbnb’s +2 day UI logic
- Clean separation between polling, flattening, and output
- Debug-safe: you can inspect payloads and responses without breaking production logic
- Extendable: add new pollers, flatteners, DB writers without touching `main.py`

---

## 🧼 Example Usage (Dev Testing)

```bash
# Pull one listing and log payloads/responses
TEST_LISTING_ID=745515... LOG_LEVEL=DEBUG python main.py
```

---

## 📌 Notes

- This project reverse-engineers Airbnb's internal metrics dashboard.
- The data is only available to hosts logged into their own Airbnb account.
- Use responsibly. This code is for educational and internal automation purposes.

---

## 📣 TODO

- [ ] Write to Postgres
- [ ] Add CLI flags
- [ ] Enable containerized cron job
- [ ] Add flattener coverage tests
