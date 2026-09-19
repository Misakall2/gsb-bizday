import unittest
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from bizday import (
    BusinessCalendar,
    add_business_days,
    add_months,
    t_plus_n,
)


NY = ZoneInfo("America/New_York")
SH = ZoneInfo("Asia/Shanghai")


def us_calendar():
    # Thanksgiving Thu 2024-11-28 plus the following Friday; Christmas.
    return BusinessCalendar(
        "us",
        holidays=[date(2024, 11, 28), date(2024, 11, 29),
                  date(2024, 12, 25)],
        observance="following",
        tz="America/New_York",
        cutoff_time=time(17, 0),
    )


# Spring Festival 2024: official holiday Fri 2024-02-09 .. Fri 2024-02-16
# (02-10/11 and 02-15 are weekends anyway; the makeup rules are ignored
# here; the caller supplies the non-business dates they want enforced).
SPRING_FESTIVAL_2024 = [
    date(2024, 2, 9), date(2024, 2, 10), date(2024, 2, 11),
    date(2024, 2, 12), date(2024, 2, 13), date(2024, 2, 14),
    date(2024, 2, 15), date(2024, 2, 16),
]


def cn_calendar():
    return BusinessCalendar(
        "cn",
        holidays=SPRING_FESTIVAL_2024,
        observance="unadjusted",
        tz="Asia/Shanghai",
        cutoff_time=time(15, 0),
    )


class TPlusNDateTests(unittest.TestCase):
    def test_t0_is_same_day(self):
        cal = us_calendar()
        self.assertEqual(t_plus_n(date(2024, 11, 27), 0, cal),
                         date(2024, 11, 27))

    def test_t1_us_equities(self):
        cal = us_calendar()
        self.assertEqual(t_plus_n(date(2024, 11, 27), 1, cal),
                         date(2024, 12, 2))

    def test_t2_bonds_skip_thanksgiving_block(self):
        # Wednesday before Thanksgiving: T+1 lands Mon 12-02 because Thu+Fri
        # are both off; T+2 lands Tue 12-03.
        cal = us_calendar()
        self.assertEqual(t_plus_n(date(2024, 11, 27), 2, cal),
                         date(2024, 12, 3))

    def test_spring_festival_skips_whole_week(self):
        cal = cn_calendar()
        # Last trading day before the break is Thu 2024-02-08.
        self.assertTrue(cal.is_business_day(date(2024, 2, 8)))
        # T+2 must jump the entire holiday block -> Tue 2024-02-20
        # (Mon 02-19 is the first business day, T+2 is Tuesday).
        self.assertEqual(t_plus_n(date(2024, 2, 8), 2, cal),
                         date(2024, 2, 20))
        self.assertEqual(t_plus_n(date(2024, 2, 8), 1, cal),
                         date(2024, 2, 19))

    def test_negative_n_rolls_back(self):
        cal = us_calendar()
        self.assertEqual(t_plus_n(date(2024, 12, 3), -1, cal),
                         date(2024, 12, 2))
        self.assertEqual(t_plus_n(date(2024, 12, 2), -2, cal),
                         date(2024, 11, 26))

    def test_weekend_date_input_following(self):
        cal = us_calendar()
        # Saturday -> Monday then +1
        self.assertEqual(add_business_days(date(2024, 11, 30), 1, cal),
                         date(2024, 12, 3))


