"""Calendar-month arithmetic with end-of-month stickiness.

Dependencies: the holiday table (business-day predicate / nearest
business day) and the adjustment entry point for convention names.
"""

from __future__ import annotations

import calendar as _cal
from datetime import date, timedelta

from . import adjustment

_ONE_DAY = timedelta(days=1)


def is_month_end_business_day(table, d: date) -> bool:
    return table.is_business_day(d) and adjustment.step(table, d, +1).month != d.month


def last_business_day_of_month(table, year: int, month: int) -> date:
    d = date(year, month, _cal.monthrange(year, month)[1])
    while not table.is_business_day(d):
        d -= _ONE_DAY
    return d


def add_months(table, d: date, months: int, convention) -> date:
    """Add calendar months with EOM stickiness.

    If ``d`` is the last business day of its month, the result is the
    last business day of the target month. Otherwise the day-of-month
    is preserved where possible (clamped, e.g. Jan 31 + 1mo -> Feb 28
    or Feb 29 in a leap year) and then adjusted per ``convention``.
    """
    total = d.year * 12 + (d.month - 1) + months
    year, month = divmod(total, 12)
    month += 1
    if is_month_end_business_day(table, d):
        return last_business_day_of_month(table, year, month)
    day = min(d.day, _cal.monthrange(year, month)[1])
    return adjustment.adjust(table, date(year, month, day), convention)
