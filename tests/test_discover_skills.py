"""Coverage for discover_skills.py (orchestrator-side ClawHub search/ranking)."""

import unittest

from _helpers import SCRIPTS  # noqa: F401
import discover_skills as ds


class TestParseArgs(unittest.TestCase):
    def test_query_joined(self):
        f = ds.parse_args(["build", "nextjs", "page"])
        self.assertEqual(f["query"], "build nextjs page")
        self.assertEqual(f["limit"], ds.DEFAULT_LIMIT)
        self.assertFalse(f["json"])
        self.assertFalse(f["dry"])

    def test_flags(self):
        f = ds.parse_args(["task", "--limit", "3", "--json", "--dry"])
        self.assertEqual(f["query"], "task")
        self.assertEqual(f["limit"], 3)
        self.assertTrue(f["json"])
        self.assertTrue(f["dry"])

    def test_bad_limit_ignored(self):
        f = ds.parse_args(["task", "--limit", "abc"])
        self.assertEqual(f["limit"], ds.DEFAULT_LIMIT)

    def test_no_query(self):
        f = ds.parse_args(["--json"])
        self.assertIsNone(f["query"])


class TestOneLine(unittest.TestCase):
    def test_collapses_whitespace(self):
        self.assertEqual(ds.one_line("a  b\n c\t d"), "a b c d")

    def test_truncates(self):
        out = ds.one_line("x" * 200, width=10)
        self.assertEqual(len(out), 10)
        self.assertTrue(out.endswith("…"))


class TestDiscover(unittest.TestCase):
    def setUp(self):
        self._search = ds.search_clawhub_all
        self._installed = ds.list_installed
        self._inspect = ds.inspect_clawhub

    def tearDown(self):
        ds.search_clawhub_all = self._search
        ds.list_installed = self._installed
        ds.inspect_clawhub = self._inspect

    def test_dry_returns_one_candidate(self):
        cands = ds.discover("nextjs landing", limit=5, dry=True)
        self.assertEqual(len(cands), 1)
        c = cands[0]
        self.assertFalse(c["installed"])
        self.assertTrue(c["repo"].startswith("https://"))
        self.assertTrue(c["desc"])
        self.assertEqual(c["rank"], 1)

    def test_ranking_and_installed_flag(self):
        ds.search_clawhub_all = lambda q, limit, dry: [
            {"slug": "nextjs", "desc": "Next.js helper", "repo": "https://x/nextjs"},
            {"slug": "vitest", "desc": "Vitest helper", "repo": "https://x/vitest"},
        ]
        ds.list_installed = lambda dry: {"vitest"}
        # repo + desc already present, so inspect must not be needed:
        ds.inspect_clawhub = lambda slug, dry: None
        cands = ds.discover("test", limit=5, dry=False)
        self.assertEqual([c["slug"] for c in cands], ["nextjs", "vitest"])
        self.assertEqual([c["rank"] for c in cands], [1, 2])
        self.assertFalse(cands[0]["installed"])
        self.assertTrue(cands[1]["installed"])

    def test_inspect_fills_missing_repo_and_desc(self):
        ds.search_clawhub_all = lambda q, limit, dry: [
            {"slug": "nextjs", "desc": "", "repo": None},
        ]
        ds.list_installed = lambda dry: set()
        ds.inspect_clawhub = lambda slug, dry: {
            "repository": "https://github.com/x/nextjs",
            "description": "official nextjs skill",
        }
        cands = ds.discover("page", limit=5, dry=False)
        self.assertEqual(cands[0]["repo"], "https://github.com/x/nextjs")
        self.assertEqual(cands[0]["desc"], "official nextjs skill")

    def test_no_results(self):
        ds.search_clawhub_all = lambda q, limit, dry: []
        ds.list_installed = lambda dry: set()
        self.assertEqual(ds.discover("nothing", limit=5, dry=False), [])


if __name__ == "__main__":
    unittest.main()
