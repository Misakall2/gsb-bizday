import unittest
from datetime import date, datetime, time

from bizday import Calendar, CompositeCalendar, JOIN, EITHER

ET = "America/New_York"
LON = "Europe/London"
BJ = "Asia/Shanghai"
DXB = "Asia/Dubai"

THANKSGIVING_2024 = date(2024, 11, 28)          # Thursday, NY shut
SPRING_FESTIVAL_2024 = {date(2024, 2, d) for d in range(10, 18)}


def ny_calendar(**kw):
    kw.setdefault("tz", ET)
    kw.setdefault("cutoff", time(17, 0))
    kw.setdefault("weekend", (5, 6))
    return Calendar(**kw)


def london_calendar(**kw):
    kw.setdefault("tz", LON)
    kw.setdefault("cutoff", time(16, 0))
    kw.setdefault("weekend", (5, 6))
    return Calendar(**kw)


class JoinCalendarTest(unittest.TestCase):
    def test_thanksgiving_new_york_closed_london_open_join_closed(self):
        # New York shut for Thanksgiving, London open: a JOIN calendar
        # (both must be open) is closed on the Thursday, open on Friday.
        ny = ny_calendar(holidays={THANKSGIVING_2024})
        lon = london_calendar()
        self.assertFalse(ny.is_business_day(THANKSGIVING_2024))
        self.assertTrue(lon.is_business_day(THANKSGIVING_2024))
        join = CompositeCalendar([ny, lon], JOIN)
        self.assertFalse(join.is_business_day(date(2024, 11, 28)))
        self.assertTrue(join.is_business_day(date(2024, 11, 29)))
        # T+1 across the joint closure skips Thursday AND the weekend.
        self.assertEqual(join.shift(date(2024, 11, 27), 1), date(2024, 11, 29))
        self.assertEqual(join.shift(date(2024, 11, 28), 1), date(2024, 11, 29))

    def test_join_observes_each_sides_holidays_before_combining(self):
        # US Independence Day 2021-07-03 was a Saturday, observed Friday
        # 07-02 by New York. London has no such holiday. The join must be
        # closed on the *observed* Friday -- proving observance happens
        # per constituent first, not by merging raw holiday tables.
        ny = ny_calendar(holidays={date(2021, 7, 3)}, observance="preceding")
        lon = london_calendar()
        join = CompositeCalendar([ny, lon], JOIN)
        self.assertFalse(join.is_business_day(date(2021, 7, 2)))
        self.assertTrue(join.is_business_day(date(2021, 7, 1)))

    def test_join_weekend_is_union_of_weekends(self):
        gulf = Calendar(weekend=(4, 5), tz=DXB)   # Fri/Sat weekend
        ny = ny_calendar()                         # Sat/Sun weekend
        join = CompositeCalendar([gulf, ny], JOIN)
        # Friday: Gulf closed. Sunday: New York closed. Only Mon-Thu shared.
        self.assertFalse(join.is_business_day(date(2024, 3, 8)))    # Friday
        self.assertFalse(join.is_business_day(date(2024, 3, 9)))    # Saturday
        self.assertFalse(join.is_business_day(date(2024, 3, 10)))   # Sunday
        self.assertTrue(join.is_business_day(date(2024, 3, 11)))    # Monday
        # Gulf T+1 from Thursday is Sunday locally, but the join rolls
        # all the way to Monday because New York is shut Sunday.
        self.assertEqual(join.shift(date(2024, 3, 7), 1), date(2024, 3, 11))

    def test_join_adjust_and_settle_with_cutoff(self):
        ny = ny_calendar()
        lon = london_calendar()
        join = CompositeCalendar([ny, lon], JOIN)  # inherits NY tz + 17:00 cutoff
        self.assertEqual(join.adjust(date(2024, 3, 9), "顺延"), date(2024, 3, 11))
        # Friday 17:30 New York time is past the joint cutoff: the trade
        # belongs to Monday and T+1 settles Tuesday.
        self.assertEqual(join.trade_date(datetime(2024, 3, 8, 17, 30)), date(2024, 3, 11))
        self.assertEqual(join.settle_date(datetime(2024, 3, 8, 17, 30), 1), date(2024, 3, 12))
        # Exactly at the cutoff still counts as Friday (inclusive rule
        # inherited unchanged from Calendar).
        self.assertEqual(join.trade_date(datetime(2024, 3, 8, 17, 0)), date(2024, 3, 8))

    def test_explicit_tz_and_cutoff_override_first_constituent(self):
        join = CompositeCalendar([ny_calendar(), london_calendar()], JOIN,
                                 tz=LON, cutoff=time(12, 0))
        # 13:00 naive read as London time, past the 12:00 joint cutoff.
        self.assertEqual(join.trade_date(datetime(2024, 3, 8, 13, 0)), date(2024, 3, 11))


