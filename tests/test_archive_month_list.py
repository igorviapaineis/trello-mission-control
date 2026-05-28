import re
import time
import unittest

from _helpers import SCRIPTS  # noqa: F401
import archive_old


class TestArchiveMonthKeyDerivation(unittest.TestCase):
    """Smoke test: month-key shape derived from an ISO date.

    archive_old.archive_month_list itself touches the API and is covered by
    the smoke shell. Here we cover the pure parse helper used to choose the
    month bucket.
    """

    def test_parse_iso_valid(self):
        t = archive_old.parse_iso("2026-05-28T14:33:00Z")
        self.assertIsNotNone(t)
        formatted = time.strftime("%Y-%m", t)
        self.assertEqual(formatted, "2026-05")

    def test_parse_iso_invalid(self):
        self.assertIsNone(archive_old.parse_iso(""))
        self.assertIsNone(archive_old.parse_iso(None))
        self.assertIsNone(archive_old.parse_iso("not a date"))

    def test_month_key_shape(self):
        dla = "2024-12-01T00:00:00Z"
        t = archive_old.parse_iso(dla)
        key = time.strftime("%Y-%m", t)
        self.assertRegex(key, re.compile(r"^\d{4}-\d{2}$"))


if __name__ == "__main__":
    unittest.main()
