"""The Monte Carlo campaigns' committed negative control (#602), off ngspice.

T1/bronze checklist item 6 (`#127`) asks every statistical claim for a
"deterministic negative control". Until #602 both mismatch campaigns satisfied
that in PROSE -- a record's Methodology field described a manual re-check that
was never committed, so nothing could re-run it and nothing would notice if it
stopped being true. This module is the half of the fix that makes the control
a *gate* rather than a second, better-formatted description:

1. **Both campaigns have a committed control artifact at all**, and every
   (stage, corner) in it passes all three legs. Derived here in Python,
   independently of `sim/lib/simenv.sh`'s awk -- two implementations that agree
   is evidence; one implementation grading its own output is not.
2. **The shell helper agrees with this module**, verdict for verdict, so
   `run.sh --recheck-control` (the path a human or CI actually runs) cannot
   drift away from what is asserted here.
3. **The checker can FAIL.** Synthetic CSVs that break each leg in turn must be
   reported as failures. A control check that cannot report a failure is
   decoration.
4. **Each record's own control table matches the CSV it claims to be derived
   from** -- the record text cannot drift from the bytes.
5. **The control stage is still wired into the full-campaign path**, and
   `tb_vco_mismatch.sp` still exposes the `mc_mismatch` handle WITHOUT a
   default -- the property that makes a forgotten switch a loud parse error
   instead of a silent mismatch-free "Monte Carlo" sample.

No PDK, no ngspice, no network.
"""

from __future__ import annotations

import csv
import io
import re
import subprocess
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
REPO = SIM_DIR.parent
SIMENV = SIM_DIR / "lib" / "simenv.sh"

# The five run tags, mirroring sim/lib/simenv.sh's SIMENV_CONTROL_RUN_* set.
R_MC1_A1 = "mc1_seedA_run1"
R_MC1_A2 = "mc1_seedA_run2"
R_MC1_B = "mc1_seedB"
R_MC0_A = "mc0_seedA"
R_MC0_B = "mc0_seedB"
RUNS = (R_MC1_A1, R_MC1_A2, R_MC1_B, R_MC0_A, R_MC0_B)

HEADER = "stage,corner,run,sw_stat_mismatch,rndseed,metric,value"

CAMPAIGNS = {
    "mc-cp-mismatch": SIM_DIR / "mc-cp-mismatch",
    "vco-tuning-range": SIM_DIR / "vco-tuning-range",
}


def _control_csvs(exp_dir: Path) -> list[Path]:
    """Every committed negative_control.csv under one experiment directory."""
    return sorted((exp_dir / "corners").glob("*/negative_control.csv"))


def _rows(csv_path: Path) -> list[dict]:
    text = csv_path.read_text()
    body = [ln for ln in text.splitlines() if not ln.startswith("#")]
    if not body:
        raise AssertionError(f"{csv_path}: no non-comment lines")
    if body[0] != HEADER:
        raise AssertionError(f"{csv_path}: header is {body[0]!r}, expected {HEADER!r}")
    return list(csv.DictReader(io.StringIO("\n".join(body))))


def derive(csv_path: Path) -> dict:
    """{(stage, corner): (repeat, vary, gate, n_metrics, n_varied)}.

    An independent re-implementation of sim/lib/simenv.sh's awk, deliberately
    NOT a wrapper around it. Values are compared as TEXT, exactly as the shell
    side does: a tolerance would let a drifting draw keep passing.
    """
    vals: dict = {}
    metrics: dict = {}
    for r in _rows(csv_path):
        key = (r["stage"], r["corner"])
        vals[(key, r["run"], r["metric"])] = r["value"]
        metrics.setdefault(key, [])
        if r["metric"] not in metrics[key]:
            metrics[key].append(r["metric"])

    out = {}
    for key, mets in metrics.items():
        if any((key, run, m) not in vals for run in RUNS for m in mets):
            out[key] = ("INCOMPLETE", "INCOMPLETE", "INCOMPLETE", len(mets), 0)
            continue
        rep = all(vals[(key, R_MC1_A1, m)] == vals[(key, R_MC1_A2, m)] for m in mets)
        varied = sum(1 for m in mets if vals[(key, R_MC1_A1, m)] != vals[(key, R_MC1_B, m)])
        gate = all(vals[(key, R_MC0_A, m)] == vals[(key, R_MC0_B, m)] for m in mets)
        out[key] = (
            "PASS" if rep else "FAIL",
            "PASS" if varied else "FAIL",
            "PASS" if gate else "FAIL",
            len(mets),
            varied,
        )
    return out


def shell_verdicts(csv_path: Path):
    """(exit_status, {(stage, corner): (repeat, vary, gate, n, varied)}) from simenv.sh."""
    proc = subprocess.run(
        ["bash", "-c", f'. "{SIMENV}" && simenv_control_verdicts "{csv_path}"'],
        capture_output=True,
        text=True,
    )
    parsed = {}
    for line in proc.stdout.splitlines():
        f = line.split()
        if len(f) != 7:
            continue
        parsed[(f[0], f[1])] = (f[2], f[3], f[4], int(f[5]), int(f[6]))
    return proc.returncode, parsed


