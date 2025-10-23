# TimescaleDB Data Retention Policy

**Priority:** P2 - Medium (Production infrastructure)
**Status:** Not implemented
**Estimated effort:** 2-3 hours

---

## Overview

Implement TimescaleDB retention policies to automatically delete old metrics data and prevent unbounded database growth.

---

## Problem

Currently, the database grows indefinitely as new metrics are inserted:
- Chart query data: ~500 rows per listing per sync
- Chart summary data: ~50 rows per listing per sync
- List of metrics data: ~50 rows per listing per sync
- Daily syncs accumulate historical snapshots forever
- No mechanism to purge old data

**Estimated Growth:**
- 10 accounts × 5 listings × 500 rows/sync × 365 days = **~9M rows/year**
- At ~1KB per row average = **~9GB/year** (uncompressed)

---

## Solution

Use TimescaleDB's automatic retention policies to drop old data:
- Keep **90 days** of raw metrics (daily snapshots)
- Enable compression for data older than 7 days
- Automatic cleanup via TimescaleDB background jobs

---

## Implementation

### 1. Add Retention Policies to Migration

**File:** `alembic/versions/<next>_add_retention_policies.py`

```python
"""Add TimescaleDB retention and compression policies

Revision ID: <generate>
Revises: <previous>
Create Date: <timestamp>
"""

from alembic import op


def upgrade() -> None:
    # Add retention policy: drop data older than 90 days
    op.execute("""
        SELECT add_retention_policy('airbnb.chart_query', INTERVAL '90 days');
    """)

    op.execute("""
        SELECT add_retention_policy('airbnb.chart_summary', INTERVAL '90 days');
    """)

    op.execute("""
        SELECT add_retention_policy('airbnb.list_of_metrics', INTERVAL '90 days');
    """)

    # Add compression policy: compress data older than 7 days
    op.execute("""
        ALTER TABLE airbnb.chart_query SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'account_id, airbnb_listing_id'
        );
    """)

    op.execute("""
        SELECT add_compression_policy('airbnb.chart_query', INTERVAL '7 days');
    """)

    op.execute("""
        ALTER TABLE airbnb.chart_summary SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'account_id, airbnb_listing_id'
        );
    """)

    op.execute("""
        SELECT add_compression_policy('airbnb.chart_summary', INTERVAL '7 days');
    """)

    op.execute("""
        ALTER TABLE airbnb.list_of_metrics SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'account_id, airbnb_listing_id'
        );
    """)

    op.execute("""
        SELECT add_compression_policy('airbnb.list_of_metrics', INTERVAL '7 days');
    """)


def downgrade() -> None:
    # Remove compression policies
    op.execute("""
        SELECT remove_compression_policy('airbnb.chart_query');
    """)

    op.execute("""
        SELECT remove_compression_policy('airbnb.chart_summary');
    """)

    op.execute("""
        SELECT remove_compression_policy('airbnb.list_of_metrics');
    """)

    # Remove retention policies
    op.execute("""
        SELECT remove_retention_policy('airbnb.chart_query');
    """)

    op.execute("""
        SELECT remove_retention_policy('airbnb.chart_summary');
    """)

    op.execute("""
        SELECT remove_retention_policy('airbnb.list_of_metrics');
    """)
```

### 2. Make Retention Configurable

**File:** `sync_airbnb/config.py`

```python
# Data retention (TimescaleDB)
RETENTION_DAYS = int(get_env("RETENTION_DAYS", required=False, default="90"))
COMPRESSION_DAYS = int(get_env("COMPRESSION_DAYS", required=False, default="7"))
```

**File:** `.env.example`

```bash
# Data Retention (TimescaleDB)
RETENTION_DAYS=90        # Keep raw data for 90 days
COMPRESSION_DAYS=7       # Compress data older than 7 days
```

### 3. Verify Policies are Active

**File:** `sync_airbnb/db/maintenance.py` (new)

