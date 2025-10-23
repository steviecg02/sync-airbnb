"""Datetime utilities for consistent timezone handling."""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """
    Get current UTC datetime (timezone-aware).

    Always use this instead of datetime.now() or datetime.utcnow() to avoid
    naive datetime objects and timezone bugs.

    Returns:
        datetime: Current UTC time with timezone info
    """
    return datetime.now(timezone.utc)


def to_utc(dt: datetime) -> datetime:
    """
    Convert datetime to UTC timezone.

    Args:
        dt: datetime object (naive or aware)

    Returns:
        datetime: Timezone-aware datetime in UTC
    """
    if dt.tzinfo is None:
        # Naive datetime - assume it's UTC
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
