import unittest
from datetime import date

from bizday import (
    BusinessCalendar,
    Weekend,
    adjust,
    following,
    modified_following,
    modified_preceding,
    preceding,
    unadjusted,
)


class WeekendTests(unittest.TestCase):
    def test_sat_sun_default(self):
        cal = BusinessCalendar()
        # Friday 2024-03-01, Sat 03-02, Sun 03-03
        self.assertTrue(cal.is_business_day(date(2024, 3, 1)))
        self.assertTrue(cal.is_weekend(date(2024, 3, 2)))
        self.assertTrue(cal.is_weekend(date(2024, 3, 3)))
        self.assertFalse(cal.is_business_day(date(2024, 3, 2)))

    def test_fri_sat_market(self):
        cal = BusinessCalendar(weekend=Weekend.FRI_SAT)
        # Friday is closed, Sunday is open.
        self.assertFalse(cal.is_business_day(date(2024, 3, 1)))
        self.assertTrue(cal.is_business_day(date(2024, 3, 3)))

    def test_weekend_aliases(self):
        cal = BusinessCalendar(weekend="fri-sat")
        self.assertTrue(cal.is_weekend(date(2024, 3, 1)))

    def test_two_markets_same_day_differ(self):
        us = BusinessCalendar("us")
        ae = BusinessCalendar("ae", weekend="fri_sat")
        fri = date(2024, 3, 1)
        self.assertTrue(us.is_business_day(fri))
        self.assertFalse(ae.is_business_day(fri))

    def test_navigation_basic(self):
        cal = BusinessCalendar()
        self.assertEqual(cal.next_business_day(date(2024, 3, 1)),
                         date(2024, 3, 4))
        self.assertEqual(cal.previous_business_day(date(2024, 3, 4)),
                         date(2024, 3, 1))


class ObservanceTests(unittest.TestCase):
    # Christmas 2021-12-25 is a Saturday.
    def test_saturday_holiday_observed_following_monday(self):
        cal = BusinessCalendar(
            holidays=[date(2021, 12, 25)], observance=following
        )
        # Monday observed
        self.assertFalse(cal.is_business_day(date(2021, 12, 27)))
        self.assertTrue(cal.is_holiday(date(2021, 12, 27)))
        self.assertTrue(cal.is_business_day(date(2021, 12, 24)))  # Friday open

    def test_saturday_holiday_observed_preceding_friday(self):
        # The exact trap from settlement: holiday on Saturday, observed on
        # Friday -> Friday must not count as a business day.
        cal = BusinessCalendar(
            holidays=[date(2021, 12, 25)], observance=preceding
        )
        fri = date(2021, 12, 24)
        self.assertFalse(cal.is_business_day(fri))
        self.assertTrue(cal.is_holiday(fri))
        self.assertEqual(cal.next_business_day(date(2021, 12, 23)),
                         date(2021, 12, 27))

    def test_sunday_holiday_observed_following(self):
        # New Year 2023-01-01 is a Sunday; observed Monday.
        cal = BusinessCalendar(
            holidays=[date(2023, 1, 1)], observance=following
        )
        self.assertFalse(cal.is_business_day(date(2023, 1, 2)))

    def test_unadjusted_weekend_holiday_leaves_weekday_open(self):
        cal = BusinessCalendar(
            holidays=[date(2021, 12, 25)], observance=unadjusted
        )
        self.assertTrue(cal.is_business_day(date(2021, 12, 24)))
        self.assertTrue(cal.is_business_day(date(2021, 12, 27)))

    def test_weekday_holiday_never_moves(self):
        cal = BusinessCalendar(
            holidays=[date(2024, 7, 4)], observance=following
        )
        self.assertTrue(cal.is_holiday(date(2024, 7, 4)))
        self.assertTrue(cal.is_business_day(date(2024, 7, 3)))
        self.assertTrue(cal.is_business_day(date(2024, 7, 5)))

    def test_observance_respects_alt_weekend(self):
        # Fri/Sat market, holiday on Saturday -> preceding lands Thursday.
        cal = BusinessCalendar(
            weekend="fri_sat",
            holidays=[date(2024, 3, 2)],
            observance="preceding",
        )
        self.assertFalse(cal.is_business_day(date(2024, 2, 29)))  # Thu
        self.assertTrue(cal.is_business_day(date(2024, 3, 3)))   # Sun


class AdjustConventionTests(unittest.TestCase):
    def test_following(self):
        cal = BusinessCalendar(holidays=[date(2024, 7, 4)])
        # Thu holiday -> Fri
        self.assertEqual(adjust(date(2024, 7, 4), following, cal),
                         date(2024, 7, 5))

    def test_preceding(self):
        cal = BusinessCalendar(holidays=[date(2024, 7, 4)])
        self.assertEqual(adjust(date(2024, 7, 4), preceding, cal),
                         date(2024, 7, 3))

    def test_modified_following_month_end_sunday(self):
        # 2024-03-31 is a Sunday. Plain following -> Mon Apr 1 (next month),
        # modified following must bounce back to Fri Mar 29.
        cal = BusinessCalendar()
        self.assertEqual(
            adjust(date(2024, 3, 31), modified_following, cal),
            date(2024, 3, 29),
        )

    def test_modified_following_within_month_still_follows(self):
        # Saturday 2024-03-02 -> Monday 2024-03-04 (same month).
        cal = BusinessCalendar()
        self.assertEqual(
            adjust(date(2024, 3, 2), modified_following, cal),
            date(2024, 3, 4),
        )

    def test_modified_preceding_month_start(self):
        # Monday 2024-04-01 is a holiday; preceding walks to Fri Mar 29
        # (previous month) -> modified preceding jumps forward to Tue Apr 2.
        cal = BusinessCalendar(holidays=[date(2024, 4, 1)])
        self.assertEqual(
            adjust(date(2024, 4, 1), modified_preceding, cal),
            date(2024, 4, 2),
        )

    def test_unadjusted_returns_input(self):
        cal = BusinessCalendar(holidays=[date(2024, 7, 4)])
        d = date(2024, 7, 4)
        self.assertIs(adjust(d, unadjusted, cal), d)

    def test_business_day_unchanged_for_all_conventions(self):
        cal = BusinessCalendar()
        d = date(2024, 3, 5)
        for conv in (following, preceding, modified_following,
                     modified_preceding, unadjusted):
            self.assertEqual(adjust(d, conv, cal), d)

    def test_chinese_convention_names(self):
        cal = BusinessCalendar(holidays=[date(2024, 7, 4)])
        self.assertEqual(adjust(date(2024, 7, 4), "顺延", cal),
                         date(2024, 7, 5))
        self.assertEqual(adjust(date(2024, 7, 4), "提前", cal),
                         date(2024, 7, 3))
        self.assertEqual(
            adjust(date(2024, 3, 31), "修正顺延", cal), date(2024, 3, 29)
        )
        self.assertEqual(adjust(date(2024, 7, 4), "未调整", cal),
                         date(2024, 7, 4))

    def test_unknown_convention_raises(self):
        cal = BusinessCalendar()
        with self.assertRaises(ValueError):
            adjust(date(2024, 3, 1), "nonsense", cal)


if __name__ == "__main__":
    unittest.main()