class ControlArtifactExists(unittest.TestCase):
    """The gap #602 closed: a campaign with no committed control has no (c)."""

    def test_every_mc_campaign_has_one(self):
        for name, exp in CAMPAIGNS.items():
            with self.subTest(campaign=name):
                found = _control_csvs(exp)
                self.assertTrue(
                    found,
                    f"{name} has no committed corners/*/negative_control.csv -- item 6's "
                    "negative control would again rest on a record's prose",
                )

    def test_artifact_carries_all_five_runs_everywhere(self):
        for name, exp in CAMPAIGNS.items():
            for csv_path in _control_csvs(exp):
                with self.subTest(campaign=name, artifact=csv_path.name):
                    for key, (_r, _v, _g, _n, _nv) in derive(csv_path).items():
                        self.assertNotEqual(
                            _r, "INCOMPLETE", f"{key} is missing one of the five runs"
                        )


class ControlPasses(unittest.TestCase):
    def test_all_legs_pass(self):
        for name, exp in CAMPAIGNS.items():
            for csv_path in _control_csvs(exp):
                verdicts = derive(csv_path)
                self.assertTrue(verdicts, f"{csv_path} derived no (stage, corner) rows")
                for key, (rep, var, gate, n_met, n_var) in verdicts.items():
                    with self.subTest(campaign=name, point=key):
                        self.assertEqual(rep, "PASS", "same seed did not reproduce")
                        self.assertEqual(var, "PASS", "a different seed changed nothing")
                        self.assertEqual(gate, "PASS", "sw_stat_mismatch=0 was seed-dependent")
                        self.assertGreater(n_met, 0)
                        self.assertGreater(n_var, 0)

    def test_shell_helper_agrees(self):
        for name, exp in CAMPAIGNS.items():
            for csv_path in _control_csvs(exp):
                with self.subTest(campaign=name, artifact=csv_path.name):
                    rc, shell = shell_verdicts(csv_path)
                    self.assertEqual(shell, derive(csv_path))
                    self.assertEqual(rc, 0, "simenv_control_verdicts must exit 0 on a clean control")


class CheckerCanFail(unittest.TestCase):
    """A gate that cannot report a failure is not a gate."""

    BASE = [
        # stage,corner,run,sw_stat_mismatch,rndseed,metric,value
        ("s", "c", R_MC1_A1, "1", "1", "m", "1.0"),
        ("s", "c", R_MC1_A2, "1", "1", "m", "1.0"),
        ("s", "c", R_MC1_B, "1", "97", "m", "2.0"),
        ("s", "c", R_MC0_A, "0", "1", "m", "3.0"),
        ("s", "c", R_MC0_B, "0", "97", "m", "3.0"),
    ]

    def _write(self, rows):
        import tempfile

        fh = tempfile.NamedTemporaryFile(
            "w", suffix=".csv", delete=False, prefix="negctl-"
        )
        fh.write("# synthetic fixture -- sim/tests/test_negative_control.py\n")
        fh.write(HEADER + "\n")
        for r in rows:
            fh.write(",".join(r) + "\n")
        fh.close()
        self.addCleanup(lambda p=fh.name: Path(p).unlink(missing_ok=True))
        return Path(fh.name)

    def test_clean_fixture_passes_both_implementations(self):
        p = self._write(self.BASE)
        self.assertEqual(derive(p)[("s", "c")][:3], ("PASS", "PASS", "PASS"))
        rc, shell = shell_verdicts(p)
        self.assertEqual(rc, 0)
        self.assertEqual(shell[("s", "c")][:3], ("PASS", "PASS", "PASS"))

    def test_nondeterministic_same_seed_is_caught(self):
        rows = [list(r) for r in self.BASE]
        rows[1][6] = "1.0000001"  # same seed, different answer
        p = self._write([tuple(r) for r in rows])
        self.assertEqual(derive(p)[("s", "c")][0], "FAIL")
        rc, shell = shell_verdicts(p)
        self.assertEqual(rc, 1)
        self.assertEqual(shell[("s", "c")][0], "FAIL")

    def test_seed_that_changes_nothing_is_caught(self):
        """The leg the prose control never had: an inert metric must not pass."""
        rows = [list(r) for r in self.BASE]
        rows[2][6] = "1.0"  # different seed, identical answer
        p = self._write([tuple(r) for r in rows])
        self.assertEqual(derive(p)[("s", "c")][1], "FAIL")
        rc, shell = shell_verdicts(p)
        self.assertEqual(rc, 1)
        self.assertEqual(shell[("s", "c")][1], "FAIL")

    def test_ungated_draw_is_caught(self):
        rows = [list(r) for r in self.BASE]
        rows[4][6] = "3.5"  # sw_stat_mismatch=0 but the seed still moved it
        p = self._write([tuple(r) for r in rows])
        self.assertEqual(derive(p)[("s", "c")][2], "FAIL")
        rc, shell = shell_verdicts(p)
        self.assertEqual(rc, 1)
        self.assertEqual(shell[("s", "c")][2], "FAIL")

    def test_missing_run_is_incomplete_not_silently_skipped(self):
        p = self._write(self.BASE[:-1])
        self.assertEqual(derive(p)[("s", "c")][0], "INCOMPLETE")
        rc, shell = shell_verdicts(p)
        self.assertEqual(rc, 1)
        self.assertEqual(shell[("s", "c")][0], "INCOMPLETE")

    def test_empty_artifact_is_a_failure(self):
        p = self._write([])
        rc, _ = shell_verdicts(p)
        self.assertEqual(rc, 1, "a control with no rows must not pass")


