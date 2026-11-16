"""The VCO / output / charge-pump / PFD re-pin delta document (#826).

`sim/REPIN-DELTAS-f6eeac7-vco-output-cp-pfd.md` makes claims a reader cannot
check by eye, and each is asserted here instead of trusted:

- **Its tables are generated, not typed.** Every table in the document is
  preceded by the `sim/lib/record_delta.py` command that produces it, so
  those commands must keep working against the committed records *and* their
  output must still be what the document shows.

- **Its flip list is exact.** #826's acceptance criterion sends any
  PASS/FAIL flip to a new issue; this document's group has four (three
  FAIL→PASS, one PASS→FAIL, all `duty_pct` at the `fs`/`lo` edge, filed as
  #966), plus four FAIL→FAIL rows with moved values. The set of eight, and
  each row's direction, is asserted as stated — a fifth silent flip is
  exactly what this test exists to catch.

- **Its attribution prose rests on committed provenance.** The document
  attributes every delta to the simulator, not the PDK, because the
  predecessor ran ngspice-46 and the new record ran ngspice-47 on the batch
  fleet under `f6eeac7` with a clean tree. Those are record fields, so they
  are asserted, not trusted; the fail-count prose (7/90 old, 5/90 new) is
  likewise recomputed from the records.

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

DOC = SIM_DIR / "REPIN-DELTAS-f6eeac7-vco-output-cp-pfd.md"

OLD = SIM_DIR / "output-driver" / "records" / "20260817-100354-0e9cfc9.md"
NEW = SIM_DIR / "output-driver" / "records" / "20261115-130526-3be016c.md"

#: A fenced regeneration command, as the document writes it:
#:     python3 sim/lib/record_delta.py \
#:       sim/<slug>/records/<old>.md \
#:       sim/<slug>/records/<new>.md
REGEN = re.compile(
    r"python3 sim/lib/record_delta\.py \\\n"
    r"\s+(sim/[\w.-]+/records/[\d-]+-\w+\.md) \\\n"
    r"\s+(sim/[\w.-]+/records/[\d-]+-\w+\.md)\n"
)

#: The four verdict flips the document files as #966: corner -> direction.
FLIPS = {
    "ff_-40c_3.30v_lo": "F2P",
    "fs_-40c_3.30v_lo": "F2P",
    "fs_27c_3.30v_lo": "F2P",
    "fs_27c_2.97v_lo": "P2F",
}

#: FAIL in both records, with a moved value.
MOVED_FAILS = [
    "fs_-40c_3.63v_lo",
    "fs_125c_3.30v_lo",
    "fs_125c_3.63v_lo",
    "fs_27c_3.63v_lo",
]


def _doc_text() -> str:
    return DOC.read_text(encoding="utf-8")


class TheDocumentsTablesAreGenerated(unittest.TestCase):
    def test_the_document_exists_and_names_at_least_one_command(self):
        self.assertTrue(DOC.is_file(), f"{DOC} missing")
        self.assertTrue(REGEN.findall(_doc_text()),
                        "no regeneration command found in the document")

    def test_every_documented_regeneration_command_reproduces_its_table(self):
        """Run each command the document prints and require its own output back.

        This is the check that stops a hand-edited table: the document is not
        merely *accompanied* by a command, it *is* the command's output.
        """
        text = _doc_text()
        for old_rel, new_rel in REGEN.findall(text):
            with self.subTest(pair=f"{old_rel} -> {new_rel}"):
                old, new = REPO_ROOT / old_rel, REPO_ROOT / new_rel
                self.assertTrue(old.is_file(), f"{old} missing")
                self.assertTrue(new.is_file(), f"{new} missing")
                r = subprocess.run(
                    [sys.executable, "sim/lib/record_delta.py", old_rel, new_rel],
                    cwd=REPO_ROOT, capture_output=True, text=True,
                )
                self.assertEqual(r.returncode, 0, r.stderr)
                missing = [ln for ln in r.stdout.splitlines()
                           if ln.strip() and ln not in text]
                self.assertEqual(
                    missing[:3], [],
                    f"{new_rel}: the document does not show this generated "
                    f"output -- regenerate it ({len(missing)} line(s) differ)",
                )


class TheFlipListTheDocumentFiles(unittest.TestCase):
    """#826's acceptance criterion: every flip is called out, here as #966.

    The comparator reports eight graded rows; the document's claim is that
    exactly four of them are flips (three FAIL->PASS, one PASS->FAIL) and
    four are FAIL->FAIL with moved values, all on `duty_pct min=45` at the
    `fs`/`lo` or `ff`/`lo` edge. Direction is asserted per corner, because
    "eight findings" would read identically if a direction were reversed.
    """

    def _flip_rows(self):
        lines, findings = record_delta.compare(OLD, NEW)
        self.assertEqual(findings, 8,
                         "the document accounts for exactly eight findings")
        self.assertTrue(any(ln.startswith("**Per-corner verdict flips**")
                            for ln in lines), "no flips table in comparator output")
        start = next(i for i, ln in enumerate(lines)
                     if ln.startswith("**Per-corner verdict flips**"))
        rows = {}
        for ln in lines[start:]:
            if not ln.startswith("| `` | `"):
                if rows:
                    break  # past the table
                continue
            cells = [c.strip() for c in ln.strip("|").split("|")]
            rows[cells[1].strip("`")] = (cells[2], cells[3])
        return rows

    def test_exactly_the_four_documented_flips_plus_four_moved_fails(self):
        rows = self._flip_rows()
        self.assertEqual(sorted(rows),
                         sorted(list(FLIPS) + MOVED_FAILS),
                         "a fifth finding appeared or one vanished")
        for corner, direction in FLIPS.items():
            with self.subTest(corner=corner, direction=direction):
                old_v, new_v = rows[corner]
                if direction == "F2P":
                    self.assertTrue(old_v.startswith("FAIL"), old_v)
                    self.assertEqual(new_v, "PASS", new_v)
                else:
                    self.assertEqual(old_v, "PASS", old_v)
                    self.assertTrue(new_v.startswith("FAIL"), new_v)
        for corner in MOVED_FAILS:
            with self.subTest(corner=corner):
                old_v, new_v = rows[corner]
                self.assertTrue(old_v.startswith("FAIL") and
                                new_v.startswith("FAIL"), (old_v, new_v))

    def test_every_finding_is_the_duty_floor_check(self):
        for old_v, new_v in self._flip_rows().values():
            with self.subTest(old=old_v[:40]):
                for v in (old_v, new_v):
                    if "FAIL" in v:
                        self.assertIn("duty_pct min=45", v, v)


class TheAttributionProseRestsOnCommittedProvenance(unittest.TestCase):
    """The document attributes every delta to ngspice-46 -> 47 residue on a
    PDK no-op, and to a clean-tree batch re-run under `f6eeac7`. Each of
    those is a committed record field, asserted here."""

    def test_predecessor_ran_ngspice_46_new_record_ran_ngspice_47(self):
        self.assertIn("ngspice-46", OLD.read_text(encoding="utf-8"))
        new_text = NEW.read_text(encoding="utf-8")
        self.assertIn("Simulator: ngspice-47", new_text)

    def test_new_record_is_clean_tree_f6eeac7_batch_executed(self):
        text = NEW.read_text(encoding="utf-8")
        self.assertIn("open_pdks `f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`", text)
        self.assertNotIn("DIRTY tree", text)
        self.assertIn("(clean tree)", text)
        self.assertIn("`batch` execution backend", text)

    def test_fail_count_prose_7_old_5_new(self):
        self.assertEqual(
            len(re.findall(r"FAIL — duty_pct", OLD.read_text(encoding="utf-8"))), 7)
        self.assertEqual(
            len(re.findall(r"FAIL — duty_pct", NEW.read_text(encoding="utf-8"))), 5)

    def test_the_document_names_the_flips_issue(self):
        self.assertIn("#966", _doc_text())


if __name__ == "__main__":
    unittest.main()
