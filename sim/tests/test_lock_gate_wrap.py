"""The closed-loop `ferr` lock gate, against the wrap that made it fail a locked corner.

`phi_a`/`phi_b` are ngspice `trig`/`targ` edge-pair delays, so each is wrapped
into ONE reference period by construction. When a locked loop's static phase
error straddles zero -- FB's edge marginally ahead of REF's -- a sample can
latch the *next* FB edge and report ~T_ref where the physical answer is ~0.
Differencing two samples on opposite sides of that wrap reads one whole
reference period of apparent drift per baseline, i.e. `ferr` = T_ref/(tb-ta),
and the gate fails a loop that is in fact locked. `sim/period-jitter` record
`20260906-063728-f3c9c23` hit exactly that at `ff_27c_2.97v_vs1p638` and
`ff_27c_3.63v_vs2p200` (issue #273): `ferr` = 3.99985e-2 / 3.99881e-2 against a
+-1e-3 gate, at two points whose `fout`, `ffb` and `nmeas` all independently
said the loop was locked to within 160 ppm.

This module pins the fix, and -- as importantly -- pins that it is a *wrap*
fix and not a widened tolerance:

- the committed `ferr` expression, evaluated on the two recorded wrap cases,
  now lands inside the manifest's own gate, while the pre-fix expression on the
  same inputs does not (`WrapCase`/`test_recorded_wrap_*`);
- the gate itself is still +-1e-3 in every affected manifest
  (`test_ferr_gate_is_unchanged`);
- a genuine residual frequency error of the same order still fails
  (`test_genuine_frequency_error_still_fails`);
- unwrapping is the identity when there is no wrap, so an already-correct
  measurement is reported unchanged (`test_unwrap_is_identity_without_a_wrap`);
- the one thing unwrapping *does* cost -- an aliasing blind spot at exact
  multiples of T_ref/(tb-ta) -- is closed by `ferr_fb`, a period-count
  frequency error with no wrap at all
  (`test_alias_blind_spot_is_caught_by_ferr_fb`). For `sim/reference-spur` that
  blind spot sits *inside* the manifest's +-1% `fout` window, so `ferr_fb` is
  not decoration there: without it that campaign really could pass a loop
  running 0.79 % off (`test_alias_blind_spot_would_pass_the_fout_window`).

The expressions under test are read out of the committed manifests and decks,
never restated here, so reverting a manifest fails these tests rather than
leaving them passing against a copy.

Runs in the harness unit-test suite: no PDK, no network. The Python evaluator
is cross-checked against real ngspice when one is on PATH
(`NgspiceAgreesWithTheEvaluator`) so the arithmetic is not merely Python
agreeing with itself; that class skips where ngspice is absent.
"""

from __future__ import annotations

import json
import math
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIM_DIR))

#: Campaigns whose manifests carry the `phi_a`/`phi_b` -> `dphi` -> `ferr`
#: idiom this issue is about, with the reference period and phase baseline
#: each one measures over.
JSON_CAMPAIGNS = ("period-jitter", "reference-spur", "period-jitter-band-top")

#: The gate every one of them applies to `ferr`. Pinned so a future "fix" that
#: widens the tolerance instead of unwrapping fails here rather than in a
#: record six weeks later.
FERR_GATE = {"min": -0.001, "max": 0.001}

#: The corroboration gate on `ferr_fb`. Looser than `ferr` on purpose: it is
#: read from a 5-to-20 cycle period count rather than a microsecond phase
#: baseline, so it is the coarse-but-unambiguous half of the pair. The largest
#: |ffb/fref - 1| any committed record of these campaigns has produced is
#: 5.5e-4, so this leaves better than 3x margin on measured evidence while
#: still sitting far below the smallest aliasing blind spot (7.9e-3).
FERR_FB_GATE = {"min": -0.002, "max": 0.002}


