"""Engineering checks: packaging surface, tz-data failure mode, and a couple
of legacy behavior probes to prove engineering work did not break the math.
"""

import re
import unittest
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfoNotFoundError

import bizday
from bizday import Calendar

REPO_ROOT = Path(__file__).resolve().parent.parent


class PublicSurfaceTest(unittest.TestCase):
    def test_tests_dir_is_not_part_of_the_package(self):
        self.assertFalse(hasattr(bizday, "tests"))
        self.assertNotIn("tests", bizday.__all__)
        for name in bizday.__all__:
            self.assertFalse(name.startswith("test"), name)

    def test_top_level_import_contract(self):
        # Callers must keep working with `from bizday import Calendar`.
        self.assertIs(bizday.Calendar, Calendar)

    def test_version_is_defined_and_matches_pyproject(self):
        self.assertTrue(re.fullmatch(r"\d+\.\d+\.\d+", bizday.__version__))
        pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        m = re.search(r'^version = "([^"]+)"', pyproject, re.MULTILINE)
        self.assertIsNotNone(m, "pyproject.toml must declare a version")
        self.assertEqual(m.group(1), bizday.__version__)

    def test_no_runtime_dependencies_declared(self):
        pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        m = re.search(r"^dependencies = \[(.*?)\]", pyproject, re.MULTILINE | re.DOTALL)
        self.assertIsNotNone(m, "pyproject.toml must declare dependencies")
        self.assertEqual(m.group(1).strip(), "", "runtime dependencies must be empty")


class TimezoneDataTest(unittest.TestCase):
    def test_missing_tz_data_fails_readably(self):
        with self.assertRaises(ZoneInfoNotFoundError) as ctx:
            Calendar(tz="Not/A_Real_Zone")
        msg = str(ctx.exception)
        self.assertIn("Not/A_Real_Zone", msg)
        self.assertIn("tzdata", msg)  # tells the operator how to fix it


class LegacyBehaviorProbeTest(unittest.TestCase):
    """Spot-checks of pre-existing semantics (cutoff, observance, T+N)."""

    def test_cutoff_minute_still_inclusive(self):
        cal = Calendar(tz="America/New_York", cutoff=time(17, 0))
        self.assertEqual(cal.trade_date(datetime(2024, 3, 8, 17, 0, 0)), date(2024, 3, 8))
        self.assertEqual(cal.trade_date(datetime(2024, 3, 8, 17, 0, 1)), date(2024, 3, 11))

    def test_observance_and_t_plus_n(self):
        cal = Calendar(holidays={date(2021, 7, 3)}, observance="preceding")
        self.assertFalse(cal.is_business_day(date(2021, 7, 2)))
        self.assertEqual(cal.shift(date(2021, 7, 1), 1), date(2021, 7, 5))


if __name__ == "__main__":
    unittest.main()
