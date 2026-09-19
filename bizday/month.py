"""Calendar-month arithmetic with end-of-month handling."""
from __future__ import annotations

import calendar as _stdcalendar
from datetime import date, datetime

from .calendar import BusinessCalendar
from .convention import Convention, get_convention


def month_end(year: int, month: int) -> date:
    """Last calendar day of the given month (works for leap Feb)."""
    last_day = _stdcalendar.monthrange(year, month)[1]
    return date(year, month, last_day)


def is_end_of_month(d: date) -> bool:
    """True if ``d`` is the last calendar day of its month."""
    return d.day == _stdcalendar.monthrange(d.year, d.month)[1]


def _shift_month(year: int, month: int, delta: int):
    total = (year * 12 + (month - 1)) + delta
    return total // 12, total % 12 + 1


def add_months(when, months: int, calendar: BusinessCalendar = None, *,
               convention=None, end_of_month: bool = None):
    """Add calendar months, honoring end-of-month (EOM) convention.

    Rules
    -----
    * The raw target day is the same day-of-month in the target month; when
      the target month is shorter, it falls on the target month's last
      calendar day (Jan 31 + 1m -> Feb 28/29).
    * If the input date is the last calendar day of its month, or
      ``end_of_month=True``, the result is the last *business* day of the
      target month (per ``calendar``). This keeps EOM rolls from spilling
      into the following month. ``end_of_month=False`` forces ordinary
      same-day behavior.
    * Otherwise, when a calendar is given, the raw target date is rolled
      with ``convention`` (default following). Without a calendar, the raw
      calendar date is returned.

    Date in -> date out. Datetime in -> datetime out (same wall time,
    calendar timezone for naive inputs).
    """
    if months != int(months):
        raise ValueError("months must be an integer")
    months = int(months)

    if isinstance(when, datetime):
        d = when.date()
        is_dt = True
    else:
        d = when
        is_dt = False

    force_eom = end_of_month if end_of_month is not None else is_end_of_month(d)

    y, m = _shift_month(d.year, d.month, months)

    if force_eom:
        target = month_end(y, m)
        if calendar is not None and not calendar.is_business_day(target):
            # Last business day of the month: walk backwards.
            target = calendar.previous_business_day(target)
    else:
        target_day = min(d.day, _stdcalendar.monthrange(y, m)[1])
        target = date(y, m, target_day)
        if calendar is not None and convention is not None and \
                get_convention(convention) is not Convention.UNADJUSTED:
            if not calendar.is_business_day(target):
                from .adjust import adjust
                target = adjust(target, convention, calendar)

    if is_dt:
        return datetime(target.year, target.month, target.day,
                        when.hour, when.minute, when.second, when.microsecond,
                        tzinfo=when.tzinfo or (calendar.tz if calendar else None))
    return target
