import unittest
from datetime import date, time

from bizday import Calendar, coupon_schedule

ET = "America/New_York"


def ny_calendar(**kw):
    kw.setdefault("tz", ET)
    kw.setdefault("cutoff", time(17, 0))
    kw.setdefault("weekend", (5, 6))
    return Calendar(**kw)


def ends(periods):
    return [p.end for p in periods]


def payments(periods):
    return [p.payment_date for p in periods]


class MonthRollingTest(unittest.TestCase):
    def test_jan_31_rolls_to_feb_month_end_sticky(self):
        # Monthly from 2024-01-31: unadjusted anchors stay glued to each
        # month's last calendar day (2024 is a leap year -> Feb 29).
        cal = ny_calendar()
        periods = coupon_schedule(cal, date(2024, 1, 31), date(2024, 7, 31), 1)
        self.assertEqual(ends(periods), [
            date(2024, 2, 29), date(2024, 3, 31), date(2024, 4, 30),
            date(2024, 5, 31), date(2024, 6, 30), date(2024, 7, 31),
        ])

    def test_leap_year_feb_29_anchor(self):
        # 2023-02-28 is month-end; rolling forward monthly crosses the
        # leap February and lands on 2024-02-29, not 02-28.
        cal = ny_calendar()
        periods = coupon_schedule(cal, date(2023, 2, 28), date(2024, 5, 31),
                                  1, stub="front")
        self.assertIn(date(2024, 2, 29), ends(periods))
        self.assertNotIn(date(2024, 2, 28), ends(periods))

    def test_eom_sticky_can_be_turned_off(self):
        cal = ny_calendar()
        periods = coupon_schedule(cal, date(2024, 1, 31), date(2024, 4, 30),
                                  1, eom_sticky=False, stub="front")
        # Day-of-month clamps instead of sticking: Jan 31 -> Feb 29 -> Mar 29
        # -> Apr 29, then the residual runs into the Apr 30 maturity.
        self.assertEqual(ends(periods), [
            date(2024, 2, 29), date(2024, 3, 29), date(2024, 4, 29),
            date(2024, 4, 30),
        ])


class AdjustmentTest(unittest.TestCase):
    def test_maturity_on_sunday_modified_following_crosses_month_back(self):
        # 2024-03-31 was a Sunday. Modified following would roll to Apr 1
        # (next month), so it falls back to Friday Mar 29. The unadjusted
        # anchor stays 03-31; only the payment moves.
        cal = ny_calendar()
        periods = coupon_schedule(cal, date(2023, 9, 30), date(2024, 3, 31), 6)
        self.assertEqual(len(periods), 1)
        self.assertEqual(periods[0].end, date(2024, 3, 31))       # anchor intact
        self.assertEqual(periods[0].payment_date, date(2024, 3, 29))

    def test_each_period_adjusted_individually_never_shifted_as_string(self):
        # 2024-03-31 (Sun) and 2024-06-30 (Sun) both need adjusting; the
        # anchors in between must NOT drift because a neighbour moved.
        cal = ny_calendar()
        periods = coupon_schedule(cal, date(2024, 1, 31), date(2024, 7, 31), 1)
        self.assertEqual(payments(periods), [
            date(2024, 2, 29),  # Thu, already a business day
            date(2024, 3, 29),  # 03-31 Sun -> modified following -> Fri 29th
            date(2024, 4, 30),
            date(2024, 5, 31),
            date(2024, 6, 28),  # 06-30 Sun -> modified following -> Fri 28th
            date(2024, 7, 31),
        ])
        # Anchors untouched by the adjustments.
        self.assertEqual(ends(periods)[1], date(2024, 3, 31))
        self.assertEqual(ends(periods)[4], date(2024, 6, 30))


