"""Parity test: the migrated reduction must reproduce the superseded record.

`sim/vco-tuning-range` moved from the `sim/lib/simenv.sh` runner + `analyze.py`
pair onto `sim/harness`, which meant re-expressing `analyze.py`'s reduction as
the manifest's `derived` module. The risk that migration carries is a *silent*
one: a reduction that quietly changes a band edge, a margin or a worst-corner
citation would look exactly like a real electrical regression in the new
record, and would be attributed to the tooling instead of investigated.

This test removes that ambiguity without a simulator. It replays the **exact
measured grid** of the record the migration supersedes -- 3528 committed points
in `corners/20260731-175947-0a12e6c/vco_tuning.csv` -- through the new
`derive.py`, and asserts every number the superseded record cites comes back
identical. Any difference in a post-migration run is therefore an electrical
difference, not an arithmetic one.

Runs in the harness unit-test suite (`sim/selftest.sh` stage 1): no PDK, no
ngspice, no network.
"""

from __future__ import annotations

import csv
import importlib.util
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
TESTBENCH = SIM_DIR / "vco-tuning-range" / "testbench"
#: The chain-head record this migration supersedes, and its committed sweep CSV.
SUPERSEDED_RECORD = "20260731-175947-0a12e6c"
SWEEP_CSV = SIM_DIR / "vco-tuning-range" / "corners" / SUPERSEDED_RECORD / "vco_tuning.csv"


