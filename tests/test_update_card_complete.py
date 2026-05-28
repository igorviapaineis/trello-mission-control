"""Migration: parse_existing accepts legacy PT-BR headers and EN ones equally."""

import unittest

from _helpers import SCRIPTS  # noqa: F401
import update_card_complete as ucc


PT_DESC = """## Objetivo
fix login

## Resultado
done

## Mudanças
- a.ts:1 — x

## Métricas
- Tempo: 10min

## Notas
quirky
"""

EN_DESC = """## Goal
fix login

## Result
done

## Changes
- a.ts:1 — x

## Metrics
- Tempo: 10min

## Notes
quirky
"""


class TestParseExisting(unittest.TestCase):
    def test_pt_legacy_parsed(self):
        s = ucc.parse_existing(PT_DESC)
        self.assertEqual(s["Goal"], "fix login")
        self.assertEqual(s["Result"], "done")
        self.assertIn("a.ts:1", s["Changes"])
        self.assertIn("10min", s["Metrics"])
        self.assertEqual(s["Notes"], "quirky")

    def test_en_parsed(self):
        s = ucc.parse_existing(EN_DESC)
        self.assertEqual(s["Goal"], "fix login")
        self.assertEqual(s["Result"], "done")

    def test_render_emits_en(self):
        s = ucc.parse_existing(PT_DESC)
        out = ucc.render(s, {})
        self.assertIn("## Goal", out)
        self.assertIn("## Result", out)
        self.assertIn("## Changes", out)
        self.assertIn("## Metrics", out)
        self.assertIn("## Notes", out)
        self.assertNotIn("## Objetivo", out)
        self.assertNotIn("## Mudanças", out)


if __name__ == "__main__":
    unittest.main()