def manifest(slug: str) -> dict:
    return json.loads((SIM_DIR / slug / "testbench" / "tb.json").read_text())


def param_expr(spec_expr: str) -> str:
    """The arithmetic inside a `raw_measures` entry's ``param='...'``."""
    text = spec_expr.strip()
    if not text.startswith("param="):
        raise AssertionError(f"not a param= measurement: {spec_expr!r}")
    return text[len("param=") :].strip().strip("'\"")


def evaluate(expr: str, env: dict) -> float:
    """Evaluate one ngspice ``param=`` expression the way ngspice would.

    The subset these gates use is plain arithmetic plus ``floor``, which
    ngspice's ``.meas ... param=`` evaluator and Python agree on exactly (see
    :class:`NgspiceAgreesWithTheEvaluator`, which checks that rather than
    assuming it).
    """
    return float(eval(expr, {"__builtins__": {}}, {"floor": math.floor, **env}))


def evaluate_chain(slug: str, measured: dict) -> dict:
    """Replay a manifest's ``param=`` measurements over simulated raw values.

    ``measured`` supplies what ngspice's ``trig``/``targ`` (and any other
    non-``param=``) cards would have produced; every ``param=`` entry is then
    evaluated in manifest order against the manifest's own ``params`` plus
    whatever has resolved so far -- which is what ngspice does, and why
    ``ferr`` may reference ``dphi``.
    """
    tb = manifest(slug)
    env = {k: float(v) for k, v in tb["params"].items()}
    env.update(measured)
    for name, spec in tb["raw_measures"].items():
        text = spec["expr"].strip()
        if not text.startswith("param="):
            continue
        try:
            env[name] = evaluate(param_expr(text), env)
        except NameError:
            # A param= measurement over inputs this case did not supply (e.g.
            # tclk20 for a case that only exercises the phase path).
            continue
    return env


class WrapCase:
    """One (phi_a, phi_b, ffb) triple, with what the loop was really doing."""

    def __init__(self, name, phi_a, phi_b, ffb):
        self.name = name
        self.phi_a = phi_a
        self.phi_b = phi_b
        self.ffb = ffb

    def measured(self) -> dict:
        return {"phi_a": self.phi_a, "phi_b": self.phi_b, "ffb": self.ffb}


#: The two points of record 20260906-063728-f3c9c23 that failed. Values are
#: the record's own, quoted in issue #273 and reproduced to seven digits across
#: two independently launched runs of the same grid.
RECORDED_WRAPS = (
    WrapCase("ff_27c_2.97v_vs1p638", 3.98121e-8, -1.86479e-10, 2.500270e7),
    WrapCase("ff_27c_3.63v_vs2p200", 3.98571e-8, -1.31045e-10, 2.499720e7),
)