def _load_derive():
    spec = importlib.util.spec_from_file_location(
        "_vco_tuning_derive_under_test", TESTBENCH / "derive.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read_sweep(path: Path):
    rows = []
    lines = [line for line in path.read_text().splitlines() if not line.startswith("#")]
    for r in csv.DictReader(lines):
        rows.append(
            {
                "corner": (r["bundle"], float(r["temp_c"]), float(r["vdd_v"])),
                "band": int(r["band"]),
                "vctrl": float(r["vctrl_v"]),
                "f": float(r["fosc_hz"]),
                "i": float(r["isupply_a"]),
            }
        )
    return rows


class VcoTuningReductionParity(unittest.TestCase):
    """Every headline number of record 20260731-175947-0a12e6c, re-derived."""

    @classmethod
    def setUpClass(cls):
        cls.d = _load_derive()
        cls.rows = _read_sweep(SWEEP_CSV)
        cls.r = cls.d.reduce_grid(cls.rows)

    def test_grid_shape(self):
        self.assertEqual(len(self.rows), 3528)
        self.assertEqual(len(self.r["corners"]), 63)
        self.assertEqual(self.r["bands"], [0, 1, 2, 3, 4, 5, 6, 7])

    def test_check1_low_band_floor(self):
        d, r = self.d, self.r
        self.assertEqual(d.mhz(r["floor_worst"]), "6.449")
        self.assertEqual(d.corner_name(r["floor_worst_c"]), "all-fast/125C/2.97V")
        self.assertTrue(r["floor_pass"])

    def test_check2_high_band_ceiling(self):
        d, r = self.d, self.r
        self.assertEqual(d.mhz(r["ceil_worst"]), "247.8")
        self.assertEqual(d.corner_name(r["ceil_worst_c"]), "all-slow/-40C/3.63V")
        self.assertTrue(r["ceil_pass"])

    def test_check3_no_overlap_hole(self):
        d, r = self.d, self.r
        worst = min(r["overlap_worst"].values())
        self.assertEqual("%.3f" % min(x for x, _c in r["overlap_worst"].values()), "1.267")
        self.assertEqual(d.corner_name(worst[1]), "ss/125C/3.63V")
        self.assertTrue(r["overlap_pass"])
        self.assertEqual(r["holes"], [])

    def test_check4a_kvco_at_the_selected_band(self):
        d, r = self.d, self.r
        self.assertEqual(d.mhz(r["k_cfg_max"]), "115.8")
        self.assertEqual(d.corner_name(r["cfg_c"]), "all-fast/27C/2.97V")
        self.assertEqual(d.mhz(r["cfg_ft"]), "200")
        self.assertEqual(r["cfg_b"], 6)
        self.assertEqual("%.2f" % r["cfg_v"], "1.54")
        self.assertTrue(r["kvco_pass"])

    def test_check4b_kvco_at_any_in_band_point_is_the_known_fail(self):
        d, r = self.d, self.r
        self.assertEqual(d.mhz(r["k_in_max"]), "154.3")
        self.assertEqual(d.corner_name(r["k_in_pt"][0]), "all-fast/27C/3.30V")
        self.assertEqual(r["k_in_pt"][1], 7)
        self.assertEqual("%.1f" % r["k_in_pt"][2], "0.9")
        # The superseded record's only FAIL, and it must stay a FAIL: check 4b
        # is the adversarial band choice, reported as a caveat rather than a
        # defect (see the record's "Caveat that must travel with these numbers").
        self.assertFalse(r["kvco_any_pass"])

    def test_check5_monotonicity(self):
        self.assertEqual(self.r["non_monotonic"], [])

    def test_overall_verdict(self):
        self.assertTrue(self.r["overall"])

    def test_band_edge_margins(self):
        r = self.r
        self.assertEqual("%.0f" % (100 * (self.d.F_LO - r["floor_worst"]) / self.d.F_LO), "36")
        self.assertEqual("%.0f" % (100 * (r["ceil_worst"] - self.d.F_HI) / self.d.F_HI), "24")
        self.assertEqual(self.d.mhz(r["floor_best"]), "2.956")
        self.assertEqual(self.d.corner_name(r["floor_best_c"]), "all-slow/-40C/3.63V")
        self.assertEqual(self.d.mhz(r["ceil_best"]), "631.8")
        self.assertEqual(self.d.corner_name(r["ceil_best_c"]), "all-fast/125C/2.97V")

    def test_band_plan_rows(self):
        d, r = self.d, self.r
        expected = {
            0: ("2.956", "6.449", "6.452", "14.45", "2.13", "2.38"),
            3: ("12.72", "29.08", "28.55", "68.69", "2.21", "2.49"),
            7: ("100.6", "274.9", "247.8", "631.8", "2.00", "2.70"),
        }
        for band, want in expected.items():
            fl = [r["per_band"][(c, band)]["flo"] for c in r["corners"]]
            fh = [r["per_band"][(c, band)]["fhi"] for c in r["corners"]]
            rr = [
                r["per_band"][(c, band)]["fhi"] / r["per_band"][(c, band)]["flo"]
                for c in r["corners"]
            ]
            got = (
                d.mhz(min(fl)), d.mhz(max(fl)), d.mhz(min(fh)), d.mhz(max(fh)),
                "%.2f" % min(rr), "%.2f" % max(rr),
            )
            self.assertEqual(got, want, f"band plan row B{band}")

    def test_adjacent_band_overlap_rows(self):
        d, r = self.d, self.r
        expected = {
            0: ("1.317", "ss/125C/3.63V"),
            4: ("1.356", "ss/125C/3.63V"),
            5: ("1.336", "sf/-40C/3.63V"),
            6: ("1.321", "ss/125C/2.97V"),
        }
        for band, (ratio, corner) in expected.items():
            got_ratio, got_corner = r["overlap_worst"][band]
            self.assertEqual("%.3f" % got_ratio, ratio, f"overlap B{band}")
            self.assertEqual(d.corner_name(got_corner), corner, f"overlap B{band}")

    def test_kvco_summary_rows(self):
        d, r = self.d, self.r
        expected = {
            0: ("1.722", "4.702", "0.71"),
            5: ("21.42", "81.52", "0.78"),
            7: ("67.32", "205.9", "0.84"),
        }
        for band, want in expected.items():
            kmins = [r["per_band"][(c, band)]["kmin"] for c in r["corners"]]
            kmaxs = [r["per_band"][(c, band)]["kmax"] for c in r["corners"]]
            rat = [r["per_band"][(c, band)]["ratio_max"] for c in r["corners"]]
            got = (d.mhz(min(kmins)), d.mhz(max(kmaxs)), "%.2f" % max(rat))
            self.assertEqual(got, want, f"kvco summary B{band}")

    def test_worst_case_kvco_anywhere(self):
        d, r = self.d, self.r
        self.assertEqual(d.mhz(r["k_all_max"]), "205.9")
        self.assertEqual(d.corner_name(r["k_all_pt"][0]), "all-fast/125C/2.97V")
        self.assertEqual(r["k_all_pt"][1], 7)
        self.assertEqual(d.mhz(r["k_all_pt"][3]), "396.8")
        self.assertEqual("%.2f .. %.2f" % (r["ratio_in_min"], r["ratio_in_max"]),
                         "0.31 .. 0.84")
        self.assertEqual(d.mhz(r["k_in_min"]), "3.182")

    def test_supply_pushing(self):
        d, r = self.d, self.r
        push = r["push"]
        self.assertEqual(len(push), 1176)
        worst, best = push[-1], push[0]
        self.assertEqual(d.mhz(worst[1]), "-52.31")
        self.assertEqual("%.1f" % (100 * worst[0]), "55.3")
        self.assertEqual((worst[2], worst[3], worst[4], worst[5]), ("ss", -40.0, 5, 2.1))
        self.assertEqual(d.mhz(worst[6]), "94.65")
        self.assertEqual(d.mhz(best[1]), "-0.76")
        self.assertEqual("%.1f" % (100 * best[0]), "20.4")
        self.assertEqual((best[2], best[3], best[4], best[5]), ("ff", -40.0, 0, 0.9))
        self.assertEqual("%.1f" % (100 * push[len(push) // 2][0]), "39.1")

    def test_block_current(self):
        for grp, n, want in ((self.r["p10"], 179, ("39", "76", "146")),
                             (self.r["p200"], 149, ("217", "328", "480"))):
            cur = sorted(p[6] for p in grp)
            self.assertEqual(len(cur), n)
            got = ("%.0f" % (cur[0] * 1e6),
                   "%.0f" % (cur[len(cur) // 2] * 1e6),
                   "%.0f" % (cur[-1] * 1e6))
            self.assertEqual(got, want)

    def test_derive_point_matches_the_grid_reduction(self):
        """The per-point columns must equal what reduce_grid computes per curve."""
        d, r = self.d, self.r
        curve_key = (("typical", 27.0, 3.30), 4)
        curve = r["curves"][curve_key]

        class _P:
            params = {"band": "4"}

            def get(self, name, default=None):
                idx = int(name[1:]) - 1
                return curve[idx][1] if name.startswith("f") else default

        got = d.derive_point(_P())
        want = r["per_band"][curve_key]
        self.assertAlmostEqual(got["kvco_min"], want["kmin"], places=6)
        self.assertAlmostEqual(got["kvco_max"], want["kmax"], places=6)
        self.assertAlmostEqual(got["kvco_mean"], want["kmean"], places=6)
        self.assertAlmostEqual(got["kvco_over_f_max"], want["ratio_max"], places=9)
        self.assertAlmostEqual(got["fine_ratio"], want["fhi"] / want["flo"], places=9)
        self.assertEqual(len([k for k in got if k.startswith("k") and k[1:].isdigit()]), 7)


if __name__ == "__main__":
    unittest.main()
