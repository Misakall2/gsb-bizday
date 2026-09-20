"""Weekend layout and holiday observance: which dates are non-business.

Dependency direction: this module sits directly above ``conventions``
and below everything else. It knows nothing about stepping, month
arithmetic, timezones, or cutoffs.
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


class Observance:
    """Resolve raw caller-supplied holidays against a weekend layout.

    Immutable value object: ``weekend``, ``holidays`` and ``observance``
    are fixed at construction and never mutated. The observed-holiday
    set is computed lazily and cached on the instance; ``Calendar``
    builds a fresh ``Observance`` whenever its own attributes change,
    so this cache can never outlive an edit to the holiday table.
    """

    __slots__ = ("weekend", "holidays", "observance", "_observed")

    def __init__(self, weekend: frozenset, holidays: frozenset, observance: str):
        self.weekend = weekend
        self.holidays = holidays
        self.observance = observance
        self._observed = None

    def is_weekend(self, d: date) -> bool:
        return d.weekday() in self.weekend

    def observed(self) -> frozenset:
        """Holidays after applying the observance rule to weekend hits."""
        if self._observed is None:
            self._observed = frozenset(
                self._observe(h) if self.is_weekend(h) else h
                for h in self.holidays
            )
        return self._observed

    def is_holiday(self, d: date) -> bool:
        return d in self.observed()

    def _observe(self, h: date) -> date:
        """Move a weekend holiday per the observance rule.

        Only raw weekends and the raw holiday table are considered here,
        so this never recurses into observed().
        """
        if self.observance == UNADJUSTED:
            return h

        def raw_ok(d: date) -> bool:
            return not self.is_weekend(d) and d not in self.holidays

        def raw_step(d: date, direction: int) -> date:
            d += direction * _ONE_DAY
            while not raw_ok(d):
                d += direction * _ONE_DAY
            return d

        if self.observance == FOLLOWING:
            return raw_step(h, +1)
        if self.observance == PRECEDING:
            return raw_step(h, -1)
        if self.observance == MODIFIED_FOLLOWING:
            fwd = raw_step(h, +1)
            return fwd if fwd.month == h.month else raw_step(h, -1)
        if self.observance == MODIFIED_PRECEDING:
            back = raw_step(h, -1)
            return back if back.month == h.month else raw_step(h, +1)
        raise ValueError(f"unknown observance: {self.observance!r}")
