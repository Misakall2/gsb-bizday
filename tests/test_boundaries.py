"""Boundary tests: cutoffs, DST, observance, streaks, EOM, multi-market."""

import unittest
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from bizday import Calendar

ET = "America/New_York"
UTC = ZoneInfo("UTC")


def us_calendar(**kw):
    kw.setdefault("tz", ET)
    kw.setdefault("cutoff", time(17, 0))
    return Calendar(weekend=(5, 6), **kw)


class CutoffBoundaryTest(unittest.TestCase):
    """Friday 2024-03-08, cutoff 17:00 ET inclusive."""

    def setUp(self):
        self.cal = us_calendar()
        self.fri = date(2024, 3, 8)
        self.mon = date(2024, 3, 11)
        self.tue = date(2024, 3, 12)

    def test_165959_counts_as_friday(self):
        t = datetime(2024, 3, 8, 16, 59, 59)
        self.assertEqual(self.cal.settle_date(t, 0), self.fri)   # T+0
        self.assertEqual(self.cal.settle_date(t, 1), self.mon)   # T+1

    def test_170000_exactly_counts_as_friday(self):
        t = datetime(2024, 3, 8, 17, 0, 0)
        self.assertEqual(self.cal.settle_date(t, 0), self.fri)
        self.assertEqual(self.cal.settle_date(t, 1), self.mon)

    def test_170001_rolls_to_monday(self):
        t = datetime(2024, 3, 8, 17, 0, 1)
        self.assertEqual(self.cal.settle_date(t, 0), self.mon)
        self.assertEqual(self.cal.settle_date(t, 1), self.tue)

    def test_1800_rolls_to_monday(self):
        t = datetime(2024, 3, 8, 18, 0, 0)
        self.assertEqual(self.cal.settle_date(t, 0), self.mon)
        self.assertEqual(self.cal.settle_date(t, 1), self.tue)

    def test_naive_and_aware_same_instant_agree(self):
        # 17:00:00 ET (EST, UTC-5) == 22:00:00 UTC; 17:00:01 ET == 22:00:01 UTC.
        pairs = [
            (datetime(2024, 3, 8, 16, 59, 59),
             datetime(2024, 3, 8, 21, 59, 59, tzinfo=UTC)),
            (datetime(2024, 3, 8, 17, 0, 0),
             datetime(2024, 3, 8, 22, 0, 0, tzinfo=UTC)),
            (datetime(2024, 3, 8, 17, 0, 1),
             datetime(2024, 3, 8, 22, 0, 1, tzinfo=UTC)),
            (datetime(2024, 3, 8, 18, 0, 0),
             datetime(2024, 3, 8, 23, 0, 0, tzinfo=UTC)),
        ]
        for naive, aware in pairs:
            with self.subTest(naive=naive):
                self.assertEqual(self.cal.settle_date(naive, 0),
                                 self.cal.settle_date(aware, 0))
                self.assertEqual(self.cal.settle_date(naive, 1),
                                 self.cal.settle_date(aware, 1))


class DSTTest(unittest.TestCase):
    def setUp(self):
        self.cal = us_calendar()

    def test_spring_forward_skipped_hour_no_crash_no_weekend(self):
        # 2024-03-10 02:30 local does not exist (02:00 -> 03:00).
        for t in (datetime(2024, 3, 10, 2, 30),
                  datetime(2024, 3, 10, 6, 30, tzinfo=UTC),   # 01:30 EST
                  datetime(2024, 3, 10, 7, 30, tzinfo=UTC)):  # 03:30 EDT
            with self.subTest(t=t):
                s = self.cal.settle_date(t, 1)
                self.assertNotIn(s.weekday(), (5, 6))
        # Sunday trade -> business date Monday, T+1 Tuesday.
        self.assertEqual(self.cal.settle_date(datetime(2024, 3, 10, 2, 30), 1),
                         date(2024, 3, 12))

    def test_fall_back_repeated_hour_no_crash_no_weekend(self):
        # 2024-11-03 01:30 local happens twice (fold=0 EDT, fold=1 EST).
        for t in (datetime(2024, 11, 3, 1, 30),
                  datetime(2024, 11, 3, 1, 30, fold=1),
                  datetime(2024, 11, 3, 5, 30, tzinfo=UTC),   # 01:30 EDT
                  datetime(2024, 11, 3, 6, 30, tzinfo=UTC)):  # 01:30 EST
            with self.subTest(t=t):
                s = self.cal.settle_date(t, 1)
                self.assertNotIn(s.weekday(), (5, 6))
        self.assertEqual(self.cal.settle_date(datetime(2024, 11, 3, 1, 30), 1),
                         date(2024, 11, 5))


