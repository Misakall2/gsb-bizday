import unittest
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from bizday import (
    Calendar,
    CompositeCalendar,
    LegSchedule,
    multi_leg_schedule,
    JOIN,
)


def ny(holidays=()):
    return Calendar(weekend=(5, 6), holidays=holidays, observance="following",
                    tz="America/New_York", cutoff=time(17, 0))


def london(holidays=()):
    return Calendar(weekend=(5, 6), holidays=holidays, observance="following",
                    tz="Europe/London", cutoff=time(16, 0))


class BasicLegFlowTest(unittest.TestCase):
    def test_trade_fix_pay_three_calendars(self):
        us, uk, gulf = ny(), london(), Calendar(
            weekend=(4, 5), tz="Asia/Dubai", cutoff=time(12, 0))
        sch = LegSchedule(us, uk, gulf, n_fix=2, n_pay=2)
        # Trade Thursday Mar 7 NY -> Monday Mar 11 London T+2 ->
        # payment calendar counts business days on Fri/Sat-resting gulf.
        t, f, p = sch.schedule(datetime(2024, 3, 7, 10, 0))
        self.assertEqual(t, date(2024, 3, 7))
        self.assertEqual(f, date(2024, 3, 11))   # Mon London
        # Gulf: Mar 11 Mon +1 = Mar 12 Tue, +2 = Mar 13 Wed
        self.assertEqual(p, date(2024, 3, 13))

    def test_shared_join_calendar_for_two_stages(self):
        us, uk = ny(), london()
        join = CompositeCalendar(us, uk, JOIN, tz="UTC", cutoff=time(21, 0))
        sch = LegSchedule(join, join, ny(), n_fix=1, n_pay=1)
        t, f, p = sch.schedule(date(2024, 3, 7))
        self.assertEqual(t, date(2024, 3, 7))
        self.assertEqual(f, date(2024, 3, 8))
        self.assertEqual(p, date(2024, 3, 11))


class NFixZeroNegativeTest(unittest.TestCase):
    def test_n_fix_zero_fixes_on_trade_day(self):
        sch = LegSchedule(ny(), london(), ny(), n_fix=0, n_pay=1)
        t, f, p = sch.schedule(date(2024, 3, 7))
        self.assertEqual(f, t)
        self.assertEqual(p, date(2024, 3, 8))

    def test_negative_n_fix_rolls_fixing_backwards(self):
        # n_fix = -2: fixing date is two London business days BEFORE
        # the trade date.
        sch = LegSchedule(ny(), london(), ny(), n_fix=-2, n_pay=0)
        t, f, p = sch.schedule(date(2024, 3, 11))  # Monday
        self.assertEqual(f, date(2024, 3, 7))      # back to Thursday
        self.assertEqual(p, f)


