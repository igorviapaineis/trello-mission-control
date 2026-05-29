"""Coverage for assemble_artifact.py (subtask part join + output derivation)."""

import os
import sys
import tempfile
import unittest

from _helpers import SCRIPTS  # noqa: F401
import assemble_artifact as aa


def _mkdir_with(names_or_pairs):
    """Create a temp dir holding the given files; returns (dir, [paths])."""
    d = tempfile.mkdtemp()
    paths = []
    for entry in names_or_pairs:
        name, body = entry if isinstance(entry, tuple) else (entry, entry)
        p = os.path.join(d, name)
        with open(p, "w", encoding="utf-8") as f:
            f.write(body)
        paths.append(p)
    return d, paths


class TestParseArgs(unittest.TestCase):
    def test_basic(self):
        f = aa.parse_args(["card1", "--parts-dir", "/tmp/p"])
        self.assertEqual(f["card_id"], "card1")
        self.assertEqual(f["parts_dir"], "/tmp/p")
        self.assertTrue(f["attach"])
        self.assertFalse(f["dry"])

    def test_flags(self):
        f = aa.parse_args([
            "c", "--parts-dir", "d", "--output", "o.md", "--separator", "---",
            "--header-from-filename", "--no-attach", "--dry",
        ])
        self.assertEqual(f["output"], "o.md")
        self.assertEqual(f["separator"], "---")
        self.assertTrue(f["header_from_filename"])
        self.assertFalse(f["attach"])
        self.assertTrue(f["dry"])


class TestCollectParts(unittest.TestCase):
    def test_sorted_by_name(self):
        d, _ = _mkdir_with(["02-b.md", "01-a.md", "10-c.md"])
        parts = aa.collect_parts(d)
        self.assertEqual(
            [os.path.basename(p) for p in parts],
            ["01-a.md", "02-b.md", "10-c.md"],
        )

    def test_skips_complete_and_dotfiles(self):
        d, _ = _mkdir_with(["01-a.md", "_complete.md", ".hidden"])
        parts = aa.collect_parts(d)
        self.assertEqual([os.path.basename(p) for p in parts], ["01-a.md"])

    def test_empty(self):
        d = tempfile.mkdtemp()
        self.assertEqual(aa.collect_parts(d), [])


class TestDeriveOutput(unittest.TestCase):
    def test_explicit_wins(self):
        self.assertEqual(
            aa.derive_output("/d", ["/d/01.md"], "/x/out.md"), "/x/out.md"
        )

    def test_uniform_ext_inherited(self):
        out = aa.derive_output("/d", ["/d/01-a.md", "/d/02-b.md"], None)
        self.assertEqual(out, os.path.join("/d", "_complete.md"))

    def test_mixed_ext_falls_back_txt(self):
        out = aa.derive_output("/d", ["/d/01-a.md", "/d/02-b.py"], None)
        self.assertEqual(out, os.path.join("/d", "_complete.txt"))


class TestAssemble(unittest.TestCase):
    def test_concat_in_order(self):
        _, paths = _mkdir_with([("01-a.md", "AAA"), ("02-b.md", "BBB")])
        self.assertEqual(aa.assemble(paths, "\n\n", False), "AAA\n\nBBB")

    def test_separator(self):
        _, paths = _mkdir_with([("01.md", "A"), ("02.md", "B")])
        self.assertEqual(aa.assemble(paths, "---", False), "A---B")

    def test_header_from_filename(self):
        _, paths = _mkdir_with([("01-a.md", "A")])
        out = aa.assemble(paths, "\n", True)
        self.assertIn("<!-- 01-a.md -->", out)
        self.assertIn("A", out)


class TestMain(unittest.TestCase):
    def _run_main(self, argv):
        saved = sys.argv
        sys.argv = ["assemble_artifact.py"] + argv
        try:
            aa.main()
        finally:
            sys.argv = saved

    def test_no_parts_exits_generic(self):
        d = tempfile.mkdtemp()
        saved = sys.argv
        sys.argv = ["assemble_artifact.py", "card1", "--parts-dir", d, "--no-attach"]
        try:
            with self.assertRaises(SystemExit) as cm:
                aa.main()
            self.assertEqual(cm.exception.code, aa.EXIT_GENERIC)
        finally:
            sys.argv = saved

    def test_writes_complete_file(self):
        d, _ = _mkdir_with([("01-a.md", "A"), ("02-b.md", "B")])
        self._run_main(["card1", "--parts-dir", d, "--no-attach"])
        out = os.path.join(d, "_complete.md")
        self.assertTrue(os.path.isfile(out))
        with open(out, encoding="utf-8") as f:
            self.assertEqual(f.read(), "A\n\nB")

    def test_rerun_is_idempotent(self):
        # _complete.md from a prior run must not fold back into itself.
        d, _ = _mkdir_with([("01-a.md", "A"), ("02-b.md", "B")])
        self._run_main(["card1", "--parts-dir", d, "--no-attach"])
        self._run_main(["card1", "--parts-dir", d, "--no-attach"])
        with open(os.path.join(d, "_complete.md"), encoding="utf-8") as f:
            self.assertEqual(f.read(), "A\n\nB")


if __name__ == "__main__":
    unittest.main()
