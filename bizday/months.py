"""End-of-month sticky month arithmetic.

Dependency direction: sits above ``workdays`` (uses its stepping and
adjustment) and knows nothing about timezones or cutoffs.
"""

from __future__ import annotations

import calendar as _cal
from datetime import date, timedelta

from .workdays import Workdays

_ONE_DAY = timedelta(days=1)


class MonthArithmetic:
    """Add calendar months with end-of-month stickiness."""

    __slots__ = ("workdays",)

    def __init__(self, workdays: Workdays):
        self.workdays = workdays

    def is_month_end_business_day(self, d: date) -> bool:
        return (
            self.workdays.is_business_day(d)
            and self.workdays.step(d, +1).month != d.month
        )

    def last_business_day_of_month(self, year: int, month: int) -> date:
        d = date(year, month, _cal.monthrange(year, month)[1])
        while not self.workdays.is_business_day(d):
            d -= _ONE_DAY
        return d

    def add_months(self, d: date, months: int, convention: str) -> date:
        """Add calendar months with EOM stickiness.

        If ``d`` is the last business day of its month, the result is the
        last business day of the target month. Otherwise the day-of-month
        is preserved where possible (clamped, e.g. Jan 31 + 1mo -> Feb 28
        or Feb 29 in a leap year) and then adjusted per ``convention``.
        """
        total = d.year * 12 + (d.month - 1) + months
        year, month = divmod(total, 12)
        month += 1
        if self.is_month_end_business_day(d):
            return self.last_business_day_of_month(year, month)
        day = min(d.day, _cal.monthrange(year, month)[1])
        return self.workdays.adjust(date(year, month, day), convention)