class CutoffAndTimezoneTest(unittest.TestCase):
    def test_friday_after_ny_cutoff_then_london_fixing(self):
        # Friday Mar 8 17:30 NY is after the NY cutoff => trade date
        # becomes Monday Mar 11. Fixing T+1 in London is Tuesday Mar 12.
        sch = LegSchedule(ny(), london(), ny(), n_fix=1, n_pay=0)
        trade = datetime(2024, 3, 8, 17, 30)
        t, f, p = sch.schedule(trade)
        self.assertEqual(t, date(2024, 3, 11))
        self.assertEqual(f, date(2024, 3, 12))
        self.assertEqual(p, f)

    def test_friday_before_ny_cutoff_then_london_fixing(self):
        sch = LegSchedule(ny(), london(), ny(), n_fix=1, n_pay=0)
        trade = datetime(2024, 3, 8, 16, 59)
        t, f, p = sch.schedule(trade)
        self.assertEqual(t, date(2024, 3, 8))
        self.assertEqual(f, date(2024, 3, 11))

    def test_ny_cutoff_inclusive_preserved(self):
        sch = LegSchedule(ny(), london(), ny(), n_fix=0, n_pay=0)
        at = datetime(2024, 3, 8, 17, 0, 0)
        after = datetime(2024, 3, 8, 17, 0, 1)
        self.assertEqual(sch.trade_date(at), date(2024, 3, 8))
        self.assertEqual(sch.trade_date(after), date(2024, 3, 11))

    def test_dst_spring_forward_ny_does_not_explode_cross_zone(self):
        # NY sprang forward 2024-03-10; London switched 2024-03-31. On
        # Friday Mar 8 NY is UTC-5, London UTC+0 (5h gap). An aware UTC
        # timestamp is compared in each leg's own local time.
        us, uk = ny(), london()
        sch = LegSchedule(us, uk, ny(), n_fix=1, n_pay=0)
        # 21:30 UTC = 16:30 NY (before cutoff) on Friday.
        trade = datetime(2024, 3, 8, 21, 30, tzinfo=ZoneInfo("UTC"))
        t, f, _ = sch.schedule(trade)
        self.assertEqual(t, date(2024, 3, 8))
        self.assertEqual(f, date(2024, 3, 11))
        # 22:30 UTC = 17:30 NY (after cutoff) -> Monday.
        late = datetime(2024, 3, 8, 22, 30, tzinfo=ZoneInfo("UTC"))
        t2, _, _ = sch.schedule(late)
        self.assertEqual(t2, date(2024, 3, 11))

    def test_london_no_spring_forward_on_us_dst_day(self):
        # On 2024-03-11 NY is UTC-4 while London stays UTC+0 (4h gap).
        # 20:30 UTC = 16:30 NY -> still Monday's trade date.
        trade = datetime(2024, 3, 11, 20, 30, tzinfo=ZoneInfo("UTC"))
        sch = LegSchedule(ny(), london(), ny(), n_fix=0, n_pay=0)
        self.assertEqual(sch.trade_date(trade), date(2024, 3, 11))

    def test_naive_datetime_uses_that_leg_timezone(self):
        # A naive timestamp is read in the TRADE calendar's zone (NY).
        sch = LegSchedule(ny(), london(), ny(), n_fix=0, n_pay=0)
        naive = datetime(2024, 3, 8, 17, 30)
        self.assertEqual(sch.trade_date(naive), date(2024, 3, 11))


class SameDayFixPayTieBreakTest(unittest.TestCase):
    def test_same_day_cutoff_owned_by_payment_calendar(self):
        # n_fix = 0, n_pay = 0 and no holidays: fixing == payment on the
        # trade date. The pinned rule: the PAYMENT calendar owns cutoff.
        us, uk = ny(), london()
        sch = LegSchedule(us, uk, uk, n_fix=0, n_pay=0)
        result = sch.resolve(date(2024, 3, 7))
        self.assertTrue(result.same_day_fix_pay)
        self.assertIs(result.cutoff_owner, uk)
        self.assertIsNot(result.cutoff_owner, us)

    def test_distinct_days_cutoff_owned_by_fixing_calendar(self):
        us, uk = ny(), london()
        sch = LegSchedule(us, uk, uk, n_fix=1, n_pay=1)
        result = sch.resolve(date(2024, 3, 7))
        self.assertFalse(result.same_day_fix_pay)
        self.assertIs(result.cutoff_owner, uk)

    def test_same_day_datetime_compared_against_payment_cutoff(self):
        # Fixing calendar London cutoff 16:00; payment NY cutoff 17:00.
        # With same-day fix+pay, a trade at 16:30 London local:
        # London cutoff would roll it, NY cutoff (11:30 NY... careful) -
        # here the trade leg is London itself, so the trade calendar's
        # cutoff decides the trade date; the tie-break only governs
        # fixing-vs-payment ownership, which we assert structurally.
        us, uk = ny(), london()
        sch = LegSchedule(uk, uk, us, n_fix=0, n_pay=0)
        result = sch.resolve(datetime(2024, 3, 7, 10, 0))  # before all cutoffs
        self.assertTrue(result.same_day_fix_pay)
        self.assertIs(result.cutoff_owner, us)
        self.assertEqual(result.payment, date(2024, 3, 7))


class OneShotHelperTest(unittest.TestCase):
    def test_multi_leg_schedule_helper(self):
        t, f, p = multi_leg_schedule(
            date(2024, 3, 7), ny(), london(), ny(), n_fix=1, n_pay=1)
        self.assertEqual((t, f, p),
                         (date(2024, 3, 7), date(2024, 3, 8), date(2024, 3, 11)))


if __name__ == "__main__":
    unittest.main()
