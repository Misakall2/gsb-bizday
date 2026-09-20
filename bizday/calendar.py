"""Market calendar facade: weekends, observed holidays, T+N, EOM, cutoffs.

This module only wires the pieces together and owns the public API.
The responsibilities live in focused modules, layered bottom-up:

    conventions  English/Chinese name normalization (single place)
    observance   weekend layout + observed-holiday resolution
    workdays     business-day stepping, adjust conventions, T+N
    months       end-of-month sticky month arithmetic
    cutoff       timezone localization + the daily cutoff rule

Each layer depends only on the ones listed above it.
"""

from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from .conventions import (
    FOLLOWING,
    UNADJUSTED,
    normalize_convention,
)
from .observance import Observance
from .workdays import Workdays
from .months import MonthArithmetic
from .cutoff import CutoffClock


class Calendar:
    """A single market's business-day calendar.

    Parameters
    ----------
    weekend:
        Iterable of weekday numbers (Monday=0 .. Sunday=6) that are
        non-business days. US/CN default is (5, 6); a Fri/Sat market
        would use (4, 5).
    holidays:
        Iterable of ``date`` objects supplied by the caller.
    observance:
        How a holiday that lands on a weekend is observed. Accepts
        following / preceding / modified_following / modified_preceding
        / unadjusted (English or Chinese names).
    tz:
        IANA timezone name for the market, e.g. "America/New_York".
        Naive datetimes passed in are interpreted in this zone.
    cutoff:
        A ``datetime.time`` in the market's local time. A trade at a
        local time strictly *later* than the cutoff counts as the next
        business day; a trade exactly *at* the cutoff still counts as
        that day (cutoff is inclusive). ``None`` disables the cutoff.
    """

    def __init__(self, weekend=(5, 6), holidays=(), observance=UNADJUSTED,
                 tz="UTC", cutoff=None):
        self.weekend = frozenset(weekend)
        for w in self.weekend:
            if not 0 <= w <= 6:
                raise ValueError(f"weekday out of range: {w}")
        self.holidays = frozenset(holidays)
        self.observance = normalize_convention(observance)
        self.tz = ZoneInfo(tz) if isinstance(tz, str) else tz
        if cutoff is not None and not isinstance(cutoff, time):
            raise TypeError("cutoff must be a datetime.time or None")
        self.cutoff = cutoff
        self._engine_key = None
        self._observance = None
        self._workdays = None
        self._months = None
        self._clock = None

    # ------------------------------------------------------------------
    # engine wiring
    # ------------------------------------------------------------------
    def _engine(self):
        """The layer stack for the current attribute values.

        Rebuilt whenever weekend/holidays/observance/tz/cutoff change,
        so the observed-holiday cache inside Observance can never go
        stale after the caller edits the holiday table.
        """
        key = (self.weekend, self.holidays, self.observance,
               self.tz, self.cutoff)
        if key != self._engine_key:
            self._observance = Observance(self.weekend, self.holidays,
                                          self.observance)
            self._workdays = Workdays(self._observance)
            self._months = MonthArithmetic(self._workdays)
            self._clock = CutoffClock(self.tz, self.cutoff, self._workdays)
            self._engine_key = key
        return self._observance, self._workdays, self._months, self._clock

    # ------------------------------------------------------------------
    # basic predicates
    # ------------------------------------------------------------------
    def is_weekend(self, d: date) -> bool:
        observance, _, _, _ = self._engine()
        return observance.is_weekend(d)

    def observed_holidays(self) -> frozenset:
        """Holidays after applying the observance rule to weekend hits."""
        observance, _, _, _ = self._engine()
        return observance.observed()

    def is_holiday(self, d: date) -> bool:
        observance, _, _, _ = self._engine()
        return observance.is_holiday(d)

    def is_business_day(self, d: date) -> bool:
        _, workdays, _, _ = self._engine()
        return workdays.is_business_day(d)

    # ------------------------------------------------------------------
    # date adjustment conventions
    # ------------------------------------------------------------------
    def adjust(self, d: date, convention=FOLLOWING) -> date:
        """Adjust ``d`` to a business day per the convention.

        ``unadjusted`` returns ``d`` unchanged, even on weekends/holidays.
        """
        _, workdays, _, _ = self._engine()
        return workdays.adjust(d, normalize_convention(convention))

    # ------------------------------------------------------------------
    # T+N (business days, N may be 0 or negative)
    # ------------------------------------------------------------------
    def shift(self, start: date, n: int, convention=FOLLOWING) -> date:
        """Move ``n`` business days from ``start``.

        ``n == 0`` adjusts ``start`` itself to a business day (per
        ``convention``). Positive ``n`` rolls forward, negative rolls
        backward; consecutive holidays/weekends are skipped as one run.
        """
        _, workdays, _, _ = self._engine()
        return workdays.shift(start, n, normalize_convention(convention))

    def business_days_between(self, start: date, end: date) -> int:
        """Signed count of business-day steps from start to end."""
        _, workdays, _, _ = self._engine()
        return workdays.business_days_between(start, end)

    # ------------------------------------------------------------------
    # month arithmetic with end-of-month stickiness
    # ------------------------------------------------------------------
    def is_month_end_business_day(self, d: date) -> bool:
        _, _, months, _ = self._engine()
        return months.is_month_end_business_day(d)

    def last_business_day_of_month(self, year: int, month: int) -> date:
        _, _, months, _ = self._engine()
        return months.last_business_day_of_month(year, month)

    def add_months(self, d: date, months: int, convention=FOLLOWING) -> date:
        """Add calendar months with EOM stickiness.

        If ``d`` is the last business day of its month, the result is the
        last business day of the target month. Otherwise the day-of-month
        is preserved where possible (clamped, e.g. Jan 31 + 1mo -> Feb 28
        or Feb 29 in a leap year) and then adjusted per ``convention``.
        """
        _, _, month_arith, _ = self._engine()
        return month_arith.add_months(d, months, normalize_convention(convention))

    # ------------------------------------------------------------------
    # datetimes, timezones, cutoffs
    # ------------------------------------------------------------------
    def localize(self, dt: datetime) -> datetime:
        """Interpret a datetime in this calendar's timezone.

        Aware datetimes are converted; naive ones are assumed to already
        be in the market's local time. DST transitions are handled by
        zoneinfo, so spring-forward/fall-back days do not blow up.
        """
        _, _, _, clock = self._engine()
        return clock.localize(dt)

    def trade_date(self, dt) -> date:
        """The business date a trade belongs to, after the cutoff rule.

        Local time strictly after the cutoff rolls to the next business
        day; exactly at the cutoff stays on the same day. The result is
        always a business day.
        """
        _, _, _, clock = self._engine()
        return clock.trade_date(dt)

    def settle_date(self, dt, n: int, convention=FOLLOWING) -> date:
        """T+N settlement date for a trade done at ``dt`` (date or datetime).

        The cutoff is applied first to find the trade's business date,
        then ``n`` business days are counted from there.
        """
        return self.shift(self.trade_date(dt), n, convention)
