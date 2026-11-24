#!/usr/bin/env python3
"""Tests for the T1 item-6 yield evidence under ``signoff/yield/`` (#1081).

Three properties, matching what ``signoff/README.md``'s "Item 6" section
claims about the chain:

* **determinism** -- ``derive.py`` re-derives the committed ``csv/`` and
  ``limits/`` outputs byte-for-byte from the committed Monte Carlo records,
  so the record -> CSV -> sample-set -> envelope chain is checkable without
  a simulator and without klt;
* **the hash chain is live** -- each committed sample-set document's
  ``derivation.csv.content_hash`` re-hashes its committed CSV, and the
  manifest's ``content_hash`` pins match the committed sample-set documents;
* **the term-1 statistic is the budget's own** -- the per-draw
  worst-of-window selection reproduces ``design/README.md``'s committed
  worst-corner figure (17.0863 % signed ``|mean| + 3sigma`` at
  ``sf``/-40C/3.63V) from the derived CSV, which is exactly the
  mis-flattening trap the old deferral in that README named: a
  ``measurements[]`` built by naive pooling would read a different number
  and fail here.

The negative-control test is two-legged. Without klt (the CI unit-test step
runs before klt is installed) it proves a perturbed per-draw record changes
the derived CSV bytes at the perturbed draw -- the input side of the chain.
With klt *and* the native extension importable (CI's post-install step, or
any host with the pinned release), it re-runs the full chain over the
perturbed record and asserts the committed **envelope** changes too.

    python3 -m unittest discover -s signoff/tests -t signoff/tests -v
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SIGNOFF_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SIGNOFF_DIR.parents[0]
YIELD_DIR = SIGNOFF_DIR / "yield"
sys.path.insert(0, str(REPO_ROOT / "lib"))

MC_RECORD_CSV = "sim/mc-cp-mismatch/corners/20260927-102154-d004d5b/mc_cp_dc.csv"
TERM1_CSV = YIELD_DIR / "csv" / "mc-cp-term1-worst-window.csv"
#: design/README.md's committed worst-corner term-1 figure (signed
#: |mean| + 3sigma at sf/-40C/3.63V), quoted to 4 decimals there.
TERM1_README_FIGURE = 17.0863
TERM1_README_CORNER = "sf_-40c_3.63v"

#: The derived artifacts derive.py owns, re-derived and byte-compared.
DERIVED_OUTPUTS = [
    "csv/mc-cp-term1-worst-window.csv",
    "csv/mc-cp-term2a-wskew.csv",
    "csv/mc-cp-terms3-4.csv",
    "csv/vco-adjacent-pair-ratio.csv",
    "limits/term1.json",
    "limits/term2a.json",
    "limits/term3.json",
    "limits/term4.json",
    "limits/vco-adjacent-pair-ratio.json",
    "digital/spec-rows.json",
]

#: sample-set document -> its source CSV (the --value it was derived with).
SAMPLES = {
    "samples/term1.json": "csv/mc-cp-term1-worst-window.csv",
    "samples/term2a.json": "csv/mc-cp-term2a-wskew.csv",
    "samples/term3.json": "csv/mc-cp-terms3-4.csv",
    "samples/term4.json": "csv/mc-cp-terms3-4.csv",
    "samples/vco-adjacent-pair-ratio.json": "csv/vco-adjacent-pair-ratio.csv",
}

SAMPLES_TO_REPORT = {
    "term1": "term1",
    "term2a": "term2a",
    "term3": "term3",
    "term4": "term4",
    "vco-adjacent-pair-ratio": "vco-adjacent-pair-ratio",
}


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def derive_into(out: Path) -> None:
    subprocess.run(
        [sys.executable, str(YIELD_DIR / "derive.py"), "--out", str(out)],
        check=True, capture_output=True, cwd=REPO_ROOT)


def _klt_available() -> bool:
    klt = shutil.which("klt")
    if not klt:
        return False
    probe = subprocess.run(
        [sys.executable, "-c", "import klt_yield_native"],
        capture_output=True)
    return probe.returncode == 0


HAVE_KLT_YIELD = _klt_available()


class DerivationTestCase(unittest.TestCase):
    """derive.py is deterministic and matches the committed bytes."""

    def test_committed_derived_outputs_reproduce_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            derive_into(out)
            for rel in DERIVED_OUTPUTS:
                committed = (YIELD_DIR / rel).read_bytes()
                fresh = (out / rel).read_bytes()
                self.assertEqual(
                    committed, fresh,
                    f"signoff/yield/{rel} does not re-derive from the "
                    f"committed records -- run "
                    f"`python3 signoff/yield/derive.py` and commit the diff, "
                    f"or re-point derive.py at the successor record")


class HashChainTestCase(unittest.TestCase):
    """The record -> CSV -> samples -> manifest pins are live, not prose."""

    def test_samples_derivation_block_rehashes_its_csv(self):
        for samples_rel, csv_rel in SAMPLES.items():
            doc = json.loads((YIELD_DIR / samples_rel).read_text())
            derivation = doc["derivation"]["csv"]
            self.assertEqual(
                derivation["path"], f"signoff/yield/{csv_rel}",
                f"{samples_rel}: derivation path is not repo-relative")
            self.assertEqual(
                derivation["content_hash"],
                sha256_file(YIELD_DIR / csv_rel),
                f"{samples_rel}: derivation hash does not match "
                f"{csv_rel} (re-run signoff/yield/run.sh)")

    def test_manifest_pins_match_the_committed_sample_sets(self):
        manifest = json.loads((SIGNOFF_DIR / "block-manifest.json").read_text())
        for entry in manifest["evidence"]["6.analog"]:
            samples = YIELD_DIR / "samples" / Path(entry["file"]).name
            self.assertEqual(
                entry["content_hash"], sha256_file(samples),
                f"{entry['file']}: manifest pin is stale")

    def test_reports_name_their_samples_and_limits(self):
        for name in SAMPLES_TO_REPORT.values():
            report = json.loads(
                (YIELD_DIR / "reports" / f"{name}.json").read_text())
            self.assertEqual(
                report["samples"],
                f"signoff/yield/samples/{name}.json",
                f"reports/{name}.json does not name its sample set "
                f"repo-relatively")
            self.assertEqual(
                report["limits"],
                f"signoff/yield/limits/{name}.json")


class Term1StatisticTestCase(unittest.TestCase):
    """The derived per-draw value is the budget table's own statistic."""

    def test_worst_corner_figure_matches_design_readme(self):
        by_corner: dict[str, list[float]] = {}
        for line in TERM1_CSV.read_text().splitlines()[1:]:
            corner, _seed, value = line.split(",")
            by_corner.setdefault(corner, []).append(float(value))
        self.assertEqual(len(by_corner), 21)
        worst_corner, worst_stat = None, -1.0
        for corner, values in by_corner.items():
            self.assertEqual(len(values), 100, f"{corner}: n != 100")
            stat = abs(statistics.fmean(values)) + 3 * statistics.stdev(values)
            if stat > worst_stat:
                worst_corner, worst_stat = corner, stat
        self.assertEqual(worst_corner, TERM1_README_CORNER)
        self.assertAlmostEqual(
            worst_stat, TERM1_README_FIGURE, delta=5e-4,
            msg="the derived term-1 samples do not reproduce "
                "design/README.md's committed worst-corner figure -- the "
                "worst-of-window selection in derive.py drifted from "
                "run.sh's verdict statistic")

    def test_limits_state_the_budget_rows_own_bounds(self):
        term1 = json.loads(
            (YIELD_DIR / "limits" / "term1.json").read_text())["measurements"]
        for entry in term1.values():
            self.assertEqual(entry["min"], -20.0)
            self.assertEqual(entry["max"], 20.0)
            self.assertEqual(entry["target_sigma"], 3.0)
            self.assertNotIn("target_yield", entry)
        vco = json.loads(
            (YIELD_DIR / "limits" / "vco-adjacent-pair-ratio.json")
            .read_text())["measurements"]
        for entry in vco.values():
            self.assertEqual(entry["min"], 1.0)
            self.assertNotIn("max", entry)


