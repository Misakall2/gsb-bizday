"""Regression tests pinning the five production settlement incidents.

Each class maps to one incident ticket. The inputs here are the exact
ones that blew up on the desk; if any of these ever go red again, the
incident is back.
"""

import unittest
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from bizday import Calendar

ET = "America/New_York"
BJ = "Asia/Shanghai"
ETZ = ZoneInfo(ET)
UTC = ZoneInfo("UTC")


def us_calendar(**kw):
    kw.setdefault("tz", ET)
    kw.setdefault("cutoff", time(17, 0))
    return Calendar(weekend=(5, 6), **kw)


def cn_calendar(**kw):
    kw.setdefault("tz", BJ)
    kw.setdefault("cutoff", time(15, 0))
    return Calendar(weekend=(5, 6), **kw)


class Incident1NyCutoffDstTest(unittest.TestCase):
    """17:00 America/New_York cutoff is inclusive; DST on 2024-03-10."""

    def test_exactly_at_cutoff_stays_on_friday(self):
        cal = us_calendar()
        at = datetime(2024, 3, 8, 17, 0, 0)  # Friday, naive -> read as ET
        self.assertEqual(cal.trade_date(at), date(2024, 3, 8))
        # T+1 counts one business day from Friday: Monday, not Saturday.
        self.assertEqual(cal.settle_date(at, 1), date(2024, 3, 11))

    def test_one_second_after_cutoff_rolls_before_counting(self):
        cal = us_calendar()
        after = datetime(2024, 3, 8, 17, 0, 1)
        # Trade belongs to the next business day (Monday)...
        self.assertEqual(cal.trade_date(after), date(2024, 3, 11))
        # ...and T+1 is counted from there: Tuesday, never Saturday.
        self.assertEqual(cal.settle_date(after, 1), date(2024, 3, 12))

    def test_aware_datetime_same_rule(self):
        cal = us_calendar()
        at = datetime(2024, 3, 8, 17, 0, 0, tzinfo=ETZ)
        after = datetime(2024, 3, 8, 17, 0, 1, tzinfo=ETZ)
        self.assertEqual(cal.settle_date(at, 1), date(2024, 3, 11))
        self.assertEqual(cal.settle_date(after, 1), date(2024, 3, 12))
        # Same instants expressed in UTC (EST is UTC-5 before the jump).
        self.assertEqual(
            cal.settle_date(datetime(2024, 3, 8, 22, 0, 0, tzinfo=UTC), 1),
            date(2024, 3, 11),
        )
        self.assertEqual(
            cal.settle_date(datetime(2024, 3, 8, 22, 0, 1, tzinfo=UTC), 1),
            date(2024, 3, 12),
        )

    def test_dst_spring_forward_weekend(self):
        # 2024-03-10 02:00 EST -> 03:00 EDT. Nothing may blow up and
        # Sunday must never become a trade date.
        cal = us_calendar()
        sunday = date(2024, 3, 10)
        self.assertFalse(cal.is_business_day(sunday))
        # Naive time inside the nonexistent 02:00-03:00 gap: no crash.
        self.assertEqual(cal.trade_date(datetime(2024, 3, 10, 2, 30)), date(2024, 3, 11))
        self.assertEqual(cal.trade_date(datetime(2024, 3, 10, 12, 0)), date(2024, 3, 11))
        self.assertEqual(
            cal.trade_date(datetime(2024, 3, 10, 12, 0, tzinfo=ETZ)),
            date(2024, 3, 11),
        )
        # After the jump New York is UTC-4: Monday 17:00 EDT == 21:00 UTC,
        # still exactly at the cutoff, so it stays on Monday.
        self.assertEqual(
            cal.trade_date(datetime(2024, 3, 11, 21, 0, 0, tzinfo=UTC)),
            date(2024, 3, 11),
        )
        self.assertEqual(
            cal.trade_date(datetime(2024, 3, 11, 21, 0, 1, tzinfo=UTC)),
            date(2024, 3, 12),
        )


