"""Engineering checks: packaging surface, version, tz-data failure mode.

These guard the embeddable-library contract; business-day semantics
live in test_bizday.py.
"""

import unittest
from datetime import date, datetime, time

import bizday
from bizday import Calendar


class PublicSurfaceTest(unittest.TestCase):
    def test_calendar_importable_from_top_level(self):
        # Callers embed the library as `from bizday import Calendar`.
        self.assertIs(Calendar, bizday.Calendar)

    def test_tests_dir_is_not_part_of_the_public_api(self):
        self.assertFalse(hasattr(bizday, "tests"))
        self.assertNotIn("tests", bizday.__all__)
        for name in bizday.__all__:
            self.assertFalse(name.startswith("test"), name)

    def test_version_exposed_and_well_formed(self):
        self.assertRegex(bizday.__version__, r"^\d+\.\d+\.\d+")
        self.assertIn("__version__", bizday.__all__)


class TzDataFailureTest(unittest.TestCase):
    def test_missing_tz_data_fails_readably(self):
        # A bogus zone exercises the same ZoneInfoNotFoundError path as a
        # real zone on a host without tzdata installed.
        with self.assertRaises(RuntimeError) as ctx:
            Calendar(tz="Not/A_Real_Zone")
        msg = str(ctx.exception)
        self.assertIn("Not/A_Real_Zone", msg)
        self.assertIn("tzdata", msg)
        self.assertIn("UTC", msg)  # says it will NOT silently assume UTC


class LegacyBehaviorSmokeTest(unittest.TestCase):
    """A few pre-existing use cases re-checked against the packaged import,
    so engineering work cannot silently break the library."""

    def test_cutoff_inclusive_then_rolls(self):
        cal = Calendar(tz="America/New_York", cutoff=time(17, 0))
        self.assertEqual(cal.trade_date(datetime(2024, 3, 8, 17, 0, 0)),
                         date(2024, 3, 8))
        self.assertEqual(cal.trade_date(datetime(2024, 3, 8, 17, 0, 1)),
                         date(2024, 3, 11))

    def test_observance_and_t_plus_n(self):
        cal = Calendar(holidays={date(2021, 7, 3)}, observance="preceding")
        self.assertFalse(cal.is_business_day(date(2021, 7, 2)))
        self.assertEqual(cal.shift(date(2021, 7, 1), 1), date(2021, 7, 5))


if __name__ == "__main__":
    unittest.main()
