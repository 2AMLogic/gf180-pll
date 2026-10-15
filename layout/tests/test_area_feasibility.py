#!/usr/bin/env python3
"""Unit tests for ``layout/harness/area_feasibility.py`` (issue #792).

The sweep's numbers are only as good as its two mechanisms: the fold probe must
produce the outline it claims, and a lever applied for one case must not leak
into the next (the committed build reads the same module constants).

    python3 -m unittest discover -s layout/tests -t layout/tests -v
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _env import HAVE_KLAYOUT

if HAVE_KLAYOUT:
    import klayout.db as db

    from harness import area_feasibility as af  # noqa: E402
    from pll_top.top_level import assemble as asm_mod  # noqa: E402
    from pll_top.top_level import netcheck  # noqa: E402


@unittest.skipUnless(HAVE_KLAYOUT, "klayout Python wheel not installed")
class FoldProbe(unittest.TestCase):
    def test_fold_outline_and_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, dst = Path(tmp, "in.gds"), Path(tmp, "out.gds")
            ly = db.Layout()
            ly.dbu = 0.001
            top = ly.create_cell("blk")
            li = ly.layer(30, 0)
            top.shapes(li).insert(db.Box(0, 0, 90_000, 10_000))  # 90 x 10 um
            top.shapes(li).insert(db.Text("P", db.Trans(db.Vector(80_000, 5_000))))
            ly.write(str(src))
            w, h = af.fold_gds(src, dst, 3)
            self.assertAlmostEqual(w, 30.0)
            self.assertAlmostEqual(h, 3 * 10.0 + 2 * af.FOLD_GAP_UM)
            out = db.Layout()
            out.read(str(dst))
            cell = out.top_cell()
            idx = out.find_layer(30, 0)
            region = db.Region(cell.begin_shapes_rec(idx)).merged()
            # the three slabs keep the drawn area and sit in three disjoint bands
            self.assertEqual(region.area(), 90_000 * 10_000)
            self.assertEqual(region.count(), 3)
            bb = cell.bbox()
            self.assertEqual((bb.width(), bb.height()), (30_000, 3 * 10_000 + 2 * 3_000))
            texts = [s.text for s in cell.shapes(idx).each() if s.is_text()]
            self.assertEqual(len(texts), 1)
            self.assertEqual((texts[0].x, texts[0].y), (80_000 - 2 * 30_000, 5_000 + 2 * (10_000 + 3_000)))


@unittest.skipUnless(HAVE_KLAYOUT, "klayout Python wheel not installed")
class LeverScope(unittest.TestCase):
    def test_levers_apply_and_restore(self):
        before = (asm_mod.DOMAIN_SPACING_UM, asm_mod.VCO_GUARD_MARGIN_UM, netcheck.VCO_GUARD_MARGIN_UM)
        case = af.Case("t", spacing=1.0, guard=2.0, gaps=(("divider_chain", 12.0),))
        with af._levers(case):
            self.assertEqual(asm_mod.DOMAIN_SPACING_UM, 1.0)
            self.assertEqual(asm_mod.VCO_GUARD_MARGIN_UM, 2.0)
            self.assertEqual(netcheck.VCO_GUARD_MARGIN_UM, 2.0)
            self.assertEqual(asm_mod.GAP_OVERRIDES_UM, {"divider_chain": 12.0})
        self.assertEqual((asm_mod.DOMAIN_SPACING_UM, asm_mod.VCO_GUARD_MARGIN_UM, netcheck.VCO_GUARD_MARGIN_UM), before)
        self.assertEqual(asm_mod.GAP_OVERRIDES_UM, {})
        self.assertEqual(before, (40.0, 15.0, 15.0))

    def test_baseline_case_is_the_committed_constants(self):
        self.assertTrue(af.Case("baseline").is_baseline)
        self.assertFalse(af.Case("x", guard=0).is_baseline)


if __name__ == "__main__":
    unittest.main()