class Incident2ObservedHolidayTest(unittest.TestCase):
    """A Saturday holiday observed 'preceding' closes the Friday."""

    def test_thursday_t1_skips_observed_friday(self):
        # 2021-07-03 was a Saturday; observed Friday 2021-07-02.
        cal = us_calendar(holidays={date(2021, 7, 3)}, observance="preceding")
        self.assertFalse(cal.is_business_day(date(2021, 7, 2)))
        # T+1 from Thursday must not land on the observed Friday.
        self.assertEqual(cal.shift(date(2021, 7, 1), 1), date(2021, 7, 5))
        self.assertEqual(cal.shift(date(2021, 7, 1), 2), date(2021, 7, 6))

    def test_chinese_observance_name_same_result(self):
        cal = us_calendar(holidays={date(2021, 7, 3)}, observance="提前")
        self.assertFalse(cal.is_business_day(date(2021, 7, 2)))
        self.assertEqual(cal.shift(date(2021, 7, 1), 1), date(2021, 7, 5))

    def test_thanksgiving_thursday_and_friday_cleared_in_one_go(self):
        # Thursday 2024-11-28 and Friday 2024-11-29 both holidays.
        cal = us_calendar(holidays={date(2024, 11, 28), date(2024, 11, 29)})
        # From Wednesday, T+1 jumps the whole Thu/Fri/weekend run at once.
        self.assertEqual(cal.shift(date(2024, 11, 27), 1), date(2024, 12, 2))
        self.assertEqual(cal.shift(date(2024, 11, 27), 2), date(2024, 12, 3))
        # Starting inside the run also escapes fully, never stops mid-run.
        self.assertEqual(cal.shift(date(2024, 11, 28), 1), date(2024, 12, 2))


class Incident3ModifiedConventionsTest(unittest.TestCase):
    """Modified following/preceding must not leak across month boundaries."""

    def test_modified_following_month_end(self):
        # 2021-01-31 was a Sunday; plain following lands on Feb 1, so
        # modified following must fall back to Friday Jan 29.
        cal = us_calendar()
        d = date(2021, 1, 31)
        self.assertEqual(cal.adjust(d, "following"), date(2021, 2, 1))
        self.assertEqual(cal.adjust(d, "modified_following"), date(2021, 1, 29))
        self.assertEqual(cal.adjust(d, "修正顺延"), date(2021, 1, 29))

    def test_modified_preceding_month_start(self):
        # 2021-05-01 was a Saturday; plain preceding lands on Apr 30, so
        # modified preceding must go forward to Monday May 3.
        cal = us_calendar()
        d = date(2021, 5, 1)
        self.assertEqual(cal.adjust(d, "preceding"), date(2021, 4, 30))
        self.assertEqual(cal.adjust(d, "modified_preceding"), date(2021, 5, 3))
        self.assertEqual(cal.adjust(d, "修正提前"), date(2021, 5, 3))

    def test_modified_following_observance_at_month_end(self):
        # Saturday 2021-07-31 holiday: following observance would observe
        # it in August, so modified following observes it Friday Jul 30.
        cal = us_calendar(holidays={date(2021, 7, 31)},
                          observance="modified_following")
        self.assertFalse(cal.is_business_day(date(2021, 7, 30)))
        self.assertTrue(cal.is_business_day(date(2021, 8, 2)))


