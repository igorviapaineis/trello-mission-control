import json
import unittest

from _helpers import SCRIPTS  # noqa: F401  ensures sys.path setup
import trello_task as tt


class TestMetaBlock(unittest.TestCase):
    def test_parse_empty(self):
        meta, desc = tt.parse_meta_block("")
        self.assertEqual(meta, {})
        self.assertEqual(desc, "")

    def test_parse_no_block(self):
        text = "## Goal\nplain description\n"
        meta, desc = tt.parse_meta_block(text)
        self.assertEqual(meta, {})
        self.assertEqual(desc, text)

    def test_parse_with_block(self):
        text = "## Goal\nfix login\n\n<!--meta\n{\"priority\": \"P0\"}\n-->\n"
        meta, desc = tt.parse_meta_block(text)
        self.assertEqual(meta, {"priority": "P0"})
        self.assertIn("## Goal", desc)
        self.assertNotIn("<!--meta", desc)

    def test_parse_invalid_json_returns_no_meta(self):
        text = "desc\n<!--meta\nnot json\n-->\n"
        meta, desc = tt.parse_meta_block(text)
        self.assertEqual(meta, {})
        self.assertEqual(desc, text)

    def test_parse_complex_block(self):
        meta_dict = {
            "priority": "P1",
            "required_skills": ["nextjs", "vitest"],
            "retries": 0,
            "parent_card": "abc123",
        }
        text = (
            "## Goal\nx\n\n<!--meta\n"
            + json.dumps(meta_dict, indent=2)
            + "\n-->\n"
        )
        meta, _ = tt.parse_meta_block(text)
        self.assertEqual(meta, meta_dict)

    def test_serialize_roundtrip(self):
        meta = {"priority": "P0", "required_skills": ["a", "b"]}
        block = tt.serialize_meta_block(meta)
        # Re-parse with the same regex
        parsed, _ = tt.parse_meta_block(f"Some desc\n{block}")
        self.assertEqual(parsed, meta)

    def test_serialize_block_has_markers(self):
        block = tt.serialize_meta_block({"k": "v"})
        self.assertIn("<!--meta", block)
        self.assertIn("-->", block)


if __name__ == "__main__":
    unittest.main()
