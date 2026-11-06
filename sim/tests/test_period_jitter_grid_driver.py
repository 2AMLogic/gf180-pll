#!/usr/bin/env python3
"""Staged period-jitter grid driver (#731).

    python3 -m unittest discover -s sim/tests

Hermetic: no ngspice, no PDK, no network. The driver is exercised through an
injected executor; `run.py --resume` skipping is exercised with the stage
functions stubbed.
"""

from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import threading
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIM_DIR))

from harness.derived import load_module  # noqa: E402

PJ = SIM_DIR / "period-jitter"
grid = load_module(PJ / "grid.py")
CAMPAIGNS = {
    # campaign: (once-only ids, per-point stages)
    "random-bound": (["calibrate", "loop"],
                     ["trajectory", "sid", "bias", "transient"]),
    "in-band-bound": (["loop"],
                      ["digital", "cp", "cells", "clkload", "ldload", "bound"]),
}
REF = "typical_27c_3.30v"


class Recorder:
    """Fake executor: records start/finish events; fails chosen unit ids."""

    def __init__(self, fail=()):
        self.fail = set(fail)
        self.events = []
        self.lock = threading.Lock()

    def __call__(self, unit):
        with self.lock:
            self.events.append(("start", unit.id))
        with self.lock:
            self.events.append(("end", unit.id))
        return 1 if unit.id in self.fail else 0

    def started(self):
        return [i for k, i in self.events if k == "start"]

    def pos(self, kind, uid):
        return self.events.index((kind, uid))


def points45(campaign):
    return grid._load_points(campaign)


def run_driver(campaign, points, rec, jobs=3, extra=()):
    out = io.StringIO()
    argv = [campaign, "--jobs", str(jobs), *extra]
    rc = grid.main(argv, executor=rec, points_provider=lambda c: points,
                   out=lambda s: out.write(s + "\n"))
    return rc, out.getvalue()


class Plan(unittest.TestCase):
    def test_unit_set_is_exactly_the_stage_table(self):
        for c, (once, stages) in CAMPAIGNS.items():
            pts = points45(c)
            self.assertEqual(len(pts), 45)
            units = grid.build_plan(c, pts)
            ids = [u.id for u in units]
            self.assertEqual(len(ids), len(set(ids)), c)
            want = (once + [f"{s}:{p}" for p in pts for s in stages]
                    + [f"validate:{REF}", "summarize"])
            self.assertEqual(sorted(ids), sorted(want), c)
            self.assertEqual(len(ids), len(once) + 45 * len(stages) + 2)

    def test_resume_passthrough_matches_the_old_scripts(self):
        rb = {u.id: "--resume" in u.argv for u in grid.build_plan("random-bound", [REF])}
        self.assertFalse(rb["calibrate"] or rb["loop"] or rb[f"validate:{REF}"])
        self.assertTrue(rb[f"trajectory:{REF}"] and rb[f"transient:{REF}"])
        ib = {u.id: "--resume" in u.argv for u in grid.build_plan("in-band-bound", [REF])}
        self.assertTrue(all(ib[i] for i in ("loop", f"digital:{REF}", f"validate:{REF}")))

    def test_every_run_unit_goes_through_run_py(self):
        for c in CAMPAIGNS:
            for u in grid.build_plan(c, [REF]):
                if u.is_run:
                    self.assertEqual(u.argv[1:2], ["run.py"], u.id)
                else:
                    self.assertEqual(u.argv[1:2], ["summarize.py"])
                self.assertNotIn("ngspice", u.argv)


