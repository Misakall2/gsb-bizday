"""Market calendars: weekend rules + holiday sets with observance."""
from __future__ import annotations

from datetime import date, timedelta
from enum import Enum
from typing import Iterable, Set
from zoneinfo import ZoneInfo

from .convention import Convention, get_convention


class WeekendRule(str, Enum):
    """Which weekdays are the weekly rest days.

    Values are (Saturday, Sunday) flags keyed by date.weekday():
    Monday=0 ... Sunday=6.
    """

    SAT_SUN = "sat_sun"  # most markets
    FRI_SAT = "fri_sat"  # e.g. parts of the Middle East
    FRI_SUN = "fri_sun"  # rare hybrid
    THU_FRI = "thu_fri"


# Backwards-friendly shorter alias.
Weekend = WeekendRule

_WEEKEND_WEEKDAYS = {
    WeekendRule.SAT_SUN: frozenset({5, 6}),
    WeekendRule.FRI_SAT: frozenset({4, 5}),
    WeekendRule.FRI_SUN: frozenset({4, 6}),
    WeekendRule.THU_FRI: frozenset({3, 4}),
}

_WEEKEND_ALIASES = {
    "satsun": WeekendRule.SAT_SUN,
    "sunsat": WeekendRule.SAT_SUN,
    "weekend": WeekendRule.SAT_SUN,
    "frisat": WeekendRule.FRI_SAT,
    "satfri": WeekendRule.FRI_SAT,
    "frisun": WeekendRule.FRI_SUN,
    "sunfri": WeekendRule.FRI_SUN,
    "thufri": WeekendRule.THU_FRI,
    "frithu": WeekendRule.THU_FRI,
}


def get_weekend_rule(value) -> WeekendRule:
    if isinstance(value, WeekendRule):
        return value
    if isinstance(value, str):
        key = "".join(ch for ch in value.strip().lower() if ch not in " _-,\t")
        if key in _WEEKEND_ALIASES:
            return _WEEKEND_ALIASES[key]
    raise ValueError(f"unknown weekend rule: {value!r}")


