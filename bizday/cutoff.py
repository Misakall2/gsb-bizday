"""Timezone localization and the cutoff-time trade-date rule.

Dependencies: the holiday table plus business-day stepping/adjustment.
Nothing here knows about T+N counting or month arithmetic.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from . import adjustment
from .conventions import FOLLOWING


def resolve_timezone(tz):
    return ZoneInfo(tz) if isinstance(tz, str) else tz


def localize(zone, dt: datetime) -> datetime:
    """Interpret a datetime in the market's timezone.

    Aware datetimes are converted; naive ones are assumed to already be
    in the market's local time. DST transitions are handled by
    zoneinfo, so spring-forward/fall-back days do not blow up.
    """
    if not isinstance(dt, datetime):
        raise TypeError("expected a datetime")
    if dt.tzinfo is None:
        return dt.replace(tzinfo=zone)
    return dt.astimezone(zone)


def trade_date(table, zone, cutoff, dt) -> date:
    """The business date a trade belongs to, after the cutoff rule.

    Local time strictly after the cutoff rolls to the next business
    day; exactly at the cutoff stays on the same day (inclusive). The
    result is always a business day.
    """
    if isinstance(dt, datetime):
        local = localize(zone, dt)
        d = local.date()
        if cutoff is not None and local.timetz().replace(tzinfo=None) > cutoff:
            d = adjustment.step(table, d, +1)
    elif isinstance(dt, date):
        d = dt
    else:
        raise TypeError("expected a date or datetime")
    return adjustment.adjust(table, d, FOLLOWING)
