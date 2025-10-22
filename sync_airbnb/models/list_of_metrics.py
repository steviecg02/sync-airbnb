from sqlalchemy import Column, String, Text, Float, Integer, Date, text, ForeignKey
from sync_airbnb.config import SCHEMA
from sync_airbnb.models.base import Base


class ListOfMetrics(Base):
    __tablename__ = "list_of_metrics"
    __table_args__ = {"schema": SCHEMA}

    account_id = Column(String, ForeignKey(f"{SCHEMA}.accounts.account_id"), nullable=False, primary_key=True)
    time = Column(Date, server_default=text("now()::date"), nullable=False, primary_key=True)
    airbnb_listing_id = Column(Text, nullable=False, primary_key=True)
    airbnb_internal_name = Column(Text)
    window_start = Column(Date, nullable=False, primary_key=True)
    window_end = Column(Date, nullable=False)
    conversion_rate_value = Column(Float)
    conversion_rate_value_string = Column(Text)
    p2_impressions_first_page_rate_value = Column(Float)
    p2_impressions_first_page_rate_value_string = Column(Text)
    search_conversion_rate_value = Column(Float)
    search_conversion_rate_value_string = Column(Text)
    listing_conversion_rate_value = Column(Float)
    listing_conversion_rate_value_string = Column(Text)
    p3_impressions_value = Column(Integer)
    p3_impressions_value_string = Column(Text)
    p2_impressions_value = Column(Integer)
    p2_impressions_value_string = Column(Text)
