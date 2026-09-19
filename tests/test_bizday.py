import unittest
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from bizday import Calendar

ET = "America/New_York"
BJ = "Asia/Shanghai"


def us_calendar(**kw):
    kw.setdefault("tz", ET)
    kw.setdefault("cutoff", time(17, 0))
    return Calendar(weekend=(5, 6), **kw)


def cn_calendar(**kw):
    kw.setdefault("tz", BJ)
    kw.setdefault("cutoff", time(15, 0))
    return Calendar(weekend=(5, 6), **kw)


class ConventionNamesTest(unittest.TestCase):
    def test_english_and_chinese_names(self):
        cal = us_calendar()
        d = date(2024, 3, 9)  # Saturday
        self.assertEqual(cal.adjust(d, "following"), date(2024, 3, 11))
        self.assertEqual(cal.adjust(d, "顺延"), date(2024, 3, 11))
        self.assertEqual(cal.adjust(d, "preceding"), date(2024, 3, 8))
        self.assertEqual(cal.adjust(d, "往前"), date(2024, 3, 8))
        self.assertEqual(cal.adjust(d, "Modified Following"), date(2024, 3, 11))
        self.assertEqual(cal.adjust(d, "修正顺延"), date(2024, 3, 11))
        self.assertEqual(cal.adjust(d, "unadjusted"), d)
        self.assertEqual(cal.adjust(d, "不调整"), d)

    def test_bad_name_raises(self):
        with self.assertRaises(ValueError):
            us_calendar().adjust(date(2024, 1, 2), "随便")


class WeekendAndHolidayTest(unittest.TestCase):
    def test_saturday_holiday_observed_on_friday(self):
        # 2021-07-03 was a Saturday; observed Friday 2021-07-02.
        cal = us_calendar(holidays={date(2021, 7, 3)}, observance="preceding")
        self.assertFalse(cal.is_business_day(date(2021, 7, 2)))
        self.assertFalse(cal.is_business_day(date(2021, 7, 3)))
        self.assertTrue(cal.is_business_day(date(2021, 7, 1)))
        # T+1 from Thursday July 1 skips the observed Friday and the weekend.
        self.assertEqual(cal.shift(date(2021, 7, 1), 1), date(2021, 7, 5))

    def test_sunday_holiday_observed_on_monday(self):
        # 2022-07-04 was a Monday already; use Christmas 2022: Dec 25 Sunday.
        cal = us_calendar(holidays={date(2022, 12, 25)}, observance="following")
        self.assertFalse(cal.is_business_day(date(2022, 12, 26)))
        self.assertTrue(cal.is_business_day(date(2022, 12, 27)))

    def test_unadjusted_observance_keeps_weekend_holiday_off_weekdays(self):
        cal = us_calendar(holidays={date(2021, 7, 3)}, observance="unadjusted")
        self.assertTrue(cal.is_business_day(date(2021, 7, 2)))

    def test_modified_following_month_end(self):
        # 2021-01-31 was a Sunday. Following would be Feb 1 (next month),
        # so modified following falls back to Friday Jan 29.
        cal = us_calendar()
        d = date(2021, 1, 31)
        self.assertEqual(d.weekday(), 6)
        self.assertEqual(cal.adjust(d, "following"), date(2021, 2, 1))
        self.assertEqual(cal.adjust(d, "modified_following"), date(2021, 1, 29))

    def test_modified_preceding_month_start(self):
        # 2021-05-01 was a Saturday. Preceding would be Apr 30 (previous
        # month), so modified preceding goes forward to Monday May 3.
        cal = us_calendar()
        d = date(2021, 5, 1)
        self.assertEqual(cal.adjust(d, "preceding"), date(2021, 4, 30))
        self.assertEqual(cal.adjust(d, "modified_preceding"), date(2021, 5, 3))


