"""Parity test: the migrated stage-count reduction must reproduce its record.

The companion of `test_vco_tuning_derive.py`, for `sim/vco-tuning-range`'s
stage-count sub-campaign. It replays the **exact measured grid** of the record
the migration supersedes -- the 144 committed measurements in
`corners/20260731-180254-0a12e6c/stage_count.csv`, 48 (corner, band, Vctrl)
points x 3 stage counts -- through the new `derive_stages.py`, and asserts
every number the superseded record cites comes back identical.

That separates the two things a migrated record can differ by: this test pins
the *arithmetic*, so any difference a post-migration run shows is the
*simulation*, and has to be explained as such.

Runs in the harness unit-test suite (`sim/selftest.sh` stage 1): no PDK, no
ngspice, no network.
"""

from __future__ import annotations

import csv
import sys
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
TESTBENCH = SIM_DIR / "vco-tuning-range" / "testbench-stages"
SUPERSEDED_RECORD = "20260731-180254-0a12e6c"
STAGE_CSV = SIM_DIR / "vco-tuning-range" / "corners" / SUPERSEDED_RECORD / "stage_count.csv"

sys.path.insert(0, str(SIM_DIR))
from harness.derived import PointView, RunView, load_module  # noqa: E402


def _load_derive():
    return load_module(TESTBENCH / "derive_stages.py")


def _run_view_from_csv(derive, path: Path) -> RunView:
    """Rebuild the harness's per-point view from the pre-migration CSV.

    The pre-migration runner wrote one row per (corner, band, Vctrl, stage
    count) with `fosc_hz = 0` for a ring that did not start; the harness's
    shape is one *point* per (corner, band, Vctrl) carrying that point's three
    rings as separate measurements, with a non-starting ring recorded as an
    absent (`optional`) measurement rather than a zero. This translates the
    former into the latter, which is exactly the shape change the migration
    makes.
    """
    lines = [line for line in path.read_text().splitlines() if not line.startswith("#")]
    grouped: dict[tuple, dict] = {}
    for r in csv.DictReader(lines):
        key = (r["bundle"], float(r["temp_c"]), float(r["vdd_v"]),
               int(r["band"]), float(r["vctrl_v"]))
        entry = grouped.setdefault(key, {})
        n = int(r["nstage"])
        f = float(r["fosc_hz"])
        if f > 0:  # a zero is "did not oscillate" -> no measurement at all
            entry["f%d" % n] = f
        entry["i%d" % n] = float(r["isupply_a"])
        entry["s%dhi" % n] = float(r["swing_hi_v"])
        entry["s%dlo" % n] = float(r["swing_lo_v"])

    points = []
    for (bundle, temp_c, vdd, band, vctrl), meas in grouped.items():
        view = PointView(
            corner=bundle,
            corner_id="%s_%gc_%.2fv_band%d_vc%g" % (bundle, temp_c, vdd, band, vctrl),
            temp_c=temp_c,
            vdd=vdd,
            axes={"band": "band%d" % band, "vc": "vc%g" % vctrl},
            params={"band": str(band), "vctrl": str(vctrl)},
            measurements=meas,
        )
        # derive_point() runs before derive_tables() in a real run; replay that
        # order so the derived columns are present for the reduction.
        meas.update(derive.derive_point(view))
        points.append(view)
    return RunView(experiment="vco-tuning-range",
                   measure_names=(), points=tuple(points))


class VcoStageCountReductionParity(unittest.TestCase):
    """Every table of record 20260731-180254-0a12e6c, re-derived."""

    @classmethod
    def setUpClass(cls):
        cls.d = _load_derive()
        cls.view = _run_view_from_csv(cls.d, STAGE_CSV)
        cls.tables = {t.name: t for t in cls.d.derive_tables(cls.view)}

    def test_grid_shape(self):
        self.assertEqual(len(self.view.points), 48)

    def test_startup_table(self):
        self.assertEqual(
            self.tables["startup"].rows,
            (("3", "2.00", "1 of 48", "**DISQUALIFIED**"),
             ("5", "1.24", "0 of 48", "oscillates everywhere"),
             ("7", "1.11", "0 of 48", "oscillates everywhere")),
        )
        notes = "\n".join(self.tables["startup"].notes)
        self.assertIn("all-fast B7 @ 0.9 V", notes)

    def test_band_edges_table(self):
        self.assertEqual(
            self.tables["band_edges"].rows,
            (("3", "550.2 MHz", "PASS (+175 %)", "11.41 MHz", "**FAIL** (+14 %)"),
             ("5", "256.6 MHz", "PASS (+28 %)", "6.633 MHz", "PASS (-34 %)"),
             ("7", "182.5 MHz", "**FAIL** (-9 %)", "4.739 MHz", "PASS (-53 %)")),
        )

    def test_energy_table(self):
        self.assertEqual(
            self.tables["energy_at_100mhz"].rows,
            (("3", "B5 @ 0.9 V", "93.8 MHz", "104 uA", "3.65 pJ"),
             ("5", "B6 @ 0.9 V", "90.4 MHz", "146 uA", "5.31 pJ"),
             ("7", "B5 @ 2.7 V", "91.79 MHz", "212 uA", "7.62 pJ")),
        )
        self.assertIn("3 stages 0.69x, 5 stages 1.00x, 7 stages 1.43x",
                      "\n".join(self.tables["energy_at_100mhz"].notes))

    def test_worst_swing_table(self):
        rows = self.tables["worst_swing"].rows
        self.assertEqual([r[1] for r in rows], ["0.680", "1.006", "1.006"])
        self.assertEqual(rows[0][2], "all-fast, B6, Vctrl 2.7 V")

    def test_conclusion_table(self):
        self.assertEqual(
            self.tables["stage_count_verdict"].rows,
            (("3", "**no**", "yes", "**no**", "3.65 pJ", "0.680", "**rejected**"),
             ("5", "yes", "yes", "yes", "5.31 pJ", "1.006", "viable"),
             ("7", "yes", "**no**", "yes", "7.62 pJ", "1.006", "**rejected**")),
        )
        notes = "\n".join(self.tables["stage_count_verdict"].notes)
        self.assertIn("**5 stages is confirmed**", notes)
        self.assertIn("9 % short of the 200 MHz v1 ceiling", notes)
        self.assertIn("14 % above the 10 MHz bottom of the band", notes)
        self.assertIn("This **confirms** rather than revises DR-001 Decision 2", notes)

    def test_a_non_starting_ring_is_absent_not_zero(self):
        """The `fosc_hz = 0` convention becomes an absent optional measurement."""
        dead = [p for p in self.view.points if p.get("f3") is None]
        self.assertEqual(len(dead), 1)
        self.assertEqual(dead[0].corner, "all-fast")
        self.assertEqual(dead[0].params["band"], "7")
        # ... and it costs the point none of its other measurements.
        self.assertIsNotNone(dead[0].get("f5"))
        self.assertIsNotNone(dead[0].get("i3"))


if __name__ == "__main__":
    unittest.main()
