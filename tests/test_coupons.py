import unittest
from datetime import date

from bizday import (
    Calendar,
    CouponCollisionError,
    coupon_schedule,
    coupon_dates,
)


def clean_cal():
    # No holidays anywhere: pure Sat/Sun calendar, so weekday arithmetic
    # is easy to reason about.
    return Calendar(weekend=(5, 6), tz="America/New_York")


class EomStickyTest(unittest.TestCase):
    def test_jan_31_effective_rolls_to_feb_month_end_sticky(self):
        cal = clean_cal()
        eff = date(2024, 1, 31)   # Wednesday
        mat = date(2024, 7, 31)
        periods = coupon_schedule(eff, mat, 1, cal,
                                  convention="following", sticky_eom=True)
        # Unadjusted first anchor must be Feb 29 (month end), not Feb 28.
        self.assertEqual(periods[0].unadjusted_end, date(2024, 2, 29))
        self.assertEqual(periods[0].end, date(2024, 2, 29))  # Thu, stays

    def test_sticky_grid_walks_month_ends(self):
        cal = clean_cal()
        periods = coupon_schedule(date(2024, 1, 31), date(2024, 4, 30), 1,
                                  cal, sticky_eom=True)
        unadj = [p.unadjusted_end for p in periods]
        self.assertEqual(unadj,
                         [date(2024, 2, 29), date(2024, 3, 31), date(2024, 4, 30)])

    def test_leap_day_anchor_kept_and_adjusted_independently(self):
        cal = clean_cal()
        # Quarterly schedule ending May 31 2024 rolls back through the
        # Feb 29 leap-day anchor.
        periods = coupon_schedule(date(2023, 11, 30), date(2024, 5, 31), 3,
                                  cal, sticky_eom=True)
        unadj = [p.unadjusted_end for p in periods]
        # back from May 31: Feb 29 2024 is a true quarterly EOM anchor.
        self.assertIn(date(2024, 2, 29), unadj)


class MaturityWeekendAdjustTest(unittest.TestCase):
    def test_maturity_sunday_following_crosses_month(self):
        cal = clean_cal()
        # Maturity Sunday Mar 31 2024 -> following -> Mon Apr 1.
        # Mid-month effective: the monthly EOM-aligned rollback reaches
        # back to a Jan 31 prior anchor, so the first period is Jan 2-31.
        eff = date(2024, 1, 2)
        mat = date(2024, 3, 31)
        periods = coupon_schedule(eff, mat, 1, cal, convention="following")
        # Final adjusted payment crosses into April.
        self.assertEqual(periods[-1].unadjusted_end, date(2024, 3, 31))
        self.assertEqual(periods[-1].end, date(2024, 4, 1))
        # Intermediate unadjusted anchors (Jan 31, Feb 29) are NOT moved
        # to follow maturity; they adjust independently.
        unadj = [p.unadjusted_end for p in periods]
        self.assertEqual(unadj,
                         [date(2024, 1, 31), date(2024, 2, 29), date(2024, 3, 31)])
        self.assertEqual(periods[1].end, date(2024, 2, 29))

    def test_maturity_modified_following_avoids_month_cross(self):
        cal = clean_cal()
        mat = date(2024, 3, 31)  # Sunday
        periods = coupon_schedule(date(2024, 1, 1), mat, 1, cal,
                                  convention="modified_following")
        # MF rolls back to Friday Mar 29 instead of crossing to April.
        self.assertEqual(periods[-1].end, date(2024, 3, 29))


class IndependentAdjustmentTest(unittest.TestCase):
    def test_each_period_adjusted_separately_no_whole_string_shift(self):
        # Quarterly EOM schedule. Jun 30 2024 is a Sunday, so its
        # following adjustment is Jul 1; Sep 30 is a clean Monday. Each
        # anchor adjusts independently; the Jun move does not drag the
        # rest of the string.
        cal = Calendar(weekend=(5, 6),
                       holidays=(),
                       tz="America/New_York")
        eff = date(2023, 12, 31)
        mat = date(2024, 9, 30)
        periods = coupon_schedule(eff, mat, 3, cal, convention="following")
        by_unadj = {p.unadjusted_end: p.end for p in periods}
        # Mar 31 Sunday -> following -> Apr 1
        self.assertEqual(by_unadj[date(2024, 3, 31)], date(2024, 4, 1))
        # Jun 30 Sunday -> following -> Jul 1 (Monday)
        self.assertEqual(by_unadj[date(2024, 6, 30)], date(2024, 7, 1))
        # Sep 30 unchanged; the Jun adjustment did not drag the string.
        self.assertEqual(by_unadj[date(2024, 9, 30)], date(2024, 9, 30))


