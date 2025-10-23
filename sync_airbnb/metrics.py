"""Prometheus metrics instrumentation.

This module defines all Prometheus metrics for monitoring the application.
Metrics are organized by category: HTTP, database, sync jobs, and errors.
"""

from prometheus_client import Counter, Gauge, Histogram, Info

# Application info
app_info = Info("sync_airbnb_app", "Application information")
app_info.info({"version": "0.1.0", "service": "sync-airbnb"})

# HTTP metrics
http_requests_total = Counter("http_requests_total", "Total HTTP requests", ["method", "endpoint", "status_code"])

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds", "HTTP request duration in seconds", ["method", "endpoint"]
)

# Database metrics
db_query_duration_seconds = Histogram(
    "db_query_duration_seconds", "Database query duration in seconds", ["operation", "table"]
)

db_connections_active = Gauge("db_connections_active", "Number of active database connections")

db_queries_total = Counter("db_queries_total", "Total database queries", ["operation", "table"])

# Sync job metrics
sync_jobs_total = Counter(
    "sync_jobs_total", "Total sync jobs started", ["account_id", "trigger"]  # trigger: scheduled, manual, startup
)

sync_jobs_duration_seconds = Histogram(
    "sync_jobs_duration_seconds", "Sync job duration in seconds", ["account_id", "status"]  # status: success, failure
)

sync_jobs_active = Gauge("sync_jobs_active", "Number of sync jobs currently running")

sync_listings_processed_total = Counter(
    "sync_listings_processed_total",
    "Total listings processed during sync",
    ["account_id", "status"],  # status: success, failure
)

sync_api_calls_total = Counter("sync_api_calls_total", "Total Airbnb API calls made", ["endpoint", "status_code"])

# Error metrics
errors_total = Counter(
    "errors_total", "Total errors encountered", ["error_type", "component"]  # component: api, db, sync, network
)

# Airbnb API metrics
airbnb_api_request_duration_seconds = Histogram(
    "airbnb_api_request_duration_seconds", "Airbnb API request duration in seconds", ["endpoint"]
)

airbnb_api_requests_total = Counter(
    "airbnb_api_requests_total", "Total Airbnb API requests", ["endpoint", "status_code"]
)

airbnb_api_retries_total = Counter("airbnb_api_retries_total", "Total Airbnb API retry attempts", ["endpoint"])

# Metrics insertion tracking
metrics_inserted_total = Counter(
    "metrics_inserted_total",
    "Total metric rows inserted into database",
    ["metric_type"],  # chart_query, list_of_metrics, chart_summary
)

metrics_insert_duration_seconds = Histogram(
    "metrics_insert_duration_seconds", "Duration of metrics insertion operations", ["metric_type"]
)
