"""The closed-loop re-pin delta document (#828, increment `reference-spur`).

`sim/REPIN-DELTAS-f6eeac7-closed-loop.md` makes claims a reader cannot check
by eye, and each is asserted here instead of trusted:

- **Its delta table is generated, not typed.** The fenced `record_delta.py`
  command must keep working against the committed records and its output must
  still be what the document shows.

- **The three per-corner verdict flips are exactly the ones stated.**
  `typical` PASS -> FAIL on `spur_dbc_200m`; `ff` and `sf` FAIL -> PASS. Unlike
  the sibling groups this pair deliberately carries findings, so it cannot be
  added to `test_record_delta.py::PAIRS` (that test asserts zero findings);
  it lives in this dedicated module instead, shaped like
  `test_repin_deltas_lock_divider.py`.

- **The overlap-point figures agree between the document and the record.**
  The document's side-by-side table and the new record's `SIMULATOR EXPOSURE`
  bullet state the same numbers for the same corner; both are asserted, plus
  the 6.06 dB simulator-vs-PDK arithmetic the prose derives from them.

Scope across #828: the document grows one section per directory increment.
Later increments should extend this module (new pairs, new flip assertions)
rather than add siblings; the regeneration test already iterates every
command the document prints, so an appended section is covered for table
drift automatically. Tests here read committed files only; no simulator runs.

Run:  python3 -m unittest discover -s sim/tests -v
"""

from __future__ import annotations

import re
import subprocess
import sys
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SIM_DIR.parent
sys.path.insert(0, str(SIM_DIR / "lib"))

import record_delta  # noqa: E402

DOC = SIM_DIR / "REPIN-DELTAS-f6eeac7-closed-loop.md"
OLD_ID = "20260816-132150-5f405e7"
NEW_ID = "20261118-212630-1649033"
OLD_REC = SIM_DIR / "reference-spur" / "records" / f"{OLD_ID}.md"
NEW_REC = SIM_DIR / "reference-spur" / "records" / f"{NEW_ID}.md"

REGEN = re.compile(
    r"python3 sim/lib/record_delta\.py \\\n"
    r"\s+(sim/[\w.-]+/records/[\d-]+-\w+\.md) \\\n"
    r"\s+(sim/[\w.-]+/records/[\d-]+-\w+\.md)\n"
)

#: corner-id -> (old verdict is PASS, new verdict is PASS)
EXPECTED_FLIPS = {
    "typical_27c_3.30v_vs1p795": (True, False),
    "ff_-40c_3.63v_vs2p430": (False, True),
    "sf_-40c_2.97v_vs1p677": (False, True),
}

#: (spur_dbc, spur_dbc_200m, spur_tie_dbc, tie_pk_ps) at the overlap corner.
OVERLAP = {
    "predecessor": ("-58.36", "-55.87", "-56.13", "3.31"),
    "ngspice-46 f6eeac7": ("-62.01", "-59.51", "-58.12", "2.63"),
    "ngspice-47 f6eeac7": ("-55.95", "-53.45", "-53.94", "4.26"),
}


def _doc_text() -> str:
    return DOC.read_text(encoding="utf-8")


def _compare():
    return record_delta.compare(OLD_REC, NEW_REC)


def _flip_rows(lines):
    """(corner, old, new) from the 'Per-corner verdict flips' table."""
    rows, on = [], False
    for ln in lines:
        if ln.startswith("**Per-corner verdict flips**"):
            on = True
            continue
        if on and ln.startswith("| `"):
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if len(cells) == 4:
                rows.append((cells[1].strip("`"), cells[2], cells[3]))
        elif on and rows and not ln.strip().startswith("|"):
            break
    return rows


class TheDocumentsTablesAreGenerated(unittest.TestCase):
    def test_the_document_and_records_exist_and_a_command_is_named(self):
        for p in (DOC, OLD_REC, NEW_REC):
            self.assertTrue(p.is_file(), f"{p} missing")
        self.assertTrue(REGEN.findall(_doc_text()),
                        "no regeneration command found in the document")

    def test_every_documented_regeneration_command_reproduces_its_table(self):
        text = _doc_text()
        for old_rel, new_rel in REGEN.findall(text):
            with self.subTest(pair=f"{old_rel} -> {new_rel}"):
                self.assertTrue((REPO_ROOT / old_rel).is_file(), old_rel)
                self.assertTrue((REPO_ROOT / new_rel).is_file(), new_rel)
                r = subprocess.run(
                    [sys.executable, "sim/lib/record_delta.py", old_rel, new_rel],
                    cwd=REPO_ROOT, capture_output=True, text=True,
                )
                self.assertEqual(r.returncode, 0, r.stderr)
                # The generator's own `###` heading is replaced by the
                # document's section heading, so headings are not compared.
                missing = [ln for ln in r.stdout.splitlines()
                           if ln.strip() and not ln.startswith("#")
                           and ln not in text]
                self.assertEqual(
                    missing[:3], [],
                    f"{new_rel}: the document does not show this generated "
                    f"output -- regenerate it ({len(missing)} line(s) differ)",
                )


