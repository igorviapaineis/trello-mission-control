"""Tests for the label-based done/reopen flow and resolve_or_create_label."""

import io
import unittest
from contextlib import redirect_stdout

from _helpers import SCRIPTS  # noqa: F401
import trello_task as t


class TestResolveOrCreateLabel(unittest.TestCase):
    def test_resolves_from_config_first(self):
        # When config.labels has the id, no API call is made (creds=None is safe).
        config = {"board_id": "B", "labels": {"done": "LBL_DONE"}}
        self.assertEqual(
            t.resolve_or_create_label("done", "green", config, creds=None),
            "LBL_DONE",
        )


class TestCmdDoneDry(unittest.TestCase):
    def _run(self, *args):
        buf = io.StringIO()
        with redirect_stdout(buf):
            t.cmd_done(*args)
        return buf.getvalue()

    def test_dry_does_not_move(self):
        out = self._run("CARD", {"board_id": "B"}, None, True)  # dry=True, no agent
        self.assertIn("done label", out)
        self.assertIn("dueComplete=true", out)
        self.assertNotIn("idList", out)
        self.assertNotIn("move", out.lower())

    def test_dry_mentions_claim_release_with_agent(self):
        out = self._run("CARD", {"board_id": "B"}, None, True, "jarvis")
        self.assertIn("release claim-jarvis", out)


class TestCmdReopenDry(unittest.TestCase):
    def test_dry(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            t.cmd_reopen("CARD", {"board_id": "B"}, None, True)
        out = buf.getvalue()
        self.assertIn("reopen", out.lower())
        self.assertIn("dueComplete=false", out)


if __name__ == "__main__":
    unittest.main()