class ObservanceTest(unittest.TestCase):
    def test_saturday_holiday_preceding_makes_friday_non_business(self):
        # Real calendar: Juneteenth 2021-06-19 was a Saturday, observed
        # Friday 2021-06-18.
        cal = us_calendar(holidays={date(2021, 6, 19)}, observance="preceding")
        self.assertFalse(cal.is_business_day(date(2021, 6, 18)))
        self.assertTrue(cal.is_business_day(date(2021, 6, 17)))

    def test_sunday_holiday_following_makes_monday_non_business(self):
        # Real calendar: New Year's Day 2023-01-01 was a Sunday, observed
        # Monday 2023-01-02.
        cal = us_calendar(holidays={date(2023, 1, 1)}, observance="following")
        self.assertFalse(cal.is_business_day(date(2023, 1, 2)))
        self.assertTrue(cal.is_business_day(date(2023, 1, 3)))

    def test_unadjusted_weekend_holiday_spares_neighboring_weekdays(self):
        cal = us_calendar(holidays={date(2021, 6, 19)}, observance="unadjusted")
        self.assertTrue(cal.is_business_day(date(2021, 6, 18)))   # Friday
        self.assertTrue(cal.is_business_day(date(2021, 6, 21)))   # Monday
        self.assertFalse(cal.is_business_day(date(2021, 6, 19)))  # Saturday

    def test_modified_following_real_month_end(self):
        # Real calendar: 2022-12-31 was a Saturday. Following lands in
        # January, so modified following falls back to Friday Dec 30.
        cal = us_calendar()
        d = date(2022, 12, 31)
        self.assertEqual(d.weekday(), 5)
        self.assertEqual(cal.adjust(d, "following"), date(2023, 1, 2))
        self.assertEqual(cal.adjust(d, "modified_following"), date(2022, 12, 30))

    def test_modified_preceding_real_month_start(self):
        # Real calendar: 2022-10-01 was a Saturday. Preceding lands in
        # September, so modified preceding goes to Monday Oct 3.
        cal = us_calendar()
        d = date(2022, 10, 1)
        self.assertEqual(d.weekday(), 5)
        self.assertEqual(cal.adjust(d, "preceding"), date(2022, 9, 30))
        self.assertEqual(cal.adjust(d, "modified_preceding"), date(2022, 10, 3))


class HolidayStreakTest(unittest.TestCase):
    def test_spring_festival_streak_and_escape_from_inside(self):
        # 2024 Spring Festival: Feb 10-17 (Sat-Sat), 8 consecutive days.
        holidays = {date(2024, 2, d) for d in range(10, 18)}
        cal = Calendar(weekend=(5, 6), holidays=holidays, tz="Asia/Shanghai")
        last = date(2024, 2, 9)  # Friday, last business day before break
        self.assertEqual(cal.shift(last, 1), date(2024, 2, 19))
        self.assertEqual(cal.shift(last, 2), date(2024, 2, 20))
        # From the middle of the streak, shifting escapes the whole run.
        self.assertEqual(cal.shift(date(2024, 2, 13), 1), date(2024, 2, 19))
        self.assertEqual(cal.shift(date(2024, 2, 13), -1), date(2024, 2, 9))

    def test_thanksgiving_and_black_friday(self):
        holidays = {date(2024, 11, 28), date(2024, 11, 29)}
        cal = us_calendar(holidays=holidays)
        self.assertEqual(cal.shift(date(2024, 11, 27), 1), date(2024, 12, 2))
        self.assertEqual(cal.shift(date(2024, 11, 27), 2), date(2024, 12, 3))
        # Escape backward out of the streak too.
        self.assertEqual(cal.shift(date(2024, 11, 29), -1), date(2024, 11, 27))


