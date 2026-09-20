"""Business-day predicates, stepping, adjustment conventions, T+N.

Dependency direction: sits above ``observance`` (an ``Observance``
instance tells it which dates are non-business) and below ``months``
and ``cutoff``. Conventions arrive here already normalized by the
``conventions`` module; no name translation happens in this file.
"""

from __future__ import annotations

from datetime import date, timedelta

from .conventions import (
    FOLLOWING,
    PRECEDING,
    MODIFIED_FOLLOWING,
    MODIFIED_PRECEDING,
    UNADJUSTED,
)
from .observance import Observance

_ONE_DAY = timedelta(days=1)


class Workdays:
    """Step and adjust over the business days of one market."""

    __slots__ = ("observance",)

    def __init__(self, observance: Observance):
        self.observance = observance

    def is_business_day(self, d: date) -> bool:
        return not self.observance.is_weekend(d) and not self.observance.is_holiday(d)

    def step(self, d: date, direction: int) -> date:
        """Next business day strictly after ``d`` in ``direction``."""
        d += direction * _ONE_DAY
        while not self.is_business_day(d):
            d += direction * _ONE_DAY
        return d

    def adjust(self, d: date, convention: str) -> date:
        """Adjust ``d`` to a business day per a canonical convention.

        ``unadjusted`` returns ``d`` unchanged, even on weekends/holidays.
        """
        if convention == UNADJUSTED:
            return d
        if self.is_business_day(d):
            return d
        if convention == FOLLOWING:
            return self.step(d, +1)
        if convention == PRECEDING:
            return self.step(d, -1)
        if convention == MODIFIED_FOLLOWING:
            fwd = self.step(d, +1)
            return fwd if fwd.month == d.month else self.step(d, -1)
        if convention == MODIFIED_PRECEDING:
            back = self.step(d, -1)
            return back if back.month == d.month else self.step(d, +1)
        raise ValueError(f"unknown convention: {convention!r}")

    def shift(self, start: date, n: int, convention: str) -> date:
        """Move ``n`` business days from ``start``.

        ``n == 0`` adjusts ``start`` itself to a business day (per
        ``convention``). Positive ``n`` rolls forward, negative rolls
        backward; consecutive holidays/weekends are skipped as one run.
        """
        if not isinstance(n, int):
            raise TypeError("n must be an int")
        if n == 0:
            return self.adjust(start, convention)
        d = start
        step = +1 if n > 0 else -1
        for _ in range(abs(n)):
            d = self.step(d, step)
        return d

    def business_days_between(self, start: date, end: date) -> int:
        """Signed count of business-day steps from start to end."""
        if start == end:
            return 0
        step = +1 if end > start else -1
        d, count = start, 0
        while d != end:
            d = self.step(d, step)
            count += step
        return count
