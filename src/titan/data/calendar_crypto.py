"""24/7 crypto calendar — UTC, no session close, no holidays."""

from datetime import date, datetime, timedelta, timezone


def is_crypto_trading_day(day: date) -> bool:
    """Crypto venues in this program trade every UTC day."""
    return True


def crypto_session_open_utc(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=timezone.utc)


def crypto_session_close_utc(day: date) -> datetime:
    return crypto_session_open_utc(day) + timedelta(days=1)


def require_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None or ts.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware UTC")
    if ts.utcoffset() != timedelta(0):
        raise ValueError("timestamp must be UTC")
    return ts.astimezone(timezone.utc)
