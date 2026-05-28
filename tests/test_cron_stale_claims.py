"""Pure-helper tests for cron_stale_claims.

The script's API call paths are covered by the smoke shell; here we cover
the pure helper that filters cards against a cutoff.
"""

import time
import unittest

from _helpers import SCRIPTS  # noqa: F401
import cron_stale_claims as csc


def card(card_id, last_iso, labels):
    return {
        "id": card_id,
        "name": f"card-{card_id}",
        "dateLastActivity": last_iso,
        "labels": labels,
    }


def claim(name="claim-executor", label_id="LBL1"):
    return {"id": label_id, "name": name}


class TestParseIso(unittest.TestCase):
    def test_valid(self):
        t = csc.parse_iso("2026-05-28T14:33:00Z")
        self.assertIsNotNone(t)
        self.assertEqual(time.strftime("%Y-%m-%d", t), "2026-05-28")

    def test_empty(self):
        self.assertIsNone(csc.parse_iso(""))

    def test_none(self):
        self.assertIsNone(csc.parse_iso(None))

    def test_garbage(self):
        self.assertIsNone(csc.parse_iso("not a date"))


class TestFindStaleClaims(unittest.TestCase):
    def setUp(self):
        # Cutoff: 1 hour ago
        self.cutoff = time.time() - 3600

    def test_old_claim_caught(self):
        cards = [
            card("A", "2000-01-01T00:00:00Z", [claim()]),  # very old
        ]
        stale = csc.find_stale_claims(cards, self.cutoff)
        self.assertEqual(len(stale), 1)
        self.assertEqual(stale[0][0]["id"], "A")
        self.assertEqual(stale[0][1]["name"], "claim-executor")

    def test_recent_claim_ignored(self):
        recent_iso = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 60)
        )
        cards = [
            card("B", recent_iso, [claim()]),
        ]
        self.assertEqual(csc.find_stale_claims(cards, self.cutoff), [])

    def test_no_claim_label_ignored(self):
        cards = [
            card("C", "2000-01-01T00:00:00Z", [{"id": "X", "name": "urgente"}]),
        ]
        self.assertEqual(csc.find_stale_claims(cards, self.cutoff), [])

    def test_multiple_claims_each_yielded(self):
        cards = [
            card("D", "2000-01-01T00:00:00Z", [
                claim("claim-executor", "L1"),
                claim("claim-orchestrator", "L2"),
            ]),
        ]
        stale = csc.find_stale_claims(cards, self.cutoff)
        self.assertEqual(len(stale), 2)
        self.assertEqual({s[1]["name"] for s in stale}, {"claim-executor", "claim-orchestrator"})

    def test_unparseable_date_skipped(self):
        cards = [
            card("E", "not a date", [claim()]),
        ]
        self.assertEqual(csc.find_stale_claims(cards, self.cutoff), [])

    def test_empty_labels(self):
        cards = [card("F", "2000-01-01T00:00:00Z", [])]
        self.assertEqual(csc.find_stale_claims(cards, self.cutoff), [])

    def test_no_label_name(self):
        cards = [card("G", "2000-01-01T00:00:00Z", [{"id": "X"}])]
        self.assertEqual(csc.find_stale_claims(cards, self.cutoff), [])


if __name__ == "__main__":
    unittest.main()