class Ordering(unittest.TestCase):
    def check(self, c):
        once, stages = CAMPAIGNS[c]
        pts = ["p1", "p2", "p3", "p4"]
        rec = Recorder()
        rc, _ = run_driver(c, pts, rec, jobs=3)
        self.assertEqual(rc, 0)
        first_point = min(rec.pos("start", f"{stages[0]}:{p}") for p in pts)
        for o in once:
            self.assertLess(rec.pos("end", o), first_point)
        self.assertLess(rec.pos("end", once[0]), rec.pos("start", once[-1])
                        if len(once) > 1 else 10**9)
        for p in pts:
            for a, b in zip(stages, stages[1:]):
                self.assertLess(rec.pos("end", f"{a}:{p}"), rec.pos("start", f"{b}:{p}"))
        # reference stage is cwd-independent of point names; find it
        ref = [i for i in rec.started() if i.startswith("validate:")][0]
        last_point_end = max(rec.pos("end", f"{stages[-1]}:{p}") for p in pts)
        self.assertLess(last_point_end, rec.pos("start", ref))
        self.assertEqual(rec.started()[-1], "summarize")

    def test_random_bound(self):
        self.check("random-bound")

    def test_in_band_bound(self):
        self.check("in-band-bound")

    def test_jobs_1_runs_in_plan_order(self):
        pts = ["p1", "p2"]
        rec = Recorder()
        run_driver("random-bound", pts, rec, jobs=1)
        self.assertEqual(rec.started(),
                         [u.id for u in grid.build_plan("random-bound", pts)])


class NoSubmit(unittest.TestCase):
    def boom(self, unit):
        raise AssertionError(f"executor invoked for {unit.id}")

    def test_plan_flag(self):
        for c, (once, stages) in CAMPAIGNS.items():
            out = io.StringIO()
            rc = grid.main([c, "--plan"], executor=self.boom,
                           out=lambda s: out.write(s + "\n"))
            self.assertEqual(rc, 0)
            self.assertIn(f"{len(once) + 45 * len(stages) + 2} units", out.getvalue())

    def test_batch_without_apply_is_a_plan(self):
        out = io.StringIO()
        rc = grid.main(["random-bound", "--backend", "batch"], executor=self.boom,
                       points_provider=lambda c: ["p1"], out=lambda s: out.write(s + "\n"))
        self.assertEqual(rc, 0)
        self.assertIn("plan only", out.getvalue())

    def test_batch_with_apply_executes(self):
        rec = Recorder()
        rc, _ = run_driver("random-bound", ["p1"], rec, extra=("--backend", "batch", "--batch-apply"))
        self.assertEqual(rc, 0)
        self.assertTrue(rec.events)


class BackendEquivalence(unittest.TestCase):
    def test_same_plan_apart_from_backend_flag(self):
        for c in CAMPAIGNS:
            pts = ["p1", "p2"]
            loc = grid.build_plan(c, pts, backend="local")
            bat = grid.build_plan(c, pts, backend="batch", batch_apply=True)
            self.assertEqual([(u.id, u.after, u.settle, u.log, u.stdout) for u in loc],
                             [(u.id, u.after, u.settle, u.log, u.stdout) for u in bat])
            for a, b in zip(loc, bat):
                if a.is_run:
                    self.assertEqual(a.argv[:-2], b.argv[:-3])
                    self.assertEqual(a.argv[-2:], ["--backend", "local"])
                    self.assertEqual(b.argv[-3:], ["--backend", "batch", "--batch-apply"])
                else:
                    self.assertEqual(a.argv, b.argv)


class Failure(unittest.TestCase):
    def test_failed_point_does_not_stop_the_rest(self):
        for c, (once, stages) in CAMPAIGNS.items():
            pts = ["p1", "p2", "p3"]
            rec = Recorder(fail={f"{stages[1]}:p2"})
            rc, out = run_driver(c, pts, rec)
            self.assertEqual(rc, 1)
            self.assertEqual(out.count("FAILED p2"), 1)
            done = rec.started()
            for s in stages[2:]:
                self.assertNotIn(f"{s}:p2", done)
            for p in ("p1", "p3"):
                self.assertIn(f"{stages[-1]}:{p}", done)
            self.assertTrue(any(i.startswith("validate:") for i in done))
            self.assertEqual(done[-1], "summarize")

    def test_failed_once_stage_aborts_before_any_point(self):
        rec = Recorder(fail={"calibrate"})
        rc, _ = run_driver("random-bound", ["p1", "p2"], rec)
        self.assertEqual(rc, 1)
        self.assertEqual(rec.started(), ["calibrate"])

    def test_failed_loop_aborts_in_band(self):
        rec = Recorder(fail={"loop"})
        rc, _ = run_driver("in-band-bound", ["p1"], rec)
        self.assertEqual(rc, 1)
        self.assertEqual(rec.started(), ["loop"])