class Incident4MonthEndStickyTest(unittest.TestCase):
    """EOM stickiness and escaping holiday runs from inside."""

    def test_jan31_plus_one_month_common_year(self):
        cal = us_calendar()
        # Jan 31 2023 is the last business day of January; Feb 2023 ends
        # on a Tuesday, so the sticky result is Feb 28, never Mar 2.
        self.assertTrue(cal.is_month_end_business_day(date(2023, 1, 31)))
        self.assertEqual(cal.add_months(date(2023, 1, 31), 1), date(2023, 2, 28))

    def test_jan31_plus_one_month_leap_year(self):
        cal = us_calendar()
        self.assertTrue(cal.is_month_end_business_day(date(2024, 1, 31)))
        self.assertEqual(cal.add_months(date(2024, 1, 31), 1), date(2024, 2, 29))

    def test_sticky_from_non_calendar_month_end(self):
        cal = us_calendar()
        # Last business day of Jan 2021 is Fri Jan 29; Feb 2021 ends on a
        # Sunday, so the sticky target is Fri Feb 26.
        self.assertTrue(cal.is_month_end_business_day(date(2021, 1, 29)))
        self.assertEqual(cal.add_months(date(2021, 1, 29), 1), date(2021, 2, 26))

    def test_shift_escapes_holiday_run_from_inside(self):
        # 2024 Spring Festival: Feb 10-17 (Sat-Sat) supplied as holidays.
        cal = cn_calendar(holidays={date(2024, 2, d) for d in range(10, 18)})
        # From inside the run, one step must clear the whole run plus the
        # Sunday on Feb 18, landing Monday Feb 19 -- never mid-holiday.
        self.assertEqual(cal.shift(date(2024, 2, 12), 1), date(2024, 2, 19))
        self.assertEqual(cal.shift(date(2024, 2, 14), 1), date(2024, 2, 19))
        # And backwards out of the run in one go.
        self.assertEqual(cal.shift(date(2024, 2, 12), -1), date(2024, 2, 9))


class Incident5IndependentMarketsTest(unittest.TestCase):
    """US and CN calendars are independent; no global weekend state."""

    def test_same_day_different_answer(self):
        us = us_calendar()
        cn = cn_calendar(holidays={date(2024, 5, 1)})  # Labour Day
        d = date(2024, 5, 1)
        self.assertTrue(us.is_business_day(d))
        self.assertFalse(cn.is_business_day(d))
        self.assertEqual(us.shift(date(2024, 4, 30), 1), date(2024, 5, 1))
        self.assertEqual(cn.shift(date(2024, 4, 30), 1), date(2024, 5, 2))

    def test_building_cn_calendar_does_not_touch_us(self):
        us = us_calendar()
        before = (us.weekend, us.cutoff, us.tz)
        cn_calendar(holidays={date(2024, 10, 1)})
        self.assertEqual((us.weekend, us.cutoff, us.tz), before)
        self.assertEqual(us.weekend, frozenset({5, 6}))

    def test_english_and_chinese_convention_names(self):
        cal = us_calendar()
        saturday = date(2024, 3, 9)
        for name in ("following", "顺延", "往后", "下一工作日"):
            self.assertEqual(cal.adjust(saturday, name), date(2024, 3, 11), name)
        for name in ("preceding", "提前", "往前", "上一工作日"):
            self.assertEqual(cal.adjust(saturday, name), date(2024, 3, 8), name)
        for name in ("modified following", "modified_following", "修正顺延"):
            self.assertEqual(cal.adjust(saturday, name), date(2024, 3, 11), name)
        for name in ("modified preceding", "modified_preceding", "修正提前"):
            self.assertEqual(cal.adjust(saturday, name), date(2024, 3, 8), name)
        for name in ("unadjusted", "不调整"):
            self.assertEqual(cal.adjust(saturday, name), saturday, name)

    def test_cutoff_inclusivity_is_per_market(self):
        # The documented rule (inclusive cutoff) holds for both markets,
        # each with its own cutoff hour.
        us = us_calendar()
        cn = cn_calendar()
        self.assertEqual(us.trade_date(datetime(2024, 3, 8, 17, 0, 0)), date(2024, 3, 8))
        self.assertEqual(us.trade_date(datetime(2024, 3, 8, 17, 0, 1)), date(2024, 3, 11))
        self.assertEqual(cn.trade_date(datetime(2024, 3, 8, 15, 0, 0)), date(2024, 3, 8))
        self.assertEqual(cn.trade_date(datetime(2024, 3, 8, 15, 0, 1)), date(2024, 3, 11))


if __name__ == "__main__":
    unittest.main()
