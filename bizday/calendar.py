"""Market calendar: composition root for the bizday modules.

The pieces live in focused modules with a one-way dependency chain::

    conventions (name normalization)
        ^
    observance (weekends, observed holidays, cached)
        ^
    adjustment (business-day stepping, adjust/shift)
        ^
    months (EOM sticky add_months)

    cutoff (localize + cutoff trade date) -> observance + adjustment

``Calendar`` itself stays immutable and per-market: it only wires a
:class:`~bizday.observance.HolidayTable`, a timezone and a cutoff
together and delegates. Each market gets its own instance; there is
no global state.
"""

from __future__ import annotations

from datetime import date, datetime, time

from . import adjustment, months
from . import cutoff as _cutoff
from .conventions import (
    FOLLOWING,
    UNADJUSTED,
    normalize_convention,
)
from .observance import HolidayTable


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
        observance = normalize_convention(observance)
        if cutoff is not None and not isinstance(cutoff, time):
            raise TypeError("cutoff must be a datetime.time or None")
        self._table = HolidayTable(weekend, holidays, observance)
        self._zone = _cutoff.resolve_timezone(tz)
        self.cutoff = cutoff

    # -- construction, never mutation --------------------------------
    def replace(self, **changes):
        """Return a new Calendar with the given construction args replaced.

        The instance is immutable on purpose; a changed holiday set is
        a new calendar, which also gets a fresh observance cache.
        """
        args = {
            "weekend": self.weekend,
            "holidays": self.holidays,
            "observance": self.observance,
            "tz": self.tz,
            "cutoff": self.cutoff,
        }
        args.update(changes)
        return type(self)(**args)

    # -- exposed configuration ---------------------------------------
    @property
    def weekend(self) -> frozenset:
        return self._table.weekend

    @property
    def holidays(self) -> frozenset:
        return self._table.holidays

    @property
    def observance(self) -> str:
        return self._table.observance

    @property
    def tz(self):
        return self._zone

    # ------------------------------------------------------------------
    # weekend / holiday predicates (observance)
    # ------------------------------------------------------------------
    def is_weekend(self, d: date) -> bool:
        return self._table.is_weekend(d)

    def observed_holidays(self) -> frozenset:
        return self._table.observed_holidays()

    def is_holiday(self, d: date) -> bool:
        return self._table.is_holiday(d)

    def is_business_day(self, d: date) -> bool:
        return self._table.is_business_day(d)

    # ------------------------------------------------------------------
    # date adjustment and T+N
    # ------------------------------------------------------------------
    def adjust(self, d: date, convention=FOLLOWING) -> date:
        """Adjust ``d`` to a business day per the convention.

        ``unadjusted`` returns ``d`` unchanged, even on weekends/holidays.
        """
        return adjustment.adjust(self._table, d, convention)

    def shift(self, start: date, n: int, convention=FOLLOWING) -> date:
        """Move ``n`` business days from ``start``.

        ``n == 0`` adjusts ``start`` itself to a business day (per
        ``convention``). Positive ``n`` rolls forward, negative rolls
        backward; consecutive holidays/weekends are skipped as one run.
        """
        return adjustment.shift(self._table, start, n, convention)

    def business_days_between(self, start: date, end: date) -> int:
        """Signed count of business-day steps from start to end."""
        return adjustment.business_days_between(self._table, start, end)

    # ------------------------------------------------------------------
    # month arithmetic with end-of-month stickiness
    # ------------------------------------------------------------------
    def is_month_end_business_day(self, d: date) -> bool:
        return months.is_month_end_business_day(self._table, d)

    def last_business_day_of_month(self, year: int, month: int) -> date:
        return months.last_business_day_of_month(self._table, year, month)

    def add_months(self, d: date, months_n: int, convention=FOLLOWING) -> date:
        """Add calendar months with EOM stickiness.

        If ``d`` is the last business day of its month, the result is the
        last business day of the target month. Otherwise the day-of-month
        is preserved where possible (clamped, e.g. Jan 31 + 1mo -> Feb 28
        or Feb 29 in a leap year) and then adjusted per ``convention``.
        """
        return months.add_months(self._table, d, months_n, convention)

    # ------------------------------------------------------------------
    # datetimes, timezones, cutoffs
    # ------------------------------------------------------------------
    def localize(self, dt: datetime) -> datetime:
        """Interpret a datetime in this calendar's timezone.

        Aware datetimes are converted; naive ones are assumed to already
        be in the market's local time. DST transitions are handled by
        zoneinfo, so spring-forward/fall-back days do not blow up.
        """
        return _cutoff.localize(self._zone, dt)

    def trade_date(self, dt) -> date:
        """The business date a trade belongs to, after the cutoff rule.

        Local time strictly after the cutoff rolls to the next business
        day; exactly at the cutoff stays on the same day. The result is
        always a business day.
        """
        return _cutoff.trade_date(self._table, self._zone, self.cutoff, dt)

    def settle_date(self, dt, n: int, convention=FOLLOWING) -> date:
        """T+N settlement date for a trade done at ``dt`` (date or datetime).

        The cutoff is applied first to find the trade's business date,
        then ``n`` business days are counted from there.
        """
        return self.shift(self.trade_date(dt), n, convention)