class FerrGateIsWrapSafe(unittest.TestCase):
    """`sim/period-jitter`'s gate, on the exact numbers that failed it."""

    slug = "period-jitter"

    def gate(self):
        return manifest(self.slug)["checks"]["ferr"]

    def test_ferr_gate_is_unchanged(self):
        """Every affected manifest still gates `ferr` at +-1e-3."""
        for slug in JSON_CAMPAIGNS:
            with self.subTest(slug=slug):
                checks = manifest(slug)["checks"]
                self.assertEqual(checks["ferr"], FERR_GATE)
                self.assertEqual(checks["ferr_fb"], FERR_FB_GATE)

    def test_recorded_wrap_failed_before_the_fix(self):
        """The pre-fix expression really does report ~1 T_ref per baseline.

        Without this, a "fix" that quietly stopped exercising the wrap would
        look identical to one that handled it.
        """
        tb = manifest(self.slug)
        t_ref = 1.0 / float(tb["params"]["fref"])
        baseline = float(tb["params"]["tb"]) - float(tb["params"]["ta"])
        gate = self.gate()
        for case in RECORDED_WRAPS:
            with self.subTest(point=case.name):
                pre_fix = -(case.phi_b - case.phi_a) / baseline
                # One whole reference period of apparent drift per baseline,
                # less the true sub-200 ps phase error.
                self.assertAlmostEqual(pre_fix, t_ref / baseline, delta=1e-4)
                self.assertGreater(pre_fix, gate["max"])

    def test_recorded_wrap_passes_after_the_fix(self):
        """The committed expression scores both recorded points as locked."""
        gate = self.gate()
        for case in RECORDED_WRAPS:
            with self.subTest(point=case.name):
                env = evaluate_chain(self.slug, case.measured())
                self.assertGreater(env["ferr"], gate["min"])
                self.assertLess(env["ferr"], gate["max"])
                # Not merely inside the gate: the unwrapped drift is the
                # sub-200 ps phase error the record's own fout/ffb implied,
                # which is three orders below the gate.
                self.assertLess(abs(env["ferr"]), 1e-4)
                self.assertLess(abs(env["dphi"]), 0.5 * 1.0 / 25e6)

    def test_recorded_wrap_also_passes_the_corroboration_gate(self):
        """`ferr_fb` agrees the two recorded points were locked."""
        for case in RECORDED_WRAPS:
            with self.subTest(point=case.name):
                env = evaluate_chain(self.slug, case.measured())
                self.assertLess(abs(env["ferr_fb"]), FERR_FB_GATE["max"])


class TheFixIsNotAWidenedTolerance(unittest.TestCase):
    """A genuinely unlocked loop must still fail, in every affected campaign."""

    def _phase_pair(self, slug, ferr_true):
        """A (phi_a, phi_b) pair for a loop drifting at `ferr_true`, no wrap.

        The phase slips by `ferr_true * (tb - ta)` across the baseline; centred
        on zero so neither sample crosses a wrap boundary of its own.
        """
        tb = manifest(slug)["params"]
        drift = ferr_true * (float(tb["tb"]) - float(tb["ta"]))
        return {"phi_a": 0.5 * drift, "phi_b": -0.5 * drift}

    def test_genuine_frequency_error_still_fails(self):
        """A residual drift above the gate is still reported as one, and as itself.

        The drifts are taken relative to each campaign's own unambiguous range
        (half the aliasing period T_ref/(tb-ta)), because that range differs by
        5x between these decks -- `sim/reference-spur`'s 5.08 us baseline
        resolves +-3.9e-3 where `sim/period-jitter`'s 1 us baseline resolves
        +-2.0e-2. Errors past that range are the alias case, covered in
        :class:`TheAliasBlindSpotIsCovered`.
        """
        for slug in JSON_CAMPAIGNS:
            tb = manifest(slug)["params"]
            unambiguous = 0.5 / float(tb["fref"]) / (float(tb["tb"]) - float(tb["ta"]))
            gate = manifest(slug)["checks"]["ferr"]
            self.assertGreater(unambiguous, 3 * gate["max"], slug)
            for ferr_true in (1.5 * gate["max"], 3 * gate["max"], -0.45 * unambiguous):
                with self.subTest(slug=slug, ferr_true=ferr_true):
                    measured = self._phase_pair(slug, ferr_true)
                    measured["ffb"] = float(tb["fref"]) * (1.0 + ferr_true)
                    env = evaluate_chain(slug, measured)
                    self.assertAlmostEqual(env["ferr"], ferr_true, places=9)
                    self.assertTrue(
                        env["ferr"] < gate["min"] or env["ferr"] > gate["max"],
                        f"{slug}: ferr={env['ferr']!r} slipped through {gate!r}",
                    )

    def test_unwrap_is_identity_without_a_wrap(self):
        """A drift the old gate reported correctly is reported unchanged."""
        for slug in JSON_CAMPAIGNS:
            for ferr_true in (0.0, 1e-6, -2.5e-5, 9e-4):
                with self.subTest(slug=slug, ferr_true=ferr_true):
                    measured = self._phase_pair(slug, ferr_true)
                    env = evaluate_chain(slug, measured)
                    naive = -(measured["phi_b"] - measured["phi_a"]) / (
                        float(manifest(slug)["params"]["tb"])
                        - float(manifest(slug)["params"]["ta"])
                    )
                    self.assertAlmostEqual(env["ferr"], naive, places=12)


