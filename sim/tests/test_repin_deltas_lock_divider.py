"""The lock-detector / lock-window / divider re-pin delta document (#827).

`sim/REPIN-DELTAS-f6eeac7-lock-divider.md` makes three kinds of claim that a
reader cannot check by eye, and each is asserted here instead of trusted:

- **Its tables are generated, not typed.** Every table in that document is
  preceded by the `sim/lib/record_delta.py` command that produces it, so
  those commands must keep working against the committed records *and* their
  output must still be what the document shows. A record pair that drifts
  from the prose is the failure mode a delta document invites.

- **No re-qualified bench flipped a per-corner verdict or moved a limit** --
  #827's third acceptance criterion. Five of the six pairs carry zero findings
  and are asserted at zero. The sixth, `lock-window-bisection`, carries six, and the
  document's claim about them is specific: every one is `FAIL` in BOTH
  records, on the same check, so none is a PASS->FAIL flip. That is asserted
  as stated rather than waved at, because "six findings, all benign" is
  exactly the shape a real regression would hide in. The one real movement in
  the group is a `lock-window-proxy` *policy* row that no per-corner
  comparator can see, so its before/after is asserted from the committed
  `proxy_candidates.csv` directly.

- **Two cited records cannot be re-run at all**, because the DUT or the
  stimulus deck they measured is no longer in the tree. Both halves of that
  are checkable without a simulator: the stimulus hash the record names is
  not the file's hash today, and the sizing deck instantiates `delaywin_3v3`
  with fewer terminals than the committed cell declares.

Run:  python3 -m unittest discover -s sim/tests -v
"""

from __future__ import annotations

import re
import subprocess
import sys
import unittest
from hashlib import sha256
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SIM_DIR.parent
sys.path.insert(0, str(SIM_DIR / "lib"))

import record_delta  # noqa: E402

DOC = SIM_DIR / "REPIN-DELTAS-f6eeac7-lock-divider.md"

#: A fenced regeneration command, as the document writes it:
#:     python3 sim/lib/record_delta.py \
#:       sim/<slug>/records/<old>.md \
#:       sim/<slug>/records/<new>.md
REGEN = re.compile(
    r"python3 sim/lib/record_delta\.py \\\n"
    r"\s+(sim/[\w.-]+/records/[\d-]+-\w+\.md) \\\n"
    r"\s+(sim/[\w.-]+/records/[\d-]+-\w+\.md)\n"
)

#: Pairs with no finding at all. `lock-window-bisection` is deliberately not
#: here -- it has six, and they get their own, stricter test.
CLEAN_PAIRS = [
    ("lock-detector", "20260919-002812-1b12179", "20261114-091604-ffbc0e2"),
    ("divider-ratio-dff", "20260801-125114-3f883e3", "20261114-080736-f53d562"),
    ("divider-ratio-cell", "20260801-140529-3f883e3", "20261114-083606-f53d562"),
    ("divider-ratio-chain", "20260802-100727-082c879", "20261114-093804-ad9eef8"),
    ("lock-window-proxy", "20260925-050022-6d57802", "20261114-194051-c8750de"),
]

BISECTION = ("lock-window-bisection",
             "20260925-162032-e341b58", "20261114-191343-8cb0847")


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
        merely *accompanied* by a command, it is the command's output.
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
                # Every non-blank line of the generated table must appear in
                # the document verbatim. Comparing line by line rather than as
                # one block keeps the failure message readable.
                missing = [ln for ln in r.stdout.splitlines()
                           if ln.strip() and ln not in text]
                self.assertEqual(
                    missing[:3], [],
                    f"{new_rel}: the document does not show this generated "
                    f"output -- regenerate it ({len(missing)} line(s) differ)",
                )


class NoReQualifiedBenchFlippedAPerCornerVerdictOrMovedALimit(unittest.TestCase):
    """#827's third acceptance criterion at the per-corner level.

    The one movement that criterion does bite on is a *policy* row of
    `lock-window-proxy`'s `proxy_candidates.csv`, which is a reduction over
    the grid rather than a per-corner row -- asserted separately below.
    """

    def test_the_four_clean_pairs_carry_no_finding(self):
        for slug, old, new in CLEAN_PAIRS:
            with self.subTest(slug=slug):
                _lines, findings = record_delta.compare(
                    REPO_ROOT / f"sim/{slug}/records/{old}.md",
                    REPO_ROOT / f"sim/{slug}/records/{new}.md",
                )
                self.assertEqual(
                    findings, 0,
                    f"{slug}: the delta document claims 0 findings for this pair",
                )

    def test_every_bisection_finding_is_fail_in_both_records(self):
        """Six findings, and the claim is that none of them is a flip.

        A PASS -> FAIL row would read identically in the finding *count*, so
        the count is not the assertion: the old and new verdict strings are.
        """
        slug, old, new = BISECTION
        lines, findings = record_delta.compare(
            REPO_ROOT / f"sim/{slug}/records/{old}.md",
            REPO_ROOT / f"sim/{slug}/records/{new}.md",
        )
        self.assertEqual(findings, 6,
                         "the document accounts for exactly six findings here")

        rows = [ln for ln in lines
                if ln.startswith("| `procedure` | `") and "FAIL" in ln]
        self.assertEqual(len(rows), 6, "\n".join(lines))
        for ln in rows:
            with self.subTest(row=ln[:60]):
                cells = [c.strip() for c in ln.strip("|").split("|")]
                old_verdict, new_verdict = cells[2], cells[3]
                self.assertTrue(
                    old_verdict.startswith("FAIL") and new_verdict.startswith("FAIL"),
                    f"not a benign row: old={old_verdict!r} new={new_verdict!r}",
                )
                self.assertIn("lock_pre min=3.2", old_verdict)
                self.assertIn("lock_pre min=3.2", new_verdict)


