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

It does that twice, over two entry points, because they fail differently:

- `VcoTuningReductionParity` calls `reduce_grid()` on the flat rows read
  straight out of the CSV. That pins the *arithmetic*.
- `VcoTuningDerivedTableParity` rebuilds the harness's own `RunView` /
  `PointView` from the same CSV and goes in the way a real run does --
  `derive_point()` per point, then `derive_tables(run)`, which internally calls
  `rows_from_run()` -> `reduce_grid()`. That pins the *record*: the seven
  tables' columns, rows and notes, verbatim as the superseded record prints
  them. A reduction that computes every number correctly and then puts them in
  the wrong column, cites the wrong corner or drops a note is a corrupted
  record, and only the second path sees it.

Runs in the harness unit-test suite (`sim/selftest.sh` stage 1): no PDK, no
ngspice, no network.
"""

from __future__ import annotations

import csv
import importlib.util
import sys
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
TESTBENCH = SIM_DIR / "vco-tuning-range" / "testbench"
#: The chain-head record this migration supersedes, and its committed sweep CSV.
SUPERSEDED_RECORD = "20260731-175947-0a12e6c"
SWEEP_CSV = SIM_DIR / "vco-tuning-range" / "corners" / SUPERSEDED_RECORD / "vco_tuning.csv"

sys.path.insert(0, str(SIM_DIR))
from harness.derived import PointView, RunView  # noqa: E402


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


def _run_view_from_csv(derive, path: Path) -> RunView:
    """Rebuild the harness's per-point view from the pre-migration CSV.

    The pre-migration runner wrote one row per (corner, band, Vctrl); the
    harness's shape is one *point* per (corner, band) carrying that point's
    seven control voltages as separate measurements -- `f1..f7` / `i1..i7`,
    indexed by position in `derive.VCTRLS`, which is exactly what
    `rows_from_run()` unpacks back into flat rows. Translating the former into
    the latter is the shape change the migration makes, so going in through
    here exercises `rows_from_run()` rather than bypassing it.
    """
    lines = [line for line in path.read_text().splitlines() if not line.startswith("#")]
    index = {v: i for i, v in enumerate(derive.VCTRLS, start=1)}
    grouped: dict[tuple, dict] = {}
    for r in csv.DictReader(lines):
        key = (r["bundle"], float(r["temp_c"]), float(r["vdd_v"]), int(r["band"]))
        n = index[float(r["vctrl_v"])]
        entry = grouped.setdefault(key, {})
        entry["f%d" % n] = float(r["fosc_hz"])
        entry["i%d" % n] = float(r["isupply_a"])

    points = []
    for (bundle, temp_c, vdd, band), meas in grouped.items():
        view = PointView(
            corner=bundle,
            corner_id="%s_%gc_%.2fv_band%d" % (bundle, temp_c, vdd, band),
            temp_c=temp_c,
            vdd=vdd,
            axes={"band": "band%d" % band},
            params={"band": str(band)},
            measurements=meas,
        )
        # derive_point() runs before derive_tables() in a real run; replay that
        # order so the derived columns are present for the reduction.
        meas.update(derive.derive_point(view))
        points.append(view)
    return RunView(experiment="vco-tuning-range",
                   measure_names=(), points=tuple(points))


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


class VcoTuningDerivedTableParity(unittest.TestCase):
    """The same grid, in through the harness hooks the record is minted from.

    `VcoTuningReductionParity` above stops at `reduce_grid()`'s dict, so it
    cannot see what the record actually prints. This class goes the whole way a
    run does -- `derive_point()` per point, then `derive_tables(run)`, which
    calls `rows_from_run()` itself -- and pins every one of the seven tables'
    columns, rows and notes against record 20260731-175947-0a12e6c's own
    Markdown. Numbers that are individually right but land in the wrong column,
    cite the wrong corner, or lose a note are a corrupted record, and this is
    what catches them.
    """

    @classmethod
    def setUpClass(cls):
        cls.d = _load_derive()
        cls.view = _run_view_from_csv(cls.d, SWEEP_CSV)
        cls.table_list = cls.d.derive_tables(cls.view)
        cls.tables = {t.name: t for t in cls.table_list}

    def test_grid_shape(self):
        """63 corners x 8 bands, each carrying its seven control voltages."""
        self.assertEqual(len(self.view.points), 504)
        for p in self.view.points:
            for n in range(1, 8):
                self.assertIsNotNone(p.get("f%d" % n), p.corner_id)
                self.assertIsNotNone(p.get("i%d" % n), p.corner_id)
        # derive_point() ran first, as it does in a real run.
        self.assertIsNotNone(self.view.points[0].get("kvco_max"))

    def test_rows_from_run_reproduces_the_flat_sweep(self):
        """`rows_from_run()` must hand `reduce_grid()` back the CSV, row for row."""
        def key(row):
            return (row["corner"], row["band"], row["vctrl"])

        self.assertEqual(sorted(self.d.rows_from_run(self.view), key=key),
                         sorted(_read_sweep(SWEEP_CSV), key=key))

    def test_table_set_and_order(self):
        self.assertEqual(
            [t.name for t in self.table_list],
            ["acceptance_checks", "band_edge_margin", "band_plan", "band_overlap",
             "kvco_summary", "supply_pushing", "block_current"],
        )

    def test_acceptance_checks_table(self):
        t = self.tables["acceptance_checks"]
        self.assertEqual(
            t.columns, ("#", "check", "binding corner", "measured", "spec line", "verdict"))
        self.assertEqual(
            t.rows,
            (("1",
              "Lowest band (B0) reaches DOWN to 10 MHz at **every** corner",
              "all-fast/125C/2.97V", "6.449 MHz floor", "<= 10 MHz", "**PASS**"),
             ("2",
              "Highest band (B7) reaches UP to 200 MHz at **every** corner",
              "all-slow/-40C/3.63V", "247.8 MHz ceiling", ">= 200 MHz", "**PASS**"),
             ("3",
              "No band-overlap hole inside 10-200 MHz at any corner",
              "ss/125C/3.63V", "worst adjacent overlap ratio 1.267", ">= 1.000",
              "**PASS**"),
             ("4a",
              "Kvco under the fixed-filter ceiling at the band a correct "
              "configuration selects",
              "all-fast/27C/2.97V, target 200 MHz -> B6 @ 1.54 V", "115.8 MHz/V",
              "<= 150 MHz/V", "**PASS**"),
             ("4b",
              "Kvco under the ceiling at *every* in-band operating point, including "
              "bands a correct configuration would not select",
              "all-fast/27C/3.30V B7 @ 0.9 V", "154.3 MHz/V", "<= 150 MHz/V",
              "**FAIL**"),
             ("5",
              "f(Vctrl) monotonic on every (corner, band) curve",
              "n/a", "0 non-monotonic curves", "0", "**PASS**")),
        )

    def test_acceptance_checks_notes(self):
        notes = self.tables["acceptance_checks"].notes
        self.assertEqual(notes[0], "**Overall: PASS.**")
        self.assertIn("of the 63 corners on the grid -- reaching below 10 MHz at the", notes)
        # The record's only FAIL travels with the numbers as a caveat (check 4b).
        self.assertIn("**Caveat that must travel with these numbers (check 4b).** Kvco", notes)
        self.assertIn("reaches 154.3 MHz/V at an in-band operating point in band B7, which",
                      notes)
        # ... and the two hand-offs #11 and #9/#10 read out of this record.
        self.assertIn("    lowest band reaches 6.449 MHz at the fastest corner, 36 % below the",
                      notes)
        self.assertIn("    number. Within the v1 band Kvco spans 3.182 .. 154.3 MHz/V across "
                      "bands and", notes)

    def test_band_edge_margin_table(self):
        t = self.tables["band_edge_margin"]
        self.assertEqual(
            t.columns, ("edge", "worst corner", "best corner", "spec", "worst-case margin"))
        self.assertEqual(
            t.rows,
            (("B0 floor (must go low enough)",
              "6.449 MHz @ all-fast/125C/2.97V", "2.956 MHz @ all-slow/-40C/3.63V",
              "10 MHz", "36% below the spec line"),
             ("B7 ceiling (must go high enough)",
              "247.8 MHz @ all-slow/-40C/3.63V", "631.8 MHz @ all-fast/125C/2.97V",
              "200 MHz", "24% above the spec line")),
        )
        self.assertIn("63-corner grid", t.description)

    def test_band_plan_table(self):
        t = self.tables["band_plan"]
        self.assertEqual(
            t.columns,
            ("band", "floor: min .. max over corners (MHz)",
             "ceiling: min .. max over corners (MHz)", "fine range (x)"),
        )
        self.assertEqual(
            t.rows,
            (("B0", "2.956 .. 6.449", "6.452 .. 14.45", "2.13 .. 2.38"),
             ("B1", "4.724 .. 10.52", "10.39 .. 23.83", "2.15 .. 2.41"),
             ("B2", "7.915 .. 17.54", "17.48 .. 40.34", "2.18 .. 2.44"),
             ("B3", "12.72 .. 29.08", "28.55 .. 68.69", "2.21 .. 2.49"),
             ("B4", "21.05 .. 51.6", "48.04 .. 125.2", "2.25 .. 2.55"),
             ("B5", "34.41 .. 87.81", "80.51 .. 220.5", "2.31 .. 2.61"),
             ("B6", "59.79 .. 155.9", "143.8 .. 389.3", "2.23 .. 2.68"),
             ("B7", "100.6 .. 274.9", "247.8 .. 631.8", "2.00 .. 2.70")),
        )

    def test_band_overlap_table(self):
        t = self.tables["band_overlap"]
        self.assertEqual(
            t.columns, ("band pair", "worst overlap ratio", "overlap", "worst corner"))
        self.assertEqual(
            t.rows,
            (("B0 -> B1", "1.317", "32%", "ss/125C/3.63V"),
             ("B1 -> B2", "1.297", "30%", "ss/125C/3.63V"),
             ("B2 -> B3", "1.334", "33%", "ss/125C/3.63V"),
             ("B3 -> B4", "1.267", "27%", "ss/125C/3.63V"),
             ("B4 -> B5", "1.356", "36%", "ss/125C/3.63V"),
             ("B5 -> B6", "1.336", "34%", "sf/-40C/3.63V"),
             ("B6 -> B7", "1.321", "32%", "ss/125C/2.97V")),
        )
        self.assertEqual(
            t.notes,
            ("No corner leaves a hole in 10-200 MHz coverage: every adjacent band",
             "pair overlaps at every one of the 63 corners."),
        )

    def test_kvco_summary_table(self):
        t = self.tables["kvco_summary"]
        self.assertEqual(
            t.columns,
            ("band", "Kvco min (MHz/V)", "Kvco max (MHz/V)", "max Kvco/f_out (per V)"))
        self.assertEqual(
            t.rows,
            (("B0", "1.722", "4.702", "0.71"),
             ("B1", "2.767", "7.91", "0.71"),
             ("B2", "4.649", "13.33", "0.73"),
             ("B3", "7.556", "23.95", "0.74"),
             ("B4", "12.84", "45.32", "0.76"),
             ("B5", "21.42", "81.52", "0.78"),
             ("B6", "38.5", "135.3", "0.80"),
             ("B7", "67.32", "205.9", "0.84")),
        )

    def test_kvco_summary_notes(self):
        notes = self.tables["kvco_summary"].notes
        self.assertIn("    band, over ALL band codes**: 154.3 MHz/V (all-fast/27C/3.30V, "
                      "B7, Vctrl 0.9 V, f =", notes)
        self.assertIn("    194.5 MHz) -- **OVER** DR-001's ~150 MHz/V ceiling. Reaching "
                      "that point", notes)
        self.assertIn("    band**: 205.9 MHz/V (all-fast/125C/2.97V, B7, Vctrl 1.5 V, "
                      "f = 396.8 MHz).", notes)
        # The worst point sits above the v1 envelope, so the deferred-stretch
        # paragraph must be present and must say "exceeds".
        self.assertIn("    ABOVE the v1 envelope and exceeds the 150 MHz/V bound; it is "
                      "reported", notes)
        self.assertIn("  - Kvco/f_out inside the v1 band spans **0.31 .. 0.84 per volt**, "
                      "which", notes)
        # No (corner, target) pair is unreachable, so no unreachable footnote.
        self.assertNotIn("not reachable by ANY band", "\n".join(notes))

    def test_supply_pushing_table(self):
        t = self.tables["supply_pushing"]
        self.assertEqual(t.columns, ("", "df/dVdd (MHz/V)", "normalized (%/V)", "point"))
        self.assertEqual(
            t.rows,
            (("Worst", "-52.31", "55.3", "ss/-40C, B5, Vctrl 2.1 V (f = 94.65 MHz)"),
             ("Best", "-0.76", "20.4", "ff/-40C, B0, Vctrl 0.9 V (f = 3.735 MHz)")),
        )
        self.assertIn("1176 combinations", t.description)
        self.assertEqual(
            t.notes[:2],
            ("Median normalized pushing 39.1 %/V; a +/-10% (+/-0.33 V) supply excursion",
             "therefore moves f_osc by up to 18% open-loop at the worst point."),
        )

    def test_block_current_table(self):
        t = self.tables["block_current"]
        self.assertEqual(
            t.columns, ("operating point", "I min (uA)", "I median (uA)", "I max (uA)"))
        self.assertEqual(
            t.rows,
            (("~10 MHz (n=179)", "39", "76", "146"),
             ("~200 MHz (n=149)", "217", "328", "480")),
        )


def _run_view_from_rows(derive, rows) -> RunView:
    """Rebuild the harness's per-point `RunView` from flat sweep rows.

    Mirrors `test_vco_stages_derive.py`'s `_run_view_from_csv`: `rows_from_run`
    (what a real `run_corners.py` invocation hands `reduce_grid`) expects one
    `PointView` per (corner, band), each carrying its seven `f<n>`/`i<n>`
    measurements -- the same shape `derive_tables` is called with in
    production, so this exercises the actual crash site (`derive_tables`,
    not just `reduce_grid`).
    """
    grouped: dict[tuple, list] = {}
    for r in rows:
        grouped.setdefault((r["corner"], r["band"]), []).append(r)

    points = []
    for (corner, band), rs in grouped.items():
        bundle, temp_c, vdd = corner
        meas = {}
        for i, r in enumerate(sorted(rs, key=lambda r: r["vctrl"]), start=1):
            meas["f%d" % i] = r["f"]
            meas["i%d" % i] = r["i"]
        view = PointView(
            corner=bundle,
            corner_id="%s_%gc_%.2fv_band%d" % (bundle, temp_c, vdd, band),
            temp_c=temp_c,
            vdd=vdd,
            axes={"band": "band%d" % band},
            params={"band": str(band)},
            measurements=meas,
        )
        meas.update(derive.derive_point(view))
        points.append(view)
    return RunView(experiment="vco-tuning-range", measure_names=(), points=tuple(points))


class VcoTuningSubsetGridDoesNotCrash(unittest.TestCase):
    """Regression for #96: `derive_tables()` must not IndexError on a run

    whose grid does not span all three supplies (e.g. `--supply-tol 0`, the
    natural low-cost calibration run before committing to the full 504-point
    campaign). Built from a supply-thinned (single supply, 3.30 V only) and
    band-thinned (bands 0-2 only, out of the full 0-7) slice of the same
    committed grid `VcoTuningReductionParity` replays, so this is still a pure
    replay -- no simulator, no PDK, no network.
    """

    @classmethod
    def setUpClass(cls):
        cls.d = _load_derive()
        all_rows = _read_sweep(SWEEP_CSV)
        # Supply-thinned: only the nominal 3.30 V supply (as --supply-tol 0
        # produces) -- excludes 2.97 V and 3.63 V, so `push` in reduce_grid()
        # can never gain an entry. Band-thinned: bands 0-2 only (consecutive,
        # so the adjacent-band-overlap table's b -> b+1 lookups stay valid).
        cls.rows = [
            r for r in all_rows
            if abs(r["corner"][2] - 3.30) < 1e-9 and r["band"] in (0, 1, 2)
        ]
        cls.run_view = _run_view_from_rows(cls.d, cls.rows)

    def test_fixture_is_actually_thinned(self):
        # Sanity check on the fixture itself: exactly one supply, three bands,
        # and non-trivially smaller than the full 3528-row / 63-corner grid.
        supplies = {r["corner"][2] for r in self.rows}
        bands = {r["band"] for r in self.rows}
        self.assertEqual(supplies, {3.30})
        self.assertEqual(bands, {0, 1, 2})
        self.assertLess(len(self.rows), 3528)
        self.assertEqual(len(self.rows), 21 * 3 * 7)  # 21 corners x 3 bands x 7 vctrl

    def test_reduce_grid_push_is_empty(self):
        r = self.d.reduce_grid(self.d.rows_from_run(self.run_view))
        self.assertEqual(r["push"], [])

    def test_derive_tables_does_not_raise(self):
        # This is the exact crash site from #96: derive_tables() unpacking
        # push[-1]/push[0] on an empty list. Must not raise IndexError.
        tables = self.d.derive_tables(self.run_view)
        self.assertTrue(tables)

    def test_supply_pushing_table_is_empty_with_an_explanation(self):
        tables = {t.name: t for t in self.d.derive_tables(self.run_view)}
        pushing = tables["supply_pushing"]
        self.assertEqual(pushing.rows, ())
        notes = "\n".join(pushing.notes)
        self.assertIn("not derivable", notes.lower())
        self.assertIn("2.97", notes)
        self.assertIn("3.63", notes)

    def test_other_tables_still_populated(self):
        # The tables that do NOT share this crash (per the issue's curated
        # analysis) should still produce sensible, non-empty output on the
        # thinned grid -- this run is a legitimate subset, not a broken one.
        tables = {t.name: t for t in self.d.derive_tables(self.run_view)}
        self.assertEqual(len(tables["band_plan"].rows), 3)  # bands 0, 1, 2
        self.assertEqual(len(tables["band_overlap"].rows), 2)  # 0->1, 1->2
        self.assertEqual(len(tables["kvco_summary"].rows), 3)
        self.assertEqual(len(tables["band_edge_margin"].rows), 2)
        self.assertTrue(tables["acceptance_checks"].rows)


if __name__ == "__main__":
    unittest.main()
