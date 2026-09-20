"""Composite calendars built from two (or more) market calendars.

Two composition modes:

* ``join``   - a day is a business day only when BOTH legs are open.
* ``either`` - a day is a business day when AT LEAST ONE leg is open.

The legs are never flattened into one holiday set: each leg keeps its
own weekend definition (Sat/Sun vs Fri/Sat) and its own observance
rule, and the composite predicate is evaluated against the legs'
independently observed holiday calendars.
"""

from __future__ import annotations

import calendar as _cal
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from .calendar import Calendar, _ONE_DAY
from .conventions import (
    FOLLOWING,
    PRECEDING,
    MODIFIED_FOLLOWING,
    MODIFIED_PRECEDING,
    UNADJUSTED,
    normalize_convention,
)

JOIN = "join"
EITHER = "either"
_MODES = (JOIN, EITHER)


class CompositeCalendar:
    """A business-day calendar composed of two market calendars.

    The resulting object exposes the same date-level surface as
    :class:`Calendar`: ``is_business_day``, ``adjust``, ``shift``,
    ``business_days_between``, ``trade_date`` and ``settle_date``.

    A timezone and optional cutoff are required so that datetime inputs
    and cutoff-aware settlement work exactly like a single-market
    calendar. Naive datetimes are read in ``tz``.
    """

    def __init__(self, left, right, mode=JOIN, tz=None, cutoff=None):
        left = _as_calendar(left)
        right = _as_calendar(right)
        if mode not in _MODES:
            raise ValueError(f"unknown composite mode: {mode!r}; expected one of {_MODES}")
        if left is right:
            raise ValueError("cannot compose a calendar with itself")
        if left.tz is None or right.tz is None:
            raise ValueError("both legs must carry an IANA timezone")
        if tz is None:
            raise ValueError("composite calendar requires an explicit tz")
        if cutoff is not None and not isinstance(cutoff, time):
            raise TypeError("cutoff must be a datetime.time or None")

        self.left = left
        self.right = right
        self.mode = mode
        self.tz = ZoneInfo(tz) if isinstance(tz, str) else tz
        self.cutoff = cutoff
        self.calendars = (left, right)

    # ------------------------------------------------------------------
    # predicates
    # ------------------------------------------------------------------
    def is_business_day(self, d: date) -> bool:
        a = self.left.is_business_day(d)
        b = self.right.is_business_day(d)
        return (a and b) if self.mode == JOIN else (a or b)

    def is_weekend(self, d: date) -> bool:
        """Composite weekend predicate; holidays are not considered."""
        wa = self.left.is_weekend(d)
        wb = self.right.is_weekend(d)
        return (wa or wb) if self.mode == JOIN else (wa and wb)

    def is_holiday(self, d: date) -> bool:
        if self.mode == JOIN:
            return self.left.is_holiday(d) or self.right.is_holiday(d)
        return self.left.is_holiday(d) and self.right.is_holiday(d)

    # ------------------------------------------------------------------
    # adjustment / shifting (same semantics as Calendar)
    # ------------------------------------------------------------------
    def _step(self, d: date, direction: int) -> date:
        d += direction * _ONE_DAY
        while not self.is_business_day(d):
            d += direction * _ONE_DAY
        return d

    def adjust(self, d: date, convention=FOLLOWING) -> date:
        convention = normalize_convention(convention)
        if convention == UNADJUSTED:
            return d
        if self.is_business_day(d):
            return d
        if convention == FOLLOWING:
            return self._step(d, +1)
        if convention == PRECEDING:
            return self._step(d, -1)
        if convention == MODIFIED_FOLLOWING:
            fwd = self._step(d, +1)
            return fwd if fwd.month == d.month else self._step(d, -1)
        if convention == MODIFIED_PRECEDING:
            back = self._step(d, -1)
            return back if back.month == d.month else self._step(d, +1)
        raise ValueError(f"unknown convention: {convention!r}")

    def shift(self, start: date, n: int, convention=FOLLOWING) -> date:
        if not isinstance(n, int):
            raise TypeError("n must be an int")
        if n == 0:
            return self.adjust(start, convention)
        d = start
        step = +1 if n > 0 else -1
        for _ in range(abs(n)):
            d = self._step(d, step)
        return d

    def business_days_between(self, start: date, end: date) -> int:
        if start == end:
            return 0
        step = +1 if end > start else -1
        d, count = start, 0
        while d != end:
            d = self._step(d, step)
            count += step
        return count

    # ------------------------------------------------------------------
    # month-end helpers (mirrors Calendar)
    # ------------------------------------------------------------------
    def is_month_end_business_day(self, d: date) -> bool:
        return self.is_business_day(d) and self._step(d, +1).month != d.month

    def last_business_day_of_month(self, year: int, month: int) -> date:
        d = date(year, month, _cal.monthrange(year, month)[1])
        while not self.is_business_day(d):
            d -= _ONE_DAY
        return d

    def add_months(self, d: date, months: int, convention=FOLLOWING) -> date:
        total = d.year * 12 + (d.month - 1) + months
        year, month = divmod(total, 12)
        month += 1
        if self.is_month_end_business_day(d):
            return self.last_business_day_of_month(year, month)
        day = min(d.day, _cal.monthrange(year, month)[1])
        return self.adjust(date(year, month, day), convention)

    # ------------------------------------------------------------------
    # datetimes / cutoff (same inclusive-cutoff semantics as Calendar)
    # ------------------------------------------------------------------
    def localize(self, dt: datetime) -> datetime:
        if not isinstance(dt, datetime):
            raise TypeError("expected a datetime")
        if dt.tzinfo is None:
            return dt.replace(tzinfo=self.tz)
        return dt.astimezone(self.tz)

    def trade_date(self, dt) -> date:
        if isinstance(dt, datetime):
            local = self.localize(dt)
            d = local.date()
            if self.cutoff is not None and local.timetz().replace(tzinfo=None) > self.cutoff:
                d = self._step(d, +1)
        elif isinstance(dt, date):
            d = dt
        else:
            raise TypeError("expected a date or datetime")
        return self.adjust(d, FOLLOWING)

    def settle_date(self, dt, n: int, convention=FOLLOWING) -> date:
        return self.shift(self.trade_date(dt), n, convention)


def _as_calendar(obj):
    if isinstance(obj, Calendar):
        return obj
    if isinstance(obj, CompositeCalendar):
        # Nested composites muddy the two-leg validation; compose the
        # underlying leaf calendars instead.
        raise TypeError("nested CompositeCalendar is not supported; pass leaf Calendars")
    raise TypeError(f"expected a Calendar, got {type(obj).__name__}")


def composite_calendar(left, right, mode=JOIN, tz=None, cutoff=None):
    """Convenience constructor mirroring ``Calendar(...)`` call style."""
    return CompositeCalendar(left, right, mode=mode, tz=tz, cutoff=cutoff)
