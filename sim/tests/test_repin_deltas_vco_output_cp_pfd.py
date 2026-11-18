"""The VCO / output / charge-pump / PFD re-pin delta document (#826).

`sim/REPIN-DELTAS-f6eeac7-vco-output-cp-pfd.md` makes claims a reader cannot
check by eye, and each is asserted here instead of trusted:

- **Its tables are generated, not typed.** Every table in the document is
  preceded by the `sim/lib/record_delta.py` command that produces it, so
  those commands must keep working against the committed records *and* their
  output must still be what the document shows.

- **Its flip list is exact.** #826's acceptance criterion sends any
  PASS/FAIL flip to a new issue; this document's group has four (three
  FAIL→PASS, one PASS→FAIL, all `duty_pct` at the `fs`/`lo` edge), plus
  four FAIL→FAIL rows with moved values. The set of eight, and
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

#: The four verdict flips the document tabulates below its verdict:
#: corner -> direction.
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


class TheFlipListTheDocumentTabulates(unittest.TestCase):
    """#826's acceptance criterion: every flip is called out, tabulated in
    the document and accepted as current evidence by operator ruling
    2026-11-15.

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


class TheChargePumpAndPfdIncrementsAddNoFlips(unittest.TestCase):
    """The 2026-11-17 increment re-qualifies both `cp-compliance` benches and
    both `pfd-deadzone` manifests. Its claim, unlike output-driver's, is that
    **nothing moved**: zero comparator findings on all four pairs, per-corner
    verdicts unchanged on every graded row, and provenance on each new record
    (clean tree, `f6eeac7`, batch fleet) together with each record's own
    per-point simulator attribution: read ngspice-47 on the two `pfd-deadzone`
    grids (their `Executing simulator` line is omitted — the harness's
    every-point-matched disclosure), and an honest `unattributed` disclosure
    on the two `cp-compliance` grids, whose decks printed no version banner
    and for which the document claims the batch image's ngspice-47 only by
    fingerprint inference, never as read provenance. Asserted here, not
    trusted."""

    #: (slug, superseded id, new id, graded rows the document claims).
    PAIRS = [
        ("cp-compliance", "20260801-190821-734f483", "20261115-025500-8da7900", 180),
        ("cp-compliance", "20260802-061841-c24ee3a", "20261116-180719-930fb6e", 135),
        ("pfd-deadzone", "20260916-051356-8cedbba", "20261116-183811-1379f1f", 405),
        ("pfd-deadzone", "20260801-234626-5b333d0", "20261116-195826-16f19a5", 225),
    ]

    #: new id -> whether its decks printed no ngspice version banner, per the
    #: record's own `Executing simulator` line (`sim/harness/report.py`
    #: discloses that as `unattributed` rather than crediting the recording
    #: host's binary).
    UNATTRIBUTED = {
        "20261115-025500-8da7900": True,
        "20261116-180719-930fb6e": True,
        "20261116-183811-1379f1f": False,
        "20261116-195826-16f19a5": False,
    }

    def _compare(self, slug, old_id, new_id):
        return record_delta.compare(
            SIM_DIR / slug / "records" / f"{old_id}.md",
            SIM_DIR / slug / "records" / f"{new_id}.md",
        )

    def test_zero_findings_and_unchanged_verdicts_on_every_pair(self):
        for slug, old_id, new_id, n_rows in self.PAIRS:
            with self.subTest(pair=f"{slug}/{new_id}"):
                lines, findings = self._compare(slug, old_id, new_id)
                self.assertEqual(findings, 0, "a flip or limit-crossing appeared")
                self.assertTrue(
                    any(f"unchanged on all {n_rows} graded rows" in ln
                        for ln in lines),
                    f"graded-row count drifted from the documented {n_rows}")

    def test_new_records_provenance_is_clean_f6eeac7_batch_and_attribution(
            self):
        for slug, _old, new, _n in self.PAIRS:
            with self.subTest(record=new):
                text = (SIM_DIR / slug / "records" / f"{new}.md").read_text(
                    encoding="utf-8")
                self.assertIn(
                    "open_pdks `f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`", text)
                self.assertIn("(clean tree)", text)
                self.assertNotIn("DIRTY tree", text)
                self.assertIn("`batch` execution backend", text)
                # The submitter's `Simulator:` bullet is NOT per-point
                # provenance (report.py: under an off-host backend it names
                # the version resolved on the host that ran no deck). What
                # counts is each record's own per-point disclosure.
                if self.UNATTRIBUTED[new]:
                    self.assertIn("Executing simulator: unattributed", text)
                else:
                    # Line omitted => every point reported the recording
                    # version (ngspice-47): the read-provenance case.
                    self.assertNotIn(
                        "Executing simulator: unattributed", text)
                    self.assertIn("Simulator: ngspice-47", text)

    def test_document_numbers_the_four_pairs_and_states_nothing_to_file(self):
        text = _doc_text()
        self.assertIn("945 graded rows", text)
        self.assertIn("add zero flips", text)