class TheProxyPolicyVerdictsTheDocumentReports(unittest.TestCase):
    """The one movement #827's third criterion bites on.

    `proxy_candidates.csv` is a reduction over the whole grid, so no
    per-corner comparator can reach it -- which is exactly why the document
    writes the two moving rows out by hand, and why they are asserted here.
    If a later re-run moves them again, the document and this test stop being
    true at the same moment.
    """

    EXPECTED = {
        # policy: (worst_code_error, verdict)
        "RULE (internal t_win)": ("0", "all in-band"),
        "ring_a": ("8", "OUT OF BAND somewhere"),
        "ring_b": ("8", "OUT OF BAND somewhere"),
        "clk_fb": ("8", "OUT OF BAND somewhere"),   # was 4 / all in-band
        "clk_do": ("2", "all in-band"),             # was 4 / all in-band
        "NONE (untrimmed, c8)": ("5", "OUT OF BAND somewhere"),
    }

    def _candidates(self, record_id):
        import csv
        path = (SIM_DIR / "lock-window-proxy" / "corners" / record_id
                / "proxy_candidates.csv")
        self.assertTrue(path.is_file(), f"{path} missing")
        with path.open(encoding="utf-8") as fh:
            rows = list(csv.DictReader(
                ln for ln in fh if not ln.startswith("#")))
        return {r["policy"]: r for r in rows}

    def test_the_new_record_scores_each_policy_as_documented(self):
        rows = self._candidates("20261114-194051-c8750de")
        self.assertEqual(sorted(rows), sorted(self.EXPECTED))
        for policy, (err, verdict) in self.EXPECTED.items():
            with self.subTest(policy=policy):
                self.assertEqual(rows[policy]["worst_code_error"], err)
                self.assertEqual(rows[policy]["verdict"], verdict)

    def test_clk_fb_flipped_and_clk_do_improved_against_the_predecessor(self):
        old = self._candidates("20260925-050022-6d57802")
        new = self._candidates("20261114-194051-c8750de")

        self.assertEqual(old["clk_fb"]["verdict"], "all in-band")
        self.assertEqual(new["clk_fb"]["verdict"], "OUT OF BAND somewhere")
        self.assertEqual((old["clk_fb"]["worst_code_error"],
                          new["clk_fb"]["worst_code_error"]), ("4", "8"))

        # clk_do moves the other way: still in-band, and its code error comes
        # inside DR-022 Tier A's +3 bound, which is the second stale sub-claim.
        self.assertEqual(old["clk_do"]["verdict"], "all in-band")
        self.assertEqual(new["clk_do"]["verdict"], "all in-band")
        self.assertEqual((old["clk_do"]["worst_code_error"],
                          new["clk_do"]["worst_code_error"]), ("4", "2"))

    def test_the_normative_rule_row_did_not_move_at_all(self):
        """The window itself is PDK-invariant here; only the proxies moved."""
        old = self._candidates("20260925-050022-6d57802")["RULE (internal t_win)"]
        new = self._candidates("20261114-194051-c8750de")["RULE (internal t_win)"]
        self.assertEqual(old, new)


class TheTwoRecordsThatCannotBeReRun(unittest.TestCase):
    """Both refusals are checkable from the tree, with no simulator."""

    def test_the_untrimmed_lock_detector_deck_is_no_longer_in_the_tree(self):
        record = (SIM_DIR / "lock-detector" / "records"
                  / "20260916-052313-b1633b5.md")
        self.assertTrue(record.is_file(), f"{record} missing")
        named = re.search(r"tb_lock_detector_harness\.sp` \(SHA-256 `(\w+)`\)",
                          record.read_text(encoding="utf-8"))
        self.assertIsNotNone(named, "record does not name its stimulus hash")
        on_tree = sha256(
            (SIM_DIR / "lock-detector" / "testbench"
             / "tb_lock_detector_harness.sp").read_bytes()
        ).hexdigest()
        self.assertNotEqual(
            named.group(1), on_tree,
            "the untrimmed deck IS in the tree -- this record is re-runnable "
            "after all, and the delta document's refusal is wrong",
        )

    def test_the_sizing_deck_underfills_the_committed_delaywin_cell(self):
        deck = (SIM_DIR / "lock-window-sizing" / "testbench"
                / "tb_lock_window.sp").read_text(encoding="utf-8")
        inst = re.search(r"^\s*xctl\s+(.*?delaywin_3v3)\s*$", deck,
                         re.MULTILINE | re.IGNORECASE)
        self.assertIsNotNone(inst, "the deck no longer instantiates delaywin_3v3")
        # "<name> <nets...> <subckt>" -- everything between is a terminal.
        deck_terminals = len(inst.group(1).split()) - 1

        netlist = (REPO_ROOT / "design" / "netlist"
                   / "lock_detector.spice").read_text(encoding="utf-8")
        decl = re.search(r"^\.subckt\s+delaywin_3v3\s+(.*)$", netlist,
                         re.MULTILINE)
        self.assertIsNotNone(decl, "delaywin_3v3 is not in the netlist")
        cell_ports = len(decl.group(1).split())

        self.assertLess(
            deck_terminals, cell_ports,
            f"the deck drives {deck_terminals} terminal(s) and the committed "
            f"cell declares {cell_ports} port(s) -- if these now agree the "
            "deck composes and the delta document's refusal is wrong",
        )


if __name__ == "__main__":
    unittest.main()