class EitherCalendarTest(unittest.TestCase):
    def test_spring_festival_shanghai_closed_new_york_open_either_open(self):
        # Shanghai shut all of Spring Festival week; New York open.
        # An EITHER calendar (any side open) trades straight through.
        sh = Calendar(weekend=(5, 6), holidays=SPRING_FESTIVAL_2024, tz=BJ)
        ny = ny_calendar()
        monday = date(2024, 2, 12)
        self.assertFalse(sh.is_business_day(monday))
        self.assertTrue(ny.is_business_day(monday))
        either = CompositeCalendar([sh, ny], EITHER)
        self.assertTrue(either.is_business_day(monday))
        self.assertEqual(either.shift(date(2024, 2, 9), 1), date(2024, 2, 12))
        # But a day BOTH sides are shut (a plain Saturday) stays closed.
        self.assertFalse(either.is_business_day(date(2024, 2, 3)))

    def test_either_weekend_is_intersection_of_weekends(self):
        gulf = Calendar(weekend=(4, 5), tz=DXB)   # Fri/Sat weekend
        ny = ny_calendar()                         # Sat/Sun weekend
        either = CompositeCalendar([gulf, ny], EITHER)
        # Only Saturday is closed on both; Friday (NY open) and Sunday
        # (Gulf open) are business days.
        self.assertTrue(either.is_business_day(date(2024, 3, 8)))    # Friday
        self.assertFalse(either.is_business_day(date(2024, 3, 9)))   # Saturday
        self.assertTrue(either.is_business_day(date(2024, 3, 10)))   # Sunday
        self.assertEqual(either.shift(date(2024, 3, 7), 1), date(2024, 3, 8))

    def test_either_settle_with_cutoff(self):
        either = CompositeCalendar([ny_calendar(), london_calendar()], EITHER,
                                   tz=ET, cutoff=time(17, 0))
        self.assertEqual(either.settle_date(datetime(2024, 3, 8, 17, 30), 1),
                         date(2024, 3, 12))


class CompositeValidationTest(unittest.TestCase):
    def test_missing_iana_timezone_raises(self):
        tz_less = Calendar(weekend=(5, 6), tz=None)
        with self.assertRaises(ValueError):
            CompositeCalendar([tz_less, ny_calendar()], JOIN)

    def test_weekday_out_of_range_raises(self):
        with self.assertRaises(ValueError):
            Calendar(weekend=(7,))
        with self.assertRaises(ValueError):
            Calendar(weekend=(-1,))

    def test_bad_mode_raises(self):
        with self.assertRaises(ValueError):
            CompositeCalendar([ny_calendar(), london_calendar()], "xor")

    def test_too_few_constituents_raises(self):
        with self.assertRaises(ValueError):
            CompositeCalendar([ny_calendar()], JOIN)

    def test_non_calendar_constituent_raises(self):
        with self.assertRaises(TypeError):
            CompositeCalendar([ny_calendar(), "not a calendar"], JOIN)


if __name__ == "__main__":
    unittest.main()