class TheAttributionProseRestsOnCommittedProvenance(unittest.TestCase):
    """The document attributes every delta to ngspice-46 -> 47 residue on a
    PDK no-op, and to a clean-tree batch re-run under `f6eeac7`. Each of
    those is a committed record field, asserted here."""

    def test_predecessor_ran_ngspice_46_new_record_ran_ngspice_47(self):
        self.assertIn("ngspice-46", OLD.read_text(encoding="utf-8"))
        new_text = NEW.read_text(encoding="utf-8")
        # Read provenance, not the submitter's `Simulator:` bullet: the
        # output-driver record omits its `Executing simulator` line, which
        # per report.py means every point reported the recording version.
        self.assertNotIn("Executing simulator: unattributed", new_text)
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

    def test_the_document_tabulates_the_flips_and_cites_the_accepting_ruling(self):
        text = _doc_text()
        self.assertIn("**Per-corner verdict flips**", text)
        self.assertIn("operator ruling 2026-11-15", text)
        self.assertNotIn("#966", text)


class TheVcoBiasCurrentIncrementIsBitForBit(unittest.TestCase):
    """The third increment (2026-11-17) re-qualifies `vco-bias-current`. Its
    claim is stronger than the cp/PFD increments': not merely no flips, but
    **bit-for-bit identical on every graded row** — the comparator's abs
    delta reads 0 on all 36 measurements across 4 topologies × 234 corners
    (936 graded rows), because the DC bias network prints the same six
    digits under either PDK pin and any of ngspice 42/46/47. The record
    discloses `Executing simulator: unattributed` on all 234 points (the
    deck prints no version banner; 47 is the shared batch image's,
    fingerprint-inferred), and 42 of its points were adopted from the fleet
    artifact store after a capacity-aborted first submission — disclosed on
    the record's face, asserted here."""

    SLUG = "vco-bias-current"
    OLD_ID = "20260911-172350-da0bb1e"
    NEW_ID = "20261117-150323-f3b3e7f"
    N_ROWS = 936
    ADOPTED = 42
    SOURCE_ATTEMPT = "20261117-141510-2673695"

    def _record_text(self):
        return (SIM_DIR / self.SLUG / "records" / f"{self.NEW_ID}.md").read_text(
            encoding="utf-8")

    def test_zero_findings_and_unchanged_verdicts_on_every_row(self):
        lines, findings = record_delta.compare(
            SIM_DIR / self.SLUG / "records" / f"{self.OLD_ID}.md",
            SIM_DIR / self.SLUG / "records" / f"{self.NEW_ID}.md",
        )
        self.assertEqual(findings, 0, "a flip or limit-crossing appeared")
        self.assertTrue(
            any(f"unchanged on all {self.N_ROWS} graded rows" in ln
                for ln in lines),
            f"graded-row count drifted from {self.N_ROWS}")

    def test_every_graded_measurement_is_bit_for_bit(self):
        lines, _ = record_delta.compare(
            SIM_DIR / self.SLUG / "records" / f"{self.OLD_ID}.md",
            SIM_DIR / self.SLUG / "records" / f"{self.NEW_ID}.md",
        )
        rows = [ln for ln in lines if ln.startswith("| `")]
        self.assertTrue(rows, "no delta table in comparator output")
        for ln in rows:
            cells = [c.strip() for c in ln.strip("|").split("|")]
            with self.subTest(meas=cells[1]):
                self.assertEqual(cells[5], "0",
                                 f"{cells[1]}: nonzero abs delta {cells[5]}")

    def test_new_record_provenance_is_clean_f6eeac7_batch_unattributed(self):
        text = self._record_text()
        self.assertIn(
            "open_pdks `f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`", text)
        self.assertIn("(clean tree)", text)
        self.assertNotIn("DIRTY tree", text)
        self.assertIn("`batch` execution backend", text)
        self.assertIn("Executing simulator: unattributed (234)", text)

    def test_adopted_points_are_disclosed_on_the_record_face(self):
        text = self._record_text()
        self.assertIn("Artifact-adopted points", text)
        self.assertIn(f"{self.ADOPTED} point(s)", text)
        self.assertIn(self.SOURCE_ATTEMPT, text)

    def test_document_states_the_bit_for_bit_result_and_nothing_to_file(self):
        text = _doc_text()
        self.assertIn("bit-for-bit identical on all 936 graded\nrows", text)
        self.assertIn("`vco-bias-current` increment (2026-11-17) adds zero findings", text)


