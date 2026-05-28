"""Pure-helper tests for scripts/bootstrap_board.py.

Covers the offline pieces (arg parsing, list-name layout, config merge,
agents-block derivation). The Trello API path is exercised in smoke.sh
under --dry.
"""

import unittest

from _helpers import SCRIPTS  # noqa: F401
import bootstrap_board as bb


class TestParseAgents(unittest.TestCase):
    def test_single(self):
        self.assertEqual(bb.parse_agents("jarvis"), ["jarvis"])

    def test_multiple(self):
        self.assertEqual(bb.parse_agents("jarvis,vision,friday,sia"), ["jarvis", "vision", "friday", "sia"])

    def test_strips_spaces(self):
        self.assertEqual(bb.parse_agents(" jarvis , vision "), ["jarvis", "vision"])

    def test_lowercases(self):
        self.assertEqual(bb.parse_agents("JARVIS,Vision"), ["jarvis", "vision"])

    def test_dedupes(self):
        self.assertEqual(bb.parse_agents("jarvis,vision,jarvis"), ["jarvis", "vision"])

    def test_empty_defaults_executor(self):
        self.assertEqual(bb.parse_agents(""), ["executor"])
        self.assertEqual(bb.parse_agents(None), ["executor"])

    def test_invalid_slug_raises(self):
        with self.assertRaises(ValueError):
            bb.parse_agents("Bad_Slug")
        with self.assertRaises(ValueError):
            bb.parse_agents("123agent")


class TestBuildListNames(unittest.TestCase):
    def test_default_executor(self):
        self.assertEqual(
            bb.build_list_names(["executor"]),
            ["inbox", "executor", "done", "_templates"],
        )

    def test_multi_agent_order(self):
        self.assertEqual(
            bb.build_list_names(["jarvis", "vision", "friday", "sia"]),
            ["inbox", "jarvis", "vision", "friday", "sia", "done", "_templates"],
        )

    def test_single_custom_agent(self):
        self.assertEqual(
            bb.build_list_names(["dev"]),
            ["inbox", "dev", "done", "_templates"],
        )


class TestMergeConfig(unittest.TestCase):
    def test_empty_existing(self):
        merged = bb.merge_config({}, {"board_id": "A", "lists": {"inbox": "1"}})
        self.assertEqual(merged, {"board_id": "A", "lists": {"inbox": "1"}})

    def test_preserves_unrelated_keys(self):
        existing = {"keep_me": "yes", "labels": {"urgente": "L1"}}
        merged = bb.merge_config(existing, {"board_id": "NEW"})
        self.assertEqual(merged["keep_me"], "yes")
        self.assertEqual(merged["labels"], {"urgente": "L1"})
        self.assertEqual(merged["board_id"], "NEW")

    def test_overwrites_top_level_scalars(self):
        existing = {"board_id": "OLD"}
        merged = bb.merge_config(existing, {"board_id": "NEW"})
        self.assertEqual(merged["board_id"], "NEW")

    def test_merges_nested_dicts(self):
        existing = {"lists": {"inbox": "old1"}, "agents": {"jarvis": {"role": "executor"}}}
        new = {"lists": {"jarvis": "new2"}}
        merged = bb.merge_config(existing, new)
        # 1-level dict merge: inbox preserved, jarvis added
        self.assertEqual(merged["lists"], {"inbox": "old1", "jarvis": "new2"})
        # agents still there
        self.assertIn("jarvis", merged["agents"])

    def test_none_inputs(self):
        self.assertEqual(bb.merge_config(None, {"a": 1}), {"a": 1})
        self.assertEqual(bb.merge_config({"a": 1}, None), {"a": 1})


class TestBuildAgentsBlock(unittest.TestCase):
    def test_two_agents(self):
        ids = {"inbox": "L0", "jarvis": "L1", "vision": "L2", "done": "L3"}
        block = bb.build_agents_block(["jarvis", "vision"], ids)
        self.assertEqual(block, {
            "jarvis": {"role": "executor", "list_id": "L1"},
            "vision": {"role": "executor", "list_id": "L2"},
        })

    def test_skips_agents_without_list_id(self):
        ids = {"inbox": "L0", "jarvis": "L1"}
        block = bb.build_agents_block(["jarvis", "ghost"], ids)
        self.assertEqual(set(block), {"jarvis"})


class TestSlugify(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(bb.slugify("Mission Control"), "mission-control")

    def test_em_dash(self):
        self.assertEqual(bb.slugify("Mission — Archive"), "mission-archive")


if __name__ == "__main__":
    unittest.main()
