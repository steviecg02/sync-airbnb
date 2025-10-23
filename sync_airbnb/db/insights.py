import logging
import time

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine

from sync_airbnb import config
from sync_airbnb.metrics import (
    db_queries_total,
    db_query_duration_seconds,
    errors_total,
    metrics_insert_duration_seconds,
    metrics_inserted_total,
)
from sync_airbnb.models.chart_query import ChartQuery
from sync_airbnb.models.chart_summary import ChartSummary
from sync_airbnb.models.list_of_metrics import ListOfMetrics

logger = logging.getLogger(__name__)


def insert_chart_query_rows(engine: Engine, rows: list[dict]):
    if not rows:
        logger.info("No chart_query rows to insert.")
        return

    if config.INSIGHTS_DRY_RUN:
        logger.info(f"[DRY RUN] Would insert {len(rows)} chart_query rows")
        logger.debug(f"[DRY RUN] Sample row: {rows[0] if rows else None}")
        return

    for r in rows:
        r["metric_date"] = r.pop("date")

    start_time = time.time()
    try:
        with engine.begin() as conn:
            stmt = insert(ChartQuery).values(rows)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_chart_query_listing_metric_date", set_={c.name: c for c in stmt.excluded}
            )
            conn.execute(stmt)

        duration = time.time() - start_time

        # Track metrics
        metrics_inserted_total.labels(metric_type="chart_query").inc(len(rows))
        metrics_insert_duration_seconds.labels(metric_type="chart_query").observe(duration)
        db_queries_total.labels(operation="upsert", table="chart_query").inc()
        db_query_duration_seconds.labels(operation="upsert", table="chart_query").observe(duration)

        logger.info(f"Inserted {len(rows)} chart_query rows.")

    except Exception as e:
        errors_total.labels(error_type=type(e).__name__, component="db").inc()
        raise


def insert_chart_summary_rows(engine: Engine, rows: list[dict]):
    if not rows:
        logger.info("No chart_summary rows to insert.")
        return

    if config.INSIGHTS_DRY_RUN:
        logger.info(f"[DRY RUN] Would insert {len(rows)} chart_summary rows")
        logger.debug(f"[DRY RUN] Sample row: {rows[0] if rows else None}")
        return

    start_time = time.time()
    try:
        with engine.begin() as conn:
            stmt = insert(ChartSummary).values(rows)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_chart_summary_listing_window", set_={c.name: c for c in stmt.excluded}
            )
            conn.execute(stmt)

        duration = time.time() - start_time

        # Track metrics
        metrics_inserted_total.labels(metric_type="chart_summary").inc(len(rows))
        metrics_insert_duration_seconds.labels(metric_type="chart_summary").observe(duration)
        db_queries_total.labels(operation="upsert", table="chart_summary").inc()
        db_query_duration_seconds.labels(operation="upsert", table="chart_summary").observe(duration)

        logger.info(f"Inserted {len(rows)} chart_summary rows.")

    except Exception as e:
        errors_total.labels(error_type=type(e).__name__, component="db").inc()
        raise


def insert_list_of_metrics_rows(engine: Engine, rows: list[dict]):
    if not rows:
        logger.info("No list_of_metrics rows to insert.")
        return

    if config.INSIGHTS_DRY_RUN:
        logger.info(f"[DRY RUN] Would insert {len(rows)} list_of_metrics rows")
        logger.debug(f"[DRY RUN] Sample row: {rows[0] if rows else None}")
        return

    start_time = time.time()
    try:
        with engine.begin() as conn:
            stmt = insert(ListOfMetrics).values(rows)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_list_of_metrics_listing_window", set_={c.name: c for c in stmt.excluded}
            )
            conn.execute(stmt)

        duration = time.time() - start_time

        # Track metrics
        metrics_inserted_total.labels(metric_type="list_of_metrics").inc(len(rows))
        metrics_insert_duration_seconds.labels(metric_type="list_of_metrics").observe(duration)
        db_queries_total.labels(operation="upsert", table="list_of_metrics").inc()
        db_query_duration_seconds.labels(operation="upsert", table="list_of_metrics").observe(duration)

        logger.info(f"Inserted {len(rows)} list_of_metrics rows.")

    except Exception as e:
        errors_total.labels(error_type=type(e).__name__, component="db").inc()
        raise
