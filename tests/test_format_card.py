import unittest

from _helpers import SCRIPTS  # noqa: F401
import trello_task as tt


class TestFormatCard(unittest.TestCase):
    def test_minimal_card(self):
        c = {"id": "abc12345", "name": "Test"}
        out = tt.format_card(c)
        self.assertIn("CARD:abc12345", out)
        self.assertIn("Test", out)
        self.assertIn("labels=", out)
        self.assertIn("members=", out)

    def test_empty_collections_do_not_crash(self):
        c = {
            "id": "x",
            "name": "n",
            "labels": [],
            "members": [],
            "due": None,
            "idChecklists": [],
            "desc": None,
        }
        out = tt.format_card(c)
        self.assertIn("CARD:x|n", out)
        self.assertIn("labels=", out)
        self.assertIn("members=", out)

    def test_labels_render(self):
        c = {
            "id": "y",
            "name": "card",
            "labels": [{"name": "urgente"}, {"name": "claim-executor"}],
        }
        out = tt.format_card(c)
        self.assertIn("urgente", out)
        self.assertIn("claim-executor", out)

    def test_label_without_name_uses_id(self):
        c = {"id": "z", "name": "x", "labels": [{"id": "lid", "name": None}]}
        out = tt.format_card(c)
        self.assertIn("lid", out)

    def test_long_desc_truncated(self):
        c = {"id": "z", "name": "x", "desc": "a" * 300}
        out = tt.format_card(c)
        self.assertNotIn("a" * 150, out)


if __name__ == "__main__":
    unittest.main()
