"""Weekend/holiday predicates and weekend-holiday observance.

This module owns one thing: deciding which calendar dates are
non-business because of weekends or the (observed) holiday table.

Dependencies: conventions only. It does not know about business-day
stepping, month arithmetic, or cutoffs.
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

_ONE_DAY = timedelta(days=1)


class HolidayTable:
    """An immutable weekend + raw-holiday table with observance rules.

    The observed-holiday cache is keyed by the exact inputs it is
    derived from, so it can never serve stale results after the inputs
    change: a different table is a different ``HolidayTable``.
    """

    def __init__(self, weekend, holidays, observance=UNADJUSTED):
        weekend = frozenset(weekend)
        for w in weekend:
            if not 0 <= w <= 6:
                raise ValueError(f"weekday out of range: {w}")
        self.weekend = weekend
        self.holidays = frozenset(holidays)
        self.observance = observance
        self._cache_key = None
        self._observed = None

    def is_weekend(self, d: date) -> bool:
        return d.weekday() in self.weekend

    def _raw_ok(self, d: date) -> bool:
        """Weekday and absent from the raw (unobserved) holiday table."""
        return not self.is_weekend(d) and d not in self.holidays

    def _raw_step(self, d: date, direction: int) -> date:
        d += direction * _ONE_DAY
        while not self._raw_ok(d):
            d += direction * _ONE_DAY
        return d

    def _observe(self, h: date) -> date:
        """Move a weekend holiday per the observance rule.

        Only raw weekends and the raw holiday table are consulted here,
        so observing one holiday never cascades through another
        holiday's observed date.
        """
        if self.observance == UNADJUSTED:
            return h
        if self.observance == FOLLOWING:
            return self._raw_step(h, +1)
        if self.observance == PRECEDING:
            return self._raw_step(h, -1)
        if self.observance == MODIFIED_FOLLOWING:
            fwd = self._raw_step(h, +1)
            return fwd if fwd.month == h.month else self._raw_step(h, -1)
        if self.observance == MODIFIED_PRECEDING:
            back = self._raw_step(h, -1)
            return back if back.month == h.month else self._raw_step(h, +1)
        raise ValueError(f"unknown observance: {self.observance!r}")

    def observed_holidays(self) -> frozenset:
        """Holidays after applying the observance rule to weekend hits."""
        key = (self.weekend, self.holidays, self.observance)
        if self._cache_key != key:
            out = set()
            for h in self.holidays:
                out.add(self._observe(h) if self.is_weekend(h) else h)
            self._observed = frozenset(out)
            self._cache_key = key
        return self._observed

    def is_holiday(self, d: date) -> bool:
        return d in self.observed_holidays()

    def is_business_day(self, d: date) -> bool:
        return not self.is_weekend(d) and not self.is_holiday(d)