```python
"""Database maintenance utilities."""

import logging
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def verify_retention_policies(engine: Engine) -> dict:
    """
    Verify TimescaleDB retention and compression policies are active.

    Returns:
        Dict with policy status for each table
    """
    with engine.connect() as conn:
        # Check retention policies
        result = conn.execute(text("""
            SELECT hypertable_name, proc_name
            FROM timescaledb_information.jobs
            WHERE proc_name = 'policy_retention'
        """))

        retention_policies = {row[0]: row[1] for row in result}

        # Check compression policies
        result = conn.execute(text("""
            SELECT hypertable_name, proc_name
            FROM timescaledb_information.jobs
            WHERE proc_name = 'policy_compression'
        """))

        compression_policies = {row[0]: row[1] for row in result}

        return {
            "retention": retention_policies,
            "compression": compression_policies,
        }


def get_database_size(engine: Engine) -> dict:
    """Get database size statistics."""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT
                hypertable_schema || '.' || hypertable_name AS table_name,
                pg_size_pretty(hypertable_size(format('%I.%I', hypertable_schema, hypertable_name)::regclass)) AS total_size,
                pg_size_pretty(chunks_size(format('%I.%I', hypertable_schema, hypertable_name)::regclass)) AS compressed_size
            FROM timescaledb_information.hypertables
            WHERE hypertable_schema = 'airbnb'
        """))

        return {row[0]: {"total": row[1], "compressed": row[2]} for row in result}
```

---

## Monitoring

### Add Health Check for Policies

**File:** `sync_airbnb/api/routes/health.py`

```python
@router.get("/health/database")
async def database_health(engine: Engine = Depends(get_db_engine)):
    """Database health check including TimescaleDB policies."""
    from sync_airbnb.db.maintenance import verify_retention_policies, get_database_size

    policies = verify_retention_policies(engine)
    sizes = get_database_size(engine)

    return {
        "status": "ok",
        "retention_policies": policies["retention"],
        "compression_policies": policies["compression"],
        "table_sizes": sizes,
    }
```

---

## Testing

### Manual Testing

```bash
# 1. Apply migration
alembic upgrade head

# 2. Verify policies are created
psql $DATABASE_URL -c "
  SELECT hypertable_name, proc_name, config
  FROM timescaledb_information.jobs
  WHERE hypertable_schema = 'airbnb'
"

# 3. Check database size
psql $DATABASE_URL -c "
  SELECT
    hypertable_schema || '.' || hypertable_name AS table_name,
    pg_size_pretty(hypertable_size(format('%I.%I', hypertable_schema, hypertable_name)::regclass)) AS size
  FROM timescaledb_information.hypertables
  WHERE hypertable_schema = 'airbnb'
"

# 4. Force compression manually (for testing)
psql $DATABASE_URL -c "
  SELECT compress_chunk(i, if_not_compressed => true)
  FROM show_chunks('airbnb.chart_query', older_than => INTERVAL '7 days') i
"
```

---

## Acceptance Criteria

- [ ] Retention policy drops data older than 90 days (configurable via `RETENTION_DAYS`)
- [ ] Compression policy compresses data older than 7 days (configurable via `COMPRESSION_DAYS`)
- [ ] Policies apply to all three metrics tables (chart_query, chart_summary, list_of_metrics)
- [ ] Migration is reversible (downgrade removes policies cleanly)
- [ ] `/health/database` endpoint shows policy status and table sizes
- [ ] Documentation updated with retention policy configuration

---

## Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `RETENTION_DAYS` | 90 | Days to keep raw data before deletion |
| `COMPRESSION_DAYS` | 7 | Days before compressing data |

**Recommendations:**
- **Development:** `RETENTION_DAYS=30` (smaller database)
- **Production:** `RETENTION_DAYS=90-365` (depends on reporting needs)
- Keep `COMPRESSION_DAYS=7` (good balance between query speed and storage)

---

## References

- TimescaleDB Retention Policies: https://docs.timescale.com/use-timescale/latest/data-retention/
- TimescaleDB Compression: https://docs.timescale.com/use-timescale/latest/compression/
- TimescaleDB Policy API: https://docs.timescale.com/api/latest/compression/