class TheAliasBlindSpotIsCovered(unittest.TestCase):
    """What unwrapping costs, and what closes it.

    Unwrapping into (-T_ref/2, +T_ref/2] makes `ferr` ambiguous modulo
    T_ref/(tb-ta): a loop drifting by an exact whole reference period per
    baseline reads as zero drift. That is the one way the fixed `ferr` can
    still be wrong, so it is measured here rather than argued away -- and
    `ferr_fb`, which counts periods instead of differencing phases and
    therefore does not wrap at all, is shown to catch it.
    """

    def _alias_ferr(self, slug):
        tb = manifest(slug)["params"]
        t_ref = 1.0 / float(tb["fref"])
        return t_ref / (float(tb["tb"]) - float(tb["ta"]))

    def test_alias_blind_spot_exists_and_is_where_the_arithmetic_says(self):
        for slug in JSON_CAMPAIGNS:
            with self.subTest(slug=slug):
                alias = self._alias_ferr(slug)
                tb = manifest(slug)["params"]
                t_ref = 1.0 / float(tb["fref"])
                # A loop slipping exactly one reference period per baseline.
                measured = {"phi_a": 0.0, "phi_b": -t_ref}
                env = evaluate_chain(slug, measured)
                self.assertAlmostEqual(env["ferr"], 0.0, places=12)
                gate = manifest(slug)["checks"]["ferr"]
                self.assertGreater(alias, gate["max"])

    def test_alias_blind_spot_is_caught_by_ferr_fb(self):
        for slug in JSON_CAMPAIGNS:
            with self.subTest(slug=slug):
                alias = self._alias_ferr(slug)
                tb = manifest(slug)["params"]
                t_ref = 1.0 / float(tb["fref"])
                measured = {
                    "phi_a": 0.0,
                    "phi_b": -t_ref,
                    "ffb": float(tb["fref"]) * (1.0 + alias),
                }
                env = evaluate_chain(slug, measured)
                gate = manifest(slug)["checks"]["ferr_fb"]
                self.assertAlmostEqual(env["ferr_fb"], alias, places=9)
                self.assertTrue(
                    env["ferr_fb"] < gate["min"] or env["ferr_fb"] > gate["max"],
                    f"{slug}: ferr_fb={env['ferr_fb']!r} slipped through {gate!r}",
                )

    def test_alias_blind_spot_would_pass_the_fout_window(self):
        """Why `ferr_fb` is required and `fout` is not a substitute for it.

        `sim/reference-spur` differences its phase over a 5.08 us baseline, so
        its first alias sits at 7.9e-3 -- a loop running 0.79 % fast, which is
        *inside* that manifest's +-1 % `fout` window. Without `ferr_fb` the
        campaign would have no check left that could see it.
        """
        slug = "reference-spur"
        tb = manifest(slug)
        alias = self._alias_ferr(slug)
        n = float(tb["params"]["nratio"])
        fout = n * float(tb["params"]["fref"]) * (1.0 + alias)
        window = tb["checks"]["fout"]
        self.assertGreater(fout, window["min"])
        self.assertLess(fout, window["max"])
        # nmeas cannot see it either: a whole loop running fast still divides
        # by the configured N.
        nmeas_window = tb["checks"]["nmeas"]
        self.assertGreater(n, nmeas_window["min"])
        self.assertLess(n, nmeas_window["max"])


