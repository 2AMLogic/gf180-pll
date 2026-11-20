"""The closed-loop re-pin delta document (#828).

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

import csv
import hashlib
import re
import subprocess
import sys
import unittest
from decimal import Decimal
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


OLD_CSV = SIM_DIR / "reference-spur" / "corners" / OLD_ID / "spur_by_corner.csv"
NEW_CSV = SIM_DIR / "reference-spur" / "corners" / NEW_ID / "spur_by_corner.csv"


def _csv_200m(path):
    """corner_id -> spur_dbc_at_200mhz (the document's `spur_dbc_200m`)."""
    with path.open(encoding="utf-8") as fh:
        rows = csv.DictReader(ln for ln in fh if not ln.startswith("#"))
        return {r["corner_id"]: float(r["spur_dbc_at_200mhz"]) for r in rows}


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


class PllTopSmokeReplay(unittest.TestCase):
    """Check the re-pin against the frozen seven-check bench and both raw logs."""

    def test_input_and_reported_deltas(self):
        campaign = SIM_DIR / "pll-top-smoke"
        (row,) = (
            line
            for line in _doc_text().splitlines()
            if line.startswith("| `pll-top-smoke` |")
        )
        ids = re.findall(r"`(\d{8}-\d{6}-[a-f0-9]{7})`", row)
        self.assertEqual(len(ids), 2, row)
        previous, replay = ids
        self.assertEqual(previous, "20260802-160926-8456ff3")
        snapshots = campaign / "netlist-snapshots"
        self.assertEqual(
            (snapshots / f"{previous}.spice").read_bytes(),
            (snapshots / f"{replay}.spice").read_bytes(),
        )
        record = (campaign / "records" / f"{replay}.md").read_text()
        self.assertIn(f"- **Supersedes**: {previous}\n", record)

        # The batch-mode log repeats measurements after the .control block.
        # The legacy runner reads the first evaluation of each measurement.
        logs = []
        settings = []
        for rid in ids:
            path = campaign / "corners" / rid / "typical_27c_3.30v.log"
            deck, output = path.read_text().split("==== ngspice output ====")
            # Compare all parameter cards, temperature and PDK library sections.
            # The absolute installation directory varies between recording hosts.
            settings.append(
                [
                    re.sub(r'"[^"]*/libs\.tech/', '"libs.tech/', line)
                    for line in deck.splitlines()
                    if line.startswith((".param ", ".lib ", ".temp ", ".option "))
                    or (line.startswith(".include ") and "libs.tech/" in line)
                ]
            )
            first = output.split("Measurements for Transient Analysis")[1]
            logs.append(
                dict(re.findall(r"^(\w+)\s+=\s+([-+.\deE]+)\b", first, re.MULTILINE))
            )

        self.assertEqual(settings[0], settings[1])

        # The record tabulates magnitudes for phase and residual error. All
        # other gated quantities on this bench are positive physical values.
        measures = {
            "ferr": 1,
            "phi_b": 10**9,
            "nmeas": 1,
            "fout": Decimal("1e-6"),
            "lock_lvl": 1,
            "vctrl_min": 1,
            "vctrl_max": 1,
            "dn_lvl": 1,
        }
        rows = [line for line in record.splitlines() if re.match(r"^\| [1-7] \|", line)]
        self.assertEqual(len(rows), len(measures))
        seen = set()
        for line in rows:
            _, quantity, _, old, new, delta, _ = (
                c.strip() for c in line.strip("|").split("|")
            )
            measure = re.search(r"`(\w+)`", quantity).group(1)
            with self.subTest(measure=measure):
                seen.add(measure)
                values = [Decimal(log[measure]) * measures[measure] for log in logs]
                if measure in ("phi_b", "ferr"):
                    values = [abs(value) for value in values]
                self.assertEqual([Decimal(old), Decimal(new)], values)
                self.assertEqual(Decimal(delta), values[1] - values[0])
        self.assertEqual(seen, set(measures))


class TheDispositionTableAndDerivedProse(unittest.TestCase):
    """Hand-maintained figures, each checked against an independent source."""

    @staticmethod
    def _norm(text):
        return text.replace("\u2212", "-")

    def _maxima(self, name):
        """(old_max, new_max) of a measurement from the generated delta table."""
        lines, _ = _compare()
        rows = [ln for ln in lines if ln.startswith(f"| `spur` | `{name}` |")]
        self.assertEqual(len(rows), 1, rows)
        cells = [c.strip() for c in rows[0].strip().strip("|").split("|")]
        return tuple(float(c.split("..")[1]) for c in cells[3:5])

    def _disposition_rows(self):
        """{corner: (old cell, new cell)} from the Disposition table only.

        The table is located by its header row, and only its contiguous
        data rows are collected: a corner listed in some other table is
        simply absent here, and one that appears twice is rejected rather
        than silently matched in whichever copy happens to fit the value
        pattern.
        """
        lines = self._norm(_doc_text()).splitlines()
        heads = [i for i, ln in enumerate(lines) if ln.startswith("| corner |")]
        self.assertEqual(len(heads), 1,
                         f"Disposition table header rows at {heads}, "
                         "expected exactly one")
        table = {}
        for ln in lines[heads[0] + 1:]:
            if not ln.startswith("|"):
                break
            if not re.search(r"[`a-zA-Z]", ln):
                continue  # the |---| separator
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            self.assertEqual(len(cells), 4, cells)
            corner = cells[0].strip("`")
            self.assertNotIn(corner, table,
                             f"{corner} occurs more than once in the "
                             f"Disposition table")
            table[corner] = (cells[1], cells[2])
        return table

    def test_each_disposition_row_matches_both_csvs(self):
        old, new = _csv_200m(OLD_CSV), _csv_200m(NEW_CSV)
        table = self._disposition_rows()
        self.assertEqual(sorted(table), sorted(EXPECTED_FLIPS),
                         "each expected corner must occur exactly once in "
                         "the Disposition table")
        for corner in EXPECTED_FLIPS:
            with self.subTest(corner=corner):
                old_cell, new_cell = table[corner]
                m = re.fullmatch(r"(-\d+\.\d+) \((?:PASS|FAIL)\)", old_cell)
                self.assertIsNotNone(m, f"{corner}: old cell {old_cell!r}")
                self.assertEqual(m.group(1), f"{old[corner]:.2f}")
                self.assertEqual(new_cell, f"{new[corner]:.2f}")

    def _prose(self):
        return re.sub(r"\s+", " ", self._norm(_doc_text()))

    def test_pdk_movement_prose_is_the_pinned_overlap_arithmetic(self):
        d = abs(float(OVERLAP["ngspice-46 f6eeac7"][0])
                - float(OVERLAP["predecessor"][0]))
        self.assertIn(f"moves it by {d:.2f} dB in the", self._prose())

    def test_worsening_at_200mhz_prose(self):
        old, new = self._maxima("spur_dbc_200m")
        self.assertIn(f"moves from {old:.2f} to {new:.2f} dBc, "
                      f"i.e. **{abs(new - old):.2f} dB worse**", self._prose())

    def test_150mhz_worst_margin_and_previous_prose(self):
        old, new = self._maxima("spur_dbc")
        margin = abs(-55.0 - new)
        prose = self._prose()
        self.assertIn(f"(worst {new:.2f} dBc, `typical`, only "
                      f"{margin:.2f} dB of margin; previously {old:.2f})", prose)


class LoopDynamicsProvenance(unittest.TestCase):
    """The `loop-dynamics` successor's unattributed simulator, recovered.

    Record `20261111-092132-343bafa` says "Executing simulator: unattributed
    (99)" because the harness cannot see inside a batch job. The archived
    fleet job outputs can, and the recovered mapping is committed beside the
    record's raw logs as `executing-simulator-provenance.csv`. Everything the
    `## loop-dynamics` section of the document claims from that CSV is
    re-derived here from committed files only -- no simulator runs, no
    network: the byte-match itself is recomputed as sha256 over each
    committed corner log, so a CSV row that drifted from the evidence it
    speaks for fails rather than trusts.
    """

    RECORD_ID = "20261111-092132-343bafa"
    BASELINE_ID = "20260731-202550-82af5a9"
    PIN = "f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7"
    INIT = "d6efd5b23e4c9bcb6d97e0516269077b983e81ac453ca7ec74f412cfc0efd385"
    AMI = "ami-095c25ae241a4d360"
    IMAGE_BUILT_AT = "2026-11-06T02:46:10Z"

    @classmethod
    def _rows(cls):
        campaign = SIM_DIR / "loop-dynamics"
        csv_path = campaign / "corners" / cls.RECORD_ID / "executing-simulator-provenance.csv"
        with csv_path.open(encoding="utf-8") as fh:
            return list(csv.DictReader(ln for ln in fh if not ln.startswith("#")))

    def test_every_committed_corner_log_is_covered_and_byte_matched(self):
        corners_dir = SIM_DIR / "loop-dynamics" / "corners" / self.RECORD_ID
        committed = {p.stem: p for p in corners_dir.glob("*.log")}
        rows = self._rows()
        self.assertEqual(sorted(r["corner_id"] for r in rows),
                         sorted(committed),
                         "the CSV must cover exactly the committed corner logs")
        self.assertEqual(len(rows), 99)
        for r in rows:
            with self.subTest(corner=r["corner_id"]):
                digest = hashlib.sha256(
                    committed[r["corner_id"]].read_bytes()).hexdigest()
                self.assertEqual(r["ngspice_log_sha256"], digest,
                                 "sha256 must be of the committed log itself")

    def test_the_attribution_is_uniform_and_names_the_re_pinned_pdk(self):
        rows = self._rows()
        self.assertEqual({r["executing_simulator"] for r in rows},
                         {"ngspice-46"},
                         "every point executed on ngspice-46")
        self.assertEqual({r["open_pdks"] for r in rows}, {self.PIN})
        self.assertEqual({r["simulator_init_sha256"] for r in rows}, {self.INIT})
        self.assertEqual({r["ami_id"] for r in rows}, {self.AMI})
        self.assertEqual({r["image_built_at"] for r in rows},
                         {self.IMAGE_BUILT_AT})
        for r in rows:
            with self.subTest(corner=r["corner_id"]):
                self.assertEqual(r["job_state"], "done")
                self.assertEqual(r["job_exit_code"], "0")
                self.assertRegex(
                    r["job_id"],
                    rf"^gf180-pll-sim-{re.escape(r['corner_id'])}-[0-9a-f]{{8}}$")

    def test_the_executing_hosts_are_the_records_own_ninety_nine(self):
        record = (SIM_DIR / "loop-dynamics" / "records"
                  / f"{self.RECORD_ID}.md").read_text(encoding="utf-8")
        self.assertIn("Executing simulator: unattributed (99)", record)
        hosts_span = re.search(r"Execution hosts:.*?-- (.*?)\n", record).group(1)
        named = set(re.findall(r"`(ip-[\d-]+)`", hosts_span))
        rows = self._rows()
        csv_hosts = {r["executing_host"] for r in rows}
        self.assertEqual(len(csv_hosts), 99, "99 points on 99 distinct hosts")
        self.assertEqual(csv_hosts, named,
                         "CSV hosts must be exactly the record's named hosts")

    def test_nine_pilot_points_report_byte_identical_prior_executions(self):
        rows = [r for r in self._rows() if r["prior_byte_identical_jobs"]]
        self.assertEqual(len(rows), 9)
        for r in rows:
            with self.subTest(corner=r["corner_id"]):
                self.assertRegex(
                    r["corner_id"],
                    r"^rtyp-mtyp-x(?:typ|ff|ss)_-?\d+c_3\.30v_z$")
                prefix = f"gf180-pll-sim-{r['corner_id']}-"
                for jid in r["prior_byte_identical_jobs"].split(";"):
                    self.assertTrue(jid.startswith(prefix), jid)
                    self.assertRegex(jid[len(prefix):], r"^[0-9a-f]{8}$")

    def test_the_document_cites_the_record_and_the_recovered_attribution(self):
        text = _doc_text()
        self.assertIn("## `loop-dynamics`", text)
        self.assertIn(self.RECORD_ID, text)
        self.assertIn("executing-simulator-provenance.csv", text)
        # The disposition row: provenance-verified, successor named.
        row = [ln for ln in text.splitlines()
               if ln.startswith("| `loop-dynamics` |")]
        self.assertEqual(len(row), 1)
        self.assertIn("**provenance-verified here**", row[0])
        self.assertIn(self.BASELINE_ID, row[0])
        self.assertIn(self.RECORD_ID, row[0])
        # The section states what the archive established.
        self.assertIn("ngspice-46 on all 99 points", text)
        self.assertIn("`open_pdks f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`",
                      text)
        # And why no generated table is printed for this pair.
        self.assertIn("0 graded rows", text)


class ReferencePhaseTransferRepin(unittest.TestCase):
    """The `reference-phase-transfer` re-qualification pair (#828).

    Successor `20261120-151718-d0000b5` supersedes `20260925-080736-b722f33`
    under the re-pinned open_pdks. Its two findings are method-guard flips
    (`pair_resid` at `ff`, `settle_resid` at `sf`), routed to #1077 -- not
    spec-limit misses. Everything asserted here is re-derived from the
    committed records and the document, mirroring the classes above.
    """

    OLD_ID = "20260925-080736-b722f33"
    NEW_ID = "20261120-151718-d0000b5"
    OLD_REC = SIM_DIR / "reference-phase-transfer" / "records" / f"{OLD_ID}.md"
    NEW_REC = SIM_DIR / "reference-phase-transfer" / "records" / f"{NEW_ID}.md"

    #: corner-id -> the guard whose band the new record exceeds there
    GUARD_FLIPS = {
        "ff_-40c_3.63v_vs2p430": "pair_resid",
        "sf_-40c_2.97v_vs1p677": "settle_resid",
    }

    #: column label -> (measured_gain_db, transfer_error_db, phi_shift_ps,
    #:                   pair_resid_ps) at the overlap corner
    OVERLAP = {
        "predecessor": ("15.8894", "0.3264", "38.3", "-10.5"),
        "ngspice-46 f6eeac7": ("15.5871", "0.0240", "2.8", "-3.4"),
        "ngspice-47 f6eeac7": ("15.5326", "-0.0305", "-3.5", "-16.9"),
    }

    def _compare(self):
        return record_delta.compare(self.OLD_REC, self.NEW_REC)

    def test_both_records_exist_and_the_successor_supersedes(self):
        for p in (self.OLD_REC, self.NEW_REC):
            self.assertTrue(p.is_file(), f"{p} missing")
        record = self.NEW_REC.read_text(encoding="utf-8")
        self.assertIn(f"- **Supersedes**: {self.OLD_ID}", record)
        # Provenance: the re-pinned PDK, executed off-host.
        self.assertIn("f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7", record)
        self.assertIn("`batch` execution backend", record)

    def test_exactly_two_findings_and_they_are_the_method_guards(self):
        lines, findings = self._compare()
        self.assertEqual(findings, 2,
                         "the pair carries exactly the two guard findings")
        rows = [ln for ln in lines if ln.startswith("| `pairing` |")
                and ("pair_resid max=" in ln or "settle_resid max=" in ln)]
        self.assertEqual(len(rows), 2, "\n".join(lines))
        seen = {}
        for ln in rows:
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            corner, guard = cells[1].strip("`"), cells[3].split(" ")[2]
            self.assertEqual(cells[2], "PASS", ln)
            self.assertTrue(cells[3].startswith("FAIL"), ln)
            seen[corner] = guard
        self.assertEqual(seen, self.GUARD_FLIPS)
        # The stated limits did not move.
        self.assertIn("**Stated limits**: identical in both records.", lines)

    def _section(self):
        """The document's `## reference-phase-transfer` section only."""
        text = _doc_text()
        start = text.index("## `reference-phase-transfer`")
        nxt = text.find("\n## ", start + 1)
        return text[start:nxt if nxt != -1 else None]

    def test_the_document_section_states_the_same_flips(self):
        text = self._norm(_doc_text())
        self.assertIn("## `reference-phase-transfer`", text)
        for corner, guard in self.GUARD_FLIPS.items():
            self.assertIn(f"`{corner}`", text)
            self.assertIn(guard, text)
        section = self._norm(self._section())
        self.assertEqual(section.count("**PASS → FAIL**"), 2)
        # Routed, not absorbed.
        self.assertIn("#1077", section)
        self.assertIn("not relaxed", section)

    def test_the_disposition_row_names_the_successor(self):
        row = [ln for ln in _doc_text().splitlines()
               if ln.startswith("| `reference-phase-transfer` |")]
        self.assertEqual(len(row), 1)
        self.assertIn("**re-qualified here**", row[0])
        self.assertIn(self.NEW_ID, row[0])

    @staticmethod
    def _norm(text):
        return text.replace("\u2212", "-")

    def test_the_overlap_table_and_the_record_bullet_agree(self):
        text = self._norm(_doc_text())
        order = list(self.OVERLAP)
        rows = {
            "measured_gain_db": ("measured_gain_db", "", 0),
            "phi_shift (ps)": ("phi_shift", " (ps)", 2),
            "pair_resid (ps)": ("pair_resid", " (ps)", 3),
        }
        for name, (core, unit, idx) in rows.items():
            with self.subTest(measurement=name):
                row = re.escape(f"| `{core}`{unit} |") + r"(.+)\|"
                m = re.search(row, text)
                self.assertIsNotNone(m, f"overlap row for {name} missing")
                cells = [c.strip() for c in m.group(1).split("|")]
                self.assertEqual(len(cells), 3, cells)
                self.assertEqual(
                    cells, [self.OVERLAP[k][idx] for k in order], cells)
        record = self._norm(self.NEW_REC.read_text(encoding="utf-8"))
        self.assertIn("SIMULATOR EXPOSURE", record)
        self.assertIn("961.9 s", record)
        for label, vals in self.OVERLAP.items():
            with self.subTest(column=label):
                g, e, p, r = vals
                signed = f"+{e}" if float(e) >= 0 else e
                self.assertIn(f"{g} / {signed} dB / {p} ps / {r} ps", record)

    def test_the_simulator_and_pdk_movement_arithmetic(self):
        s46 = float(self.OVERLAP["ngspice-46 f6eeac7"][0])
        s47 = float(self.OVERLAP["ngspice-47 f6eeac7"][0])
        pred = float(self.OVERLAP["predecessor"][0])
        self.assertAlmostEqual(abs(s46 - s47), 0.0545, places=4)
        self.assertAlmostEqual(abs(pred - s46), 0.30, places=2)
        text = self._norm(_doc_text())
        record = self._norm(self.NEW_REC.read_text(encoding="utf-8"))
        for doc in (text, record):
            self.assertIn("0.055 dB", doc)
            self.assertIn("0.30 dB", doc)

    def test_the_verdict_flip_leaves_the_transfer_substance_stated(self):
        text = self._norm(_doc_text())
        # The tightened error range the disposition quotes, both ends.
        self.assertIn("-0.0305…+0.2988 dB", text)
        self.assertIn("-0.0345…+0.8032 dB", text)
        record = self._norm(self.NEW_REC.read_text(encoding="utf-8"))
        self.assertIn("**Overall: FAIL**", record)


if __name__ == "__main__":
    unittest.main()
