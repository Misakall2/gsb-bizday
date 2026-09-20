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

    def test_real_calendar_juneteenth_2021_observed_friday(self):
        # Juneteenth 2021-06-19 fell on a Saturday; US federal observance
        # was Friday 2021-06-18.
        cal = us_calendar(holidays={date(2021, 6, 19)}, observance="preceding")
        self.assertFalse(cal.is_business_day(date(2021, 6, 18)))
        self.assertTrue(cal.is_business_day(date(2021, 6, 17)))
        self.assertTrue(cal.is_business_day(date(2021, 6, 21)))

    def test_real_calendar_new_years_2022_modified_following(self):
        # New Year's Day 2022-01-01 fell on a Saturday. Modified following
        # observes it Monday 2022-01-03 (same month, so no fallback).
        cal = us_calendar(holidays={date(2022, 1, 1)}, observance="modified_following")
        self.assertFalse(cal.is_business_day(date(2022, 1, 3)))
        self.assertTrue(cal.is_business_day(date(2021, 12, 31)))
        self.assertEqual(cal.shift(date(2021, 12, 30), 1), date(2021, 12, 31))
        self.assertEqual(cal.shift(date(2021, 12, 31), 1), date(2022, 1, 4))

    def test_unadjusted_weekend_holiday_leaves_neighbours_alone(self):
        # Unadjusted: the Saturday holiday itself stays "observed" on
        # Saturday (already a weekend), and the adjacent Friday/Monday
        # remain ordinary business days.
        cal = us_calendar(holidays={date(2021, 7, 3)}, observance="unadjusted")
        self.assertTrue(cal.is_business_day(date(2021, 7, 2)))
        self.assertTrue(cal.is_business_day(date(2021, 7, 5)))
        self.assertEqual(cal.shift(date(2021, 7, 2), 1), date(2021, 7, 5))


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

    def test_jan_30_is_not_sticky(self):
        cal = us_calendar()
        # Jan 30 2026 is a Friday business day but NOT the last business
        # day of January (Jan 30 is the last Friday; Jan 31 2026 is Sat,
        # so month-end business day is actually Jan 30 -- pick a clean
        # year instead): Jan 30 2024 (Tuesday) is not month-end because
        # Jan 31 2024 is a business day.
        d = date(2024, 1, 30)
        self.assertFalse(cal.is_month_end_business_day(d))
        # Clamped to Feb 29 (leap year), which is a business day.
        self.assertEqual(cal.add_months(d, 1), date(2024, 2, 29))

    def test_jan_30_not_sticky_weekend_feb_end(self):
        cal = us_calendar()
        # Jan 30 2021 was a Saturday (not even a business day, so sticky
        # must not trigger). Feb 2021 ended on Sunday Feb 28. Sticky
        # would give Fri Feb 26; the correct non-sticky path clamps to
        # Feb 28 and adjusts following -> Mon Mar 1.
        d = date(2021, 1, 30)
        self.assertFalse(cal.is_month_end_business_day(d))
        self.assertEqual(cal.last_business_day_of_month(2021, 2), date(2021, 2, 26))
        self.assertEqual(cal.add_months(d, 1), date(2021, 3, 1))

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
    def test_friday_cutoff_ladder_t0_and_t1(self):
        # Friday 2024-03-08, cutoff 17:00 ET inclusive.
        cal = us_calendar()
        fri = date(2024, 3, 8)
        mon = date(2024, 3, 11)
        tue = date(2024, 3, 12)
        cases = [
            # (local time, trade_date, T+0, T+1)
            (time(16, 59, 59), fri, fri, mon),
            (time(17, 0, 0), fri, fri, mon),   # exactly at cutoff: same day
            (time(17, 0, 1), mon, mon, tue),   # strictly after: rolls
            (time(18, 0, 0), mon, mon, tue),
        ]
        for t, expected_trade, expected_t0, expected_t1 in cases:
            with self.subTest(t=t):
                dt = datetime(2024, 3, 8, t.hour, t.minute, t.second)
                self.assertEqual(cal.trade_date(dt), expected_trade)
                self.assertEqual(cal.settle_date(dt, 0), expected_t0)
                self.assertEqual(cal.settle_date(dt, 1), expected_t1)

    def test_cutoff_exactly_1700_counts_same_day(self):
        # Exactly 17:00:00 ET is INCLUSIVE: the trade belongs to Friday
        # itself, not the next business day. (Written red first with the
        # Monday expectation, then corrected after seeing it fail.)
        cal = us_calendar()
        trade = datetime(2024, 3, 8, 17, 0, 0)
        self.assertEqual(cal.trade_date(trade), date(2024, 3, 8))

    def test_naive_and_aware_same_instant_agree(self):
        # EST is UTC-5 on 2024-03-08. A naive ET reading and the same
        # instant expressed in UTC must produce identical results.
        cal = us_calendar()
        for local_t in (time(16, 59, 59), time(17, 0, 0), time(17, 0, 1), time(18, 0)):
            with self.subTest(t=local_t):
                naive = datetime(2024, 3, 8, local_t.hour, local_t.minute, local_t.second)
                aware = naive.replace(tzinfo=ZoneInfo(ET)).astimezone(ZoneInfo("UTC"))
                self.assertEqual(cal.trade_date(naive), cal.trade_date(aware))
                self.assertEqual(cal.settle_date(naive, 1), cal.settle_date(aware, 1))

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

    def test_dst_spring_forward_skipped_hour(self):
        # 2024-03-10 02:30 does not exist in America/New_York (02:00 -> 03:00).
        # settle_date must not raise and must land on a business day.
        cal = us_calendar()
        ghost = datetime(2024, 3, 10, 2, 30)  # Sunday, skipped hour
        result = cal.settle_date(ghost, 1)
        self.assertNotIn(result.weekday(), (5, 6))
        self.assertTrue(cal.is_business_day(result))
        # Sunday trade belongs to Monday Mar 11; T+1 is Tuesday Mar 12.
        self.assertEqual(cal.trade_date(ghost), date(2024, 3, 11))
        self.assertEqual(result, date(2024, 3, 12))

    def test_dst_fall_back_repeated_hour(self):
        # 2024-11-03 01:30 happens twice in America/New_York (fold 0 and 1).
        cal = us_calendar()
        for fold in (0, 1):
            with self.subTest(fold=fold):
                ambiguous = datetime(2024, 11, 3, 1, 30, fold=fold)  # Sunday
                result = cal.settle_date(ambiguous, 1)
                self.assertNotIn(result.weekday(), (5, 6))
                self.assertTrue(cal.is_business_day(result))
                self.assertEqual(cal.trade_date(ambiguous), date(2024, 11, 4))
                self.assertEqual(result, date(2024, 11, 5))

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

    def test_same_day_different_result_across_weekend_schemes(self):
        # Friday 2024-03-08: a business day in the US, a weekend day in a
        # Fri/Sat market. Same input date, different T+1.
        gulf = Calendar(weekend=(4, 5), tz="Asia/Dubai")
        us = us_calendar()
        friday = date(2024, 3, 8)
        self.assertFalse(gulf.is_business_day(friday))
        self.assertTrue(us.is_business_day(friday))
        # Gulf T+1 from Thursday skips Fri/Sat and lands on Sunday;
        # US T+1 from Thursday is Friday itself.
        thursday = date(2024, 3, 7)
        self.assertNotEqual(gulf.shift(thursday, 1), us.shift(thursday, 1))

    def test_english_and_chinese_convention_same_result(self):
        cal = us_calendar()
        d = date(2024, 3, 9)  # Saturday
        self.assertEqual(cal.adjust(d, "following"), cal.adjust(d, "顺延"))
        self.assertEqual(cal.adjust(d, "modified_preceding"), cal.adjust(d, "修正提前"))


