import logging
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine

from sync_airbnb.models.chart_query import ChartQuery
from sync_airbnb.models.chart_summary import ChartSummary
from sync_airbnb.models.list_of_metrics import ListOfMetrics

logger = logging.getLogger(__name__)


def insert_chart_query_rows(engine: Engine, rows: list[dict]):
    if not rows:
        logger.info("No chart_query rows to insert.")
        return

    for r in rows:
        r["metric_date"] = r.pop("date")

    with engine.begin() as conn:
        stmt = insert(ChartQuery).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_chart_query_listing_metric_date",
            set_={c.name: c for c in stmt.excluded}
        )
        conn.execute(stmt)
        logger.info(f"Inserted {len(rows)} chart_query rows.")


def insert_chart_summary_rows(engine: Engine, rows: list[dict]):
    if not rows:
        logger.info("No chart_summary rows to insert.")
        return

    with engine.begin() as conn:
        stmt = insert(ChartSummary).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_chart_summary_listing_window",
            set_={c.name: c for c in stmt.excluded}
        )
        conn.execute(stmt)
        logger.info(f"Inserted {len(rows)} chart_summary rows.")


def insert_list_of_metrics_rows(engine: Engine, rows: list[dict]):
    if not rows:
        logger.info("No list_of_metrics rows to insert.")
        return

    with engine.begin() as conn:
        stmt = insert(ListOfMetrics).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_list_of_metrics_listing_window",
            set_={c.name: c for c in stmt.excluded}
        )
        conn.execute(stmt)
        logger.info(f"Inserted {len(rows)} list_of_metrics rows.")