class ShiftTest(unittest.TestCase):
    def test_t_plus_one_equity(self):
        cal = us_calendar()
        self.assertEqual(cal.shift(date(2024, 3, 7), 1), date(2024, 3, 8))

    def test_t_plus_two_bond_over_weekend(self):
        cal = us_calendar()
        self.assertEqual(cal.shift(date(2024, 3, 7), 2), date(2024, 3, 11))

    def test_t_plus_zero_on_business_day(self):
        cal = us_calendar()
        self.assertEqual(cal.shift(date(2024, 3, 7), 0), date(2024, 3, 7))

    def test_t_plus_zero_on_weekend_adjusts(self):
        cal = us_calendar()
        self.assertEqual(cal.shift(date(2024, 3, 9), 0), date(2024, 3, 11))

    def test_negative_n_rolls_backward(self):
        cal = us_calendar()
        self.assertEqual(cal.shift(date(2024, 3, 11), -1), date(2024, 3, 8))
        self.assertEqual(cal.shift(date(2024, 3, 11), -2), date(2024, 3, 7))

    def test_spring_festival_week_skipped_in_one_go(self):
        # 2024 Spring Festival: Feb 10-17 2024 (Sat-Sat) as supplied holidays.
        holidays = {date(2024, 2, d) for d in range(10, 18)}
        cal = cn_calendar(holidays=holidays)
        # Last trading day before the break is Friday Feb 9... but Feb 9
        # is a weekday not in the holiday set, so it stays a business day.
        last = date(2024, 2, 9)
        self.assertTrue(cal.is_business_day(last))
        # T+1 and T+2 must land after the whole 8-day gap, not inside it.
        self.assertEqual(cal.shift(last, 1), date(2024, 2, 19))
        self.assertEqual(cal.shift(last, 2), date(2024, 2, 20))
        # Counting from inside the holiday also escapes the run.
        self.assertEqual(cal.shift(date(2024, 2, 12), 1), date(2024, 2, 19))

    def test_thanksgiving_plus_black_friday(self):
        holidays = {date(2024, 11, 28), date(2024, 11, 29)}
        cal = us_calendar(holidays=holidays)
        self.assertEqual(cal.shift(date(2024, 11, 27), 1), date(2024, 12, 2))


class MonthEndTest(unittest.TestCase):
    def test_eom_sticky_common_year(self):
        cal = us_calendar()
        # Last business day of Jan 2021 is Fri Jan 29; Feb 2021 ends Sunday,
        # so the sticky result is Fri Feb 26.
        self.assertTrue(cal.is_month_end_business_day(date(2021, 1, 29)))
        self.assertEqual(cal.add_months(date(2021, 1, 29), 1), date(2021, 2, 26))

    def test_eom_sticky_leap_year(self):
        cal = us_calendar()
        # Jan 31 2024 is Wednesday, the last business day of January.
        self.assertTrue(cal.is_month_end_business_day(date(2024, 1, 31)))
        self.assertEqual(cal.add_months(date(2024, 1, 31), 1), date(2024, 2, 29))

    def test_jan_31_clamps_to_feb_common_year(self):
        cal = us_calendar()
        # Jan 31 2023 is Tuesday (also month-end, so EOM applies and the
        # clamped day coincides): result is Feb 28 2023.
        self.assertEqual(cal.add_months(date(2023, 1, 31), 1), date(2023, 2, 28))

    def test_jan_31_clamps_to_feb_leap_year(self):
        cal = us_calendar()
        self.assertEqual(cal.add_months(date(2024, 1, 31), 1), date(2024, 2, 29))

    def test_mid_month_add_months(self):
        cal = us_calendar()
        self.assertEqual(cal.add_months(date(2024, 1, 15), 1), date(2024, 2, 15))
        # Feb 15 2025 is a Saturday, so following adjusts to Monday Feb 17.
        self.assertEqual(cal.add_months(date(2024, 1, 15), 13), date(2025, 2, 17))

    def test_eom_round_trip_back(self):
        cal = us_calendar()
        # Feb 29 2024 is month-end; going back one month gives Jan 31 2024.
        self.assertEqual(cal.add_months(date(2024, 2, 29), -1), date(2024, 1, 31))


