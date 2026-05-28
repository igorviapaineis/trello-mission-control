"""Coverage for ensure_skills.py's clawhub-inspect + git-clone resolution."""

import unittest

from _helpers import SCRIPTS  # noqa: F401
import ensure_skills as es


class TestRepoUrlFromMetadata(unittest.TestCase):
    def test_https_repository(self):
        meta = {"repository": "https://github.com/x/y"}
        self.assertEqual(es.repo_url_from_metadata(meta), "https://github.com/x/y")

    def test_nested_repository_object(self):
        meta = {"repository": {"url": "https://github.com/x/y.git", "type": "git"}}
        self.assertEqual(es.repo_url_from_metadata(meta), "https://github.com/x/y.git")

    def test_repo_alias(self):
        meta = {"repo": "https://gitlab.com/x/y"}
        self.assertEqual(es.repo_url_from_metadata(meta), "https://gitlab.com/x/y")

    def test_git_ssh_form(self):
        meta = {"git": "git@github.com:x/y.git"}
        self.assertEqual(es.repo_url_from_metadata(meta), "git@github.com:x/y.git")

    def test_no_url_anywhere(self):
        meta = {"description": "no repo here"}
        self.assertIsNone(es.repo_url_from_metadata(meta))

    def test_non_dict_input(self):
        self.assertIsNone(es.repo_url_from_metadata(None))
        self.assertIsNone(es.repo_url_from_metadata("string"))

    def test_ignores_non_url_strings(self):
        meta = {"repository": "just-a-name"}
        self.assertIsNone(es.repo_url_from_metadata(meta))


class TestDryRunPaths(unittest.TestCase):
    """Dry-run code paths should not hit any subprocess."""

    def test_search_dry_returns_slug(self):
        slug = es.search_clawhub("nextjs", dry=True)
        self.assertEqual(slug, "dry-nextjs")

    def test_inspect_dry_returns_stub(self):
        meta = es.inspect_clawhub("nextjs", dry=True)
        self.assertIn("repository", meta)
        self.assertTrue(meta["repository"].startswith("https://"))

    def test_repo_url_from_dry_inspect(self):
        meta = es.inspect_clawhub("nextjs", dry=True)
        url = es.repo_url_from_metadata(meta)
        self.assertIsNotNone(url)


if __name__ == "__main__":
    unittest.main()
