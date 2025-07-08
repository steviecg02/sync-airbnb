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
WINDOW_START_DAYS_AGO=...
WINDOW_END_DAYS_AHEAD=...
WINDOW_SIZE=...
```

3. **Run the poller**

```bash
python main.py
```

---

## 🧠 Architecture Principles

- No hardcoded offsets — everything aligns to Airbnb’s +2 day UI logic
- Clean separation between polling, flattening, and output
- Debug-safe: you can inspect payloads and responses without breaking production logic
- Extendable: add new pollers, flatteners, DB writers without touching `main.py`

---

## 📌 Notes

- This project reverse-engineers Airbnb's internal metrics dashboard.
- The data is only available to hosts logged into their own Airbnb account.
- Use responsibly. This code is for educational and internal automation purposes.

---

## 📣 TODO

- [ ] Add CLI flags
- [ ] Enable containerized cron job
- [ ] Add flattener coverage tests