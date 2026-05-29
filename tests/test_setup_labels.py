"""Tests for setup_labels canonical set."""

import unittest

from _helpers import SCRIPTS  # noqa: F401
import setup_labels


class TestCanonicalLabels(unittest.TestCase):
    def test_done_label_present(self):
        names = [n for n, _ in setup_labels.CANONICAL_LABELS]
        self.assertIn("done", names)

    def test_done_is_green(self):
        d = dict(setup_labels.CANONICAL_LABELS)
        self.assertEqual(d["done"], "green")

    def test_core_labels_intact(self):
        names = [n for n, _ in setup_labels.CANONICAL_LABELS]
        for n in ("urgente", "bloqueado", "revisao", "pediu", "stale", "qa-failed"):
            self.assertIn(n, names)


if __name__ == "__main__":
    unittest.main()
