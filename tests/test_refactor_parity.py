"""Behavior-parity tests pinned down for the refactor.

Each test states externally visible behavior that must survive the
restructuring, independent of which file or class implements it.
"""

import unittest
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from bizday import Calendar


def us_calendar(**kw):
    kw.setdefault("tz", "America/New_York")
    kw.setdefault("cutoff", time(17, 0))
    return Calendar(weekend=(5, 6), **kw)


class CutoffBoundaryParity(unittest.TestCase):
    def test_cutoff_minute_inclusive_second_after_rolls(self):
        cal = us_calendar()
        self.assertEqual(cal.trade_date(datetime(2024, 3, 8, 17, 0, 0)),
                         date(2024, 3, 8))
        self.assertEqual(cal.trade_date(datetime(2024, 3, 8, 17, 0, 1)),
                         date(2024, 3, 11))
        self.assertEqual(cal.settle_date(datetime(2024, 3, 8, 17, 0, 0), 1),
                         date(2024, 3, 11))
        self.assertEqual(cal.settle_date(datetime(2024, 3, 8, 17, 0, 1), 1),
                         date(2024, 3, 12))


class SaturdayHolidayParity(unittest.TestCase):
    def test_saturday_holiday_observed_friday_is_not_a_business_day(self):
        cal = us_calendar(holidays={date(2021, 7, 3)}, observance="preceding")
        self.assertFalse(cal.is_business_day(date(2021, 7, 2)))
        self.assertEqual(cal.shift(date(2021, 7, 1), 1), date(2021, 7, 5))


class MonthEndParity(unittest.TestCase):
    def test_jan_31_plus_one_month(self):
        cal = us_calendar()
        self.assertEqual(cal.add_months(date(2024, 1, 31), 1),
                         date(2024, 2, 29))
        self.assertEqual(cal.add_months(date(2023, 1, 31), 1),
                         date(2023, 2, 28))


class SpringFestivalParity(unittest.TestCase):
    def test_t_plus_two_escapes_whole_break(self):
        holidays = {date(2024, 2, d) for d in range(10, 18)}
        cal = Calendar(weekend=(5, 6), holidays=holidays,
                       tz="Asia/Shanghai", cutoff=time(15, 0))
        self.assertEqual(cal.shift(date(2024, 2, 9), 2), date(2024, 2, 20))
        self.assertEqual(cal.shift(date(2024, 2, 12), 1), date(2024, 2, 19))


class NewYorkDstParity(unittest.TestCase):
    def test_settle_across_spring_forward(self):
        cal = us_calendar()
        self.assertEqual(cal.settle_date(datetime(2024, 3, 8, 16, 0), 1),
                         date(2024, 3, 11))
        self.assertEqual(
            cal.trade_date(datetime(2024, 3, 8, 22, 0, tzinfo=ZoneInfo("UTC"))),
            date(2024, 3, 8))
        self.assertEqual(
            cal.trade_date(datetime(2024, 3, 11, 21, 0, tzinfo=ZoneInfo("UTC"))),
            date(2024, 3, 11))


class HolidayTableEditParity(unittest.TestCase):
    def test_observed_cache_does_not_outlive_holiday_edit(self):
        cal = us_calendar()
        d = date(2024, 7, 4)
        self.assertTrue(cal.is_business_day(d))
        cal.holidays = frozenset({d})
        self.assertFalse(cal.is_business_day(d))
        self.assertEqual(cal.observed_holidays(), frozenset({d}))


if __name__ == "__main__":
    unittest.main()
