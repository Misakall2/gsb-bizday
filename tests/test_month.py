import unittest
from datetime import date, datetime

from bizday import BusinessCalendar, add_months, is_end_of_month, month_end


class MonthEndTests(unittest.TestCase):
    def test_end_of_month_predicate(self):
        self.assertTrue(is_end_of_month(date(2024, 2, 29)))
        self.assertTrue(is_end_of_month(date(2023, 2, 28)))
        self.assertFalse(is_end_of_month(date(2024, 2, 28)))

    def test_month_end_leap_and_common(self):
        self.assertEqual(month_end(2024, 2), date(2024, 2, 29))
        self.assertEqual(month_end(2023, 2), date(2023, 2, 28))

    def test_jan31_plus_one_month_no_calendar(self):
        self.assertEqual(add_months(date(2024, 1, 31), 1),
                         date(2024, 2, 29))
        self.assertEqual(add_months(date(2023, 1, 31), 1),
                         date(2023, 2, 28))

    def test_eom_lands_on_last_business_day_common_year(self):
        # 2023-02-28 Tuesday. Jan 31 EOM + 1m -> Feb 28.
        cal = BusinessCalendar()
        self.assertEqual(add_months(date(2023, 1, 31), 1, cal),
                         date(2023, 2, 28))

    def test_eom_lands_on_last_business_day_leap_year(self):
        # 2024-02-29 Thursday.
        cal = BusinessCalendar()
        self.assertEqual(add_months(date(2024, 1, 31), 1, cal),
                         date(2024, 2, 29))

    def test_eom_rolls_back_over_weekend(self):
        # 2024-03-31 Sunday -> last business day Fri Mar 29.
        cal = BusinessCalendar()
        self.assertEqual(add_months(date(2024, 1, 31), 2, cal),
                         date(2024, 3, 29))

    def test_eom_rolls_back_over_holiday(self):
        # Friday 2024-05-31 is a holiday -> Thu May 30.
        cal = BusinessCalendar(holidays=[date(2024, 5, 31)])
        self.assertEqual(add_months(date(2024, 2, 29), 3, cal),
                         date(2024, 5, 30))

    def test_eom_chained_does_not_overshoot(self):
        # Rolling EOM month by month must stay inside each target month.
        cal = BusinessCalendar()
        d = date(2024, 1, 31)
        seq = [add_months(d, i, cal) for i in range(6)]
        months = [(x.year, x.month) for x in seq]
        self.assertEqual(months, [
            (2024, 1), (2024, 2), (2024, 3),
            (2024, 4), (2024, 5), (2024, 6),
        ])
        self.assertEqual(seq[3], date(2024, 4, 30))
        self.assertEqual(seq[5], date(2024, 6, 28))  # Jun 30 Sunday

    def test_non_eom_keeps_day_of_month(self):
        cal = BusinessCalendar()
        self.assertEqual(add_months(date(2024, 1, 15), 1, cal),
                         date(2024, 2, 15))

    def test_non_eom_target_on_weekend_uses_convention(self):
        # 2024-02-15 is Thursday, shift +0; pick a date landing on weekend:
        # 2024-06-15 Saturday + 0m not applicable; use 2024-03-15 (Fri ok).
        # Instead: Jan 13 2024 (Sat) + 0 is input; test add_months where
        # target day lands on weekend across months:
        # 2024-08-31 (Sat, non-EOM input Aug 15 +0 no). Use Dec:
        # 2024-09-14 Sat reached from 2024-06-14 +3.
        cal = BusinessCalendar()
        self.assertEqual(
            add_months(date(2024, 6, 14), 3, cal, convention="following"),
            date(2024, 9, 16),
        )
        self.assertEqual(
            add_months(date(2024, 6, 14), 3, cal, convention="preceding"),
            date(2024, 9, 13),
        )

    def test_force_eom_false_on_month_end_input(self):
        cal = BusinessCalendar()
        # Jan 31 + 1m clamps to Feb 29 even with EOM disabled.
        self.assertEqual(
            add_months(date(2024, 1, 31), 1, cal, end_of_month=False),
            date(2024, 2, 29),
        )

    def test_datetime_preserved(self):
        result = add_months(datetime(2024, 1, 31, 10, 30), 1)
        self.assertEqual(result.date(), date(2024, 2, 29))
        self.assertEqual((result.hour, result.minute), (10, 30))

    def test_backward_months(self):
        cal = BusinessCalendar()
        self.assertEqual(add_months(date(2024, 3, 31), -1, cal),
                         date(2024, 2, 29))


if __name__ == "__main__":
    unittest.main()
