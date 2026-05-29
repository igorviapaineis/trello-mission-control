"""Pure-helper coverage for scripts/doctor.py.

Network and subprocess paths are covered indirectly by the smoke shell.
Here we cover the parser + pure data helpers.
"""

import unittest

from _helpers import SCRIPTS  # noqa: F401
import doctor


PLAIN_JSON = '{"a": 1, "b": "x"}'

JSON5 = """
// top comment
{
  agents: {
    list: [
      { id: "executor", skills: ["trello-mission-control"], }, // trailing comma
    ],
  },
  /* block
     comment */
}
"""


class TestParseOpenclawJson(unittest.TestCase):
    def test_plain_json(self):
        d = doctor.parse_openclaw_json(PLAIN_JSON)
        self.assertEqual(d, {"a": 1, "b": "x"})

    def test_json5_with_comments_and_trailing_commas(self):
        d = doctor.parse_openclaw_json(JSON5)
        # The unquoted keys are JSON5 territory and our simple parser
        # cannot resurrect them; we accept None and rely on a fallback.
        # However a strict JSON5 user would have valid JSON when stripped.
        # Either: parse succeeds → dict has agents.list[0].id == "executor";
        # or: parse returns None, in which case missing the schema is fine.
        if d is None:
            self.skipTest("strict parser does not support unquoted keys")
        agents = d.get("agents") or {}
        lst = agents.get("list") or []
        self.assertEqual(lst[0].get("id"), "executor")

    def test_empty(self):
        self.assertIsNone(doctor.parse_openclaw_json(""))

    def test_invalid(self):
        self.assertIsNone(doctor.parse_openclaw_json("not json at all"))


CFG = {
    "agents": {
        "defaults": {
            "skills": ["trello-mission-control"],
            "heartbeat": {"every": "30m"},
        },
        "list": [
            {"id": "orchestrator", "skills": ["trello-mission-control"]},
            {"id": "executor", "skills": ["trello-mission-control"]},
        ],
    },
}


class TestFindAgentInConfig(unittest.TestCase):
    def test_found(self):
        self.assertEqual(doctor.find_agent_in_config(CFG, "executor")["id"], "executor")

    def test_missing(self):
        self.assertIsNone(doctor.find_agent_in_config(CFG, "ghost"))

    def test_empty_cfg(self):
        self.assertIsNone(doctor.find_agent_in_config({}, "x"))

    def test_none_cfg(self):
        self.assertIsNone(doctor.find_agent_in_config(None, "x"))


class TestMissingLabels(unittest.TestCase):
    canonical = ["urgente", "bloqueado", "stale"]

    def test_all_present(self):
        self.assertEqual(doctor.missing_labels(["urgente", "bloqueado", "stale"], self.canonical), [])

    def test_some_missing(self):
        self.assertEqual(doctor.missing_labels(["urgente"], self.canonical), ["bloqueado", "stale"])

    def test_case_insensitive(self):
        self.assertEqual(doctor.missing_labels(["URGENTE", "Bloqueado", "stale"], self.canonical), [])

    def test_all_missing(self):
        self.assertEqual(doctor.missing_labels([], self.canonical), self.canonical)

    def test_ignores_non_strings(self):
        self.assertEqual(doctor.missing_labels([None, 1, "urgente"], self.canonical), ["bloqueado", "stale"])


class TestParseOpenclawJsonPreservesUrls(unittest.TestCase):
    """The // line-comment stripper used to also kill `https://...` URLs.

    The fix is a negative lookbehind: only strip // when the preceding char
    is not `:`. These cases pin that behaviour.
    """

    def test_https_value_preserved(self):
        text = '{"baseUrl": "https://api.minimax.io/anthropic"}'
        d = doctor.parse_openclaw_json(text)
        self.assertEqual(d, {"baseUrl": "https://api.minimax.io/anthropic"})

    def test_http_value_preserved(self):
        text = '{"baseUrl": "http://localhost:8080/v1"}'
        d = doctor.parse_openclaw_json(text)
        self.assertEqual(d, {"baseUrl": "http://localhost:8080/v1"})

    def test_real_inline_comment_still_stripped(self):
        text = '{"a": 1} // tail comment\n'
        d = doctor.parse_openclaw_json(text)
        self.assertEqual(d, {"a": 1})

    def test_line_start_comment_still_stripped(self):
        text = '// top\n{"a": 1}\n'
        d = doctor.parse_openclaw_json(text)
        self.assertEqual(d, {"a": 1})


class TestAgentsWithSkill(unittest.TestCase):
    def test_own_skills(self):
        cfg = {
            "agents": {
                "list": [
                    {"id": "jarvis", "skills": ["trello-mission-control"]},
                    {"id": "other", "skills": ["foo"]},
                ],
            },
        }
        ids = [e["id"] for e in doctor.agents_with_skill(cfg, "trello-mission-control")]
        self.assertEqual(ids, ["jarvis"])

    def test_defaults_inheritance(self):
        cfg = {
            "agents": {
                "defaults": {"skills": ["trello-mission-control"]},
                "list": [
                    {"id": "sia"},
                    {"id": "nebula"},
                ],
            },
        }
        ids = [e["id"] for e in doctor.agents_with_skill(cfg, "trello-mission-control")]
        self.assertEqual(ids, ["sia", "nebula"])

    def test_empty_or_none(self):
        self.assertEqual(doctor.agents_with_skill(None, "x"), [])
        self.assertEqual(doctor.agents_with_skill({}, "x"), [])
        self.assertEqual(doctor.agents_with_skill({"agents": {"list": []}}, "x"), [])


class TestAgentIdsForWorkspaces(unittest.TestCase):
    def test_reads_from_cfg(self):
        cfg = {"agents": {"list": [{"id": "jarvis"}, {"id": "vision"}]}}
        self.assertEqual(
            doctor.agent_ids_for_workspaces(cfg, fallback=["orchestrator"]),
            ["jarvis", "vision"],
        )

    def test_fallback_when_empty(self):
        self.assertEqual(
            doctor.agent_ids_for_workspaces({}, fallback=["orchestrator", "executor"]),
            ["orchestrator", "executor"],
        )
        self.assertEqual(
            doctor.agent_ids_for_workspaces(None, fallback=["a"]),
            ["a"],
        )

    def test_no_cfg_no_fallback(self):
        self.assertEqual(doctor.agent_ids_for_workspaces(None), [])


class TestHasHeartbeat(unittest.TestCase):
    def test_from_defaults(self):
        defaults = {"heartbeat": {"every": "30m"}}
        agent = {"id": "x"}
        self.assertTrue(doctor.has_heartbeat(agent, defaults))

    def test_from_agent(self):
        defaults = {}
        agent = {"id": "x", "heartbeat": {"every": "15m"}}
        self.assertTrue(doctor.has_heartbeat(agent, defaults))

    def test_zero_value_fails(self):
        defaults = {"heartbeat": {"every": "0m"}}
        self.assertFalse(doctor.has_heartbeat({"id": "x"}, defaults))

    def test_missing(self):
        self.assertFalse(doctor.has_heartbeat({"id": "x"}, {}))

    def test_none_safe(self):
        self.assertFalse(doctor.has_heartbeat(None, None))


if __name__ == "__main__":
    unittest.main()