class BusinessCalendar:
    """A market calendar.

    Parameters
    ----------
    name:
        Market identifier, e.g. ``"us"`` / ``"cn"``.
    holidays:
        Raw holiday dates supplied by the caller. A holiday falling on a
        weekend is *observed* on another business day per ``observance``.
    weekend:
        Weekly rest days. Defaults to Saturday/Sunday.
    observance:
        Convention used when a raw holiday lands on the weekend.
    tz:
        Default IANA timezone for naive datetimes and cutoff evaluation.
    cutoff_time:
        ``datetime.time`` (tz-aware recommended). An event at exactly the
        cutoff is treated as *on* the cutoff: i.e. it belongs to the next
        business day (cutoff is exclusive of the current day).
    """

    name: str = "default"
    def __init__(
        self,
        name: str = "default",
        holidays: Iterable[date] = (),
        weekend=WeekendRule.SAT_SUN,
        observance=Convention.UNADJUSTED,
        tz="UTC",
        cutoff_time=None,
    ):
        weekend = get_weekend_rule(weekend)
        observance = get_convention(observance)
        if isinstance(tz, str):
            tz = ZoneInfo(tz)

        raw = frozenset(holidays)
        for h in raw:
            if not isinstance(h, date):
                raise TypeError(f"holidays must contain dates, got {type(h)!r}")

        observed = self._build_observed(raw, weekend, observance)

        self.name = name
        self.holidays = raw
        self.weekend = weekend
        self.observance = observance
        self.tz = tz
        self.cutoff_time = cutoff_time
        self._off = observed

    def __eq__(self, other):
        if not isinstance(other, BusinessCalendar):
            return NotImplemented
        return (
            self.name == other.name
            and self.holidays == other.holidays
            and self.weekend == other.weekend
            and self.observance == other.observance
            and str(self.tz) == str(other.tz)
        )

    def __hash__(self):
        return hash((self.name, self.holidays, self.weekend, self.observance, str(self.tz)))

    def __repr__(self):
        return (
            f"BusinessCalendar(name={self.name!r}, weekend={self.weekend.value!r}, "
            f"observance={self.observance.value!r}, tz={self.tz})"
        )

    def replace(self, **kwargs) -> "BusinessCalendar":
        """Return a copy with selected fields replaced."""
        params = dict(
            name=self.name,
            holidays=self.holidays,
            weekend=self.weekend,
            observance=self.observance,
            tz=self.tz,
            cutoff_time=self.cutoff_time,
        )
        params.update(kwargs)
        return BusinessCalendar(**params)

    # ------------------------------------------------------------------
    # construction helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _build_observed(
        raw: frozenset, weekend: WeekendRule, observance: Convention
    ) -> frozenset:
        """Expand raw holidays into the set of non-business dates.

        The raw holiday date and its observed date (if different) are both
        non-business. A Saturday holiday observed following -> Monday;
        a Sunday holiday observed following also -> Monday. Observed dates
        only skip the weekly rest days and other *raw* holidays, so two
        holidays sharing an observed Monday both land on that Monday rather
        than cascading apart.
        """
        off: Set[date] = set()
        rest = _WEEKEND_WEEKDAYS[weekend]
        for h in raw:
            if h.weekday() in rest and observance is not Convention.UNADJUSTED:
                obs = _shift_to_business(
                    h,
                    observance,
                    is_nonbiz=lambda d, _rest=rest, _raw=raw: (
                        d.weekday() in _rest or d in _raw
                    ),
                )
                off.add(obs)
        off |= raw
        return frozenset(off)

    # ------------------------------------------------------------------
    # day predicates / navigation
    # ------------------------------------------------------------------
    def is_weekend(self, d: date) -> bool:
        return d.weekday() in _WEEKEND_WEEKDAYS[self.weekend]

    def is_holiday(self, d: date) -> bool:
        """True if the date is a raw holiday or an observed holiday."""
        return d in self._off

    def is_business_day(self, d: date) -> bool:
        return not self.is_weekend(d) and d not in self._off

    def next_business_day(self, d: date) -> date:
        d = d + timedelta(days=1)
        while not self.is_business_day(d):
            d += timedelta(days=1)
        return d

    def previous_business_day(self, d: date) -> date:
        d = d - timedelta(days=1)
        while not self.is_business_day(d):
            d -= timedelta(days=1)
        return d

    def adjust(self, d: date, convention="following") -> date:
        # local import to avoid cycle at module import time
        from .adjust import adjust

        return adjust(d, convention, self)

    def add_business_days(self, d, n: int, convention="following"):
        from .offset import add_business_days

        return add_business_days(d, n, self, convention=convention)

    def t_plus_n(self, when, n: int, convention="following"):
        from .offset import t_plus_n

        return t_plus_n(when, n, self, convention=convention)

    def add_months(self, d, months: int, convention=None):
        from .month import add_months

        return add_months(d, months, self, convention=convention)


# Friendly alias used by the trading team.
MarketCalendar = BusinessCalendar


def _shift_to_business(d: date, convention: Convention, *, is_nonbiz) -> date:
    """Shift one date per convention against an arbitrary non-business test."""
    if convention is Convention.FOLLOWING:
        cur = d
        while is_nonbiz(cur):
            cur += timedelta(days=1)
        return cur
    if convention is Convention.PRECEDING:
        cur = d
        while is_nonbiz(cur):
            cur -= timedelta(days=1)
        return cur
    if convention is Convention.MODIFIED_FOLLOWING:
        cur = d
        while is_nonbiz(cur):
            cur += timedelta(days=1)
        if cur.month != d.month:
            cur = d
            while is_nonbiz(cur):
                cur -= timedelta(days=1)
        return cur
    if convention is Convention.MODIFIED_PRECEDING:
        cur = d
        while is_nonbiz(cur):
            cur -= timedelta(days=1)
        if cur.month != d.month:
            cur = d
            while is_nonbiz(cur):
                cur += timedelta(days=1)
        return cur
    return d