class CommittedEvidenceStillPassesTheNewGate(unittest.TestCase):
    """`ferr_fb` is a new check; it must not retro-fail committed evidence.

    Every `ffb` any of these campaigns has ever recorded is replayed through
    the `ferr_fb` expression and its gate. A tolerance that would have failed
    a point already committed as PASS is a tolerance chosen wrong, and this is
    the only way to find that out without re-running the grid.
    """

    def test_every_recorded_ffb_passes_ferr_fb(self):
        import csv

        seen = 0
        for slug in JSON_CAMPAIGNS:
            gate = manifest(slug)["checks"]["ferr_fb"]
            fref = float(manifest(slug)["params"]["fref"])
            corners = SIM_DIR / slug / "corners"
            for path in sorted(corners.glob("*/raw_measures.csv")):
                rows = list(csv.DictReader(path.read_text().splitlines()))
                for row in rows:
                    try:
                        ffb = float(row.get("ffb", ""))
                    except ValueError:
                        continue  # "not measured" / an ERROR point
                    seen += 1
                    ferr_fb = ffb / fref - 1.0
                    with self.subTest(record=path.parent.name, point=row["corner_id"]):
                        self.assertGreater(ferr_fb, gate["min"])
                        self.assertLess(ferr_fb, gate["max"])
        self.assertGreater(seen, 0, "no committed ffb evidence was found to replay")


class PllTopSmokeSharesTheFix(unittest.TestCase):
    """`sim/pll-top-smoke` runs the same idiom through its own bash/awk gate.

    Its `.meas` cards are in the deck rather than a manifest and its checks are
    in `run.sh`, so a fix scoped to the JSON manifests would not reach it.
    """

    DECK = SIM_DIR / "pll-top-smoke" / "testbench" / "tb_pll_smoke.sp"
    RUN = SIM_DIR / "pll-top-smoke" / "testbench" / "run.sh"

    #: The smoke deck's own operating point (run.sh: KFREF/KTA/KTB).
    FREF = 9e6
    TA = 50e-6
    TB = 53e-6

    def _meas(self, name):
        for line in self.DECK.read_text().splitlines():
            parts = line.split()
            if len(parts) >= 4 and parts[0] == ".meas" and parts[2] == name:
                return param_expr(" ".join(parts[3:]))
        raise AssertionError(f"no `.meas tran {name} param=...` card in {self.DECK}")

    def _env(self, **extra):
        env = {"tref": 1.0 / self.FREF, "ta": self.TA, "tb": self.TB}
        env.update(extra)
        return env

    def test_deck_unwraps_the_phase_difference(self):
        t_ref = 1.0 / self.FREF
        # FB 0.2 ns ahead of REF at both instants; the sample at ta wrapped.
        phi_a, phi_b = t_ref - 0.2e-9, -0.2e-9
        env = self._env(phi_a=phi_a, phi_b=phi_b)
        env["dphi"] = evaluate(self._meas("dphi"), env)
        ferr = evaluate(self._meas("ferr"), env)
        self.assertLess(abs(ferr), 1e-3)  # run.sh's ACC_FERR
        naive = -(phi_b - phi_a) / (self.TB - self.TA)
        self.assertGreater(abs(naive), 1e-3)

    def test_deck_unwraps_each_phase_sample_for_the_static_phase_gate(self):
        t_ref = 1.0 / self.FREF
        env = self._env(phi_a=t_ref - 0.2e-9, phi_b=t_ref - 0.2e-9)
        for card in ("phi_a_uw", "phi_b_uw"):
            with self.subTest(card=card):
                value = evaluate(self._meas(card), env)
                self.assertAlmostEqual(value, -0.2e-9, places=15)
                # run.sh's ACC_PHI_FRAC gate, which the raw sample would fail.
                self.assertLess(abs(value), 0.02 * t_ref)
                self.assertGreater(abs(t_ref - 0.2e-9), 0.02 * t_ref)

    def test_run_sh_gates_on_the_unwrapped_samples(self):
        """The wiring, not just the cards: a deck fix nothing reads is no fix."""
        text = self.RUN.read_text()
        self.assertIn("PHI_A=$(m phi_a_uw)", text)
        self.assertIn("PHI_B=$(m phi_b_uw)", text)
        self.assertIn("ACC_FERR=1e-3", text)  # tolerance unchanged
        self.assertIn("ACC_PHI_FRAC=0.02", text)

    def test_genuine_drift_still_fails_the_smoke_gate(self):
        for ferr_true in (2e-3, -5e-3):
            with self.subTest(ferr_true=ferr_true):
                drift = ferr_true * (self.TB - self.TA)
                env = self._env(phi_a=0.5 * drift, phi_b=-0.5 * drift)
                env["dphi"] = evaluate(self._meas("dphi"), env)
                ferr = evaluate(self._meas("ferr"), env)
                self.assertAlmostEqual(ferr, ferr_true, places=9)
                self.assertGreater(abs(ferr), 1e-3)


