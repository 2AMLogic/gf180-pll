"""`sim/period-jitter/testbench/tb.json`'s 45-point PVT grid, against committed evidence.

This campaign releases every PVT point at *its own* predicted lock point (see
`sim/period-jitter/testbench/vstart_from_vco_record.py`), so the manifest carries
45 hand-checkable numbers that came out of another record. Three things can rot
there, none of which any simulator run would notice — it would just silently
measure a loop released at the wrong voltage:

- a `vstart` drifting away from what the committed VCO record actually says,
- a point id (`vs1p795`) drifting away from the voltage it names,
- the union of the grid blocks quietly ceasing to be the mandated PVT matrix.

Plus one cross-campaign invariant worth pinning: `sim/reference-spur` measures
the *same* ripple at the *same* operating point in the frequency domain, and
this campaign's numbers are only comparable with its corner-for-corner if the
two manifests agree about where each of those corners locks.

Runs in the harness unit-test suite: no PDK, no ngspice, no network — it reads
committed CSV and committed JSON only.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
TESTBENCH = SIM_DIR / "period-jitter" / "testbench"
REF_SPUR_TB = SIM_DIR / "reference-spur" / "testbench" / "tb.json"

sys.path.insert(0, str(SIM_DIR))
from harness.derived import load_module  # noqa: E402

#: The mandated matrix: `sim/harness/corners.py`'s `CORNER_SETS["mos"]` x the
#: three temperatures x the three supplies.
MOS_BUNDLES = {"typical", "ff", "ss", "fs", "sf"}
TEMPERATURES = {-40.0, 27.0, 125.0}
SUPPLY_ALIASES = {"low", "nom", "high"}


def _manifest():
    return json.loads((TESTBENCH / "tb.json").read_text())


class PeriodJitterGrid(unittest.TestCase):
    """The manifest's own shape: is the declared grid the mandated matrix?"""

    @classmethod
    def setUpClass(cls):
        cls.manifest = _manifest()
        cls.blocks = cls.manifest["grid"]
        cls.points = cls.manifest["sweeps"]["vs"]["points"]

    def test_grid_union_is_exactly_the_mandated_pvt_matrix(self):
        seen = []
        for block in self.blocks:
            for corner in block["corners"]:
                for temp in block["temperatures_c"]:
                    for supply in block["supplies"]:
                        seen.append((corner, float(temp), supply))
        self.assertEqual(len(seen), len(set(seen)), "a PVT point is declared twice")
        expected = {
            (corner, temp, supply)
            for corner in MOS_BUNDLES
            for temp in TEMPERATURES
            for supply in SUPPLY_ALIASES
        }
        self.assertEqual(set(seen), expected)
        self.assertEqual(len(seen), 45)

    def test_every_block_carries_a_description_and_exactly_one_release_voltage(self):
        for block in self.blocks:
            self.assertTrue(block.get("description", "").strip(), block)
            self.assertEqual(len(block["axes"]["vs"]), 1, block)
            self.assertIn(block["axes"]["vs"][0], self.points, block)

    def test_point_id_spells_its_own_release_voltage(self):
        # `vs1p795` must name 1.795 V. A hand-edit that changes one without the
        # other produces a manifest that reads correctly and simulates wrongly.
        for point_id, spec in self.points.items():
            self.assertTrue(point_id.startswith("vs"), point_id)
            self.assertEqual(
                point_id, "vs" + spec["params"]["vstart"].replace(".", "p"), point_id
            )

    def test_no_fixed_vstart_shadows_the_axis(self):
        # A leftover `params.vstart` is emitted before the axis point's own, so
        # it would not change the deck -- but it would make the manifest read as
        # though every corner were released at one voltage.
        self.assertNotIn("vstart", self.manifest["params"])

    def test_pvt_axes_are_the_full_default_grid(self):
        self.assertEqual(self.manifest["corners"], ["mos"])
        self.assertEqual(set(self.manifest["temperatures_c"]), {-40, 27, 125})
        self.assertEqual(self.manifest["supply_tolerance"], 0.1)


class VstartAgainstCommittedEvidence(unittest.TestCase):
    """Every declared release voltage, re-derived from the VCO record itself."""

    TOL_V = 5e-3  # the millivolt rounding tb.json carries

    @classmethod
    def setUpClass(cls):
        cls.vstart = load_module(TESTBENCH / "vstart_from_vco_record.py")
        cls.manifest = _manifest()

    def test_check_mode_passes_against_the_committed_vco_record(self):
        rows, target = self.vstart.derive_table(self.manifest, band=6)
        self.assertEqual(len(rows), 45)
        self.assertAlmostEqual(target, 150e6, delta=1.0)
        declared = self.vstart.declared_map(self.manifest)
        for corner, temp, _vdd, alias, derived in rows:
            self.assertIsNotNone(
                derived, "150 MHz is unreachable in band 6 at %s/%g C" % (corner, temp)
            )
            got = declared.get((corner, temp, alias))
            self.assertIsNotNone(got, "tb.json declares no vstart for %s/%g C/%s"
                                 % (corner, temp, alias))
            self.assertLess(
                abs(got - derived), self.TOL_V,
                "%s/%g C/%s: tb.json says %.4f V, the VCO record says %.4f V"
                % (corner, temp, alias, got, derived),
            )

    def test_emit_reproduces_the_committed_manifest_fragment(self):
        # `--emit` is what generated the manifest; if it no longer reproduces it,
        # the manifest has been hand-edited away from its own generator.
        rows, target = self.vstart.derive_table(self.manifest, band=6)
        emitted = self.vstart.emit(self.manifest, rows, 6, target)
        self.assertEqual(emitted["sweeps"]["vs"]["points"],
                         self.manifest["sweeps"]["vs"]["points"])
        self.assertEqual(emitted["grid"], self.manifest["grid"])


class AgreesWithReferenceSpur(unittest.TestCase):
    """The two campaigns measure the same ripple; they must agree on where it locks."""

    @classmethod
    def setUpClass(cls):
        cls.manifest = _manifest()
        cls.ref = json.loads(REF_SPUR_TB.read_text())

    def test_same_operating_point(self):
        for key in ("fref", "nratio", "b0_code", "b1_code", "b2_code",
                    "cpb0_code", "cpb1_code",
                    "sel0_code", "sel1_code", "sel2_code",
                    "sel3_code", "sel4_code", "sel5_code",
                    "p0_code", "p1_code", "p2_code", "p3_code", "p4_code", "p5_code"):
            self.assertEqual(self.manifest["params"][key], self.ref["params"][key], key)

    def test_reference_spur_release_voltages_are_a_subset_of_this_grid(self):
        # sim/reference-spur runs five hand-picked corners; this manifest covers
        # all 45. Same operating point + same corner => same release voltage, so
        # its five point ids must appear verbatim here.
        mine = self.manifest["sweeps"]["vs"]["points"]
        for point_id, spec in self.ref["sweeps"]["vs"]["points"].items():
            self.assertIn(point_id, mine,
                          "reference-spur releases at %s; this grid has no such point"
                          % point_id)
            self.assertEqual(mine[point_id]["params"]["vstart"],
                             spec["params"]["vstart"], point_id)


if __name__ == "__main__":
    unittest.main()