class DigitalStatementTestCase(unittest.TestCase):
    """The not_applicable projection and statement stay in lockstep."""

    def test_statement_covers_every_projected_row_exactly_once(self):
        projection = json.loads(
            (YIELD_DIR / "digital" / "spec-rows.json").read_text())
        statement = json.loads(
            (YIELD_DIR / "digital" / "item6-statement.json").read_text())
        self.assertEqual(projection["status"], "ratified")
        spec_ids = [row["id"] for row in projection["rows"]]
        statement_ids = [row["id"] for row in statement["rows"]]
        self.assertEqual(sorted(spec_ids), sorted(statement_ids))
        # spec/pll.md's header carves rows 9 and 16 out of the ratification:
        # the projection claims only ratified rows, and the statement names
        # the carve-outs separately.
        unratified = [row["id"] for row in statement["unratified_rows"]]
        self.assertEqual(sorted(unratified), ["16", "9"])
        self.assertFalse(set(unratified) & set(spec_ids))
        spec_text = " ".join(
            (REPO_ROOT / "spec/pll.md").read_text().split("\n## ", 1)[0]
            .split())
        self.assertIn("remain unratified", spec_text)
        self.assertIn("(row 9)", spec_text)
        self.assertIn("(row 16)", spec_text)
        for row in statement["rows"]:
            self.assertTrue(row.get("class"), f"row {row['id']}: no class")
            self.assertTrue(row.get("reason"), f"row {row['id']}: no reason")


