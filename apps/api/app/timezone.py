"""Time conversion between Kite's IST wall clock and the UTC we store.

Kite returns every timestamp as a bare `YYYY-MM-DD HH:MM:SS` string with no
offset; the Kite Connect v3 docs never state a zone because it is always IST.
A naive datetime must therefore never reach the database: it goes through
`to_utc` first (SRS 4.3, Time; NFR-10).
"""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

# The Kite access token expires at 06:00 IST the morning after it was issued
# (Kite Connect v3, user session; SRS 1.3 and FR-KITE-04).
TOKEN_EXPIRY_HOUR_IST = 6


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def to_utc(value: dt.datetime) -> dt.datetime:
    """Normalise to UTC, reading a naive value as IST wall-clock time."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=IST)
    return value.astimezone(dt.UTC)


def ist_date(value: dt.datetime) -> dt.date:
    """The IST calendar date a moment falls on: the trading day."""
    return to_utc(value).astimezone(IST).date()


def next_six_am_ist(after: dt.datetime) -> dt.datetime:
    """The first 06:00 IST strictly after `after`, returned in UTC."""
    local = to_utc(after).astimezone(IST)
    candidate = local.replace(hour=TOKEN_EXPIRY_HOUR_IST, minute=0, second=0, microsecond=0)
    if candidate <= local:
        candidate += dt.timedelta(days=1)
    return candidate.astimezone(dt.UTC)
