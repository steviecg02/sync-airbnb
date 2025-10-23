from sqlalchemy import Column, Date, Float, ForeignKey, Integer, String, Text, text

from sync_airbnb.config import SCHEMA
from sync_airbnb.models.base import Base


class ChartQuery(Base):
    __tablename__ = "chart_query"
    __table_args__ = {"schema": SCHEMA}

    account_id = Column(String, ForeignKey(f"{SCHEMA}.accounts.account_id"), nullable=False, primary_key=True)
    time = Column(Date, server_default=text("now()::date"), nullable=False, primary_key=True)
    airbnb_listing_id = Column(Text, nullable=False, primary_key=True)
    airbnb_internal_name = Column(Text)
    metric_date = Column(Date, nullable=False, primary_key=True)
    conversion_rate_your_value = Column(Float)
    conversion_rate_your_value_string = Column(Text)
    conversion_rate_similar_value = Column(Float)
    conversion_rate_similar_value_string = Column(Text)
    p3_impressions_your_value = Column(Integer)
    p3_impressions_your_value_string = Column(Text)
    p3_impressions_similar_value = Column(Integer)
    p3_impressions_similar_value_string = Column(Text)