class CutoffTest(unittest.TestCase):
    def test_friday_evening_after_cutoff_t1_is_monday(self):
        cal = us_calendar()
        trade = datetime(2024, 3, 8, 17, 30)  # Friday 5:30pm, naive -> ET
        self.assertEqual(cal.settle_date(trade, 1), date(2024, 3, 12))
        # The trade itself belongs to Monday, not Saturday.
        self.assertEqual(cal.trade_date(trade), date(2024, 3, 11))

    def test_friday_before_cutoff_t1_is_monday(self):
        cal = us_calendar()
        trade = datetime(2024, 3, 8, 16, 59)
        self.assertEqual(cal.trade_date(trade), date(2024, 3, 8))
        self.assertEqual(cal.settle_date(trade, 1), date(2024, 3, 11))

    def test_cutoff_minute_is_inclusive(self):
        # Documented rule: exactly AT the cutoff still counts as that day;
        # strictly after rolls to the next business day.
        cal = us_calendar()
        at = datetime(2024, 3, 8, 17, 0, 0)
        after = datetime(2024, 3, 8, 17, 0, 1)
        self.assertEqual(cal.trade_date(at), date(2024, 3, 8))
        self.assertEqual(cal.trade_date(after), date(2024, 3, 11))

    def test_aware_datetime_other_zone_converted(self):
        cal = us_calendar()
        # 2024-03-08 22:00 UTC == 17:00 EST exactly -> still Friday.
        trade = datetime(2024, 3, 8, 22, 0, tzinfo=ZoneInfo("UTC"))
        self.assertEqual(cal.trade_date(trade), date(2024, 3, 8))
        # 22:01 UTC -> 17:01 EST -> next business day.
        trade = datetime(2024, 3, 8, 22, 1, tzinfo=ZoneInfo("UTC"))
        self.assertEqual(cal.trade_date(trade), date(2024, 3, 11))

    def test_dst_spring_forward_day(self):
        # US DST sprang forward on 2024-03-10 (02:00 -> 03:00).
        cal = us_calendar()
        # Friday Mar 8 17:00 EST (UTC-5) == 22:00 UTC: at cutoff, same day.
        before = datetime(2024, 3, 8, 22, 0, tzinfo=ZoneInfo("UTC"))
        self.assertEqual(cal.trade_date(before), date(2024, 3, 8))
        # Monday Mar 11 17:00 EDT (UTC-4) == 21:00 UTC: at cutoff, same day.
        after = datetime(2024, 3, 11, 21, 0, tzinfo=ZoneInfo("UTC"))
        self.assertEqual(cal.trade_date(after), date(2024, 3, 11))
        # T+1 from Friday afternoon crosses the DST weekend cleanly.
        trade = datetime(2024, 3, 8, 16, 0)
        self.assertEqual(cal.settle_date(trade, 1), date(2024, 3, 11))

    def test_dst_fall_back_day(self):
        # US DST fell back on 2024-11-03. Monday Nov 4 17:00 EST == 22:00 UTC.
        cal = us_calendar()
        trade = datetime(2024, 11, 4, 22, 0, tzinfo=ZoneInfo("UTC"))
        self.assertEqual(cal.trade_date(trade), date(2024, 11, 4))

    def test_naive_datetime_uses_calendar_zone(self):
        cal = cn_calendar()
        # 15:00 cutoff; 15:30 naive is interpreted as Beijing time.
        trade = datetime(2024, 3, 8, 15, 30)
        self.assertEqual(cal.trade_date(trade), date(2024, 3, 11))

    def test_plain_date_input_bypasses_cutoff(self):
        cal = us_calendar()
        self.assertEqual(cal.settle_date(date(2024, 3, 8), 1), date(2024, 3, 11))


class MultiMarketTest(unittest.TestCase):
    def test_calendars_are_independent(self):
        us = us_calendar()
        cn = cn_calendar(holidays={date(2024, 5, 1)})  # Labour Day
        d = date(2024, 5, 1)
        self.assertTrue(us.is_business_day(d))
        self.assertFalse(cn.is_business_day(d))
        self.assertEqual(us.shift(date(2024, 4, 30), 1), date(2024, 5, 1))
        self.assertEqual(cn.shift(date(2024, 4, 30), 1), date(2024, 5, 2))

    def test_friday_saturday_weekend_market(self):
        gulf = Calendar(weekend=(4, 5), tz="Asia/Dubai")
        us = us_calendar()
        sunday = date(2024, 3, 10)
        self.assertTrue(gulf.is_business_day(sunday))
        self.assertFalse(us.is_business_day(sunday))
        # Thursday is the last business day of the Gulf week.
        self.assertEqual(gulf.shift(date(2024, 3, 7), 1), date(2024, 3, 10))
        self.assertEqual(us.shift(date(2024, 3, 7), 1), date(2024, 3, 8))


class MiscTest(unittest.TestCase):
    def test_business_days_between(self):
        cal = us_calendar()
        self.assertEqual(cal.business_days_between(date(2024, 3, 7), date(2024, 3, 11)), 2)
        self.assertEqual(cal.business_days_between(date(2024, 3, 11), date(2024, 3, 7)), -2)

    def test_unadjusted_adjust_returns_input(self):
        cal = us_calendar()
        d = date(2024, 3, 9)
        self.assertEqual(cal.adjust(d, "unadjusted"), d)

    def test_shift_rejects_non_int(self):
        with self.assertRaises(TypeError):
            us_calendar().shift(date(2024, 1, 2), 1.5)


if __name__ == "__main__":
    unittest.main()