class RecordTextMatchesBytes(unittest.TestCase):
    """A record's control table is derived; it must not drift from its CSV."""

    ROW = re.compile(
        r"^\s*\|\s*(?P<stage>[\w.+-]+)\s*\|\s*`(?P<corner>[^`]+)`\s*\|"
        r"\s*\*\*(?P<rep>PASS|FAIL|INCOMPLETE)\*\*\s*\|"
        r"\s*\*\*(?P<var>PASS|FAIL|INCOMPLETE)\*\*\s*\|"
        r"\s*\*\*(?P<gate>PASS|FAIL|INCOMPLETE)\*\*\s*\|"
        r"\s*(?P<nvar>\d+)\s+of\s+(?P<nmet>\d+)\s*\|\s*$"
    )

    def test_each_record_table_matches_its_own_artifact(self):
        checked = 0
        for name, exp in CAMPAIGNS.items():
            for csv_path in _control_csvs(exp):
                rid = csv_path.parent.name
                record = exp / "records" / f"{rid}.md"
                with self.subTest(campaign=name, record=rid):
                    self.assertTrue(
                        record.is_file(),
                        f"{csv_path} has no records/{rid}.md -- an uncitable artifact",
                    )
                    table = {}
                    for line in record.read_text().splitlines():
                        m = self.ROW.match(line)
                        if m:
                            table[(m["stage"], m["corner"])] = (
                                m["rep"],
                                m["var"],
                                m["gate"],
                                int(m["nmet"]),
                                int(m["nvar"]),
                            )
                    self.assertEqual(
                        table,
                        derive(csv_path),
                        f"{record.name}'s control table disagrees with {csv_path.name}",
                    )
                    checked += 1
        self.assertGreater(checked, 0)


class StaysWired(unittest.TestCase):
    """The regression half: a future edit must not quietly drop the stage."""

    SCRIPTS = (
        SIM_DIR / "mc-cp-mismatch" / "testbench" / "run.sh",
        SIM_DIR / "vco-tuning-range" / "testbench" / "run_mismatch.sh",
    )

    def test_full_campaign_path_still_emits_a_control(self):
        for script in self.SCRIPTS:
            with self.subTest(script=script.name):
                text = script.read_text()
                self.assertIn("emit_control_evidence", text)
                # Not only defined -- actually called outside the --control branch,
                # i.e. at least twice in the file (standalone + full campaign).
                self.assertGreaterEqual(
                    text.count("emit_control_evidence"), 3, "definition + both call sites"
                )
                self.assertIn("--recheck-control", text)

    def test_simenv_exposes_the_shared_schema(self):
        text = SIMENV.read_text()
        for name in (
            "SIMENV_CONTROL_HEADER",
            "simenv_control_verdicts",
            "simenv_control_report",
            "simenv_control_md_rows",
        ):
            self.assertIn(name, text)
        self.assertIn(HEADER, text)

    def test_vco_deck_keeps_the_mc_mismatch_handle_without_a_default(self):
        """A pinned literal made the `gate` leg unrunnable; a default would make
        a forgotten switch silent instead of loud."""
        deck = SIM_DIR / "vco-tuning-range" / "testbench" / "tb_vco_mismatch.sp"
        body = [
            ln.strip()
            for ln in deck.read_text().splitlines()
            if ln.strip().startswith(".param")
        ]
        self.assertIn(".param sw_stat_mismatch='mc_mismatch'", body)
        self.assertNotIn(".param sw_stat_mismatch=1", body)
        self.assertFalse(
            [ln for ln in body if ln.startswith(".param mc_mismatch")],
            "mc_mismatch must have NO default in the deck: an invocation that "
            "forgets it has to fail at parse time, not fall through to "
            "design.ngspice's sw_stat_mismatch=0 and mint a mismatch-free sample",
        )

    def test_every_script_that_uses_that_deck_passes_the_handle(self):
        tb = SIM_DIR / "vco-tuning-range" / "testbench"
        users = [
            p
            for p in sorted(tb.glob("*.sh"))
            if "tb_vco_mismatch.sp" in p.read_text() and "simenv_run_deck" in p.read_text()
        ]
        self.assertTrue(users, "expected at least run_mismatch.sh and run_band0_worst_corner.sh")
        for script in users:
            with self.subTest(script=script.name):
                self.assertIn("mc_mismatch=", script.read_text())


if __name__ == "__main__":
    unittest.main()
