"""Composite calendars: combine two or more market calendars.

Weekend shapes and holiday observance are applied by each constituent
*first*; the composite only combines the resulting business-day
predicates. Holidays are never merged at the raw-table level.
"""

from __future__ import annotations

from datetime import date

from .calendar import Calendar
from .conventions import UNADJUSTED

JOIN = "join"
EITHER = "either"

_MODES = {JOIN, EITHER}


class CompositeCalendar(Calendar):
    """A calendar built from several constituent calendars.

    mode="join":   a day is a business day only if *every* constituent
                   is open (cross-market payments, CLS-style).
    mode="either": a day is a business day if *any* constituent is open.

    The composite has its own ``tz``/``cutoff`` (defaulting to the first
    constituent's) so it can localize datetimes and settle with a cutoff
    like any other calendar.
    """

    def __init__(self, calendars, mode=JOIN, tz=None, cutoff=None):
        calendars = tuple(calendars)
        if mode not in _MODES:
            raise ValueError(f"mode must be one of {sorted(_MODES)}, got {mode!r}")
        if len(calendars) < 2:
            raise ValueError("a composite calendar needs at least two constituents")
        for cal in calendars:
            if not isinstance(cal, Calendar):
                raise TypeError(f"constituent must be a Calendar, got {type(cal).__name__}")
            if cal.tz is None:
                raise ValueError("constituent calendar has no IANA timezone")
            for w in cal.weekend:
                if not 0 <= w <= 6:
                    raise ValueError(f"constituent weekday out of range: {w}")
        self.calendars = calendars
        self.mode = mode
        super().__init__(
            weekend=(),
            holidays=(),
            observance=UNADJUSTED,
            tz=tz if tz is not None else calendars[0].tz,
            cutoff=cutoff if cutoff is not None else calendars[0].cutoff,
        )

    # Constituents observe their own holidays first, then the results
    # are combined -- never the other way around.
    def is_weekend(self, d: date) -> bool:
        if self.mode == JOIN:
            return any(cal.is_weekend(d) for cal in self.calendars)
        return all(cal.is_weekend(d) for cal in self.calendars)

    def is_holiday(self, d: date) -> bool:
        if self.mode == JOIN:
            return any(cal.is_holiday(d) for cal in self.calendars)
        return all(cal.is_holiday(d) for cal in self.calendars)

    def is_business_day(self, d: date) -> bool:
        if self.mode == JOIN:
            return all(cal.is_business_day(d) for cal in self.calendars)
        return any(cal.is_business_day(d) for cal in self.calendars)

    def observed_holidays(self) -> frozenset:
        sets = [cal.observed_holidays() for cal in self.calendars]
        if self.mode == JOIN:
            return frozenset().union(*sets)
        return frozenset.intersection(*sets)
