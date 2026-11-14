"""The old-vs-new record comparator behind the re-pin delta tables (#825).

Covers the contract in ``sim/lib/record_delta.py``: it reads a committed
evidence record's own Result tables, and it must not quietly mis-report a
movement, because the tables it prints are what a reviewer reads instead of
two 45-row records side by side.

The cases worth pinning are the ones where a wrong answer looks plausible:

- a verdict flip must surface as a finding, not vanish into a numeric table;
- a changed `limits` entry must surface too -- a measurement can sit still
  while the bound it is graded against moves, and that is the same class of
  drift `sim/lib/check-record-supersession.sh` exists to catch;
- a measurement whose OLD value is zero has no meaningful *relative* change,
  so it must contribute to the absolute column only rather than dividing by
  zero or silently reading 0 % when the absolute step is large. This is not
  hypothetical: it is exactly the moscap `leak_*` family (#932), where the
  real movement is 0 -> about -1 nA and a naive relative figure would report
  it as no change at all;
- a record pair whose measurement coverage differs (the #40 harness migration
  both dropped and added columns) must list the difference rather than
  intersect it away in silence.

Run:  python3 -m unittest discover -s sim/tests -v
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SIM_DIR.parent
sys.path.insert(0, str(SIM_DIR / "lib"))

import record_delta  # noqa: E402


def _record(topologies, spread_rows, *, multi_topology=True):
    """Render a minimal record in the shape sim/harness/report.py emits.

    ``topologies`` is ``{name: (columns, {corner: [cells...]})}``; the last
    column is always ``pass/fail``, as the harness writes it.
    """
    out = ["# Record 20260101-000000-deadbee", "", "- **Result**:", ""]
    for name, (cols, rows) in topologies.items():
        out.append(f"  **{name}** — prose caption the parser must skip")
        out.append("")
        out.append("  | corner-id | " + " | ".join(cols) + " | pass/fail |")
        out.append("  |---|" + "---|" * (len(cols) + 1))
        for corner, cells in rows.items():
            out.append(f"  | `{corner}` | " + " | ".join(cells) + " |")
        out.append("")
    out.append("  Spread across the grid:")
    out.append("")
    if multi_topology:
        out.append("  | topology | measurement | min | max | mean | spread % | limits |")
        out.append("  |---|---|---|---|---|---|---|")
        for topo, meas, limit in spread_rows:
            out.append(f"  | `{topo}` | `{meas}` | 0 | 1 | 0.5 | 1 | {limit} |")
    else:
        out.append("  | measurement | min | max | mean | spread % | limits |")
        out.append("  |---|---|---|---|---|---|")
        for _topo, meas, limit in spread_rows:
            out.append(f"  | `{meas}` | 0 | 1 | 0.5 | 1 | {limit} |")
    return "\n".join(out) + "\n"


class ParsesTheRecordTablesTheHarnessActuallyWrites(unittest.TestCase):
    def test_reads_values_verdicts_and_limits_keyed_by_topology(self):
        text = _record(
            {"ring1x": (["r1_fosc"], {"typical_27c_3.30v": ["1.5e+09", "PASS"]})},
            [("ring1x", "r1_fosc", "min_spread_pct=5")],
        )
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "r.md"
            p.write_text(text)
            values, limits = record_delta.parse_record(p)
        self.assertEqual(values[("ring1x", "r1_fosc", "typical_27c_3.30v")], 1.5e9)
        self.assertEqual(values[("ring1x", "pass/fail", "typical_27c_3.30v")], "PASS")
        self.assertEqual(limits[("ring1x", "r1_fosc")], "min_spread_pct=5")

    def test_single_topology_spread_table_still_yields_limits(self):
        """harness-selftest's spread table has no topology column."""
        text = _record(
            {"": (["idsat_n"], {"typical_27c_3.30v": ["-1e-03", "PASS"]})},
            [("", "idsat_n", "min_spread_pct=5")],
            multi_topology=False,
        )
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "r.md"
            p.write_text(text)
            _values, limits = record_delta.parse_record(p)
        self.assertEqual(limits[("", "idsat_n")], "min_spread_pct=5")

    def test_a_non_numeric_cell_is_dropped_not_coerced_to_zero(self):
        """Records render `—` for an absent value; 0 would be a false reading."""
        self.assertIsNone(record_delta._num("—"))
        self.assertIsNone(record_delta._num(""))
        self.assertIsNone(record_delta._num("PASS"))
        self.assertEqual(record_delta._num(" `1.25e-09` "), 1.25e-09)


