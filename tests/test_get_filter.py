"""Pure-helper tests for the `claim-<other>` filter used by `cmd_get --for-agent`.

Covers is_claim_label, claim_label_owner, filter_cards_for_agent. No network.
"""

import unittest

from _helpers import SCRIPTS  # noqa: F401
import trello_task as t


class TestIsClaimLabel(unittest.TestCase):
    def test_claim_vision(self):
        self.assertTrue(t.is_claim_label("claim-vision"))

    def test_claim_with_hyphenated_owner(self):
        self.assertTrue(t.is_claim_label("claim-jarvis-2"))

    def test_urgente_is_not_claim(self):
        self.assertFalse(t.is_claim_label("urgente"))

    def test_bare_claim_dash_is_not_claim(self):
        # Defensive: `claim-` with no owner is invalid.
        self.assertFalse(t.is_claim_label("claim-"))

    def test_none_is_not_claim(self):
        self.assertFalse(t.is_claim_label(None))

    def test_int_is_not_claim(self):
        self.assertFalse(t.is_claim_label(42))


class TestClaimLabelOwner(unittest.TestCase):
    def test_extracts_owner(self):
        self.assertEqual(t.claim_label_owner("claim-jarvis"), "jarvis")

    def test_extracts_hyphenated_owner(self):
        self.assertEqual(t.claim_label_owner("claim-jarvis-2"), "jarvis-2")

    def test_non_claim_returns_none(self):
        self.assertIsNone(t.claim_label_owner("urgente"))

    def test_bare_claim_dash_returns_none(self):
        self.assertIsNone(t.claim_label_owner("claim-"))

    def test_none_returns_none(self):
        self.assertIsNone(t.claim_label_owner(None))


def card(cid, label_names):
    return {"id": cid, "name": cid, "labels": [{"name": n} for n in label_names]}


class TestFilterCardsForAgent(unittest.TestCase):
    def test_excludes_card_claimed_by_other(self):
        cards = [card("A", ["claim-jarvis"])]
        out = t.filter_cards_for_agent(cards, "vision")
        self.assertEqual([c["id"] for c in out], [])

    def test_keeps_card_claimed_by_self(self):
        cards = [card("A", ["claim-vision"])]
        out = t.filter_cards_for_agent(cards, "vision")
        self.assertEqual([c["id"] for c in out], ["A"])

    def test_keeps_unclaimed_card(self):
        cards = [card("A", [])]
        out = t.filter_cards_for_agent(cards, "vision")
        self.assertEqual([c["id"] for c in out], ["A"])

    def test_claim_wins_over_urgente(self):
        cards = [card("A", ["claim-jarvis", "urgente"])]
        out = t.filter_cards_for_agent(cards, "vision")
        self.assertEqual([c["id"] for c in out], [])

    def test_mixed_listing(self):
        cards = [
            card("A", ["claim-jarvis"]),
            card("B", ["claim-vision"]),
            card("C", ["urgente"]),
            card("D", []),
        ]
        out = t.filter_cards_for_agent(cards, "vision")
        self.assertEqual([c["id"] for c in out], ["B", "C", "D"])

    def test_empty_input(self):
        self.assertEqual(t.filter_cards_for_agent([], "vision"), [])
        self.assertEqual(t.filter_cards_for_agent(None, "vision"), [])

    def test_no_agent_is_identity(self):
        cards = [card("A", ["claim-jarvis"]), card("B", [])]
        out = t.filter_cards_for_agent(cards, None)
        self.assertEqual([c["id"] for c in out], ["A", "B"])
        out = t.filter_cards_for_agent(cards, "")
        self.assertEqual([c["id"] for c in out], ["A", "B"])

    def test_label_without_name_ignored(self):
        cards = [{"id": "A", "name": "A", "labels": [{"id": "L1"}]}]
        out = t.filter_cards_for_agent(cards, "vision")
        self.assertEqual([c["id"] for c in out], ["A"])

    def test_missing_labels_key(self):
        cards = [{"id": "A", "name": "A"}]
        out = t.filter_cards_for_agent(cards, "vision")
        self.assertEqual([c["id"] for c in out], ["A"])


if __name__ == "__main__":
    unittest.main()