class ThePerCornerVerdictFlips(unittest.TestCase):
    def test_exactly_three_findings(self):
        _lines, findings = _compare()
        self.assertEqual(findings, 3,
                         "the document accounts for exactly three findings")

    def test_each_flip_goes_the_stated_direction(self):
        lines, _ = _compare()
        rows = _flip_rows(lines)
        self.assertEqual(sorted(r[0] for r in rows), sorted(EXPECTED_FLIPS),
                         "\n".join(lines))
        for corner, old, new in rows:
            with self.subTest(corner=corner):
                old_pass, new_pass = EXPECTED_FLIPS[corner]
                self.assertEqual(old == "PASS", old_pass, f"old={old!r}")
                self.assertEqual(new == "PASS", new_pass, f"new={new!r}")
                for verdict in (old, new):
                    if verdict != "PASS":
                        self.assertTrue(verdict.startswith("FAIL"), verdict)
                        self.assertIn("spur_dbc_200m max=-55", verdict)

    def test_the_document_shows_the_same_flips(self):
        text = _doc_text()
        self.assertIn("**PASS → FAIL**", text)
        self.assertEqual(text.count("FAIL → PASS"), 2)
        for corner in EXPECTED_FLIPS:
            self.assertIn(f"`{corner}`", text)

    def test_the_stated_limits_did_not_move(self):
        lines, _ = _compare()
        self.assertIn("**Stated limits**: identical in both records.", lines)


class TheOverlapPointFigures(unittest.TestCase):
    """Document table and record bullet must tell the same story."""

    #: doc-table measurement name -> index into the OVERLAP tuples
    ROWS = {"spur_dbc": 0, "spur_dbc_200m": 1, "spur_tie_dbc": 2, "tie_pk_ps": 3}

    def _doc_row(self, name):
        m = re.search(rf"^\| `{name}`(?: \(max -55\))? \|(.*)\|$",
                      _doc_text(), re.MULTILINE)
        self.assertIsNotNone(m, f"overlap row for {name} missing")
        cells = [c.strip() for c in m.group(1).split("|")]
        self.assertEqual(len(cells), 3, cells)
        # The document prints some rows to 3 decimals; the record bullet
        # rounds to 2. Compare at the coarser precision.
        return [f"{float(re.match(r'-?\d+\.\d+', c).group(0)):.2f}"
                for c in cells]

    def test_the_document_table_matches_the_expected_figures(self):
        order = list(OVERLAP)
        for name, idx in self.ROWS.items():
            with self.subTest(measurement=name):
                self.assertEqual(self._doc_row(name),
                                 [OVERLAP[k][idx] for k in order])

    def test_the_record_exposure_bullet_states_the_same_figures(self):
        rec = NEW_REC.read_text(encoding="utf-8")
        self.assertIn("SIMULATOR EXPOSURE", rec)
        for label, vals in OVERLAP.items():
            with self.subTest(column=label):
                a, b, c, d = vals
                self.assertIn(f"{a} / {b} / {c} dBc / {d} ps", rec)
        # The spur_dbc_200m column is the one the flip hangs on.
        self.assertIn("-53.45", rec)

    def test_the_simulator_effect_arithmetic(self):
        s46 = float(OVERLAP["ngspice-46 f6eeac7"][0])
        s47 = float(OVERLAP["ngspice-47 f6eeac7"][0])
        pred = float(OVERLAP["predecessor"][0])
        self.assertAlmostEqual(abs(s46 - s47), 6.06, places=2)
        self.assertAlmostEqual(abs(pred - s46), 3.65, places=2)
        text, rec = _doc_text(), NEW_REC.read_text(encoding="utf-8")
        self.assertIn("6.06 dB", text)
        self.assertIn("6.06 dB", rec)

    def test_the_overlap_corner_is_the_typical_flip_corner(self):
        self.assertIn("typical_27c_3.30v_vs1p795", EXPECTED_FLIPS)
        self.assertIn("`typical_27c_3.30v_vs1p795`, 1/1 ok", _doc_text())
        # ngspice-46 under the new PDK passes where ngspice-47 fails: the
        # flip at this corner is a simulator effect, as stated.
        self.assertLessEqual(float(OVERLAP["ngspice-46 f6eeac7"][1]), -55.0)
        self.assertGreater(float(OVERLAP["ngspice-47 f6eeac7"][1]), -55.0)


if __name__ == "__main__":
    unittest.main()