class MonthEndStickyTest(unittest.TestCase):
    def setUp(self):
        self.cal = us_calendar()

    def test_jan31_plus_one_month_common_and_leap(self):
        self.assertEqual(self.cal.add_months(date(2023, 1, 31), 1),
                         date(2023, 2, 28))
        self.assertEqual(self.cal.add_months(date(2024, 1, 31), 1),
                         date(2024, 2, 29))

    def test_sticky_from_month_end_business_day(self):
        # 2024-03-28 is Thursday; Mar 29-31 are Fri/Sat/Sun... but with no
        # holidays Mar 29 (Friday) is the last business day. Use it.
        self.assertTrue(self.cal.is_month_end_business_day(date(2024, 3, 29)))
        # April 2024 ends Tuesday the 30th, a business day.
        self.assertEqual(self.cal.add_months(date(2024, 3, 29), 1),
                         date(2024, 4, 30))

    def test_jan30_not_sticky(self):
        # Jan 30 2024 is a Tuesday but NOT the last business day of January.
        d = date(2024, 1, 30)
        self.assertFalse(self.cal.is_month_end_business_day(d))
        # Plain clamp path: day 30 -> clamped to Feb 29 (leap), a Thursday.
        self.assertEqual(self.cal.add_months(d, 1), date(2024, 2, 29))
        # +2 months: Mar 30 2024 is a Saturday. Sticky would give Mar 28
        # (last business day); the non-sticky path clamps to Mar 30 then
        # adjusts following to Apr 1. This is where sticky would misfire.
        self.assertEqual(self.cal.add_months(d, 2), date(2024, 4, 1))


class MultiMarketAndValidationTest(unittest.TestCase):
    def test_same_day_differs_between_weekend_regimes(self):
        sat_sun = Calendar(weekend=(5, 6), tz=ET)
        fri_sat = Calendar(weekend=(4, 5), tz="Asia/Dubai")
        friday = date(2024, 3, 8)
        sunday = date(2024, 3, 10)
        self.assertTrue(sat_sun.is_business_day(friday))
        self.assertFalse(fri_sat.is_business_day(friday))
        self.assertFalse(sat_sun.is_business_day(sunday))
        self.assertTrue(fri_sat.is_business_day(sunday))
        # Same start, same N, different answers.
        self.assertEqual(sat_sun.shift(date(2024, 3, 7), 1), friday)
        self.assertEqual(fri_sat.shift(date(2024, 3, 7), 1), sunday)

    def test_chinese_and_english_convention_names_agree(self):
        cal = us_calendar()
        d = date(2024, 3, 9)  # Saturday
        self.assertEqual(cal.adjust(d, "following"), cal.adjust(d, "顺延"))
        self.assertEqual(cal.adjust(d, "modified_preceding"),
                         cal.adjust(d, "修正提前"))

    def test_invalid_convention_name_raises(self):
        with self.assertRaises(ValueError):
            us_calendar().adjust(date(2024, 1, 2), "whatever")
        with self.assertRaises(ValueError):
            Calendar(weekend=(5, 6), observance="随便")

    def test_invalid_weekday_raises(self):
        with self.assertRaises(ValueError):
            Calendar(weekend=(7,))
        with self.assertRaises(ValueError):
            Calendar(weekend=(-1,))

    def test_non_int_n_raises(self):
        cal = us_calendar()
        with self.assertRaises(TypeError):
            cal.shift(date(2024, 1, 2), 1.5)
        with self.assertRaises(TypeError):
            cal.shift(date(2024, 1, 2), "1")


class CountAndZeroShiftTest(unittest.TestCase):
    def test_business_days_between_pos_neg_zero(self):
        cal = us_calendar()
        thu, mon = date(2024, 3, 7), date(2024, 3, 11)
        self.assertEqual(cal.business_days_between(thu, mon), 2)
        self.assertEqual(cal.business_days_between(mon, thu), -2)
        self.assertEqual(cal.business_days_between(thu, thu), 0)

    def test_shift_zero_on_holiday_adjusts_to_business_day(self):
        cal = us_calendar(holidays={date(2024, 7, 4)})
        self.assertFalse(cal.is_business_day(date(2024, 7, 4)))
        self.assertEqual(cal.shift(date(2024, 7, 4), 0), date(2024, 7, 5))
        self.assertEqual(cal.shift(date(2024, 7, 4), 0, "preceding"),
                         date(2024, 7, 3))


if __name__ == "__main__":
    unittest.main()
