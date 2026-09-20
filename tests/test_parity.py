"""Behavior-parity tests: refactored bizday vs. the frozen pre-refactor copy.

These tests compare *behavior*, not file layout. ``tests/_legacy`` is a
verbatim snapshot of the single-file implementation kept only as an
oracle; it is loaded as its own package so it never imports the
refactored ``bizday`` by accident.
"""

import importlib.util
import sys
import unittest
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from bizday import Calendar

ET = "America/New_York"
BJ = "Asia/Shanghai"


def _load_legacy():
    root = Path(__file__).resolve().parent / "_legacy"
    pkg_name = "legacy_bizday_oracle"
    if pkg_name in sys.modules:
        return sys.modules[pkg_name]
    spec = importlib.util.spec_from_loader(pkg_name, loader=None)
    pkg = importlib.util.module_from_spec(spec)
    pkg.__path__ = [str(root)]
    sys.modules[pkg_name] = pkg
    loaded = []
    for name in ("conventions", "calendar"):
        module_spec = importlib.util.spec_from_file_location(
            f"{pkg_name}.{name}", root / f"{name}.py"
        )
        module = importlib.util.module_from_spec(module_spec)
        sys.modules[f"{pkg_name}.{name}"] = module
        module_spec.loader.exec_module(module)
        loaded.append(module)
    pkg.conventions, pkg.calendar = loaded
    return pkg


_LEGACY_PKG = _load_legacy()
LegacyCalendar = _LEGACY_PKG.calendar.Calendar


SPRING_FESTIVAL_2024 = {date(2024, 2, d) for d in range(10, 18)}


def _pair(**kwargs):
    """Build matching refactored and legacy calendars."""
    return Calendar(**kwargs), LegacyCalendar(**kwargs)


class ParityTest(unittest.TestCase):
    # -- cutoff boundary: 17:00:00 inclusive, 17:00:01 rolls ---------
    def test_cutoff_boundary_inclusive_minute(self):
        new, old = _pair(tz=ET, cutoff=time(17, 0))
        at = datetime(2024, 3, 8, 17, 0, 0)
        after = datetime(2024, 3, 8, 17, 0, 1)
        for dt in (at, after):
            self.assertEqual(new.trade_date(dt), old.trade_date(dt))
        self.assertEqual(new.trade_date(at), date(2024, 3, 8))
        self.assertEqual(new.trade_date(after), date(2024, 3, 11))
        self.assertEqual(new.settle_date(after, 1),
                         old.settle_date(after, 1))
        self.assertEqual(new.settle_date(after, 1), date(2024, 3, 12))

    def test_cutoff_aware_conversion_matches(self):
        new, old = _pair(tz=ET, cutoff=time(17, 0))
        # 22:00 UTC == 17:00 EST exactly (inclusive); 22:01 UTC rolls.
        for hour, minute in ((22, 0), (22, 1)):
            dt = datetime(2024, 3, 8, hour, minute, tzinfo=ZoneInfo("UTC"))
            self.assertEqual(new.trade_date(dt), old.trade_date(dt))

    # -- Saturday holiday observed on Friday is not a business day ---
    def test_saturday_holiday_observed_friday_parity(self):
        kwargs = dict(
            holidays={date(2021, 7, 3)},
            observance="preceding",
            tz=ET,
            cutoff=time(17, 0),
        )
        new, old = Calendar(**kwargs), LegacyCalendar(**kwargs)
        friday, saturday, thursday = (
            date(2021, 7, 2), date(2021, 7, 3), date(2021, 7, 1)
        )
        self.assertEqual(new.is_business_day(friday),
                         old.is_business_day(friday))
        self.assertFalse(new.is_business_day(friday))
        self.assertFalse(new.is_business_day(saturday))
        self.assertTrue(new.is_business_day(thursday))
        # T+1 from Thursday jumps observed Friday + weekend as one run.
        self.assertEqual(new.shift(thursday, 1), old.shift(thursday, 1))
        self.assertEqual(new.shift(thursday, 1), date(2021, 7, 5))
        self.assertEqual(new.observed_holidays(), old.observed_holidays())

    # -- Jan 31 add_months: clamp and EOM sticky ---------------------
    def test_jan_31_add_months_parity(self):
        new, old = _pair(tz=ET, cutoff=time(17, 0))
        for d, n in (
            (date(2024, 1, 31), 1),   # leap: EOM sticky -> Feb 29
            (date(2023, 1, 31), 1),   # common: -> Feb 28
            (date(2024, 2, 29), -1),  # round trip -> Jan 31
            (date(2024, 1, 15), 13),  # mid-month clamp+adjust
        ):
            self.assertEqual(new.add_months(d, n), old.add_months(d, n),
                             (d, n))
        self.assertEqual(new.add_months(date(2024, 1, 31), 1),
                         date(2024, 2, 29))

    # -- Spring Festival multi-day run, T+2 escapes in one go --------
    def test_spring_festival_t_plus_two_parity(self):
        kwargs = dict(
            holidays=SPRING_FESTIVAL_2024,
            observance="unadjusted",
            tz=BJ,
            cutoff=time(15, 0),
        )
        new, old = Calendar(**kwargs), LegacyCalendar(**kwargs)
        last = date(2024, 2, 9)
        inside = date(2024, 2, 12)
        for n in (1, 2):
            self.assertEqual(new.shift(last, n), old.shift(last, n))
            self.assertEqual(new.shift(inside, n), old.shift(inside, n))
        self.assertEqual(new.shift(last, 2), date(2024, 2, 20))
        self.assertEqual(new.shift(inside, 1), date(2024, 2, 19))

    # -- New York DST settlement days --------------------------------
    def test_new_york_dst_settle_parity(self):
        new, old = _pair(tz=ET, cutoff=time(17, 0))
        # Spring forward 2024-03-10; fall back 2024-11-03.
        cases = [
            datetime(2024, 3, 8, 16, 0),                            # naive EST
            datetime(2024, 3, 8, 22, 0, tzinfo=ZoneInfo("UTC")),    # at cutoff
            datetime(2024, 3, 11, 21, 0, tzinfo=ZoneInfo("UTC")),  # EDT cutoff
            datetime(2024, 11, 4, 22, 0, tzinfo=ZoneInfo("UTC")),   # EST again
        ]
        for dt in cases:
            self.assertEqual(new.trade_date(dt), old.trade_date(dt), dt)
            for n in (0, 1, 2):
                self.assertEqual(new.settle_date(dt, n),
                                 old.settle_date(dt, n), (dt, n))
        # Concrete anchor: Friday before cutoff settles Monday across DST.
        self.assertEqual(new.settle_date(cases[0], 1), date(2024, 3, 11))

    # -- modified following folds back across a month boundary -------
    def test_modified_following_cross_month_parity(self):
        new, old = _pair(tz=ET, cutoff=time(17, 0))
        d = date(2021, 1, 31)  # Sunday; following -> Feb 1, mod-fol -> Jan 29
        for conv in ("following", "modified_following",
                     "modified preceding", "顺延", "修正顺延"):
            self.assertEqual(new.adjust(d, conv), old.adjust(d, conv), conv)
        self.assertEqual(new.adjust(d, "modified_following"),
                         date(2021, 1, 29))


if __name__ == "__main__":
    unittest.main()