class ReportsMovementAgainstTheOldRecordAsTheBaseline(unittest.TestCase):
    def _compare(self, old_text, new_text):
        with tempfile.TemporaryDirectory() as d:
            o, n = Path(d) / "old.md", Path(d) / "new.md"
            o.write_text(old_text)
            n.write_text(new_text)
            return record_delta.compare(o, n)

    def test_identical_records_report_no_movement_and_no_findings(self):
        text = _record(
            {"ring1x": (["r1_fosc"], {"typical_27c_3.30v": ["1.5e+09", "PASS"]})},
            [("ring1x", "r1_fosc", "—")],
        )
        lines, findings = self._compare(text, text)
        body = "\n".join(lines)
        self.assertEqual(findings, 0)
        self.assertIn("| 0 | 0 |", body.replace("`—`", "—"))
        self.assertIn("unchanged on all 1 graded rows", body)

    def test_a_zero_baseline_contributes_to_the_absolute_column_only(self):
        """The moscap leak_* case (#932): 0 -> -1 nA must not read as no change."""
        old = _record(
            {"cn": (["leak_cn"], {"typical_27c_3.30v": ["0", "PASS"]})},
            [("cn", "leak_cn", "—")],
        )
        new = _record(
            {"cn": (["leak_cn"], {"typical_27c_3.30v": ["-9.086050e-10", "PASS"]})},
            [("cn", "leak_cn", "—")],
        )
        lines, findings = self._compare(old, new)
        row = next(l for l in lines if "leak_cn" in l)
        self.assertIn("9.086050e-10", row, "the absolute step must be reported")
        self.assertEqual(findings, 0, "no verdict flipped and no limit moved")

    def test_a_verdict_flip_is_a_finding(self):
        old = _record(
            {"cn": (["c330_cn"], {"typical_27c_3.30v": ["1.0", "PASS"]})},
            [("cn", "c330_cn", "min=0")],
        )
        new = _record(
            {"cn": (["c330_cn"], {"typical_27c_3.30v": ["1.0", "FAIL"]})},
            [("cn", "c330_cn", "min=0")],
        )
        lines, findings = self._compare(old, new)
        body = "\n".join(lines)
        self.assertEqual(findings, 1)
        self.assertIn("verdict flips", body)
        self.assertIn("| `cn` | `typical_27c_3.30v` | PASS | FAIL |", body)

    def test_a_changed_stated_limit_is_a_finding_even_when_values_sit_still(self):
        old = _record(
            {"cn": (["cvr_cn"], {"typical_27c_3.30v": ["1.0", "PASS"]})},
            [("cn", "cvr_cn", "min=0.99")],
        )
        new = _record(
            {"cn": (["cvr_cn"], {"typical_27c_3.30v": ["1.0", "PASS"]})},
            [("cn", "cvr_cn", "min=0.90")],
        )
        lines, findings = self._compare(old, new)
        body = "\n".join(lines)
        self.assertEqual(findings, 1)
        self.assertIn("Stated limits changed", body)
        self.assertIn("min=0.99", body)
        self.assertIn("min=0.90", body)

    def test_coverage_differences_are_listed_not_silently_intersected(self):
        old = _record(
            {"cp": (["vcomp_ro50"], {"typical_27c_3.30v": ["0.5", "PASS"]})},
            [("cp", "vcomp_ro50", "—")],
        )
        new = _record(
            {"cp": (["chd0v20"], {"typical_27c_3.30v": ["0.99", "PASS"]})},
            [("cp", "chd0v20", "—")],
        )
        lines, _findings = self._compare(old, new)
        body = "\n".join(lines)
        self.assertIn("Measurement coverage differs", body)
        self.assertIn("vcomp_ro50", body)
        self.assertIn("chd0v20", body)


class RunsAsACliOverTheCommittedRecords(unittest.TestCase):
    """The delta tables in sim/REPIN-DELTAS-f6eeac7-devchar.md are regenerated
    by the commands that document names, so those commands must keep working
    against the records on the tree."""

    PAIRS = [
        ("devchar-cp", "20260801-102353-79f398e", "20261114-012159-cd5e8ce"),
        ("devchar-passives", "20260801-102454-79f398e", "20261114-005851-658a7fd"),
        ("devchar-delay", "20260801-084448-01b0db8", "20261114-010350-72be45d"),
        ("harness-selftest", "20260731-151931-58c52d9", "20261114-014020-a21aa0c"),
    ]

    def test_every_documented_regeneration_command_succeeds(self):
        for slug, old, new in self.PAIRS:
            with self.subTest(slug=slug):
                o = REPO_ROOT / f"sim/{slug}/records/{old}.md"
                n = REPO_ROOT / f"sim/{slug}/records/{new}.md"
                self.assertTrue(o.is_file(), f"{o} missing")
                self.assertTrue(n.is_file(), f"{n} missing")
                r = subprocess.run(
                    [sys.executable, "sim/lib/record_delta.py", str(o), str(n)],
                    cwd=REPO_ROOT, capture_output=True, text=True,
                )
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertIn(f"`{new}` vs `{old}`", r.stdout)
                self.assertIn("| topology | measurement | limit |", r.stdout)

    def test_no_re_qualified_bench_flipped_a_verdict_or_moved_a_limit(self):
        """#825's third acceptance criterion, asserted rather than asserted-to.

        If a future re-run does flip one, this fails and the claim in
        sim/REPIN-DELTAS-f6eeac7-devchar.md stops being true at the same
        moment -- which is the point.
        """
        for slug, old, new in self.PAIRS:
            with self.subTest(slug=slug):
                _lines, findings = record_delta.compare(
                    REPO_ROOT / f"sim/{slug}/records/{old}.md",
                    REPO_ROOT / f"sim/{slug}/records/{new}.md",
                )
                self.assertEqual(
                    findings, 0,
                    f"{slug}: the delta document claims 0 findings for this pair",
                )

    def test_a_missing_record_is_an_error_not_an_empty_table(self):
        r = subprocess.run(
            [sys.executable, "sim/lib/record_delta.py",
             "sim/devchar-cp/records/does-not-exist.md",
             "sim/devchar-cp/records/20261114-012159-cd5e8ce.md"],
            cwd=REPO_ROOT, capture_output=True, text=True,
        )
        self.assertEqual(r.returncode, 2)
        self.assertIn("no such record", r.stderr)


if __name__ == "__main__":
    unittest.main()
