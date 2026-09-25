#!/usr/bin/env python3
"""Unit tests for ``sim/lib/check-pvt-coverage-claims.sh`` (issue #237).

    python3 -m unittest discover -s sim/tests -v

The check grades *where a number was measured*: which process bundle a
reader-facing document attributes a value to, and which PVT grid that bundle
belongs to.  It exists because four rows of the Chipalooza proposal's section-5
table reported worst cases at ``all-fast`` / ``all-slow`` -- combined bundles
that skew every device family together and are **not** in this repository's
45-point mandated grid -- in a column whose every other row means "of 45", and
said so nowhere.

It has since grown the converse rule: a row claiming it covers the *whole*
mandated grid must cite records whose committed evidence, in union, contains
every mandated point.  Rules 1-3 grade corners a row names; a row overclaiming
coverage is characterized by the corners it does not name.

Every test builds a throwaway tree whose answer is known and runs the real
script in it, because a check that only ever runs where it passes proves
nothing about what it would have caught.  The fixture copies the real
``sim/harness/corners.py``, so the mandated grid size and the bundle registry
the tests assert against are the ones the harness actually defines -- and
``test_mandated_grid_size_is_derived_from_the_harness`` edits that copy to
prove the check reads it rather than remembering 45.

No PDK, no ngspice, no KLayout: the script reads committed Markdown and the
committed per-corner CSV/log artifacts under ``sim/*/corners/``.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SIM_DIR.parent
CHECK = SIM_DIR / "lib" / "check-pvt-coverage-claims.sh"
HARNESS = SIM_DIR / "harness"

README = "README.md"
CHARACTERIZATION = "sim/CHARACTERIZATION.md"
PROPOSAL = "docs/chipalooza/challenge-5-proposal.md"
GRADED = (README, CHARACTERIZATION, PROPOSAL)

#: Record ids in this tree's format: <YYYYMMDD>-<HHMMSS>-<7 hex>.
MANDATED_REC = "20260901-155456-46b92f8"
SUPERSET_REC = "20260731-175947-0a12e6c"
#: 13 bundles / 117 PVT points, the shape `sim/lock-detector` runs.
WIDE_REC = "20260919-002812-1b12179"
#: 3 bundles / 9 points at one supply, the shape `sim/devchar-passives` runs.
NARROW_REC = "20260801-102454-79f398e"
#: 16 PVT points, all on-grid bundles -- `sim/period-jitter`'s `fs`/`sf` block.
PARTIAL_REC = "20260906-080511-69b36ef"
#: Three slices that reach the mandated grid only in union -- the shape
#: `sim/period-jitter` actually has (5 records covering 1, 4, 8, 18 and 16
#: points, none of them the grid).
SLICE_TYPICAL = "20260906-024225-aaaaaa1"
SLICE_FF_SS = "20260906-063728-bbbbbb2"
SLICE_FS_SF = "20260906-080511-ccccce3"
#: 45 points, every bundle on-grid, and NOT the mandated grid: the 3.63 V rail
#: is never measured and 3.00 V is measured instead. Only a point-by-point
#: rule can tell it apart from the real thing.
SKEWED_REC = "20260907-101112-dddddd4"
#: A record whose corner axis is not the MOS grid at all -- the
#: `sim/loop-dynamics` shape (issue #516).
NON_MOS_REC = "20260731-202550-1a2b3c4"
#: A record that is a deliberately non-rectangular sample of a larger
#: cross-product -- the `sim/divider-ratio-chain` shape (issue #516).
NON_RECT_REC = "20260802-100727-5d6e7f8"

MOS_BUNDLES = ("typical", "ff", "ss", "fs", "sf")
COMBINED_BUNDLES = ("all-slow", "all-fast")
PASSIVE_BUNDLES = (
    "res_ff",
    "res_ss",
    "moscap_ff",
    "moscap_ss",
    "mimcap_ff",
    "mimcap_ss",
)
TEMPS = ("-40", "27", "125")
SUPPLIES = ("2.97", "3.30", "3.63")


def _corner_files(bundles, temps=TEMPS, supplies=SUPPLIES) -> list[str]:
    """One log stem per PVT point, in the `<bundle>_<T>c_<V>v` form the tree uses."""
    return [
        f"{bundle}_{temp}c_{vdd}v.log"
        for bundle in bundles
        for temp in temps
        for vdd in supplies
    ]


class PvtCoverageCheckTest(unittest.TestCase):
    """Each test writes a tree, runs the real script in it, asserts the verdict."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="pvt-coverage-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

        # The script locates the repo root two levels above itself.
        (self.tmp / "sim" / "lib").mkdir(parents=True)
        shutil.copy2(CHECK, self.tmp / "sim" / "lib" / CHECK.name)

        # The real corner registry -- the source of truth for both the bundle
        # names and the mandated grid size.
        dest = self.tmp / "sim" / "harness"
        dest.mkdir(parents=True)
        for name in ("__init__.py", "corners.py"):
            shutil.copy2(HARNESS / name, dest / name)

        # Two campaigns' committed per-corner evidence: one that ran the
        # mandated 45-point grid, one that ran the 63-point superset.
        self._evidence("mandated-campaign", MANDATED_REC, _corner_files(MOS_BUNDLES))
        self._evidence(
            "superset-campaign",
            SUPERSET_REC,
            _corner_files(MOS_BUNDLES + COMBINED_BUNDLES),
        )
        # 13 bundles / 117 points: the mandated five, the two combined
        # bundles, and the six passive-only ones.
        self._evidence(
            "wide-campaign",
            WIDE_REC,
            _corner_files(MOS_BUNDLES + COMBINED_BUNDLES + PASSIVE_BUNDLES),
        )
        # 3 bundles / 9 points at one supply -- off the grid in both
        # directions at once.
        self._evidence(
            "narrow-campaign",
            NARROW_REC,
            _corner_files(("typical",) + COMBINED_BUNDLES, supplies=("3.30",)),
        )
        # 16 PVT points, every bundle on-grid.
        self._evidence(
            "partial-campaign",
            PARTIAL_REC,
            _corner_files(("fs", "sf"))[:16],
        )
        # One campaign, three records, 9 + 18 + 18 = the mandated 45 -- but
        # only in union, which is how `sim/period-jitter` got there.
        self._evidence("union-campaign", SLICE_TYPICAL, _corner_files(("typical",)))
        self._evidence("union-campaign", SLICE_FF_SS, _corner_files(("ff", "ss")))
        self._evidence("union-campaign", SLICE_FS_SF, _corner_files(("fs", "sf")))
        # 45 points that are not the 45: the mandated top rail is missing.
        self._evidence(
            "skewed-campaign",
            SKEWED_REC,
            _corner_files(MOS_BUNDLES, supplies=("2.97", "3.30", "3.00")),
        )

        for doc in GRADED:
            self.write(doc, "# placeholder\n")

    # -- fixture helpers -------------------------------------------------

    def _record(self, campaign: str, record_id: str, text: str) -> None:
        """A committed records/<record-id>.md -- rules 5 and 6 read this
        directly, since a non-MOS axis's own file names are not something
        evidence() can turn into a bundle/point count, and a non-rectangular
        sample's declared total is not itself a per-corner artifact."""
        d = self.tmp / "sim" / campaign / "records"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{record_id}.md").write_text(text, encoding="utf-8")

    def _evidence(self, campaign: str, record_id: str, files) -> None:
        d = self.tmp / "sim" / campaign / "corners" / record_id
        d.mkdir(parents=True, exist_ok=True)
        for name in files:
            (d / name).write_text("run log\n", encoding="utf-8")

    def write(self, rel: str, text: str) -> None:
        path = self.tmp / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def proposal(self, *rows: str) -> None:
        """A miniature section-5 table -- the shape the real check grades."""
        body = [
            "# Chipalooza Challenge #5 — integer-N PLL proposal",
            "",
            "## 5. Target specification",
            "",
            # Prose, not a table row: satisfies the parser guard (a real
            # document always quotes at least one corner) without being
            # subject to the row-scoped rules 2 and 3.
            "The nominal corner is `typical`/27 °C/3.30 V throughout.",
            "",
            "| Parameter | Target | Measured | Verdict | Source |",
            "|---|---|---|---|---|",
        ]
        body.extend(rows)
        self.write(PROPOSAL, "\n".join(body) + "\n")

    def run_check(self) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(self.tmp / "sim" / "lib" / CHECK.name)],
            capture_output=True,
            text=True,
        )

    def assertPasses(self, result) -> None:
        self.assertEqual(
            result.returncode, 0, f"expected a pass\nstdout:{result.stdout}\nstderr:{result.stderr}"
        )

    def assertFailsWith(self, result, *needles: str) -> None:
        self.assertEqual(
            result.returncode, 1, f"expected a failure\nstdout:{result.stdout}"
        )
        for needle in needles:
            self.assertIn(needle, result.stderr)

    # -- rule 0: the fixture itself --------------------------------------

    def test_a_tree_whose_rows_all_sit_on_the_mandated_grid_passes(self):
        self.proposal(
            "| Lock time | < 100 µs | Worst 71 µs (`ss`/125 °C/2.97 V); "
            "10/45 corners FAIL | **UNMET** | "
            f"`sim/mandated-campaign/records/{MANDATED_REC}.md` |"
        )
        self.assertPasses(self.run_check())

    # -- rule 1: corner names are real -----------------------------------

    def test_a_bundle_the_harness_does_not_define_fails(self):
        self.proposal(
            "| Kvco | ≤ 150 MHz/V | Worst 115.8 MHz/V (`all-medium`/27 °C/2.97 V) "
            f"| **MET** | `sim/superset-campaign/records/{SUPERSET_REC}.md` |"
        )
        self.assertFailsWith(
            self.run_check(),
            "`all-medium`",
            "not a bundle sim/harness/corners.py defines",
        )

    def test_a_renamed_bundle_is_caught_in_every_graded_document(self):
        self.write(
            CHARACTERIZATION,
            "# aggregation\n\n| `vco` | worst at `ff_old`/125 °C/3.63 V |\n",
        )
        self.proposal(
            "| Lock time | < 100 µs | Worst 71 µs (`ss`/125 °C/2.97 V) | **MET** | "
            f"`sim/mandated-campaign/records/{MANDATED_REC}.md` |"
        )
        self.assertFailsWith(self.run_check(), CHARACTERIZATION, "`ff_old`")

    # -- rule 2: off-grid corners are disclosed --------------------------

    def test_an_off_grid_corner_with_no_disclosure_fails(self):
        self.proposal(
            "| Output band | 10–200 MHz | Floor 6.449 MHz (`all-fast`/125 °C/2.97 V) "
            f"| **MET** | `sim/superset-campaign/records/{SUPERSET_REC}.md` |"
        )
        self.assertFailsWith(
            self.run_check(),
            "`all-fast`",
            "does not say which grid it came from",
            "covers 63 PVT points across 7 bundles",
        )

    def test_an_off_grid_corner_disclosed_by_point_count_passes(self):
        self.proposal(
            "| Output band | 10–200 MHz | Floor 6.449 MHz (`all-fast`/125 °C/2.97 V), "
            "over this campaign's 63-point PVT grid, a superset of the mandated grid "
            f"| **MET** | `sim/superset-campaign/records/{SUPERSET_REC}.md` |"
        )
        self.assertPasses(self.run_check())

    def test_an_off_grid_corner_disclosed_by_bundle_count_passes(self):
        self.proposal(
            "| Output band | 10–200 MHz | Floor 6.449 MHz (`all-fast`/125 °C/2.97 V), "
            "measured over the full 7-bundle corner set "
            f"| **MET** | `sim/superset-campaign/records/{SUPERSET_REC}.md` |"
        )
        self.assertPasses(self.run_check())

    def test_a_disclosure_that_repeats_the_mandated_numbers_does_not_count(self):
        """45 points / 5 bundles disclose nothing: they *are* the mandated grid."""
        self.proposal(
            "| Output band | 10–200 MHz | Floor 6.449 MHz (`all-fast`/125 °C/2.97 V), "
            "over the 45-point grid at all 5 bundles "
            f"| **MET** | `sim/superset-campaign/records/{SUPERSET_REC}.md` |"
        )
        self.assertFailsWith(self.run_check(), "does not say which grid it came from")

    def test_a_disclosure_naming_a_count_the_record_does_not_have_fails(self):
        self.proposal(
            "| Output band | 10–200 MHz | Floor 6.449 MHz (`all-fast`/125 °C/2.97 V), "
            "over this campaign's 99-point PVT grid "
            f"| **MET** | `sim/superset-campaign/records/{SUPERSET_REC}.md` |"
        )
        self.assertFailsWith(self.run_check(), "does not say which grid it came from")

    def test_an_off_grid_row_that_cites_no_record_says_so(self):
        self.proposal(
            "| Power | < 5 mW | Derived ≈ 1.98 mW (`all-fast`/125 °C/3.63 V) "
            "| **MET** | `spec/pll.md#power` |"
        )
        self.assertFailsWith(
            self.run_check(), "the row cites no record at all -- name one"
        )

    def test_a_mandated_grid_corner_needs_no_disclosure(self):
        self.proposal(
            "| Supply sensitivity | ≤ 0.6 V | Worst 2.642 V (`ss`/−40 °C/3.63 V) "
            f"| **UNMET** | `sim/mandated-campaign/records/{MANDATED_REC}.md` |"
        )
        self.assertPasses(self.run_check())

    # -- rule 2, trigger (b): off-grid *evidence* is disclosed too ---------

    def test_off_grid_evidence_fails_even_when_every_quoted_corner_is_on_grid(self):
        """The Lock detector case: 13 bundles measured, `fs` and `ss` quoted.

        Trigger (a) alone is a disclosure rule keyed on what a row happens to
        say, and a campaign's worst case does not have to land on the bundles
        the campaign added.
        """
        self.proposal(
            "| Lock detector | 1 … 2 ns | Window edge [1.14, 1.16) ns at "
            "`fs`/−40 °C/3.63 V and [1.78, 1.80) ns at `ss`/125 °C/2.97 V; "
            "0 of 205 points fail | **MET** | "
            f"`sim/wide-campaign/records/{WIDE_REC}.md` |"
        )
        self.assertFailsWith(
            self.run_check(),
            "rests on evidence measured at",
            "does not say which grid it came from",
            "covers 117 PVT points across 13 bundles",
        )

    def test_off_grid_evidence_disclosed_by_bundle_count_passes(self):
        self.proposal(
            "| Lock detector | 1 … 2 ns | Window edge [1.14, 1.16) ns at "
            "`fs`/−40 °C/3.63 V, measured over a 13-bundle PVT grid | **MET** | "
            f"`sim/wide-campaign/records/{WIDE_REC}.md` |"
        )
        self.assertPasses(self.run_check())

    def test_off_grid_evidence_disclosed_by_point_count_passes(self):
        self.proposal(
            "| Lock detector | 1 … 2 ns | Window edge [1.14, 1.16) ns at "
            "`fs`/−40 °C/3.63 V, measured over a 117-point PVT grid | **MET** | "
            f"`sim/wide-campaign/records/{WIDE_REC}.md` |"
        )
        self.assertPasses(self.run_check())

    def test_a_subset_campaign_off_the_grid_discloses_with_a_smaller_count(self):
        """`devchar-passives` is off the grid in both directions at once.

        9 points across 3 bundles: the passive axes reach `ff`/`ss` extremes
        the mandated grid never does, while the five MOS bundles and the
        supply axis are not swept at all. "9-point" is the honest name for
        that, which is why the token has to differ from the mandated numbers
        rather than exceed them.
        """
        self.proposal(
            "| Cap C–V | linear to 5 % | Worst at `all-slow`/125 °C/3.30 V "
            "over this campaign's 9-point passive-corner grid | **MET** | "
            f"`sim/narrow-campaign/records/{NARROW_REC}.md` |"
        )
        self.assertPasses(self.run_check())

        self.proposal(
            "| Cap C–V | linear to 5 % | Worst at `all-slow`/125 °C/3.30 V "
            f"| **MET** | `sim/narrow-campaign/records/{NARROW_REC}.md` |"
        )
        self.assertFailsWith(
            self.run_check(), "covers 9 PVT points across 3 bundles"
        )

    def test_a_count_belonging_to_an_on_grid_record_does_not_disclose(self):
        """A number that matches some *other*, on-grid record is not a grid.

        `sim/CHARACTERIZATION.md`'s period-jitter row says "16 points" about
        the `fs`/`sf` block that completed its 45-point grid, in the same cell
        that cites a 63-point `vco-tuning-range` record.
        """
        self.proposal(
            "| Period jitter | ≤ 1.0 % RMS | the last 16 points close the grid "
            f"| **MET** | `sim/partial-campaign/records/{PARTIAL_REC}.md`, "
            f"`sim/superset-campaign/records/{SUPERSET_REC}.md` |"
        )
        self.assertFailsWith(
            self.run_check(),
            "covers 63 PVT points across 7 bundles",
        )

    def test_a_stated_mandated_grid_the_cited_record_contradicts_fails(self):
        """Rule 3 allows 45 unconditionally, so only trigger (b) catches this.

        `sim/CHARACTERIZATION.md`'s `harness-selftest` row called its record's
        grid "45-point" when that record's own corner field reads "63 point
        full-factorial grid" over 7 bundles.
        """
        self.proposal(
            "| Harness self-test | n/a | real 45-point PVT grid, no design claim "
            f"| **PASS** | `sim/superset-campaign/records/{SUPERSET_REC}.md` |"
        )
        self.assertFailsWith(
            self.run_check(),
            "does not say which grid it came from",
            "covers 63 PVT points across 7 bundles",
        )

    def test_a_row_resting_only_on_mandated_evidence_needs_no_disclosure(self):
        """The no-false-positive guard for trigger (b)."""
        self.proposal(
            "| Power | < 5 mW | 0.9863–1.98 mW over the full grid | **MET** | "
            f"`sim/mandated-campaign/records/{MANDATED_REC}.md` |"
        )
        self.assertPasses(self.run_check())

    # -- rule 3: corner counts have evidence behind them ------------------

    def test_a_corner_denominator_matching_nothing_on_the_tree_fails(self):
        self.proposal(
            "| Supply sensitivity | ≤ 0.6 V | FAILs on 9/40 corners "
            f"| **UNMET** | `sim/mandated-campaign/records/{MANDATED_REC}.md` |"
        )
        self.assertFailsWith(
            self.run_check(), "9/40 corners", "neither the 45-point mandated grid"
        )

    def test_a_denominator_the_cited_record_produces_passes(self):
        self._evidence(
            "spur-campaign",
            "20260816-132150-5f405e7",
            _corner_files(MOS_BUNDLES)[:5],
        )
        self.proposal(
            "| Reference spur | ≤ −55 dBc | PASS at 3/5 corners "
            "| **UNMET** | `sim/spur-campaign/records/20260816-132150-5f405e7.md` |"
        )
        self.assertPasses(self.run_check())

    def test_a_bare_point_count_is_not_graded_as_a_pvt_grid(self):
        """90 output-driver runs are 45 PVT points x 2 band edges, not 90 corners."""
        self.proposal(
            "| Output duty cycle | 45–55 % | 7/90 points below the floor "
            f"| **UNMET** | `sim/mandated-campaign/records/{MANDATED_REC}.md` |"
        )
        self.assertPasses(self.run_check())

    def test_a_grid_size_matching_nothing_on_the_tree_fails(self):
        self.proposal(
            "| Supply sensitivity | ≤ 0.6 V | Full 40-point PVT grid "
            f"| **UNMET** | `sim/mandated-campaign/records/{MANDATED_REC}.md` |"
        )
        self.assertFailsWith(self.run_check(), "40-point PVT grid")

    def test_same_record_inherits_the_previous_rows_citation(self):
        self._evidence(
            "driver-campaign",
            "20260817-100354-0e9cfc9",
            _corner_files(MOS_BUNDLES) + ["raw_measures.csv"],
        )
        csv_path = (
            self.tmp
            / "sim/driver-campaign/corners/20260817-100354-0e9cfc9/raw_measures.csv"
        )
        csv_path.write_text(
            "corner,temp_c,vdd,edge\n"
            + "".join(
                f"{b},{t},{v},{e}\n"
                for b in MOS_BUNDLES
                for t in TEMPS
                for v in SUPPLIES
                for e in ("lo", "hi")
            ),
            encoding="utf-8",
        )
        self.proposal(
            "| Output duty cycle | 45–55 % | 44.4–50.7 % measured | **UNMET** | "
            "`sim/driver-campaign/records/20260817-100354-0e9cfc9.md` |",
            "| Output levels | V_OH ≥ 0.9·VDD | full 90-point grid | **MET** | "
            "Same record |",
        )
        self.assertPasses(self.run_check())

    def test_a_row_that_cites_nothing_cannot_borrow_an_unrelated_rows_record(self):
        self.proposal(
            "| Reference spur | ≤ −55 dBc | 3/5 corners PASS | **UNMET** | "
            f"`sim/mandated-campaign/records/{MANDATED_REC}.md` |",
            "",
            "| Loop bandwidth | ≤ f_ref/10 | 3/5 corners PASS | **MET** | n/a |",
        )
        self.assertFailsWith(self.run_check(), "3/5 corners")

    # -- rule 4: a full-coverage claim is checked point by point -----------

    def test_a_full_coverage_claim_met_by_the_union_of_several_records_passes(self):
        """`sim/period-jitter` reached 45 across five records covering 1-18 each.

        A per-record test would reject the honest row; the union is the unit.
        """
        self.proposal(
            "| Period jitter | ≤ 1.0 % RMS | **All 45 of the mandated PVT "
            "points now measured**, 0.0508–0.2691 % RMS | **MET** | "
            f"`sim/union-campaign/records/{SLICE_TYPICAL}.md`; "
            f"`sim/union-campaign/records/{SLICE_FF_SS}.md`; "
            f"`sim/union-campaign/records/{SLICE_FS_SF}.md` |"
        )
        self.assertPasses(self.run_check())

    def test_a_full_coverage_claim_missing_part_of_the_grid_fails(self):
        """Drop the `fs`/`sf` slice: the claim outruns the evidence by 18 points."""
        self.proposal(
            "| Period jitter | ≤ 1.0 % RMS | **All 45 of the mandated PVT "
            "points now measured** | **MET** | "
            f"`sim/union-campaign/records/{SLICE_TYPICAL}.md`; "
            f"`sim/union-campaign/records/{SLICE_FF_SS}.md` |"
        )
        self.assertFailsWith(
            self.run_check(),
            "covers 27 of the 45 mandated PVT points -- 18 missing",
            "`fs`/-40 °C/2.97 V",
            "has to cite evidence that covers it",
        )

    def test_a_full_coverage_claim_that_cites_no_record_fails(self):
        """The row this rule was written for: a campaign directory is not a citation.

        `sim/CHARACTERIZATION.md`'s Verification-owed cross-reference said the
        deterministic jitter component is "measured at all 45 of the mandated
        PVT corners" and pointed at `sim/period-jitter/`, so nothing -- no
        check and no reader -- could follow the claim to evidence.
        """
        self.proposal(
            "| Period jitter | ≤ 1.0 % RMS | measured at all 45 of the mandated "
            "PVT corners | **MET** | `sim/period-jitter/` |"
        )
        self.assertFailsWith(
            self.run_check(),
            "covers 0 of the 45 mandated PVT points",
            "the row cites no record at all -- name the record(s) whose "
            "evidence covers it",
        )

    def test_full_coverage_is_the_points_and_not_the_count(self):
        """45 measured points that are not the mandated 45 still fail.

        Rules 1-3 all pass this row: every bundle is real and on-grid, and the
        count it states is the mandated grid's own, which rule 3 allows
        unconditionally.
        """
        self.proposal(
            "| Supply sensitivity | ≤ 0.6 V | Full 45-point PVT grid measured "
            f"| **MET** | `sim/skewed-campaign/records/{SKEWED_REC}.md` |"
        )
        self.assertFailsWith(
            self.run_check(),
            "covers 30 of the 45 mandated PVT points -- 15 missing",
            "3.63 V",
        )

    def test_a_saturated_fraction_is_a_full_coverage_claim(self):
        self.proposal(
            "| Period jitter | ≤ 1.0 % RMS | **MET at every measured corner "
            f"(45/45)** | **MET** | `sim/partial-campaign/records/{PARTIAL_REC}.md` |"
        )
        self.assertFailsWith(
            self.run_check(), "covers 16 of the 45 mandated PVT points"
        )

    def test_a_partial_fraction_is_not_a_full_coverage_claim(self):
        """"5 of 45 PVT points measured, not the full grid" is honest, and stays legal.

        This is why rule 3 keeps allowing the mandated size unconditionally:
        naming the grid you did *not* cover is exactly the disclosure these
        checks exist to encourage. Only a saturated fraction is a claim.
        """
        self._evidence(
            "spur-campaign",
            "20260816-132150-5f405e7",
            _corner_files(MOS_BUNDLES)[:5],
        )
        self.proposal(
            "| Reference spur | ≤ −55 dBc | PASS at 5 spanning corners -- 5 of "
            "45 PVT points measured, not the full grid | **UNMET** | "
            "`sim/spur-campaign/records/20260816-132150-5f405e7.md` |"
        )
        self.assertPasses(self.run_check())

    def test_a_full_coverage_claim_backed_by_a_superset_record_passes(self):
        """`period-jitter-band-top` declares the mandated 45 from a 63-point record.

        The superset contains the grid, so the claim is covered; the row still
        has to disclose the wider grid under rule 2, which it does here.
        """
        self.proposal(
            "| Period jitter at band top | ≤ 1.0 % RMS | its full 45-point grid "
            "is declared, derived from a 63-point superset grid | **UNMET** | "
            f"`sim/superset-campaign/records/{SUPERSET_REC}.md` |"
        )
        self.assertPasses(self.run_check())

    def test_a_row_with_no_full_coverage_claim_is_not_graded_by_rule_4(self):
        """The no-false-positive guard: partial coverage, stated plainly, passes."""
        self.proposal(
            "| Period jitter | ≤ 1.0 % RMS | 16 points measured so far "
            f"| **UNMET** | `sim/partial-campaign/records/{PARTIAL_REC}.md` |"
        )
        self.assertPasses(self.run_check())

    # -- the mandated size is derived, not remembered ---------------------

    def test_mandated_grid_points_are_derived_from_the_harness(self):
        """Widen the temperature axis: the 45-point record now covers 45 of 75."""
        corners = self.tmp / "sim" / "harness" / "corners.py"
        text = corners.read_text(encoding="utf-8")
        widened = text.replace(
            "DEFAULT_TEMPERATURES_C: tuple[float, ...] = (-40.0, 27.0, 125.0)",
            "DEFAULT_TEMPERATURES_C: tuple[float, ...] = (-40.0, 0.0, 27.0, 85.0, 125.0)",
        )
        self.assertNotEqual(text, widened, "the temperature axis declaration moved")
        corners.write_text(widened, encoding="utf-8")

        self.proposal(
            "| Supply sensitivity | ≤ 0.6 V | measured at all 75 of the mandated "
            f"PVT corners | **MET** | `sim/mandated-campaign/records/{MANDATED_REC}.md` |"
        )
        self.assertFailsWith(
            self.run_check(), "covers 45 of the 75 mandated PVT points -- 30 missing"
        )

    def test_mandated_grid_size_is_derived_from_the_harness(self):
        """Widen the temperature axis: 45 stops being the mandated grid, 75 starts."""
        corners = self.tmp / "sim" / "harness" / "corners.py"
        text = corners.read_text(encoding="utf-8")
        widened = text.replace(
            "DEFAULT_TEMPERATURES_C: tuple[float, ...] = (-40.0, 27.0, 125.0)",
            "DEFAULT_TEMPERATURES_C: tuple[float, ...] = (-40.0, 0.0, 27.0, 85.0, 125.0)",
        )
        self.assertNotEqual(text, widened, "the temperature axis declaration moved")
        corners.write_text(widened, encoding="utf-8")

        self.proposal(
            "| Supply sensitivity | ≤ 0.6 V | FAILs on 10/45 corners | **UNMET** | "
            "n/a |",
            "| Lock time | < 100 µs | Worst 71 µs (`ss`/125 °C/2.97 V) | **MET** | "
            "n/a |",
        )
        result = self.run_check()
        self.assertFailsWith(result, "10/45 corners", "75-point mandated grid")

        self.proposal(
            "| Supply sensitivity | ≤ 0.6 V | FAILs on 10/75 corners | **UNMET** | "
            "n/a |",
            "| Lock time | < 100 µs | Worst 71 µs (`ss`/125 °C/2.97 V) | **MET** | "
            "n/a |",
        )
        self.assertPasses(self.run_check())

    # -- rule 5: a non-MOS corner axis claim is checked against the record --

    def _non_mos_record(self) -> None:
        self._record(
            "non-mos-campaign",
            NON_MOS_REC,
            "# Record\n\n"
            "- **Corner matrix run**: 81 filter-impedance points (27 "
            "passive-corner bundles x 3 temperatures), each swept over 6 "
            "Vctrl bias points.\n"
            "  - **Axes not swept**: MOS process bundles (`tt/ff/ss/fs/sf`) "
            "N/A -- the filter contains no active device; supply (`vdd`) "
            "N/A for the same reason.\n",
        )

    def test_a_non_mos_axis_claim_matching_the_record_passes(self):
        self._non_mos_record()
        self.proposal(
            "| Loop bandwidth | 26-430 kHz | loop-dynamics sweeps 81 "
            "filter-impedance points (27 passive-corner bundles x 3 "
            "temperatures) and declares the MOS axis N/A "
            f"| **MET** | `sim/non-mos-campaign/records/{NON_MOS_REC}.md` |"
        )
        self.assertPasses(self.run_check())

    def test_a_non_mos_axis_claim_with_the_wrong_count_fails(self):
        self._non_mos_record()
        self.proposal(
            "| Loop bandwidth | 26-430 kHz | loop-dynamics sweeps 82 "
            "filter-impedance points (27 passive-corner bundles x 3 "
            "temperatures) and declares the MOS axis N/A "
            f"| **MET** | `sim/non-mos-campaign/records/{NON_MOS_REC}.md` |"
        )
        self.assertFailsWith(
            self.run_check(),
            "states a non-MOS corner axis as 82 points",
            "declare 81 points (27 bundles x 3 temperatures)",
        )

    def test_a_bare_non_mos_axis_token_matching_the_record_passes(self):
        self._non_mos_record()
        self.proposal(
            "| Loop bandwidth | 26-430 kHz | worst case over the cross-product "
            f"| **MET** | `sim/non-mos-campaign/records/{NON_MOS_REC}.md` |",
            "| Phase margin | >= 45 deg | Same 81-point filter-impedance basis "
            f"as the row above | **MET** | `sim/non-mos-campaign/records/{NON_MOS_REC}.md` |",
        )
        self.assertPasses(self.run_check())

    def test_a_bare_non_mos_axis_token_not_matching_the_record_fails(self):
        self._non_mos_record()
        self.proposal(
            "| Loop bandwidth | 26-430 kHz | worst case over the cross-product "
            f"| **MET** | `sim/non-mos-campaign/records/{NON_MOS_REC}.md` |",
            "| Phase margin | >= 45 deg | Same 82-point filter-impedance basis "
            f"as the row above | **MET** | `sim/non-mos-campaign/records/{NON_MOS_REC}.md` |",
        )
        self.assertFailsWith(
            self.run_check(),
            'states "82" as a point/bundle count',
            "declare 81 points (27 bundles x 3 temperatures) and 82 matches neither",
        )

    # -- rule 6: a non-rectangular sample is checked against declared slices --

    def _non_rect_record(self) -> None:
        self._record(
            "non-rect-campaign",
            NON_RECT_REC,
            "# Record\n\n"
            "- **Corner matrix run**: ...\n"
            "  - **Deliberately non-rectangular**: 12 points run of the 100 "
            "a full cross-product of the axes above would be.\n",
        )
        self._evidence(
            "non-rect-campaign",
            NON_RECT_REC,
            [
                "typical_27c_3.30v_f200n04.log",
                "typical_27c_3.30v_f200n05.log",
                "ss_125c_2.97v_f200n06.log",
            ],
        )

    def test_a_non_rectangular_sample_claim_matching_the_record_passes(self):
        self._non_rect_record()
        self.proposal(
            "| Multiplication ratio | N = 4-64 | 3 distinct N exercised; "
            "12 of its 100 cells, not a grid "
            f"| **MET** | `sim/non-rect-campaign/records/{NON_RECT_REC}.md` |"
        )
        self.assertPasses(self.run_check())

    def test_a_non_rectangular_sample_fraction_mismatch_fails(self):
        self._non_rect_record()
        self.proposal(
            "| Multiplication ratio | N = 4-64 | 3 distinct N exercised; "
            "13 of its 100 cells, not a grid "
            f"| **MET** | `sim/non-rect-campaign/records/{NON_RECT_REC}.md` |"
        )
        self.assertFailsWith(
            self.run_check(),
            "states 13 of 100 cells",
            "declare 12 of 100 cells",
        )

    def test_a_distinct_n_claim_not_matching_the_committed_files_fails(self):
        self._non_rect_record()
        self.proposal(
            "| Multiplication ratio | N = 4-64 | 4 distinct N exercised; "
            "12 of its 100 cells, not a grid "
            f"| **MET** | `sim/non-rect-campaign/records/{NON_RECT_REC}.md` |"
        )
        self.assertFailsWith(
            self.run_check(),
            "claims 4 distinct N",
            "carry 3 distinct N values",
        )

    # -- guards: a check that did not run is not a check that passed ------

    def test_a_missing_graded_document_fails(self):
        self.proposal(
            "| Lock time | < 100 µs | Worst 71 µs (`ss`/125 °C/2.97 V) | **MET** | "
            f"`sim/mandated-campaign/records/{MANDATED_REC}.md` |"
        )
        (self.tmp / README).unlink()
        self.assertFailsWith(self.run_check(), "README.md does not exist")

    def test_documents_with_no_corner_triple_at_all_fail_as_a_parser_error(self):
        for doc in GRADED:
            self.write(doc, "# nothing here quotes a corner\n")
        self.assertFailsWith(
            self.run_check(), "no corner triple", "parser failure, not a clean tree"
        )

    def test_an_unimportable_harness_fails(self):
        (self.tmp / "sim" / "harness" / "corners.py").write_text(
            "raise RuntimeError('broken registry')\n", encoding="utf-8"
        )
        self.proposal(
            "| Lock time | < 100 µs | Worst 71 µs (`ss`/125 °C/2.97 V) | **MET** | "
            f"`sim/mandated-campaign/records/{MANDATED_REC}.md` |"
        )
        self.assertFailsWith(
            self.run_check(), "could not import sim/harness/corners.py"
        )


class RealTreeTest(unittest.TestCase):
    """The committed tree must pass its own check."""

    def test_the_repository_passes_its_own_pvt_coverage_check(self):
        result = subprocess.run(
            ["bash", str(CHECK)], cwd=REPO_ROOT, capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("OK:", result.stdout)


if __name__ == "__main__":
    unittest.main()