NGSPICE = shutil.which("ngspice")


@unittest.skipUnless(NGSPICE, "ngspice is not on PATH")
class NgspiceAgreesWithTheEvaluator(unittest.TestCase):
    """The evaluator above is Python; the gate runs in ngspice.

    Everything else in this module would still pass if ngspice's `.meas
    param=` evaluator did not implement `floor` at all, or implemented it as
    truncation-toward-zero (which is *not* the same function for the negative
    arguments this unwrap depends on). So the committed expressions are run
    through a real ngspice here and compared against the Python answer.
    """

    def _run(self, exprs: dict, params: dict) -> dict:
        lines = ["* #273 lock-gate expression cross-check"]
        lines += [f".param {k}={v!r}" for k, v in params.items()]
        lines += ["v1 1 0 dc 1", "r1 1 0 1k", ".tran 1n 10n", ".print tran v(1)"]
        lines += [f".meas tran {name} param='{expr}'" for name, expr in exprs.items()]
        lines.append(".end")
        with tempfile.TemporaryDirectory() as tmp:
            deck = Path(tmp) / "probe.sp"
            deck.write_text("\n".join(lines) + "\n")
            proc = subprocess.run(
                [NGSPICE, "-b", str(deck)],
                capture_output=True,
                text=True,
                timeout=120,
            )
        out = {}
        for line in proc.stdout.splitlines():
            parts = line.split("=")
            if len(parts) == 2 and parts[0].strip() in exprs:
                out[parts[0].strip()] = float(parts[1].strip())
        return out

    def test_ngspice_matches_python_on_the_committed_expressions(self):
        tb = manifest("period-jitter")
        raw = tb["raw_measures"]
        params = {k: float(v) for k, v in tb["params"].items()}
        for case in RECORDED_WRAPS:
            with self.subTest(point=case.name):
                probe_params = dict(params, phi_a=case.phi_a, phi_b=case.phi_b)
                exprs = {
                    "dphi": param_expr(raw["dphi"]["expr"]),
                    "ferr": param_expr(raw["ferr"]["expr"]),
                }
                got = self._run(exprs, probe_params)
                self.assertEqual(
                    set(got),
                    set(exprs),
                    f"ngspice did not evaluate every card (got {got!r}); "
                    "the unwrap must not depend on a function this ngspice lacks",
                )
                want = evaluate_chain("period-jitter", case.measured())
                self.assertAlmostEqual(got["dphi"], want["dphi"], delta=1e-15)
                self.assertAlmostEqual(got["ferr"], want["ferr"], delta=1e-9)
                self.assertLess(abs(got["ferr"]), tb["checks"]["ferr"]["max"])

    def test_ngspice_floor_is_a_floor_for_negative_arguments(self):
        """Truncation-toward-zero would put the unwrap a period out of place."""
        got = self._run({"m": "floor(x)"}, {"x": -0.4})
        self.assertEqual(got["m"], -1.0)


if __name__ == "__main__":
    unittest.main()
