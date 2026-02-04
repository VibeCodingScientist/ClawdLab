"""Datetime utilities for timezone-aware operations.

Provides SOTA-compliant datetime functions that avoid deprecated
`datetime.utcnow()` and ensure timezone awareness.
"""

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Return current UTC time with timezone info.

    This is the SOTA replacement for the deprecated `datetime.utcnow()`.
    The returned datetime object is timezone-aware and uses UTC.

    Returns:
        Current UTC datetime with tzinfo=timezone.utc

    Example:
        >>> from platform.shared.utils.datetime_utils import utcnow
        >>> now = utcnow()
        >>> now.tzinfo is not None
        True
    """
    return datetime.now(timezone.utc)


def ensure_utc(dt: datetime) -> datetime:
    """Ensure a datetime object is timezone-aware and in UTC.

    If the datetime is naive (no tzinfo), it's assumed to be UTC.
    If the datetime has a different timezone, it's converted to UTC.

    Args:
        dt: A datetime object (naive or aware)

    Returns:
        Timezone-aware datetime in UTC
    """
    if dt.tzinfo is None:
        # Naive datetime - assume UTC
        return dt.replace(tzinfo=timezone.utc)
    else:
        # Convert to UTC
        return dt.astimezone(timezone.utc)


def is_expired(expires_at: datetime | None) -> bool:
    """Check if a datetime has expired.

    Args:
        expires_at: Expiration datetime (or None for never expires)

    Returns:
        True if expired, False otherwise
    """
    if expires_at is None:
        return False
    return utcnow() > ensure_utc(expires_at)


__all__ = [
    "ensure_utc",
    "is_expired",
    "utcnow",
]
