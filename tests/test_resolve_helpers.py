import unittest

from _helpers import SCRIPTS  # noqa: F401
import trello_task as tt


CONFIG = {
    "lists": {"inbox": "L1", "executor": "L2", "Done": "L3"},
    "labels": {"urgente": "LBL1", "claim-executor": "LBL2"},
}


class TestResolveList(unittest.TestCase):
    def test_lookup_by_lower_name(self):
        self.assertEqual(tt.resolve_list("inbox", CONFIG), "L1")

    def test_lookup_case_insensitive(self):
        self.assertEqual(tt.resolve_list("INBOX", CONFIG), "L1")
        self.assertEqual(tt.resolve_list("done", CONFIG), "L3")

    def test_lookup_by_id_passes_through(self):
        self.assertEqual(tt.resolve_list("L1", CONFIG), "L1")

    def test_unknown_passes_through(self):
        self.assertEqual(tt.resolve_list("nothing", CONFIG), "nothing")


class TestResolveLabel(unittest.TestCase):
    def test_lookup_by_name(self):
        self.assertEqual(tt.resolve_label("urgente", CONFIG), "LBL1")

    def test_case_insensitive(self):
        self.assertEqual(tt.resolve_label("URGENTE", CONFIG), "LBL1")

    def test_lookup_by_id_passes_through(self):
        self.assertEqual(tt.resolve_label("LBL1", CONFIG), "LBL1")

    def test_unknown_passes_through(self):
        self.assertEqual(tt.resolve_label("missing", CONFIG), "missing")


class TestClaimLabelName(unittest.TestCase):
    def test_format(self):
        self.assertEqual(tt.claim_label_name("executor"), "claim-executor")
        self.assertEqual(tt.claim_label_name("backend-dev"), "claim-backend-dev")


if __name__ == "__main__":
    unittest.main()