class NegativeControlTestCase(unittest.TestCase):
    """A perturbed per-draw input must move the committed evidence.

    Without klt this proves the input side: the derived CSV changes at the
    perturbed draw (so the committed sample-set's derivation hash -- and
    therefore the envelope the manifest pins -- cannot survive it). With
    klt and the native extension it proves the whole chain, by regenerating
    the sample-set document and the envelope over the perturbed record and
    diffing both against the committed bytes.
    """

    def _perturbed_tree(self, tmp: Path) -> Path:
        """A scratch copy of the yield-relevant tree with one mc_cp_dc draw
        (sf/-40C/3.63V, seed 7, the 0.9 V point) nudged, plus a patched
        derive.py that reads the perturbed record instead of the committed
        one. Returns derive.py's output directory."""
        tree = tmp / "tree"
        mc_dir = tree / "sim/mc-cp-mismatch/corners/perturbed"
        mc_dir.mkdir(parents=True)
        lines = (REPO_ROOT / MC_RECORD_CSV).read_text().splitlines()
        target = next(
            i for i, ln in enumerate(lines)
            if ln.startswith(f"{TERM1_README_CORNER},7,0.9,"))
        corner, seed, vctrl, iup, idn, _mism = lines[target].split(",")
        lines[target] = ",".join([corner, seed, vctrl, iup, idn, "99.0"])
        (mc_dir / "mc_cp_dc.csv").write_text("\n".join(lines) + "\n")
        for sibling in ("mc_cp_switch.csv", "mc_pfd_cp.csv"):
            shutil.copy(
                (REPO_ROOT / MC_RECORD_CSV).parent / sibling,
                mc_dir / sibling)
        vco_dir = tree / "sim/vco-tuning-range/corners/20260927-220631-546a397"
        vco_dir.mkdir(parents=True)
        shutil.copy(
            REPO_ROOT / vco_dir.relative_to(tree) / "mismatch.csv",
            vco_dir / "mismatch.csv")
        patched = tmp / "derive.py"
        patched.write_text(
            (YIELD_DIR / "derive.py").read_text()
            .replace("REPO_ROOT = YIELD_DIR.parents[1]",
                     f"REPO_ROOT = Path({json.dumps(str(REPO_ROOT))})")
            .replace(f'MC_RECORD = "{MC_RECORD_CSV.rsplit("/", 1)[0]}"',
                     f'MC_RECORD = {json.dumps(str(mc_dir))}'))
        out = tmp / "out"
        subprocess.run(
            [sys.executable, str(patched), "--out", str(out)],
            check=True, capture_output=True)
        return out

    def test_perturbed_draw_changes_the_derived_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = self._perturbed_tree(Path(tmp))
            committed = TERM1_CSV.read_text().splitlines()
            fresh = (out / "csv" / "mc-cp-term1-worst-window.csv"
                     ).read_text().splitlines()
            self.assertNotEqual(
                committed, fresh,
                "a perturbed per-draw record left the derived term-1 CSV "
                "byte-identical")
            changed = [i for i, (a, b) in enumerate(zip(committed, fresh))
                       if a != b]
            self.assertTrue(
                any(committed[i].startswith(f"{TERM1_README_CORNER},7,")
                    for i in changed),
                "the perturbed draw did not change in the derived CSV")

    @unittest.skipUnless(
        HAVE_KLT_YIELD,
        "klt with the klt-yield-native extension is not on this host "
        "(CI runs this class in its post-klt-install step)")
    def test_sample_sets_rederive_byte_identically_through_yield_csv(self):
        cases = [
            ("term1", "mism_worst_pct", "corner", "%"),
            ("term2a", "wskew_s", "corner", "s"),
            ("term3", "qnet0_c", "corner", "C"),
            ("term4", "t_offset_s", "corner", "s"),
            ("vco-adjacent-pair-ratio", "ratio", "point_id", ""),
        ]
        for name, value, group, unit in cases:
            csv_name = Path(SAMPLES[f"samples/{name}.json"]).name
            argv = ["klt", "yield-csv", f"signoff/yield/csv/{csv_name}",
                    "--group-by", group, "--value", value,
                    "--draw-col", "seed"]
            if unit is not None:
                argv += ["--unit", unit]
            argv += ["--format", "json"]
            fresh = subprocess.run(
                argv, check=True, capture_output=True,
                cwd=REPO_ROOT).stdout
            committed = (YIELD_DIR / "samples" / f"{name}.json").read_bytes()
            self.assertEqual(
                committed, fresh,
                f"signoff/yield/samples/{name}.json does not re-derive "
                f"through klt yield-csv from its committed CSV")

    @unittest.skipUnless(
        HAVE_KLT_YIELD,
        "klt with the klt-yield-native extension is not on this host "
        "(CI runs this class in its post-klt-install step)")
    def test_every_committed_envelope_regenerates_byte_identically(self):
        """Positive comparison: each committed envelope equals a clean
        `klt yield` run over its committed sample set and limits. Exit 3 is
        a completed failing measurement (the report is still written)."""
        for name in (Path(k).stem for k in SAMPLES):
            run = subprocess.run(
                ["klt", "yield", f"signoff/yield/samples/{name}.json",
                 "--limits", f"signoff/yield/limits/{name}.json",
                 "--format", "json"],
                capture_output=True, cwd=REPO_ROOT)
            self.assertIn(run.returncode, (0, 3), run.stderr.decode())
            committed = (YIELD_DIR / "reports" / f"{name}.json").read_bytes()
            self.assertEqual(
                committed, run.stdout,
                f"signoff/yield/reports/{name}.json does not regenerate "
                f"from its committed sample set and limits")

    @unittest.skipUnless(
        HAVE_KLT_YIELD,
        "klt with the klt-yield-native extension is not on this host "
        "(CI runs this class in its post-klt-install step)")
    def test_perturbed_draw_changes_the_committed_envelope(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = self._perturbed_tree(Path(tmp))
            csv = out / "csv" / "mc-cp-term1-worst-window.csv"
            samples = out / "samples" / "term1.json"
            samples.parent.mkdir(parents=True, exist_ok=True)
            samples.write_bytes(subprocess.run(
                ["klt", "yield-csv", str(csv),
                 "--group-by", "corner", "--value", "mism_worst_pct",
                 "--draw-col", "seed", "--unit", "%", "--format", "json"],
                check=True, capture_output=True, cwd=REPO_ROOT).stdout)
            run = subprocess.run(
                ["klt", "yield", str(samples), "--format", "json",
                 "--limits", str(YIELD_DIR / "limits" / "term1.json")],
                capture_output=True, cwd=REPO_ROOT)
            # A failing status exits non-zero but still writes the report;
            # the negative control only claims the ENVELOPE moves.
            self.assertIn(run.returncode, (0, 3), run.stderr.decode())
            fresh = json.loads(run.stdout)
            committed = json.loads(
                (YIELD_DIR / "reports" / "term1.json").read_text())
            self.assertNotEqual(
                fresh["measurements"], committed["measurements"],
                "a perturbed per-draw record left the term-1 envelope's "
                "measurements identical -- the negative control cannot "
                "detect a changed campaign")


if __name__ == "__main__":
    unittest.main()
