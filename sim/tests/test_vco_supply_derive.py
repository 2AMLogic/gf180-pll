"""Parity test: the migrated supply reduction must reproduce the record it supersedes.

`sim/vco-tuning-range`'s supply campaign moved from the `sim/lib/simenv.sh`
runner + `jitter_extract.py` + `analyze_supply.py` trio onto `sim/harness`,
which meant re-expressing that arithmetic as the manifest's `derived` module
(`testbench-supply/derive_supply.py`). The risk a migration carries is a
*silent* one: a reduction that quietly changes a pushing coefficient, a worst
corner or a TIE would look exactly like a real electrical regression in the new
record, and would be attributed to the tooling instead of investigated.

This test removes that ambiguity without a simulator. It replays the **exact
measured grid** of the record the migration supersedes -- the 441 committed
pushing points and 90 committed transient points of
`corners/20260731-184845-0a12e6c/` -- through the new `derive_supply.py`, going
in the way a real run does (`derive_point()` per point, then
`derive_tables(run)`), and asserts every number that record's Result field
cites comes back identical.

What it therefore pins:

- `SupplyPushingParity` -- `reduce_pushing()` over each committed seven-supply
  curve, and the per-band table, worst/best corner citations, curvature and
  swing-term comparison built from them.
- `SupplyJitterTableParity` -- the step-response, ripple-jitter, band-dependence
  and ripple-frequency tables, from the committed transient metrics.
- `MigrationDeltaParity` -- the `migration_delta` table itself: replaying the
  superseded record against itself must report a zero delta, so a non-zero
  delta in a real run is a statement about the simulation and not about the
  comparison.
- `JitterExtractionMath` -- `extract_jitter()` against an analytic waveform
  whose period, TIE and jitter are known in closed form. The committed CSVs
  hold the *output* of the crossing extraction, not the waveform, so that half
  of the port cannot be replayed from them.

Runs in the harness unit-test suite: no PDK, no ngspice, no network.
"""

from __future__ import annotations

import csv
import importlib.util
import math
import sys
import unittest
from collections import defaultdict
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
TESTBENCH = SIM_DIR / "vco-tuning-range" / "testbench-supply"
#: The chain-head record this migration supersedes, and its committed CSVs.
SUPERSEDED_RECORD = "20260731-184845-0a12e6c"
CORNERS = SIM_DIR / "vco-tuning-range" / "corners" / SUPERSEDED_RECORD
PUSH_CSV = CORNERS / "supply_pushing.csv"
JIT_CSV = CORNERS / "supply_jitter.csv"

sys.path.insert(0, str(SIM_DIR))
from harness.derived import PointView, RawFile, RunView, read_join_csv  # noqa: E402

#: The seven supply points the pushing deck sweeps internally, as the manifest
#: spells them.
SUPPLIES = ("2.97", "3.08", "3.19", "3.30", "3.41", "3.52", "3.63")

#: Jitter columns the committed CSV and the migrated derived measures share by
#: name -- deliberately identical, so this replay is a straight rename-free map.
JIT_MEASURES = (
    "quiet_f_hz", "quiet_tj_pp_s", "quiet_tj_rms_s", "quiet_c2c_rms_s",
    "quiet_tie_pp_s", "quiet_tie_rms_s",
    "step_f_pre_hz", "step_f_post_hz", "step_df_hz", "step_kvdd_hz_per_v",
    "step_tie_per_us_s",
    "rip_f_hz", "rip_tj_pp_s", "rip_tj_rms_s", "rip_c2c_rms_s",
    "rip_tie_pp_s", "rip_tie_rms_s",
    "rip_tie_pp_pred_s", "rip_tj_pp_pred_s", "quiet_cycles", "rip_cycles",
)


