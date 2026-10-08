#!/usr/bin/env python3
"""Period-jitter runners delegate to the harness execution layer (#712).

    python3 -m unittest discover -s sim/tests -v

Hermetic: no ngspice, no PDK, no network. Covers

* deck execution of every period-jitter ``run.py`` goes through an injected
  backend (the ``execution`` backend interface), and nothing launches ``ngspice``
  directly from the runner files;
* the provenance dictionaries produced through
  ``harness.legacy_provenance`` keep the exact key set, value types and values
  of the per-runner ``environment()`` helpers they replaced (a legacy copy of
  each is embedded below as the oracle).
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

SIM_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIM_DIR))

from harness import execution, legacy_provenance  # noqa: E402
from harness.derived import load_module  # noqa: E402

PJ = SIM_DIR / "period-jitter"
RUNNERS = ("in-band-bound", "random-bound", "sid-trajectory", "isf-bringup")

NGSPICE_V = (
    "******\n"
    "** ngspice-46 : Circuit level simulation program\n"
    "** The U. C. Berkeley CAD Group\n"
)


class RecordingBackend:
    """Stand-in backend: records calls, fabricates clk.dat/dig.dat."""

    name = "recording"

    def __init__(self, output="ok\n", timed_out=False, make_files=("clk.dat", "dig.dat")):
        self.output = output
        self.timed_out = timed_out
        self.make_files = make_files
        self.calls = []

    def describe(self):
        return {"backend": self.name}

    def prepare(self, points):
        pass

    def run_deck(self, deck_path, rundir, timeout_s, env=None):
        self.calls.append((Path(deck_path), Path(rundir), timeout_s))
        assert Path(deck_path).read_text()
        for name in self.make_files:
            (Path(rundir) / name).write_text("0 0\n")
        return execution.DeckRun(
            output=self.output, returncode=-1 if self.timed_out else 0,
            seconds=1.5, host="h", timed_out=self.timed_out)


def _fake_subprocess(cmd, **kw):
    cmd = list(cmd)
    out = ""
    if cmd[:2] == ["ngspice", "-v"]:
        out = NGSPICE_V
    elif cmd[0] == "git":
        out = "deadbeef\n" if "rev-parse" in cmd else (" M x\n" if "status" in cmd else "cafe\n")
    return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")


class BackendDispatch(unittest.TestCase):
    def _run(self, name, backend, *args, **kw):
        mod = load_module(PJ / name / "run.py")
        mod.BACKEND = backend
        return mod, mod.run_deck(*args, **kw)

    def test_random_bound_goes_through_backend(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            be = RecordingBackend()
            _, (el, out) = self._run("random-bound", be, "* deck\n.end\n",
                                     t / "w", t / "l" / "x.log", "clk.dat")
            self.assertEqual(len(be.calls), 1)
            self.assertEqual(be.calls[0][0].name, "deck.sp")
            self.assertEqual(el, 1.5)
            self.assertTrue((t / "l" / "x.log").is_file())

    def test_in_band_bound_backend_and_timeout(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            be = RecordingBackend()
            self._run("in-band-bound", be, "* d\n", t / "w", t / "a.log", timeout=7)
            self.assertEqual(be.calls[0][2], 7)
            slow = RecordingBackend(output="partial", timed_out=True)
            with self.assertRaises(SystemExit) as cm:
                self._run("in-band-bound", slow, "* d\n", t / "w2", t / "b.log", timeout=7)
            self.assertIn("did not finish within 7 s", str(cm.exception))
            self.assertEqual((t / "b.log").read_text(), "partial")

    def test_fatal_scan_still_refuses(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            be = RecordingBackend(output="Timestep too small\n")
            with self.assertRaises(SystemExit):
                self._run("random-bound", be, "* d\n", t / "w", t / "l.log")

    def test_isf_and_sid_go_through_backend(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            be = RecordingBackend()
            mod, el = self._run("isf-bringup", be, "* d\n", t / "w", "p.log", t / "logs")
            self.assertEqual((el, len(be.calls)), (1.5, 1))
            be2 = RecordingBackend()
            mod, (el, out) = self._run("sid-trajectory", be2, "* d\n", t / "w2",
                                       "s.log", t / "logs")
            self.assertEqual((el, out, len(be2.calls)), (1.5, "ok\n", 1))

    def test_no_direct_ngspice_launch_in_runner_files(self):
        for name in RUNNERS:
            text = (PJ / name / "run.py").read_text()
            self.assertNotRegex(text, r'\[\s*"ngspice"', name)
            self.assertNotIn("subprocess.run([\"ngspice", text, name)


# --- legacy oracles: verbatim copies of the replaced helpers ----------------

def _legacy_rb_ib(models, repo, pathspec):
    def sh(*cmd, cwd=None):
        try:
            return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd).stdout.strip()
        except OSError:
            return ""
    ver = next((ln.strip("* ").split(" :")[0] for ln in
                sh("ngspice", "-v").splitlines() if "ngspice-" in ln), "")
    return {
        "ngspice": ver, "pdk_models": str(models),
        "repo_head": sh("git", "rev-parse", "--short=8", "HEAD", cwd=repo),
        "repo_dirty": bool(sh("git", "status", "--porcelain", "--untracked-files=no",
                              *pathspec, cwd=repo)),
        "run_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def _legacy_sid(models, repo):
    ver = subprocess.run(["ngspice", "-v"], capture_output=True, text=True)
    return {
        "ngspice": ver.stdout.splitlines()[1].strip() if len(
            ver.stdout.splitlines()) > 1 else ver.stdout.strip(),
        "pdk_models": str(models),
        "repo_head": subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True).stdout.strip(),
        "vco_netlist_sha1": subprocess.run(
            ["git", "-C", str(repo), "hash-object",
             str(repo / "design" / "netlist" / "vco.spice")],
            capture_output=True, text=True).stdout.strip(),
        "python": sys.version.split()[0],
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


class RecordCompatibility(unittest.TestCase):
    def setUp(self):
        p = mock.patch("subprocess.run", side_effect=_fake_subprocess)
        p.start()
        self.addCleanup(p.stop)
        t = mock.patch("time.strftime", return_value="2026-01-01T00:00:00Z")
        t.start()
        self.addCleanup(t.stop)
        self.repo = Path("/repo")

    def test_rb_key_shape_and_values(self):
        rb = load_module(PJ / "random-bound" / "run.py")
        got = rb.environment("/pdk/models")
        want = _legacy_rb_ib("/pdk/models", rb.REPO, ("--", "design", "sim/period-jitter"))
        self.assertEqual(got, want)
        self.assertEqual(sorted(got),
                         ["ngspice", "pdk_models", "repo_dirty", "repo_head", "run_utc"])
        self.assertEqual(got["ngspice"], "ngspice-46")
        self.assertIs(type(got["repo_dirty"]), bool)

    def test_ib_key_shape_and_values(self):
        ib = load_module(PJ / "in-band-bound" / "run.py")
        got = ib.environment("/pdk/models")
        want = _legacy_rb_ib("/pdk/models", ib.REPO, ("design", "spec", "sim/period-jitter"))
        self.assertEqual(got, want)

    def test_sid_key_shape_and_values(self):
        sid = load_module(PJ / "sid-trajectory" / "run.py")
        got = sid.environment("/pdk/models")
        self.assertEqual(got, _legacy_sid("/pdk/models", sid.REPO))
        self.assertEqual(sorted(got), ["ngspice", "pdk_models", "python", "repo_head",
                                       "utc", "vco_netlist_sha1"])

    def test_isf_banner_matches_legacy_form(self):
        legacy = " ".join(NGSPICE_V.splitlines()[1].split())
        self.assertEqual(legacy_provenance.ngspice_banner("second-line-squeezed"), legacy)

    def test_pathspec_is_passed_to_git(self):
        seen = []

        def spy(cmd, **kw):
            seen.append(list(cmd))
            return _fake_subprocess(cmd, **kw)
        with mock.patch("subprocess.run", side_effect=spy):
            legacy_provenance.runner_environment("m", self.repo, ("a", "b"))
        status = next(c for c in seen if "status" in c)
        self.assertEqual(status[-3:], ["--", "a", "b"])


if __name__ == "__main__":
    unittest.main()