class StubTest(unittest.TestCase):
    START = date(2024, 1, 20)   # 5 days past the 3-month grid from maturity
    END = date(2025, 1, 15)

    def test_back_short_stub_sits_at_front(self):
        cal = ny_calendar()
        periods = coupon_schedule(cal, self.START, self.END, 3, stub="back")
        self.assertEqual(
            [(p.start, p.end) for p in periods],
            [(date(2024, 1, 20), date(2024, 4, 15)),   # short front stub
             (date(2024, 4, 15), date(2024, 7, 15)),
             (date(2024, 7, 15), date(2024, 10, 15)),
             (date(2024, 10, 15), date(2025, 1, 15))])

    def test_back_long_stub_merges_into_first_period(self):
        cal = ny_calendar()
        periods = coupon_schedule(cal, self.START, self.END, 3,
                                  stub="back", long_stub=True)
        self.assertEqual(
            [(p.start, p.end) for p in periods],
            [(date(2024, 1, 20), date(2024, 7, 15)),   # long first period
             (date(2024, 7, 15), date(2024, 10, 15)),
             (date(2024, 10, 15), date(2025, 1, 15))])

    def test_front_short_stub_sits_at_end(self):
        cal = ny_calendar()
        periods = coupon_schedule(cal, self.START, self.END, 3, stub="front")
        self.assertEqual(
            [(p.start, p.end) for p in periods],
            [(date(2024, 1, 20), date(2024, 4, 20)),
             (date(2024, 4, 20), date(2024, 7, 20)),
             (date(2024, 7, 20), date(2024, 10, 20)),
             (date(2024, 10, 20), date(2025, 1, 15))])  # short final stub

    def test_front_long_stub_merges_into_last_period(self):
        cal = ny_calendar()
        periods = coupon_schedule(cal, self.START, self.END, 3,
                                  stub="front", long_stub=True)
        self.assertEqual(
            [(p.start, p.end) for p in periods],
            [(date(2024, 1, 20), date(2024, 4, 20)),
             (date(2024, 4, 20), date(2024, 7, 20)),
             (date(2024, 7, 20), date(2025, 1, 15))])   # long final period


class CollisionTest(unittest.TestCase):
    # Front-rolled anchors: 2024-01-06, 2024-07-06 (Sat), 2024-07-08 (Mon,
    # the maturity). The first period's payment adjusts forward off the
    # Saturday and lands exactly on the next period's unadjusted end.
    START = date(2024, 1, 6)
    END = date(2024, 7, 8)

    def test_collision_drop_is_the_default(self):
        # Pinned rule: an adjusted payment that lands on the NEXT period's
        # unadjusted end anchor is DROPPED (the later period's own payment
        # covers that date); it is never silently kept or re-nudged.
        cal = ny_calendar()
        periods = coupon_schedule(cal, self.START, self.END, 6,
                                  convention="following", stub="front")
        self.assertEqual(
            [(p.start, p.end, p.payment_date) for p in periods],
            [(date(2024, 7, 6), date(2024, 7, 8), date(2024, 7, 8))])

    def test_collision_error_mode_raises(self):
        cal = ny_calendar()
        with self.assertRaises(ValueError):
            coupon_schedule(cal, self.START, self.END, 6,
                            convention="following", stub="front",
                            on_collision="error")

    def test_bad_collision_mode_raises(self):
        cal = ny_calendar()
        with self.assertRaises(ValueError):
            coupon_schedule(cal, self.START, self.END, 6, on_collision="keep")


class ScheduleValidationTest(unittest.TestCase):
    def test_end_must_be_after_start(self):
        with self.assertRaises(ValueError):
            coupon_schedule(ny_calendar(), date(2024, 6, 1), date(2024, 1, 1), 3)

    def test_step_must_be_positive_int(self):
        with self.assertRaises(ValueError):
            coupon_schedule(ny_calendar(), date(2024, 1, 1), date(2025, 1, 1), 0)

    def test_bad_stub_raises(self):
        with self.assertRaises(ValueError):
            coupon_schedule(ny_calendar(), date(2024, 1, 1), date(2025, 1, 1),
                            3, stub="middle")

    def test_non_calendar_raises(self):
        with self.assertRaises(TypeError):
            coupon_schedule("ny", date(2024, 1, 1), date(2025, 1, 1), 3)


if __name__ == "__main__":
    unittest.main()