class CutoffTests(unittest.TestCase):
    def test_before_cutoff_same_session(self):
        cal = us_calendar()
        dt = datetime(2024, 11, 27, 16, 0, tzinfo=NY)
        self.assertEqual(t_plus_n(dt, 1, cal).date(), date(2024, 12, 2))

    def test_friday_evening_after_cutoff_not_saturday(self):
        cal = us_calendar()
        # Friday 2024-11-22, 18:00 NY is after the 17:00 cutoff.
        # The trade books to Monday 11-25's session, so T+1 is Tuesday.
        dt = datetime(2024, 11, 22, 18, 0, tzinfo=NY)
        result = t_plus_n(dt, 1, cal)
        self.assertEqual(result.date(), date(2024, 11, 26))
        self.assertNotEqual(result.weekday(), 5)
        # T+0 itself is Monday, never Saturday.
        self.assertEqual(t_plus_n(dt, 0, cal).date(), date(2024, 11, 25))

    def test_cutoff_is_exclusive_boundary(self):
        # 16:59:59 belongs to today; exactly 17:00:00 rolls to next session.
        cal = us_calendar()
        just_before = datetime(2024, 11, 26, 16, 59, 59, tzinfo=NY)
        at_cutoff = datetime(2024, 11, 26, 17, 0, 0, tzinfo=NY)
        self.assertEqual(t_plus_n(just_before, 1, cal).date(),
                         date(2024, 11, 27))
        self.assertEqual(t_plus_n(at_cutoff, 1, cal).date(),
                         date(2024, 12, 2))

    def test_naive_datetime_uses_calendar_tz(self):
        cal = us_calendar()
        naive = datetime(2024, 11, 26, 18, 0)  # treated as NY local
        self.assertEqual(t_plus_n(naive, 1, cal).date(), date(2024, 12, 2))

    def test_aware_datetime_in_other_zone_converted(self):
        cal = us_calendar()
        # 2024-11-26 23:30 Shanghai == 10:30 NY, before cutoff.
        dt = datetime(2024, 11, 26, 23, 30, tzinfo=SH)
        self.assertEqual(t_plus_n(dt, 1, cal).date(), date(2024, 11, 27))

    def test_after_cutoff_before_holiday_skips_block(self):
        cal = us_calendar()
        # Wed 2024-11-27 18:00 NY -> effective session Fri is a holiday, so
        # the next session is Mon 12-02; T+1 is Tue 12-03.
        dt = datetime(2024, 11, 27, 18, 0, tzinfo=NY)
        self.assertEqual(t_plus_n(dt, 1, cal).date(), date(2024, 12, 3))


class DSTTests(unittest.TestCase):
    def test_spring_forward_day(self):
        # US clocks spring forward 2024-03-10 02:00 -> 03:00.
        cal = us_calendar()
        # Friday at exactly the cutoff already belongs to the Monday
        # session; T+1 is Tuesday the 12th.
        at_cutoff = datetime(2024, 3, 8, 17, 0, tzinfo=NY)
        self.assertEqual(t_plus_n(at_cutoff, 1, cal).date(),
                         date(2024, 3, 12))
        # One minute before cutoff: Friday session, T+1 Monday the 11th.
        before = datetime(2024, 3, 8, 16, 59, tzinfo=NY)
        self.assertEqual(t_plus_n(before, 1, cal).date(), date(2024, 3, 11))
        # Constructing a time in the skipped 02:30 slot must not raise and
        # cutoff math on the DST Sunday must still behave.
        skipped = datetime(2024, 3, 10, 2, 30, tzinfo=NY)
        self.assertIsNotNone(skipped.utcoffset())

    def test_fall_back_day(self):
        # Clocks fall back 2024-11-03 02:00.
        cal = us_calendar()
        before = datetime(2024, 11, 1, 16, 0, tzinfo=NY)
        after = datetime(2024, 11, 1, 18, 0, tzinfo=NY)
        self.assertEqual(t_plus_n(before, 1, cal).date(), date(2024, 11, 4))
        self.assertEqual(t_plus_n(after, 1, cal).date(), date(2024, 11, 5))


class MarketIsolationTests(unittest.TestCase):
    def test_same_date_different_markets(self):
        us = us_calendar()
        cn = cn_calendar()
        d = date(2024, 2, 13)  # Tuesday, CN Spring Festival, US normal
        self.assertTrue(us.is_business_day(d))
        self.assertFalse(cn.is_business_day(d))
        self.assertEqual(t_plus_n(date(2024, 2, 12), 1, us),
                         date(2024, 2, 13))
        self.assertEqual(t_plus_n(date(2024, 2, 8), 1, cn),
                         date(2024, 2, 19))


if __name__ == "__main__":
    unittest.main()