class AppendOnly(unittest.TestCase):
    def test_driver_writes_only_driver_logs_and_summary(self):
        for c in CAMPAIGNS:
            for u in grid.build_plan(c, ["p1"]):
                for path in (u.log, u.stdout):
                    if path is not None:
                        rel = path.relative_to(PJ / c).as_posix()
                        self.assertTrue(rel == "results/SUMMARY.md"
                                        or rel == "logs/grid_p1.txt", rel)

    def test_plan_run_touches_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            before = sorted(Path(td).iterdir())
            grid.main(["random-bound", "--plan"], out=lambda s: None)
            self.assertEqual(before, sorted(Path(td).iterdir()))


class RunPyResume(unittest.TestCase):
    """The completed-stage skip lives in run.py; prove it with stubbed stages."""

    def _boom(self, *a, **k):
        raise AssertionError("stage executed despite --resume and a result on disk")

    def test_random_bound_skips_done_and_runs_missing(self):
        mod = load_module(PJ / "random-bound" / "run.py")
        mod.pdk_models = lambda: Path(".")
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "results"
            out.mkdir()
            (out / f"sid_{REF}.json").write_text("{}")
            ran = []
            mod.stage_sid = self._boom
            mod.stage_bias = lambda *a, **k: ran.append("bias")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                mod.main(["--resume", "--point", REF, "--outdir", str(out),
                          "--stage", "sid", "--stage", "bias"])
            self.assertIn("already done, skipped (--resume)", buf.getvalue())
            self.assertEqual(ran, ["bias"])

    def test_random_bound_once_only_not_resumed(self):
        mod = load_module(PJ / "random-bound" / "run.py")
        mod.pdk_models = lambda: Path(".")
        ran = []
        mod.stage_loop = lambda outdir: ran.append("loop")
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "loop.json").write_text("{}")
            with contextlib.redirect_stdout(io.StringIO()):
                mod.main(["--resume", "--outdir", td, "--stage", "loop"])
        self.assertEqual(ran, ["loop"])

    def test_in_band_skips_done_loop_and_point_stage(self):
        mod = load_module(PJ / "in-band-bound" / "run.py")
        with tempfile.TemporaryDirectory() as td:
            res = Path(td)
            (res / "loop.json").write_text("{}")
            (res / f"cp_{REF}.json").write_text("{}")
            mod.RESULTS = res
            mod.pdk_models = lambda: Path(".")
            mod.environment = lambda models: {}
            mod.load_config = lambda: ({}, 1.0, 1.0, 1.0)
            mod.stage_loop = self._boom
            mod.stage_cp = self._boom
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = mod.main(["--resume", "--point", REF, "--stage", "loop", "--stage", "cp"])
            self.assertEqual(rc, 0)
            self.assertEqual(buf.getvalue().count("skipped (--resume)"), 2)


class BackendFlag(unittest.TestCase):
    def test_batch_without_apply_runs_nothing(self):
        for c in CAMPAIGNS:
            mod = load_module(PJ / c / "run.py")
            mod.pdk_models = self._no
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = mod.main(["--backend", "batch", "--point", REF, "--stage", "validate"])
            self.assertEqual(rc, 0)
            self.assertIn("plan only", buf.getvalue())

    def test_local_selects_local_backend(self):
        for c in CAMPAIGNS:
            mod = load_module(PJ / c / "run.py")
            self.assertEqual(mod.select_backend("local").name, "local")

    @staticmethod
    def _no(*a):
        raise AssertionError("pdk lookup before plan-only exit")


if __name__ == "__main__":
    unittest.main()
