import unittest
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from bizday import (
    Calendar,
    CompositeCalendar,
    composite_calendar,
    JOIN,
    EITHER,
)


def ny(holidays=(), observance="unadjusted", cutoff=time(17, 0)):
    return Calendar(weekend=(5, 6), holidays=holidays, observance=observance,
                    tz="America/New_York", cutoff=cutoff)


def london(holidays=(), observance="unadjusted", cutoff=time(16, 0)):
    return Calendar(weekend=(5, 6), holidays=holidays, observance=observance,
                    tz="Europe/London", cutoff=cutoff)


def shanghai(holidays=(), observance="unadjusted"):
    return Calendar(weekend=(5, 6), holidays=holidays, observance=observance,
                    tz="Asia/Shanghai", cutoff=time(15, 0))


def gulf(holidays=()):
    return Calendar(weekend=(4, 5), holidays=holidays, observance="unadjusted",
                    tz="Asia/Dubai", cutoff=time(12, 0))


class CompositeBasicTest(unittest.TestCase):
    def test_thanksgiving_ny_closed_london_open_join_is_closed(self):
        # 2024-11-28 Thursday: US Thanksgiving (NY closed), London open.
        us = ny(holidays={date(2024, 11, 28)})
        uk = london()
        j = composite_calendar(us, uk, JOIN, tz="UTC")
        self.assertFalse(j.is_business_day(date(2024, 11, 28)))
        # Neighbouring days both markets are open.
        self.assertTrue(j.is_business_day(date(2024, 11, 27)))
        # Shift over the holiday on the composite.
        self.assertEqual(j.shift(date(2024, 11, 27), 1), date(2024, 11, 29))

    def test_thanksgiving_either_stays_open(self):
        us = ny(holidays={date(2024, 11, 28)})
        uk = london()
        e = composite_calendar(us, uk, EITHER, tz="UTC")
        self.assertTrue(e.is_business_day(date(2024, 11, 28)))
        self.assertEqual(e.shift(date(2024, 11, 27), 1), date(2024, 11, 28))

    def test_spring_festival_shanghai_closed_ny_open_either_is_open(self):
        # 2024-02-12 Monday inside Chinese Spring Festival; NY normal.
        cn = shanghai(holidays={date(2024, 2, d) for d in range(10, 18)})
        us = ny()
        e = composite_calendar(cn, us, EITHER, tz="UTC")
        self.assertTrue(e.is_business_day(date(2024, 2, 12)))  # NY carries it
        # Under join the same day is closed because Shanghai rests.
        j = composite_calendar(cn, us, JOIN, tz="UTC")
        self.assertFalse(j.is_business_day(date(2024, 2, 12)))

    def test_both_closed_days_close_either_too(self):
        # Saturday: both Sat/Sun markets closed even under either.
        us, uk = ny(), london()
        e = composite_calendar(us, uk, EITHER, tz="UTC")
        self.assertFalse(e.is_business_day(date(2024, 3, 9)))


class MismatchedWeekendTest(unittest.TestCase):
    def test_gulf_fri_sat_with_ny_sat_sun(self):
        g = gulf()
        us = ny()
        j = composite_calendar(g, us, JOIN, tz="UTC")
        e = composite_calendar(g, us, EITHER, tz="UTC")
        # Week of 2024-03-04:
        # Fri Mar 8  - NY open, Gulf weekend
        # Sat Mar 9  - NY weekend, Gulf weekend
        # Sun Mar 10 - NY weekend, Gulf OPEN
        self.assertTrue(us.is_business_day(date(2024, 3, 8)))
        self.assertFalse(g.is_business_day(date(2024, 3, 8)))
        self.assertTrue(g.is_business_day(date(2024, 3, 10)))
        self.assertFalse(us.is_business_day(date(2024, 3, 10)))
        # join: only Monday-Thursday are shared business days.
        self.assertFalse(j.is_business_day(date(2024, 3, 8)))
        self.assertFalse(j.is_business_day(date(2024, 3, 9)))
        self.assertFalse(j.is_business_day(date(2024, 3, 10)))
        self.assertTrue(j.is_business_day(date(2024, 3, 7)))
        # T+1 from Thursday on the join lands on Monday.
        self.assertEqual(j.shift(date(2024, 3, 7), 1), date(2024, 3, 11))
        # either: Friday (NY) and Sunday (Gulf) both open.
        self.assertTrue(e.is_business_day(date(2024, 3, 8)))
        self.assertFalse(e.is_business_day(date(2024, 3, 9)))  # both rest Sat
        self.assertTrue(e.is_business_day(date(2024, 3, 10)))

    def test_gulf_holiday_does_not_borrow_ny_weekend_definition(self):
        # A Gulf holiday on Friday must be evaluated against the Gulf's
        # Fri/Sat weekend + its own observance, never against NY weekends.
        g = gulf(holidays={date(2024, 3, 8)})
        us = ny()
        j = composite_calendar(g, us, JOIN, tz="UTC")
        self.assertFalse(j.is_business_day(date(2024, 3, 8)))


