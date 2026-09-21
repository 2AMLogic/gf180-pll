#!/usr/bin/env python3
"""Every committed block GDS still comes out of its own generator (issue #451).

This is the check that was missing when `lock_detector`'s committed GDS drifted
seven commits away from its generator while every other check in the repository
stayed green -- see ``layout/harness/reproduce.py``'s module docstring for the
full account. `layout/run_pv.py` runs a deck against whatever file it is
handed; `layout/lib/check-layout-status-claims.sh` grades prose against the
*recorded* verdict. Neither re-derives the artifact, so nothing noticed.

Three things are asserted here, and all three are load-bearing:

1. **Every registered block reproduces.** Rebuild it, XOR it layer by layer
   against the committed file, require an empty difference.
2. **The comparator can actually see a difference** -- the negative control.
   A check only ever shown reporting clean is not evidence it can report
   dirty (``layout/harness/faults.py``'s own discipline, applied here to the
   reproducibility check rather than to the DRC deck): a *deliberately stale*
   committed GDS, built by mutating one real artifact by a single 0.1 um box,
   must be reported as drift. Without this, ``layer_differences()`` returning
   ``{}`` unconditionally would pass test 1 for every block forever.
3. **The registry covers the evidence tree.** Every ``*.gds`` under
   ``layout/evidence/`` is either registered or explicitly excluded with a
   reason, so an unchecked artifact cannot appear by omission -- which is how
   a "the guard exists" claim quietly becomes untrue.

    python3 -m unittest discover -s layout/tests -t layout/tests -v
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

LAYOUT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAYOUT_DIR))

try:
    import klayout.db as db

    _HAVE_KLAYOUT = True
except ImportError:
    _HAVE_KLAYOUT = False

from harness import reproduce  # noqa: E402


@unittest.skipUnless(_HAVE_KLAYOUT, "needs the klayout pip wheel (klayout.db)")
class CommittedArtifactsReproduceTests(unittest.TestCase):
    """The claim: every committed block GDS is its generator's current output."""

    def test_every_block_reproduces_from_its_generator(self):
        drifted = {}
        for block in reproduce.BLOCKS:
            with self.subTest(block=block.gds):
                self.assertTrue(block.committed.is_file(), f"{block.gds} is registered but not committed")
                with tempfile.TemporaryDirectory() as tmp:
                    rebuilt = reproduce.rebuild(block, Path(tmp))
                    diffs = reproduce.layer_differences(block.committed, rebuilt)
                if diffs:
                    drifted[block.gds] = diffs
                self.assertEqual(
                    diffs,
                    {},
                    f"{block.gds} no longer reproduces from {block.module}: "
                    + ", ".join(f"layer {ly}/{dt} differs by {a:.3f} um^2" for (ly, dt), a in diffs.items())
                    + " -- regenerate the artifact (and its deck output) or fix the generator; "
                    "a DRC/LVS claim on a file the generator no longer produces is a claim about nothing",
                )
        self.assertEqual(drifted, {})


@unittest.skipUnless(_HAVE_KLAYOUT, "needs the klayout pip wheel (klayout.db)")
class NegativeControlTests(unittest.TestCase):
    """The check must fail on a stale artifact, or test 1 above proves nothing."""

    #: The block used as the control's raw material. Any registered block
    #: would do; this one is the artifact issue #451 was opened about.
    CONTROL = next(b for b in reproduce.BLOCKS if b.name == "lock_detector.gds")

    @staticmethod
    def _stale_copy(src: Path, dst: Path) -> Path:
        """``src`` with one extra 0.1 x 0.1 um Metal1 box -- a 'stale' artifact.

        Deliberately tiny and far outside the block, so the mutation models
        only "this file is not what the generator emits" and cannot be
        mistaken for a plausible layout edit.
        """
        layout = db.Layout()
        layout.read(str(src))
        top = next(iter(layout.top_cells()))
        index = layout.layer(34, 0)  # Metal1 drawing
        dbu_per_um = int(round(1.0 / layout.dbu))
        origin = int(round(-1000 * dbu_per_um))
        top.shapes(index).insert(
            db.Box(origin, origin, origin + dbu_per_um // 10, origin + dbu_per_um // 10)
        )
        options = db.SaveLayoutOptions()
        options.select_cell(top.cell_index())
        options.format = "GDS2"
        layout.write(str(dst), options)
        return dst

    def test_a_stale_committed_gds_is_reported_as_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            rebuilt = reproduce.rebuild(self.CONTROL, tmp / "fresh")
            stale = self._stale_copy(rebuilt, tmp / "stale.gds")

            self.assertEqual(
                reproduce.layer_differences(self.CONTROL.committed, rebuilt),
                {},
                "positive control: the unmutated pair must compare equal",
            )
            diffs = reproduce.layer_differences(stale, rebuilt)
            self.assertIn((34, 0), diffs, "negative control came back clean -- the comparator is not a gate")
            self.assertAlmostEqual(diffs[(34, 0)], 0.01, places=6)

    def test_a_generator_that_does_not_run_is_a_failure_not_a_pass(self):
        """A rebuild that cannot happen must raise, never silently compare equal."""
        broken = reproduce.Block(self.CONTROL.gds, "pll_top.lock_detector.no_such_module")
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError):
                reproduce.rebuild(broken, Path(tmp))


class RegistryCoversTheEvidenceTreeTests(unittest.TestCase):
    """No committed GDS may be silently unchecked. Needs no KLayout."""

    def test_every_committed_gds_is_registered_or_excluded(self):
        registered = {b.gds for b in reproduce.BLOCKS}
        found = set(reproduce.committed_gds_files())
        unaccounted = found - registered - set(reproduce.EXCLUDED)
        self.assertEqual(
            unaccounted,
            set(),
            "committed GDS with no generator registered and no stated exclusion -- "
            "add it to harness/reproduce.py's BLOCKS, or to EXCLUDED with a reason",
        )

    def test_no_registration_or_exclusion_is_stale(self):
        found = set(reproduce.committed_gds_files())
        self.assertEqual({b.gds for b in reproduce.BLOCKS} - found, set(), "registered block GDS no longer exists")
        self.assertEqual(set(reproduce.EXCLUDED) - found, set(), "excluded GDS no longer exists")

    def test_every_exclusion_states_a_reason(self):
        for path, why in reproduce.EXCLUDED.items():
            with self.subTest(path=path):
                self.assertGreater(len(why.strip()), 20, "an exclusion without a real reason is an unchecked artifact")

    def test_registry_has_no_duplicate_entries(self):
        paths = [b.gds for b in reproduce.BLOCKS]
        self.assertEqual(len(paths), len(set(paths)))
        self.assertEqual(set(paths) & set(reproduce.EXCLUDED), set(), "a block cannot be both registered and excluded")


if __name__ == "__main__":
    unittest.main()
