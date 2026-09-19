"""T+N style business day offsets.

Counting convention
-------------------
N counts business days, never calendar days:

* t_plus_n(trade, 0) -> the trade's effective business day;
* t_plus_n(trade, 1) -> the next business day after it (US equities);
* t_plus_n(trade, 2) -> two business days after (many bonds);
* negative N walks backwards.

The starting day is the effective trade day after applying the calendar
cutoff (e.g. 17:00 NY rolls a trade to the next session). A plain date is
treated as that local business day (following is used if it is not one).
Multi-day holiday blocks (Spring Festival, Thanksgiving plus the Friday)
are skipped as a whole because stepping goes business day by business day.
"""
from __future__ import annotations

from datetime import date, datetime

from .calendar import BusinessCalendar
from .convention import get_convention
from .cutoff import effective_trade_day


def add_business_days(when, n: int, calendar: BusinessCalendar, *,
                      convention="following"):
    """Add ``n`` business days to a date or datetime.

    Datetime inputs observe the calendar cutoff and timezone; date inputs
    do not. The returned type matches the input: datetime in -> datetime
    (calendar tz) out, date in -> date out.

    ``convention`` controls how a non-business date input is first rolled
    (ignored for business-day inputs and for datetimes, where the cutoff
    fixes the effective session and following applies afterwards).
    """
    conv = get_convention(convention)

    if isinstance(when, datetime):
        start = effective_trade_day(when, calendar)
        result = _step(start, n, calendar)
        return datetime(result.year, result.month, result.day, tzinfo=calendar.tz)

    d = when
    if not calendar.is_business_day(d):
        from .adjust import adjust
        d = adjust(d, conv, calendar)
    return _step(d, n, calendar)


def _step(d: date, n: int, calendar: BusinessCalendar) -> date:
    if n >= 0:
        for _ in range(n):
            d = calendar.next_business_day(d)
    else:
        for _ in range(-n):
            d = calendar.previous_business_day(d)
    return d


def t_plus_n(when, n: int, calendar: BusinessCalendar, *, convention="following"):
    """Trade date plus N business (settlement) days.

    Semantic alias for :func:`add_business_days`: counting starts from the
    effective trade session (post-cutoff trades belong to the next session).
    """
    return add_business_days(when, n, calendar, convention=convention)


# Settlement desk vocabulary.
settlement_date = t_plus_n
value_date = t_plus_n