class TheOutputRangeIncrementRequalifiesTwoSinglePoints(unittest.TestCase):
    """The fourth increment (2026-11-17) re-qualifies `output-range`'s two
    single-point records. Both predecessors are narrative investigation
    records whose tables predate the corner-id schema the comparator
    parses, so both comparisons come back with an EMPTY shared-measurement
    intersection — the generated output is the explicit coverage-differs
    form, and the document says so instead of hiding it. The attribution
    rests on quoted rows plus the controls: the `lo` point's `vctrl_final`
    is 1.70267 V under ngspice-42, 46 and the fleet build alike, and the
    previously-CAPPED `hi` point completes under the re-pinned PDK on
    every source that tried it, landing on the predecessor's own
    perturbed-seed control run."""

    SLUG = "output-range"
    OLD_LO = "20260801-061907-67d7127"
    NEW_LO = "20261117-174557-327ee00"
    OLD_HI = "20260819-190341-70a4128"
    NEW_HI = "20261117-174951-33cbd72"
    INIT = "sha256:d6efd5b23e4c9bcb6d97e0516269077b983e81ac453ca7ec74f412cfc0efd385"

    def _record_text(self, record_id):
        return (SIM_DIR / self.SLUG / "records" / f"{record_id}.md").read_text(
            encoding="utf-8")

    def _pair(self, old_id, new_id):
        return record_delta.compare(
            SIM_DIR / self.SLUG / "records" / f"{old_id}.md",
            SIM_DIR / self.SLUG / "records" / f"{new_id}.md",
        )

    def test_both_pairs_grade_zero_shared_rows_with_explicit_coverage_list(self):
        for old_id, new_id in ((self.OLD_LO, self.NEW_LO),
                               (self.OLD_HI, self.NEW_HI)):
            with self.subTest(pair=new_id):
                lines, findings = self._pair(old_id, new_id)
                self.assertEqual(findings, 0, "a finding appeared")
                self.assertTrue(
                    any("unchanged on all 0 graded rows" in ln for ln in lines),
                    "the empty-intersection form changed")
                self.assertTrue(
                    any("Measurement coverage differs" in ln for ln in lines),
                    "the coverage-differs section is missing")

    def test_both_new_records_are_clean_f6eeac7_batch_with_version_attributed(self):
        for new_id in (self.NEW_LO, self.NEW_HI):
            with self.subTest(record=new_id):
                text = self._record_text(new_id)
                self.assertIn(
                    "open_pdks `f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`", text)
                self.assertIn("(clean tree)", text)
                self.assertNotIn("DIRTY tree", text)
                self.assertIn("`batch` execution backend", text)
                # No `Executing simulator` aggregate line: per
                # sim/harness/report.py that means every point reported
                # exactly the recording version, and the record's Simulator
                # line is ngspice-47.
                self.assertNotIn("Executing simulator", text)
                self.assertIn("Simulator: ngspice-47", text)
                self.assertIn(self.INIT, text)

    def test_each_record_supersedes_its_own_predecessor(self):
        self.assertIn(
            f"**Supersedes**: {self.OLD_LO} -- re-pin re-qualification (#826)",
            self._record_text(self.NEW_LO))
        self.assertIn(
            f"**Supersedes**: {self.OLD_HI} -- re-pin re-qualification (#826)",
            self._record_text(self.NEW_HI))

    def test_recorded_values_match_the_document_quotes(self):
        lo = self._record_text(self.NEW_LO)
        hi = self._record_text(self.NEW_HI)
        self.assertIn("`vctrl_final` | 1.70267", lo)
        self.assertIn("`vctrl_final` | 1.45651", hi)
        self.assertIn("`dn_lvl` | 0.0339103", hi)
        self.assertIn("**Overall: FAIL**", lo)
        self.assertIn("**Overall: FAIL**", hi)

    def test_document_states_empty_intersection_dut_migration_and_nothing_to_file(self):
        text = _doc_text()
        self.assertIn("shared-measurement intersection is **empty**",
                      text)
        self.assertIn("the DUT migration, not the re-pin", text)
        self.assertIn("0.33 mV", text)
        self.assertIn("**CAPPED →\nFAIL is not a verdict flip**", text)
        self.assertIn("`output-range` increment (2026-11-17) adds zero verdict flips",
                      text)

    def test_document_states_the_stall_does_not_reproduce_and_the_control_landing(self):
        text = _doc_text()
        self.assertIn("The `hi` point's stall does not reproduce under the re-pinned PDK",
                      text)
        self.assertIn("1.45651 V", text)
        self.assertIn("0.0339103", text)
        self.assertIn("20 µV", text)