class SeparateObservanceTest(unittest.TestCase):
    def test_each_leg_applies_its_own_observance(self):
        # 2021-07-03 is Saturday. NY (Sat/Sun) with preceding observes
        # Friday Jul 2; a Fri/Sat market would observe Thursday Jul 1
        # with preceding. Compose and confirm both observed days block.
        us = Calendar(weekend=(5, 6), holidays={date(2021, 7, 3)},
                      observance="preceding", tz="America/New_York")
        g = Calendar(weekend=(4, 5), holidays={date(2021, 7, 3)},
                     observance="preceding", tz="Asia/Dubai")
        j = composite_calendar(us, g, JOIN, tz="UTC")
        self.assertFalse(us.is_business_day(date(2021, 7, 2)))   # NY observed Fri
        self.assertFalse(g.is_business_day(date(2021, 7, 1)))    # Gulf observed Thu
        # Both observed weekdays independently close the join.
        self.assertFalse(j.is_business_day(date(2021, 7, 2)))
        self.assertFalse(j.is_business_day(date(2021, 7, 1)))


class CompositeCutoffTest(unittest.TestCase):
    def test_composite_trade_date_and_settle_with_cutoff(self):
        us, uk = ny(), london()
        j = composite_calendar(us, uk, JOIN, tz="America/New_York",
                               cutoff=time(14, 0))
        # 14:30 NY on Friday Mar 8 is after the composite's own cutoff,
        # so trade date rolls to Monday; T+1 is Tuesday.
        trade = datetime(2024, 3, 8, 14, 30)
        self.assertEqual(j.trade_date(trade), date(2024, 3, 11))
        self.assertEqual(j.settle_date(trade, 1), date(2024, 3, 12))
        # Cutoff stays inclusive, like the single-market Calendar.
        at = datetime(2024, 3, 8, 14, 0)
        self.assertEqual(j.trade_date(at), date(2024, 3, 8))


class CompositeValidationTest(unittest.TestCase):
    def test_missing_tz_on_leg_rejected(self):
        # Calendar default tz is UTC, so construct a deliberately tz-less
        # scenario by clearing it.
        us = ny()
        us.tz = None
        uk = london()
        with self.assertRaises(ValueError):
            composite_calendar(us, uk, JOIN, tz="UTC")

    def test_missing_composite_tz_rejected(self):
        with self.assertRaises(ValueError):
            composite_calendar(ny(), london(), JOIN)

    def test_bad_mode_rejected(self):
        with self.assertRaises(ValueError):
            composite_calendar(ny(), london(), "union", tz="UTC")

    def test_bad_weekday_rejected_at_leaf(self):
        with self.assertRaises(ValueError):
            Calendar(weekend=(7,), tz="America/New_York")
        with self.assertRaises(ValueError):
            Calendar(weekend=(-1,), tz="America/New_York")

    def test_same_leg_twice_rejected(self):
        us = ny()
        with self.assertRaises(ValueError):
            composite_calendar(us, us, JOIN, tz="UTC")

    def test_nested_composite_rejected(self):
        j = composite_calendar(ny(), london(), JOIN, tz="UTC")
        with self.assertRaises(TypeError):
            composite_calendar(j, ny(), JOIN, tz="UTC")

    def test_iana_tz_string_is_required(self):
        # Strings pass; nonsense zone names fail via ZoneInfo.
        with self.assertRaises(Exception):
            composite_calendar(
                Calendar(tz="Not/AZone"), london(), JOIN, tz="UTC")


if __name__ == "__main__":
    unittest.main()