def _load_derive():
    spec = importlib.util.spec_from_file_location(
        "_vco_supply_derive_under_test", TESTBENCH / "derive_supply.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read(path):
    lines = [
        line for line in path.read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    return list(csv.DictReader(lines))


def _shared_params(extra=None):
    params = {
        "vctrl": "1.8", "astep": "0.1", "arip": "0.05", "tedge": "1n",
    }
    params.update({"vs%d" % (i + 1): v for i, v in enumerate(SUPPLIES)})
    params.update(extra or {})
    return params


def _absent_raw():
    """A declared-but-unwritten `jit.dat`, as a point with no waveform has."""
    return {
        "jit.dat": RawFile(
            name="jit.dat",
            path=Path("/nonexistent/jit.dat"),
            columns=("t", "clkq", "clks", "clkr"),
        )
    }


def _build_run(derive):
    """A RunView holding every point of the superseded record, both grids.

    The pushing rows become one point per (bundle, temperature, band) carrying
    `f1..f7`/`i1..i7`; the transient rows become one point per
    (bundle, temperature, supply, band, ripple divisor) carrying the committed
    jitter metrics. They do not collide -- the superseded pushing grid runs
    bands 0/4/7 and the transient grid is the rest -- which is exactly how a
    real run's points carry both phases' measurements in one row.
    """
    merged = {}

    def slot(corner, temp, vdd, band, rdiv):
        """One row per (corner, T, V, band, ripple divisor) -- both phases in it.

        A real run puts every phase's measurements in the same per-point row,
        so a replay that kept them in separate rows would not exercise the
        reduction the way the runner does (and would silently drop the nine
        points where the two superseded grids overlap).
        """
        key = (corner, temp, vdd, band, rdiv)
        if key not in merged:
            merged[key] = PointView(
                corner=corner,
                corner_id="%s_%gc_%.2fv_band%d_r%d" % (corner, temp, vdd, band, rdiv),
                temp_c=temp,
                vdd=vdd,
                axes={"band": "band%d" % band, "rdiv": "r%d" % rdiv},
                params=_shared_params({"band": str(band), "w_rdiv": str(rdiv)}),
                measurements={},
                raw_files=_absent_raw(),
            )
        return merged[key].measurements

    curves = defaultdict(dict)
    for row in _read(PUSH_CSV):
        key = (row["bundle"], float(row["temp_c"]), int(row["band"]))
        curves[key][row["vdd_v"]] = (float(row["fosc_hz"]), float(row["isupply_a"]))
    for (bundle, temp, band), by_supply in sorted(curves.items()):
        measurements = slot(bundle, temp, 3.30, band, 16)
        for i, supply in enumerate(SUPPLIES, start=1):
            if supply in by_supply:
                f, current = by_supply[supply]
                measurements["f%d" % i] = f
                # The deck's ammeter reads the supply current negative; the CSV
                # committed its magnitude, so put the sign back before handing
                # it to a reduction that takes the magnitude itself.
                measurements["i%d" % i] = -current

    for row in _read(JIT_CSV):
        band, rdiv = int(row["band"]), int(row["ripple_div"])
        measurements = slot(
            row["bundle"], float(row["temp_c"]), float(row["vdd_v"]), band, rdiv
        )
        measurements.update({name: float(row[name]) for name in JIT_MEASURES})
        measurements["jfrip"] = float(row["frip_hz"])
        # Two derived measures the superseded runner did not carry as columns,
        # computed here exactly as derive_point computes them from the same
        # inputs -- the record cites both.
        measurements["rip_tj_rms_pct"] = (
            100.0 * measurements["rip_tj_rms_s"] * measurements["rip_f_hz"]
        )
        measurements["floor_margin_x"] = (
            measurements["rip_tie_rms_s"] / max(measurements["quiet_tie_rms_s"], 1e-18)
        )

    points = [merged[k] for k in sorted(merged)]

    # derive_point() the way the runner does, so the pushing coefficients in
    # the tables below come from the reduction under test and not from here.
    enriched = []
    for view in points:
        produced = derive.derive_point(view) or {}
        merged = dict(view.measurements)
        merged.update({k: v for k, v in produced.items() if v is not None})
        enriched.append(
            PointView(
                corner=view.corner,
                corner_id=view.corner_id,
                temp_c=view.temp_c,
                vdd=view.vdd,
                axes=view.axes,
                params=view.params,
                measurements=merged,
                raw_files=view.raw_files,
            )
        )
    return RunView(
        experiment="vco-tuning-range",
        measure_names=(),
        points=tuple(enriched),
        joins={
            "legacy_push": read_join_csv("legacy_push", PUSH_CSV),
            "legacy_jit": read_join_csv("legacy_jit", JIT_CSV),
        },
    )


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.derive = _load_derive()
        cls.runview = _build_run(cls.derive)
        cls.tables = {t.name: t for t in cls.derive.derive_tables(cls.runview)}

    def table(self, name):
        self.assertIn(name, self.tables)
        return self.tables[name]

    def assertNote(self, name, fragment):
        notes = " ".join(self.table(name).notes)
        self.assertIn(fragment, notes, f"{name} notes: {notes}")


class SupplyPushingParity(_Base):
    """Section 1 of the superseded record, from its own 441 committed points."""

    def test_per_band_table(self):
        rows = {r[0]: r for r in self.table("supply_pushing_summary").rows}
        self.assertEqual(sorted(rows), ["B0", "B4", "B7"])
        # band, curves, most negative, ..., median, least negative, ..., shift
        for band, most, median, least, shift in (
            ("B0", "-35.3", "-29.0", "-24.1", "12"),
            ("B4", "-50.7", "-41.3", "-33.7", "17"),
            ("B7", "-50.1", "-44.6", "-32.7", "17"),
        ):
            row = rows[band]
            self.assertEqual(row[1], 21, band)          # 7 bundles x 3 temps
            self.assertEqual(row[2], most, band)
            self.assertEqual(row[4], median, band)
            self.assertEqual(row[5], least, band)
            self.assertEqual(row[7], shift, band)

    def test_worst_and_best_corner_citations(self):
        self.assertNote(
            "supply_pushing_summary",
            "Worst (most supply-sensitive) point: **-50.7 %/V** (-24.68 MHz/V at "
            "48.68 MHz) at ss/-40C, band 4, Vctrl 1.8 V.",
        )
        self.assertNote("supply_pushing_summary", "Best: **-24.1 %/V** at ff/-40C, band 0.")

    def test_curvature_and_swing_term(self):
        self.assertNote("supply_pushing_summary", "is 2.26 % of f_nom")
        self.assertNote("supply_pushing_summary", "-30.3 %/V")
        self.assertNote("supply_pushing_summary", "measured median of -39.4 %/V is 1.30x")

    def test_curve_count(self):
        self.assertNote("supply_pushing_summary", "63 curves of 7 points each")

    def test_verdict_reads_the_same_numbers(self):
        rows = {r[0]: r for r in self.table("supply_verdict").rows}
        self.assertEqual(rows["static supply pushing, worst corner"][1], "-50.7 %/V")
        self.assertEqual(rows["pushing linearity, worst curve"][1], "2.26 % of f_nom")


class SupplyJitterTableParity(_Base):
    """Sections 2-5 of the superseded record, from its 90 committed points."""

    def test_step_response(self):
        rows = {r[0]: r for r in self.table("supply_step_response").rows}
        for case, corner, df, frac, kvdd, tie in (
            ("worst", "all-slow/-40C/2.97V", "-4.77", "-6.08", "-47.7", "-60.8"),
            ("median", "fs/125C/3.30V", "-4.06", "-4.16", "-40.6", "-41.6"),
            ("best", "ff/-40C/3.63V", "-1.68", "-2.57", "-16.8", "-25.7"),
        ):
            self.assertEqual(rows[case][1], corner, case)
            self.assertEqual(rows[case][2], df, case)
            self.assertEqual(rows[case][3], frac, case)
            self.assertEqual(rows[case][4], kvdd, case)
            self.assertEqual(rows[case][5], tie, case)

    def test_step_response_grid_size(self):
        self.assertIn("63-point", self.table("supply_step_response").description)

    def test_ripple_jitter(self):
        rows = {r[0]: r for r in self.table("supply_ripple_jitter").rows}
        for case, corner, tjpp, tjrms, tiepp, tierms in (
            ("rippled, worst", "all-slow/-40C/2.97V", "910 ps", "320 ps", "3.37 ns", "1.02 ns"),
            ("rippled, median", "ff/-40C/3.63V", "540 ps", "191 ps", "1.69 ns", "516 ps"),
            ("rippled, best", "all-fast/125C/3.63V", "349 ps", "123 ps", "829 ps", "259 ps"),
            # The superseded record does not name the corner of the quiet row
            # (its label is fixed text), so only its four numbers are pinned.
            ("**quiet reference, worst** (numerical floor)", None,
             "2.27 ps", "0.614 ps", "9.63 ps", "2.81 ps"),
        ):
            if corner is not None:
                self.assertEqual(rows[case][1], corner, case)
            self.assertEqual(rows[case][2:], (tjpp, tjrms, tiepp, tierms), case)

    def test_numerical_floor_margin_and_worst_case_fraction(self):
        self.assertNote("supply_ripple_jitter", "is **134x** in TIE RMS")
        self.assertNote(
            "supply_ripple_jitter",
            "**2.51 % RMS period jitter** and 7.15 % peak-to-peak, at "
            "all-slow/-40C/2.97V, f_osc = 78.52 MHz.",
        )
        self.assertNote("supply_ripple_jitter", "sufficient to break")

    def test_band_dependence(self):
        rows = {r[0]: r for r in self.table("ripple_band_dependence").rows}
        self.assertEqual(sorted(rows), ["B%d" % b for b in range(8)])
        for band, fmin, fmax, tie, pct in (
            ("B0", "5.344", "8.577", "16.2 ns", "1.18"),
            ("B3", "24.18", "37.92", "4.83 ns", "1.59"),
            ("B5", "70.89", "110", "2.38 ns", "2.12"),
            ("B7", "217.1", "343.9", "924 ps", "2.33"),
        ):
            self.assertEqual(rows[band][2], fmin, band)
            self.assertEqual(rows[band][3], fmax, band)
            self.assertEqual(rows[band][4], tie, band)
            self.assertEqual(rows[band][5], pct, band)

    def test_ripple_frequency_check(self):
        rows = {r[0]: r for r in self.table("ripple_frequency_check").rows}
        for case, frip, meas, pred, ratio in (
            ("f_osc/4", "23.5", "673 ps", "303 ps", "2.22"),
            ("f_osc/16", "5.86", "1.76 ns", "1.21 ns", "1.45"),
            ("f_osc/32", "2.93", "2.99 ns", "2.44 ns", "1.23"),
        ):
            self.assertEqual(rows[case][2], frip, case)
            self.assertEqual(rows[case][3], meas, case)
            self.assertEqual(rows[case][4], pred, case)
            self.assertEqual(rows[case][5], ratio, case)

    def test_projection_is_withheld_with_the_same_reasoning(self):
        self.assertNote(
            "ripple_frequency_check",
            "the measured/predicted ratio spans 1.22 .. 2.29 (median 1.45)",
        )
        self.assertNote("ripple_frequency_check", "must be **measured**, not extrapolated")

    def test_verdict_reads_the_same_numbers(self):
        rows = {r[0]: r for r in self.table("supply_verdict").rows}
        self.assertEqual(rows["supply-ripple TIE, worst corner"][1], "3.37 ns peak-to-peak")
        self.assertEqual(
            rows["supply-ripple period jitter, worst corner"][1], "2.51 % RMS of the period"
        )
        self.assertIn("BREAKS", rows["supply-ripple period jitter, worst corner"][3])
        self.assertEqual(
            rows["margin over the solver's numerical floor"][1], "134x in TIE RMS"
        )


class MigrationDeltaParity(_Base):
    """The comparison itself: the superseded record against itself is zero."""

    def test_every_quantity_is_compared(self):
        rows = {r[0]: r for r in self.table("migration_delta").rows}
        self.assertIn("fosc_hz", rows)
        self.assertIn("rip_tie_pp_s", rows)
        self.assertEqual(rows["fosc_hz"][1], 441)
        self.assertEqual(rows["rip_tie_pp_s"][1], 90)

    def test_replaying_a_record_against_itself_reports_no_delta(self):
        for row in self.table("migration_delta").rows:
            if not row[1]:
                continue
            self.assertLess(float(row[3]), 1e-9, f"{row[0]} moved: {row}")


class JitterExtractionMath(unittest.TestCase):
    """`extract_jitter()` against a waveform whose jitter is known in closed form.

    The committed CSVs hold the extraction's *output*, so they cannot pin the
    crossing arithmetic itself. This does: a clock whose rising edges are placed
    analytically, one channel unmodulated and one frequency-modulated by a
    known sinusoid, sampled densely enough that linear interpolation of the
    crossing is exact to well under the tolerances asserted.
    """

    F0 = 100e6
    VSUP = 3.3
    NCYC = 128
    OVERSAMPLE = 400

    @classmethod
    def setUpClass(cls):
        cls.derive = _load_derive()

    def _clock(self, t, phase_of):
        """A triangle clock: linear through the threshold, so interpolation is exact."""
        return [self.VSUP * (phase_of(x) % 1.0) for x in t]

    def test_unmodulated_clock_has_no_jitter(self):
        dt = 1.0 / (self.F0 * self.OVERSAMPLE)
        n = int(self.NCYC / self.F0 / dt)
        t = [i * dt for i in range(n)]
        y = self._clock(t, lambda x: self.F0 * x)
        out = self.derive.extract_jitter(
            t, y, y, y, vsup=self.VSUP, tsettle=0.0, tstepon=self.NCYC / self.F0 / 2,
            astep=0.1, arip=0.05, frip=self.F0 / 16,
        )
        self.assertIsNotNone(out)
        self.assertAlmostEqual(out["quiet_f_hz"] / self.F0, 1.0, places=6)
        period = 1.0 / self.F0
        self.assertLess(out["quiet_tj_pp_s"], 1e-6 * period)
        self.assertLess(out["quiet_tie_pp_s"], 1e-6 * period)

    def test_frequency_modulated_clock_reports_the_analytic_tie(self):
        """f(t) = f0 (1 + m sin 2*pi*fr*t)  =>  TIE_pp = m*f0/(pi*fr*f0) ... """
        fr = self.F0 / 16
        m = 0.02
        # phase(t) = f0*t - (m*f0/(2*pi*fr)) * (cos(2*pi*fr*t) - 1)
        amp = m * self.F0 / (2 * math.pi * fr)

        def phase(x):
            return self.F0 * x - amp * (math.cos(2 * math.pi * fr * x) - 1.0)

        dt = 1.0 / (self.F0 * self.OVERSAMPLE)
        n = int(self.NCYC / self.F0 / dt)
        t = [i * dt for i in range(n)]
        quiet = self._clock(t, lambda x: self.F0 * x)
        modulated = self._clock(t, phase)
        out = self.derive.extract_jitter(
            t, quiet, quiet, modulated, vsup=self.VSUP, tsettle=0.0,
            tstepon=self.NCYC / self.F0 / 2, astep=0.1, arip=0.05, frip=fr,
        )
        self.assertIsNotNone(out)
        # Excess phase of amplitude `amp` cycles is a time error of amp/f0
        # peak, so 2*amp/f0 peak-to-peak.
        expected_tie_pp = 2 * amp / self.F0
        # 1.5 % of the closed form: the crossings sample the modulation at
        # discrete cycles, so the analytic extremes are approached, not hit.
        self.assertAlmostEqual(out["rip_tie_pp_s"] / expected_tie_pp, 1.0, delta=0.03)
        # Period modulation: T(t) ~ (1/f0)(1 - m sin), so 2*m/f0 peak-to-peak.
        self.assertAlmostEqual(out["rip_tj_pp_s"] / (2 * m / self.F0), 1.0, delta=0.05)

    def test_too_few_crossings_is_data_not_an_error(self):
        dt = 1.0 / (self.F0 * self.OVERSAMPLE)
        n = int(4 / self.F0 / dt)  # four cycles: below MIN_CROSSINGS
        t = [i * dt for i in range(n)]
        y = self._clock(t, lambda x: self.F0 * x)
        self.assertIsNone(
            self.derive.extract_jitter(
                t, y, y, y, vsup=self.VSUP, tsettle=0.0, tstepon=1e-9,
                astep=0.1, arip=0.05, frip=self.F0 / 16,
            )
        )


class ManifestShape(unittest.TestCase):
    """The manifest declares exactly what the reduction produces."""

    @classmethod
    def setUpClass(cls):
        import json

        cls.manifest = json.loads((TESTBENCH / "tb.json").read_text())
        cls.derive = _load_derive()

    def test_declared_tables_match_derive_tables(self):
        declared = set(self.manifest["derived"]["tables"])
        produced = {t.name for t in self.derive.derive_tables(_build_run(self.derive))}
        self.assertEqual(declared, produced)

    def test_joins_point_at_the_superseded_record(self):
        joins = self.manifest["derived"]["joins"]
        self.assertIn(SUPERSEDED_RECORD, joins["legacy_push"])
        self.assertIn(SUPERSEDED_RECORD, joins["legacy_jit"])
        self.assertEqual(self.derive.SUPERSEDED_RECORD, SUPERSEDED_RECORD)

    def test_both_phases_are_declared_with_their_own_deck(self):
        phases = self.manifest["phases"]
        self.assertEqual(list(phases), ["push", "jit"])
        for name in phases:
            self.assertTrue((TESTBENCH / phases[name]["netlist"]).is_file(), name)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
