import re
import unittest

from _helpers import SCRIPTS  # noqa: F401
import trello_task as tt


class TestTagPrefix(unittest.TestCase):
    pattern = re.compile(
        r"^\[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}Z \| @[\w\-]+ \| "
        r"(claim|done|blocked|handoff|note)\]$"
    )

    def test_shape_claim(self):
        s = tt.tag_prefix("executor", "claim")
        self.assertRegex(s, self.pattern)

    def test_shape_done(self):
        s = tt.tag_prefix("orchestrator", "done")
        self.assertRegex(s, self.pattern)

    def test_shape_blocked(self):
        s = tt.tag_prefix("agent-1", "blocked")
        self.assertRegex(s, self.pattern)

    def test_agent_with_hyphen(self):
        s = tt.tag_prefix("backend-dev", "handoff")
        self.assertIn("@backend-dev", s)

    def test_iso_now_format(self):
        s = tt.iso_now()
        self.assertRegex(s, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}Z$")


if __name__ == "__main__":
    unittest.main()
