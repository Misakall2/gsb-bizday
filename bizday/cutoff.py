"""Datetime / timezone / cutoff handling.

Cutoff semantics
----------------
A calendar may define a daily cutoff (e.g. 17:00 America/New_York for US
equities). The cutoff instant is the boundary:

* ``event_time < cutoff``  -> the trade belongs to that local business day;
* ``event_time >= cutoff`` -> it is booked on the *next* business day, and
  T+N counting starts from there.

In other words the cutoff minute itself is exclusive of the current day
(``>=`` rolls forward), uniformly for every entry point in this library.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from .calendar import BusinessCalendar


def as_calendar_datetime(when, calendar: BusinessCalendar) -> datetime:
    """Normalize a date/datetime into the calendar timezone.

    Naive datetimes are interpreted in the calendar's default timezone.
    Aware datetimes are converted into it. A plain ``date`` becomes
    00:00 local (start of day, always before any reasonable cutoff).
    """
    tz = calendar.tz
    if isinstance(when, datetime):
        if when.tzinfo is None:
            return when.replace(tzinfo=tz)
        return when.astimezone(tz)
    if isinstance(when, date):
        return datetime(when.year, when.month, when.day, tzinfo=tz)
    raise TypeError(f"expected date or datetime, got {type(when)!r}")


def _cutoff_for(local_day: date, calendar: BusinessCalendar):
    cutoff = calendar.cutoff_time
    if cutoff is None:
        return None
    if isinstance(cutoff, datetime):
        cutoff = cutoff.timetz()
    if cutoff.tzinfo is None:
        # Naive cutoff time means local wall-clock time of the calendar.
        return datetime.combine(local_day, cutoff).replace(tzinfo=calendar.tz)
    # An aware time: combine then convert to calendar tz.
    aware = datetime.combine(local_day, cutoff)
    return aware.astimezone(calendar.tz)


def effective_trade_day(when, calendar: BusinessCalendar) -> date:
    """Return the business day a trade is booked on.

    Applies the cutoff first, then rolls to a business day using following.
    """
    local = as_calendar_datetime(when, calendar)
    day = local.date()

    cutoff = _cutoff_for(day, calendar)
    if cutoff is not None and local >= cutoff:
        day = day + timedelta(days=1)

    if not calendar.is_business_day(day):
        day = calendar.next_business_day(day)
    return day