class StubTest(unittest.TestCase):
    def test_front_short_stub(self):
        cal = clean_cal()
        eff = date(2024, 1, 15)    # mid-month
        first_anchor = date(2024, 5, 15)  # stub Feb 15 + 3 months
        mat = date(2024, 8, 15)
        front = date(2024, 2, 15)  # 1-month short front stub
        periods = coupon_schedule(eff, mat, 3, cal,
                                  convention="following", sticky_eom=True,
                                  front_stub=front)
        self.assertTrue(periods[0].is_stub)
        self.assertEqual(periods[0].unadjusted_start, eff)
        self.assertEqual(periods[0].unadjusted_end, front)
        self.assertEqual(periods[0].end, front)  # Thu
        # Regular periods follow from the stub to the regular grid.
        self.assertEqual(periods[1].unadjusted_end, first_anchor)
        self.assertFalse(periods[1].is_stub)
        self.assertEqual(periods[-1].unadjusted_end, mat)

    def test_back_long_stub(self):
        cal = clean_cal()
        eff = date(2023, 12, 31)
        mat = date(2024, 9, 30)
        # Regular grid back from Sep: Jun 30, Mar 31, Dec 31...
        # A back stub of Aug 31 makes the final span Jun 30 -> Aug 31 ->
        # Sep 30: a two-month long stub + short final month. We mark the
        # period ending at the stub boundary as the stub.
        back = date(2024, 8, 31)  # Saturday
        periods = coupon_schedule(eff, mat, 3, cal,
                                  convention="following", sticky_eom=True,
                                  back_stub=back)
        # Find the period whose raw start is the back stub.
        stub_periods = [p for p in periods if p.is_stub]
        self.assertEqual(len(stub_periods), 1)
        stub = stub_periods[0]
        self.assertEqual(stub.unadjusted_start, back)
        self.assertEqual(stub.unadjusted_end, mat)
        # Aug 31 Sat adjusts independently to Mon Sep 2 (start payment).
        self.assertEqual(stub.start, date(2024, 9, 2))
        self.assertEqual(stub.end, date(2024, 9, 30))

    def test_back_short_and_front_long_stubs_also_supported(self):
        cal = clean_cal()
        # Back short stub: regular quarterly grid Mar 31 / Jun 30 /
        # Sep 30, with a one-month stub Sep 30 -> maturity Oct 31.
        eff = date(2023, 12, 31)
        mat = date(2024, 10, 31)
        back = date(2024, 9, 30)
        # Sep 30 coincides with a regular anchor in a plain grid, so use
        # a maturity that leaves a genuine one-month tail: maturity
        # Oct 31 and back stub Sep 30, grid back from Oct rolls Jul 31.
        mat = date(2024, 10, 31)
        back = date(2024, 9, 30)
        periods = coupon_schedule(eff, mat, 3, cal,
                                  convention="following", sticky_eom=True,
                                  back_stub=back)
        stub = [p for p in periods if p.is_stub]
        self.assertEqual(len(stub), 1)
        self.assertEqual(stub[0].unadjusted_start, date(2024, 9, 30))
        self.assertEqual(stub[0].unadjusted_end, date(2024, 10, 31))

        # Front LONG stub: effective is 5 months before the first
        # regular anchor but a stub boundary is supplied, producing a
        # 2-month front stub then quarterly grid.
        eff2 = date(2024, 1, 10)
        front2 = date(2024, 3, 10)   # 2-month front (long vs 3-month freq)
        mat2 = date(2024, 9, 10)
        p2 = coupon_schedule(eff2, mat2, 3, cal, convention="following",
                             sticky_eom=False, front_stub=front2)
        self.assertTrue(p2[0].is_stub)
        self.assertEqual(p2[0].unadjusted_end, front2)
        self.assertEqual(p2[1].unadjusted_end, date(2024, 6, 10))
        self.assertEqual(p2[2].unadjusted_end, date(2024, 9, 10))


class CollisionPolicyTest(unittest.TestCase):
    def test_adjusted_coupon_colliding_next_anchor_raises(self):
        # Non-sticky monthly anchors from a day-1 effective:
        # Feb 1, Mar 1 (Friday), Apr 1 (Monday). Make Mar 1 a holiday and
        # close every weekday Mar 4..Mar 29 too, so following from Mar 1
        # skips the month and lands on Apr 1 = the NEXT unadjusted anchor.
        closed = {date(2024, 3, 1)}
        d = date(2024, 3, 4)
        while d <= date(2024, 3, 29):
            if d.weekday() < 5:
                closed.add(d)
            d = date.fromordinal(d.toordinal() + 1)
        cal = Calendar(weekend=(5, 6), holidays=closed,
                       observance="unadjusted", tz="America/New_York")
        with self.assertRaises(CouponCollisionError):
            coupon_schedule(date(2024, 1, 1), date(2024, 5, 1), 1, cal,
                            convention="following", sticky_eom=False)

    def test_policy_is_consistent_for_front_stub_path(self):
        # Same raise must happen even when the colliding period is the
        # front stub (no path silently keeps/drops it).
        # Front stub Jan 15 -> Feb 15 (Thursday). Quarterly anchors step
        # forward from the stub, so the next unadjusted anchor is
        # May 15. Close Feb 15 and every weekday through May 14 so
        # following the stub lands exactly on May 15.
        eff = date(2024, 1, 15)
        front = date(2024, 2, 15)
        mat = date(2024, 8, 15)
        closed = set()
        d = date(2024, 2, 15)
        while d < date(2024, 5, 15):
            if d.weekday() < 5:
                closed.add(d)
            d = date.fromordinal(d.toordinal() + 1)
        cal = Calendar(weekend=(5, 6), holidays=closed,
                       observance="unadjusted", tz="America/New_York")
        with self.assertRaises(CouponCollisionError):
            coupon_schedule(eff, mat, 3, cal, convention="following",
                            sticky_eom=False, front_stub=front)


class CouponDatesHelperTest(unittest.TestCase):
    def test_coupon_dates_returns_adjusted_payments(self):
        cal = clean_cal()
        dates = coupon_dates(date(2024, 1, 1), date(2024, 4, 1), 1, cal)
        self.assertEqual(dates,
                         [date(2024, 2, 1), date(2024, 3, 1), date(2024, 4, 1)])


if __name__ == "__main__":
    unittest.main()
