"""Market calendar: weekends, observed holidays, T+N, EOM, cutoffs."""

from __future__ import annotations

import calendar as _cal
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from .conventions import (
    FOLLOWING,
    PRECEDING,
    MODIFIED_FOLLOWING,
    MODIFIED_PRECEDING,
    UNADJUSTED,
    normalize_convention,
)

_ONE_DAY = timedelta(days=1)


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
        self._observed_cache = None

    # ------------------------------------------------------------------
    # basic predicates
    # ------------------------------------------------------------------
    def is_weekend(self, d: date) -> bool:
        return d.weekday() in self.weekend

    def observed_holidays(self) -> frozenset:
        """Holidays after applying the observance rule to weekend hits."""
        if self._observed_cache is not None:
            return self._observed_cache
        out = set()
        for h in self.holidays:
            if self.is_weekend(h):
                out.add(self._observe(h))
            else:
                out.add(h)
        self._observed_cache = frozenset(out)
        return self._observed_cache

    def _observe(self, h: date) -> date:
        """Move a weekend holiday per the observance rule.

        Only raw weekends and the raw holiday table are considered here,
        so this never recurses into observed_holidays().
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

    def is_holiday(self, d: date) -> bool:
        return d in self.observed_holidays()

    def is_business_day(self, d: date) -> bool:
        return not self.is_weekend(d) and not self.is_holiday(d)

    # ------------------------------------------------------------------
    # date adjustment conventions
    # ------------------------------------------------------------------
    def _step(self, d: date, direction: int) -> date:
        d += direction * _ONE_DAY
        while not self.is_business_day(d):
            d += direction * _ONE_DAY
        return d

    def _adjust_raw(self, d: date, convention: str) -> date:
        """Adjust without consulting the observed-holiday cache."""
        if convention == UNADJUSTED:
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

    def adjust(self, d: date, convention=FOLLOWING) -> date:
        """Adjust ``d`` to a business day per the convention.

        ``unadjusted`` returns ``d`` unchanged, even on weekends/holidays.
        """
        convention = normalize_convention(convention)
        if convention == UNADJUSTED:
            return d
        if self.is_business_day(d):
            return d
        return self._adjust_raw(d, convention)

    # ------------------------------------------------------------------
    # T+N (business days, N may be 0 or negative)
    # ------------------------------------------------------------------
    def shift(self, start: date, n: int, convention=FOLLOWING) -> date:
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
            d = self._step(d, step)
        return d

    def business_days_between(self, start: date, end: date) -> int:
        """Signed count of business-day steps from start to end."""
        if start == end:
            return 0
        step = +1 if end > start else -1
        d, count = start, 0
        while d != end:
            d = self._step(d, step)
            count += step
        return count

    # ------------------------------------------------------------------
    # month arithmetic with end-of-month stickiness
    # ------------------------------------------------------------------
    def is_month_end_business_day(self, d: date) -> bool:
        return self.is_business_day(d) and self._step(d, +1).month != d.month

    def last_business_day_of_month(self, year: int, month: int) -> date:
        d = date(year, month, _cal.monthrange(year, month)[1])
        while not self.is_business_day(d):
            d -= _ONE_DAY
        return d

    def add_months(self, d: date, months: int, convention=FOLLOWING) -> date:
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
        return self.adjust(date(year, month, day), convention)

    # ------------------------------------------------------------------
    # datetimes, timezones, cutoffs
    # ------------------------------------------------------------------
    def localize(self, dt: datetime) -> datetime:
        """Interpret a datetime in this calendar's timezone.

        Aware datetimes are converted; naive ones are assumed to already
        be in the market's local time. DST transitions are handled by
        zoneinfo, so spring-forward/fall-back days do not blow up.
        """
        if not isinstance(dt, datetime):
            raise TypeError("expected a datetime")
        if dt.tzinfo is None:
            return dt.replace(tzinfo=self.tz)
        return dt.astimezone(self.tz)

    def trade_date(self, dt) -> date:
        """The business date a trade belongs to, after the cutoff rule.

        Local time strictly after the cutoff rolls to the next business
        day; exactly at the cutoff stays on the same day. The result is
        always a business day.
        """
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
        """T+N settlement date for a trade done at ``dt`` (date or datetime).

        The cutoff is applied first to find the trade's business date,
        then ``n`` business days are counted from there.
        """
        return self.shift(self.trade_date(dt), n, convention)