class TheVcoTuningRangeIncrementRequalifiesTwoBenches(unittest.TestCase):
    """The fifth increment (2026-11-18) re-qualifies `vco-tuning-range`'s two
    harness-form benches: the 504-point tuning grid and the 144-point
    supply bench. Per-point comparator verdicts are unchanged on both (0
    findings), and the one movement is a curve-level acceptance-check flip —
    check 5, f(Vctrl) monotonicity, PASS->FAIL on one `all-fast`/27 C/
    3.30 V band-1 curve under the batch image's ngspice-47 — filed as
    #1059 per #826's acceptance criteria, not left silent. The tuning grid
    landed through the per-point store: 496 of 504 points adopted from two
    interrupted earlier attempts, disclosed on the record's face."""

    SLUG = "vco-tuning-range"
    TUNING = ("20260804-162735-72883fb", "20261118-021803-deb4ec0", 504)
    SUPPLY = ("20260804-211600-f599a65", "20261118-023753-1b6f7c2", 288)
    ADOPTED = 496
    SOURCE_ATTEMPTS = ("20261118-004057-6f0fd4e", "20261118-012236-8e80a30")
    FLIP_ISSUE = "#1059"

    def _pair(self, triple):
        old_id, new_id, n_rows = triple
        lines, findings = record_delta.compare(
            SIM_DIR / self.SLUG / "records" / f"{old_id}.md",
            SIM_DIR / self.SLUG / "records" / f"{new_id}.md",
        )
        return lines, findings, n_rows

    def _record_text(self, new_id):
        return (SIM_DIR / self.SLUG / "records" / f"{new_id}.md").read_text(
            encoding="utf-8")

    def test_zero_findings_and_unchanged_verdicts_on_both_pairs(self):
        for old_id, new_id, n_rows in (self.TUNING, self.SUPPLY):
            with self.subTest(pair=f"{old_id} -> {new_id}"):
                lines, findings, n = self._pair((old_id, new_id, n_rows))
                self.assertEqual(findings, 0,
                                 "a flip or limit-crossing appeared")
                self.assertTrue(
                    any(f"unchanged on all {n} graded rows" in ln
                        for ln in lines),
                    f"graded-row count drifted from {n}")

    def test_both_new_records_are_clean_f6eeac7_batch_ngspice_47(self):
        for _, new_id, _ in (self.TUNING, self.SUPPLY):
            with self.subTest(record=new_id):
                text = self._record_text(new_id)
                self.assertIn(
                    "open_pdks `f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`",
                    text)
                self.assertIn("(clean tree)", text)
                self.assertNotIn("DIRTY tree", text)
                self.assertIn("`batch` execution backend", text)
                self.assertIn("Simulator: ngspice-47", text)

    def test_each_new_record_supersedes_its_own_predecessor(self):
        for (old_id, new_id, _) in (self.TUNING, self.SUPPLY):
            with self.subTest(record=new_id):
                self.assertIn(f"**Supersedes**: {old_id}",
                              self._record_text(new_id))

    def test_tuning_grids_adopted_points_are_disclosed_on_the_record_face(self):
        text = self._record_text(self.TUNING[1])
        self.assertIn("Artifact-adopted points", text)
        self.assertIn(f"{self.ADOPTED} point(s)", text)
        for attempt in self.SOURCE_ATTEMPTS:
            self.assertIn(attempt, text)

    def test_check_5_flips_pass_to_fail_exactly_as_the_document_states(self):
        """The one acceptance-check flip, read off both records' own
        acceptance_checks tables rather than trusted from prose."""
        old_text = self._record_text(self.TUNING[0])
        new_text = self._record_text(self.TUNING[1])
        self.assertIn(
            "| 5 | f(Vctrl) monotonic on every (corner, band) curve | n/a"
            " | 0 non-monotonic curves | 0 | **PASS** |",
            old_text)
        self.assertIn(
            "| 5 | f(Vctrl) monotonic on every (corner, band) curve |"
            " all-fast/27C/3.30V | 1 non-monotonic curves | 0 | **FAIL** |",
            new_text)
        # check 4b is NOT a flip: the predecessor already read FAIL there.
        self.assertIn("154.4 MHz/V | <= 150 MHz/V | **FAIL** |", old_text)
        self.assertIn("154.4 MHz/V | <= 150 MHz/V | **FAIL** |", new_text)

    def test_document_states_the_increment_its_flip_and_its_filing(self):
        text = _doc_text()
        self.assertIn(
            "`vco-tuning-range` increment (2026-11-18) adds one curve-level",
            text)
        self.assertIn("504 graded rows on the tuning", text)
        self.assertIn("288 on the supply bench", text)
        self.assertIn(self.FLIP_ISSUE, text)
        self.assertIn(
            "six band-select-mirror Monte Carlo / negative-control records",
            text)


if __name__ == "__main__":
    unittest.main()