class MiscTest(unittest.TestCase):
    def test_business_days_between(self):
        cal = us_calendar()
        self.assertEqual(cal.business_days_between(date(2024, 3, 7), date(2024, 3, 11)), 2)
        self.assertEqual(cal.business_days_between(date(2024, 3, 11), date(2024, 3, 7)), -2)

    def test_business_days_between_zero(self):
        cal = us_calendar()
        self.assertEqual(cal.business_days_between(date(2024, 3, 7), date(2024, 3, 7)), 0)

    def test_shift_zero_on_holiday_adjusts(self):
        holidays = {date(2024, 11, 28)}  # Thanksgiving, a Thursday
        cal = us_calendar(holidays=holidays)
        self.assertFalse(cal.is_business_day(date(2024, 11, 28)))
        self.assertEqual(cal.shift(date(2024, 11, 28), 0), date(2024, 11, 29))
        self.assertEqual(cal.shift(date(2024, 11, 28), 0, "preceding"), date(2024, 11, 27))

    def test_invalid_weekday_raises(self):
        with self.assertRaises(ValueError):
            Calendar(weekend=(7,))
        with self.assertRaises(ValueError):
            Calendar(weekend=(-1,))

    def test_invalid_convention_on_calendar_raises(self):
        with self.assertRaises(ValueError):
            Calendar(observance="随便")
        with self.assertRaises(TypeError):
            Calendar(observance=123)

    def test_unadjusted_adjust_returns_input(self):
        cal = us_calendar()
        d = date(2024, 3, 9)
        self.assertEqual(cal.adjust(d, "unadjusted"), d)

    def test_shift_rejects_non_int(self):
        with self.assertRaises(TypeError):
            us_calendar().shift(date(2024, 1, 2), 1.5)


if __name__ == "__main__":
    unittest.main()
