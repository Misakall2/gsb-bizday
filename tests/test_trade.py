import unittest
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from bizday import Calendar, CompositeCalendar, JOIN, schedule_trade

ET = "America/New_York"
LON = "Europe/London"


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


class MultiLegTest(unittest.TestCase):
    def test_three_distinct_calendars(self):
        # Trade in New York, fixed in London, paid on a NY+London join.
        ny = ny_calendar()
        lon = london_calendar()
        join = CompositeCalendar([ny, lon], JOIN)
        t = schedule_trade(datetime(2024, 3, 7, 10, 0), ny, lon, 2, join, 1)
        self.assertEqual(t.trade_date, date(2024, 3, 7))
        self.assertEqual(t.fixing_date, date(2024, 3, 11))   # London T+2
        self.assertEqual(t.payment_date, date(2024, 3, 12))  # joint T+1

    def test_fixing_and_payment_can_share_one_join_calendar(self):
        ny = ny_calendar()
        lon = london_calendar()
        join = CompositeCalendar([ny, lon], JOIN)
        t = schedule_trade(datetime(2024, 3, 7, 10, 0), ny, join, 1, join, 1)
        self.assertEqual(t.fixing_date, date(2024, 3, 8))
        self.assertEqual(t.payment_date, date(2024, 3, 11))

    def test_negative_n_fix_fixes_before_trade_date(self):
        # NDF style: the rate is fixed two business days BEFORE the trade
        # is dealt; payment follows the trade date.
        ny = ny_calendar()
        lon = london_calendar()
        t = schedule_trade(datetime(2024, 3, 8, 16, 0), ny, lon, -2, ny, 1)
        self.assertEqual(t.trade_date, date(2024, 3, 8))
        self.assertEqual(t.fixing_date, date(2024, 3, 6))   # London T-2
        self.assertEqual(t.payment_date, date(2024, 3, 7))  # fixing + 1

    def test_friday_after_ny_cutoff_rolls_then_london_fixing(self):
        # Friday 17:30 New York: past the NY cutoff, so the trade belongs
        # to Monday. London fixing (n_fix=0) is that same Monday -- London
        # was open all along, but the trade date already rolled.
        ny = ny_calendar()
        lon = london_calendar()
        t = schedule_trade(datetime(2024, 3, 8, 17, 30), ny, lon, 0, ny, 1)
        self.assertEqual(t.trade_date, date(2024, 3, 11))
        self.assertEqual(t.fixing_date, date(2024, 3, 11))
        self.assertEqual(t.payment_date, date(2024, 3, 12))

    def test_same_day_fixing_and_payment_payment_cutoff_wins(self):
        # Pinned rule: when n_fix == 0 and n_pay == 0 (trade, fixing and
        # payment all land on one date), the PAYMENT calendar's cutoff is
        # authoritative for the trade datetime -- not the trade/fixing
        # calendar's.
        ny = ny_calendar()                       # 17:00 ET cutoff
        lon = london_calendar()                  # 16:00 London cutoff
        # 16:30 naive, read in the payment (London) zone: past London's
        # 16:00 cutoff, so everything rolls to Monday. Had the trade
        # calendar ruled, 16:30 < 17:00 would have kept it on Friday.
        t = schedule_trade(datetime(2024, 3, 8, 16, 30), ny, lon, 0, lon, 0)
        self.assertEqual(t.trade_date, date(2024, 3, 11))
        self.assertEqual(t.fixing_date, date(2024, 3, 11))
        self.assertEqual(t.payment_date, date(2024, 3, 11))
        # Before the payment cutoff it stays on Friday.
        t2 = schedule_trade(datetime(2024, 3, 8, 15, 30), ny, lon, 0, lon, 0)
        self.assertEqual(t2.trade_date, date(2024, 3, 8))

    def test_naive_datetime_read_in_trade_calendar_zone(self):
        # 16:30 naive is New York local for the trade leg: before the
        # 17:00 ET cutoff, so the trade stays on Friday even though it is
        # already Saturday in Shanghai.
        ny = ny_calendar()
        lon = london_calendar()
        t = schedule_trade(datetime(2024, 3, 8, 16, 30), ny, lon, 1, ny, 1)
        self.assertEqual(t.trade_date, date(2024, 3, 8))

    def test_dst_weeks_new_york_and_london_diverge(self):
        # US sprang forward 2024-03-10; the UK not until 2024-03-31. In
        # the gap weeks London 22:00 GMT is 18:00 EDT (not 17:00 EST):
        # past New York's 17:00 cutoff, so the trade rolls to Tuesday.
        ny = ny_calendar()
        lon = london_calendar()
        aware = datetime(2024, 3, 11, 22, 0, tzinfo=ZoneInfo(LON))
        t = schedule_trade(aware, ny, lon, 0, ny, 0)
        self.assertEqual(t.trade_date, date(2024, 3, 12))
        # One hour earlier in London is exactly 17:00 EDT: at the cutoff,
        # still Monday (cutoff stays inclusive, not exclusive).
        aware = datetime(2024, 3, 11, 21, 0, tzinfo=ZoneInfo(LON))
        t = schedule_trade(aware, ny, lon, 0, ny, 0)
        self.assertEqual(t.trade_date, date(2024, 3, 11))

    def test_aware_datetime_other_zone_converted(self):
        ny = ny_calendar()
        lon = london_calendar()
        # 2024-03-08 22:00 UTC == 17:00 EST exactly: at cutoff, Friday.
        t = schedule_trade(datetime(2024, 3, 8, 22, 0, tzinfo=ZoneInfo("UTC")),
                           ny, lon, 0, ny, 0)
        self.assertEqual(t.trade_date, date(2024, 3, 8))

    def test_non_calendar_leg_raises(self):
        ny = ny_calendar()
        with self.assertRaises(TypeError):
            schedule_trade(datetime(2024, 3, 7, 10, 0), ny, "london", 1, ny, 1)

    def test_non_int_offsets_raise(self):
        ny = ny_calendar()
        with self.assertRaises(TypeError):
            schedule_trade(datetime(2024, 3, 7, 10, 0), ny, ny, 1.5, ny, 1)


if __name__ == "__main__":
    unittest.main()
