from sqlalchemy import Table, Column, Text, Float, Integer, Date, TIMESTAMP, MetaData
from sqlalchemy import insert
from sqlalchemy.engine import Engine
from sqlalchemy.sql import func

metadata = MetaData()

airbnb_chart_query = Table("airbnb_chart_query", metadata,
    Column("time", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("airbnb_listing_id", Text, nullable=False),
    Column("airbnb_internal_name", Text),
    Column("metric_date", Date, nullable=False),
    Column("conversion_rate_your_value", Float),
    Column("conversion_rate_your_value_string", Text),
    Column("conversion_rate_similar_value", Float),
    Column("conversion_rate_similar_value_string", Text),
    Column("p3_impressions_your_value", Integer),
    Column("p3_impressions_your_value_string", Text),
    Column("p3_impressions_similar_value", Integer),
    Column("p3_impressions_similar_value_string", Text),
)

airbnb_chart_summary = Table("airbnb_chart_summary", metadata,
    Column("time", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("airbnb_listing_id", Text, nullable=False),
    Column("airbnb_internal_name", Text),
    Column("window_start", Date, nullable=False),
    Column("window_end", Date, nullable=False),
    Column("conversion_rate_value", Float),
    Column("conversion_rate_value_string", Text),
    Column("conversion_rate_value_change", Float),
    Column("conversion_rate_value_change_string", Text),
    Column("p2_impressions_first_page_rate_value", Float),
    Column("p2_impressions_first_page_rate_value_string", Text),
    Column("search_conversion_rate_value", Float),
    Column("search_conversion_rate_value_string", Text),
    Column("listing_conversion_rate_value", Float),
    Column("listing_conversion_rate_value_string", Text),
    Column("p3_impressions_value", Integer),
    Column("p3_impressions_value_string", Text),
    Column("p3_impressions_value_change", Float),
    Column("p3_impressions_value_change_string", Text),
    Column("p2_impressions_value", Integer),
    Column("p2_impressions_value_string", Text),
)

airbnb_list_of_metrics = Table("airbnb_list_of_metrics", metadata,
    Column("time", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("airbnb_listing_id", Text, nullable=False),
    Column("airbnb_internal_name", Text),
    Column("window_start", Date, nullable=False),
    Column("window_end", Date, nullable=False),
    Column("conversion_rate_value", Float),
    Column("conversion_rate_value_string", Text),
    Column("p2_impressions_first_page_rate_value", Float),
    Column("p2_impressions_first_page_rate_value_string", Text),
    Column("search_conversion_rate_value", Float),
    Column("search_conversion_rate_value_string", Text),
    Column("listing_conversion_rate_value", Float),
    Column("listing_conversion_rate_value_string", Text),
    Column("p3_impressions_value", Integer),
    Column("p3_impressions_value_string", Text),
    Column("p2_impressions_value", Integer),
    Column("p2_impressions_value_string", Text),
)

def insert_chart_query_rows(engine: Engine, rows: list[dict]):
    """
    Insert parsed chart_query rows using SQLAlchemy Core.
    """
    if not rows:
        return
    
    for r in rows:
        r["metric_date"] = r.pop("date")

    with engine.begin() as conn:
        stmt = insert(airbnb_chart_query).values(rows)
        conn.execute(stmt)

def insert_chart_summary_rows(engine: Engine, rows: list[dict]):
    """
    Insert parsed chart_summary rows using SQLAlchemy Core.
    """
    if not rows:
        return

    with engine.begin() as conn:
        stmt = insert(airbnb_chart_summary).values(rows)
        conn.execute(stmt)

def insert_list_of_metrics_rows(engine: Engine, rows: list[dict]):
    """
    Insert parsed list_of_metrics rows using SQLAlchemy Core.
    """
    if not rows:
        return

    with engine.begin() as conn:
        stmt = insert(airbnb_list_of_metrics).values(rows)
        conn.execute(stmt)