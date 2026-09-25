#!/usr/bin/env python3
"""Unit tests for ``sim/lib/check-bias-drive-claims.sh`` (issue #237).

    python3 -m unittest discover -s sim/tests -v

The check grades what ``docs/chipalooza/challenge-5-proposal.md`` says about
how the closed-loop testbenches drive the four charge-pump bias references
(``IBN``/``ICN``/``IBP``/``ICP``) against the committed decks, and grades a
quotation it attributes "verbatim" to evidence records against those records.
Both defects it was written for were real: section 4 sent a bench operator to
a ``.param iunit=8u`` line ``tb_lock_time.sp`` does not contain (its value
comes from ``run.sh``), and section 2.2 attributed "a separate, unbuilt block"
to every closed-loop record when 7 of 35 say it.

Every test builds a throwaway tree whose answer is known -- a few miniature
decks, run scripts and records, one miniature proposal -- installs the real
script in it, and runs it. No ngspice, no PDK.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SIM_DIR.parent
CHECK = SIM_DIR / "lib" / "check-bias-drive-claims.sh"

PROPOSAL = "docs/chipalooza/challenge-5-proposal.md"
README = "README.md"
CHARACTERIZATION = "sim/CHARACTERIZATION.md"

#: The four bias sources, in the orientation every real closed-loop deck uses.
SOURCES = (
    "iibn vdd ibn dc 'iunit'\n"
    "iicn vdd icn dc 'iunit'\n"
    "iibp ibp 0   dc 'iunit'\n"
    "iicp icp 0   dc 'iunit'\n"
)

#: What makes a campaign closed-loop: it composes the assembled PLL.
COMPOSES = "* design/netlist/pll_top.spice is composed ahead of this deck\n"


def _deck(param: str | None = ".param iunit=8u", sources: str = SOURCES,
          composes: bool = True) -> str:
    out = "* a miniature deck\n"
    if composes:
        out += COMPOSES
    if param:
        out += param + "\n"
    return out + sources + ".end\n"


#: A run.sh that supplies the value on the command line, as lock-time's does.
RUN_SH = 'IUNIT=8u\nparams=( "vsup=${vdd}" "iunit=${IUNIT}" )\n'

#: The drive claim, in the proposal's shape, citing a deck that sets the value.
GOOD_CLAIM = (
    "1. **Bring-up.** `IBN` and `ICN` are sourced *into* the die from the\n"
    "   supply side, `IBP` and `ICP` are sunk *out of* the die to `VSS`, each at\n"
    "   the 8 µA every closed-loop record in this repository drives them with\n"
    "   (`.param iunit=8u` in the decks of `sim/pll-top-smoke`; `IUNIT=8u` in\n"
    "   `sim/lock-time/testbench/run.sh`; the polarity is those decks' own\n"
    "   `iibn vdd ibn` / `iibp ibp 0`).\n"
)


class _Tree:
    """A throwaway repo tree with the real check installed."""

    def __init__(self, root: Path):
        self.root = root
        (root / "sim" / "lib").mkdir(parents=True)
        shutil.copy2(CHECK, root / "sim" / "lib" / CHECK.name)
        for rel in (README, CHARACTERIZATION, PROPOSAL):
            self.write(rel, "# placeholder\n")

    def write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def run(self) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(self.root / "sim" / "lib" / CHECK.name)],
            capture_output=True,
            text=True,
            env=dict(os.environ),
        )


class _TreeTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tree = _Tree(Path(self._tmp.name))
        self.addCleanup(self._tmp.cleanup)
        # Baseline: one closed-loop deck that sets its own value, one that
        # takes it from run.sh (lock-time's real shape), and one charge-pump-
        # only deck at another current that is not closed-loop at all.
        self.tree.write("sim/pll-top-smoke/testbench/tb_pll_smoke.sp", _deck())
        self.tree.write("sim/lock-time/testbench/tb_lock_time.sp", _deck(param=None))
        self.tree.write("sim/lock-time/testbench/run.sh", RUN_SH)
        self.tree.write(
            "sim/cp-compliance/testbench/tb_cp_dc.sp",
            _deck(param=".param iunit=2u", composes=False),
        )

    def claim(self, text: str) -> None:
        self.tree.write(PROPOSAL, "# proposal\n\n" + text)

    def assertPasses(self) -> subprocess.CompletedProcess:
        result = self.tree.run()
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        return result

    def assertFails(self, *needles: str) -> subprocess.CompletedProcess:
        result = self.tree.run()
        self.assertEqual(result.returncode, 1, msg=result.stdout + result.stderr)
        for needle in needles:
            self.assertIn(needle, result.stderr)
        return result


class TestEnumeration(_TreeTest):
    def test_a_tree_with_no_claims_passes(self):
        result = self.assertPasses()
        self.assertIn("2 closed-loop deck(s) across 2 campaign(s)", result.stdout)

    def test_charge_pump_only_decks_are_not_closed_loop(self):
        """cp-compliance's 2 µA deck would fail rule 4 if it counted."""
        self.claim(GOOD_CLAIM)
        self.assertPasses()

    def test_no_closed_loop_deck_fails(self):
        for rel in ("sim/pll-top-smoke/testbench/tb_pll_smoke.sp",
                    "sim/lock-time/testbench/tb_lock_time.sp"):
            (self.tree.root / rel).unlink()
        self.assertFails("enumeration is broken")

    def test_an_unresolvable_value_fails(self):
        self.tree.write("sim/lock-time/testbench/run.sh", "# sets nothing\n")
        self.assertFails("cannot resolve the current")

    def test_a_tb_json_params_entry_resolves(self):
        self.tree.write("sim/period-jitter/testbench/tb_period_jitter.sp",
                        _deck(param=None))
        self.tree.write("sim/period-jitter/testbench/tb.json",
                        '{"params": {"iunit": "8u"}}\n')
        result = self.assertPasses()
        self.assertIn("3 closed-loop deck(s)", result.stdout)

    def test_netlist_snapshots_are_not_decks(self):
        self.tree.write("sim/lock-time/netlist-snapshots/x.spice",
                        _deck(param=".param iunit=99u"))
        self.claim(GOOD_CLAIM)
        self.assertPasses()


class TestDriveClaim(_TreeTest):
    def test_the_good_claim_passes(self):
        self.claim(GOOD_CLAIM)
        result = self.assertPasses()
        self.assertIn("1 drive claim(s)", result.stdout)

    def test_citing_a_deck_that_does_not_set_the_value_fails(self):
        """The defect this check was written for, in section 4 step 1."""
        self.claim(GOOD_CLAIM.replace(
            "`sim/lock-time/testbench/run.sh`",
            "`sim/lock-time/testbench/tb_lock_time.sp`"))
        self.assertFails("tb_lock_time.sp` as where", "sets no such value",
                         "sim/lock-time/testbench/run.sh")

    def test_citing_a_campaign_whose_value_is_set_another_way_fails(self):
        """`sim/output-range` next to `.param iunit=8u`, with the value in run.sh."""
        self.claim(GOOD_CLAIM.replace("`sim/pll-top-smoke`", "`sim/lock-time`")
                   .replace("`IUNIT=8u` in\n   `sim/lock-time/testbench/run.sh`",
                            "nothing else"))
        self.assertFails("cites `sim/lock-time` as where",
                         "not one of the settings the document quotes")

    def test_quoting_the_shell_setting_for_a_campaign_passes(self):
        self.claim(GOOD_CLAIM.replace("`sim/lock-time/testbench/run.sh`",
                                      "`sim/lock-time`"))
        self.assertPasses()

    def test_a_script_that_feeds_no_deck_fails(self):
        self.tree.write("sim/lock-time/testbench/other.sh", "IUNIT=8u\n")
        self.claim(GOOD_CLAIM.replace("run.sh", "other.sh"))
        self.assertFails("other.sh` as where", "not where any")

    def test_a_cited_campaign_at_another_current_fails(self):
        self.tree.write("sim/pll-top-smoke/testbench/tb_pll_smoke.sp",
                        _deck(param=".param iunit=16u"))
        self.claim(GOOD_CLAIM)
        self.assertFails("cites `sim/pll-top-smoke`", "runs at 16 µA")

    def test_a_quoted_setting_at_another_current_fails(self):
        self.claim(GOOD_CLAIM.replace("`IUNIT=8u`", "`IUNIT=4u`"))
        self.assertFails("quotes the setting `IUNIT=4u`, which is 4 µA")

    def test_a_stated_current_the_decks_do_not_run_fails(self):
        self.claim(GOOD_CLAIM.replace("the 8 µA", "the 10 µA")
                   .replace("iunit=8u", "iunit=10u").replace("IUNIT=8u", "IUNIT=10u"))
        self.assertFails("states 10 µA")

    def test_a_cited_campaign_with_no_closed_loop_deck_fails(self):
        self.claim(GOOD_CLAIM.replace("`sim/pll-top-smoke`", "`sim/cp-compliance`"))
        self.assertFails("cites `sim/cp-compliance`", "has no closed-loop deck")

    def test_an_uncited_closed_loop_deck_at_another_current_fails(self):
        """Rule 4: "every closed-loop record" is graded over every deck."""
        self.tree.write("sim/output-range/testbench/tb_output_range.sp",
                        _deck(param=".param iunit=12u"))
        self.claim(GOOD_CLAIM)
        self.assertFails("what every closed-loop record drives",
                         "tb_output_range.sp", "runs at 12 µA")

    def test_a_quoted_source_line_a_cited_deck_lacks_fails(self):
        self.tree.write(
            "sim/pll-top-smoke/testbench/tb_pll_smoke.sp",
            _deck(sources=SOURCES.replace("iibn vdd ibn", "ibias_n vdd ibn")),
        )
        self.claim(GOOD_CLAIM)
        self.assertFails("quotes `iibn vdd ibn`", "tb_pll_smoke.sp")

    def test_a_reversed_source_fails_the_stated_polarity(self):
        self.tree.write(
            "sim/lock-time/testbench/tb_lock_time.sp",
            _deck(param=None, sources=SOURCES.replace("iibp ibp 0", "iibp 0 ibp")),
        )
        self.claim(GOOD_CLAIM)
        self.assertFails("`IBP` is sourced out of the die", "tb_lock_time.sp")

    def test_a_document_making_no_drive_claim_is_not_graded(self):
        self.tree.write("sim/pll-top-smoke/testbench/tb_pll_smoke.sp",
                        _deck(param=".param iunit=16u"))
        self.claim("The bias pins are driven from ideal sources.\n")
        self.assertPasses()


class TestVerbatimQuotation(_TreeTest):
    PHRASE = "a separate, unbuilt block"

    def setUp(self) -> None:
        super().setUp()
        self.tree.write("sim/pll-top-smoke/records/20260802-000000-aaaaaaa.md",
                        "- **Limitations**: The bias generator is a separate,\n"
                        "  unbuilt block; nothing here models it.\n")
        self.tree.write("sim/lock-time/records/20260801-000000-bbbbbbb.md",
                        "- **Limitations**: schematic-level.\n")

    def test_a_universal_attribution_most_records_lack_fails(self):
        """The defect this check was written for, in section 2.2."""
        self.claim('| `IBN` | in | x | 1 | is "%s" (every closed-loop evidence '
                   "record's own Limitations field says so verbatim). |\n" % self.PHRASE)
        self.assertFails("attributes it verbatim to every closed-loop record",
                         "1 of the 2", "sim/lock-time/records/20260801-000000-bbbbbbb.md")

    def test_naming_the_records_that_say_it_passes(self):
        self.claim('| `IBN` | in | x | 1 | is "%s" (quoted verbatim from '
                   "`sim/pll-top-smoke/records/20260802-000000-aaaaaaa.md`). |\n"
                   % self.PHRASE)
        result = self.assertPasses()
        self.assertIn("1 verbatim quotation(s)", result.stdout)

    def test_naming_a_record_that_does_not_say_it_fails(self):
        self.claim('The generator is "%s" (quoted verbatim from '
                   "`sim/lock-time/records/20260801-000000-bbbbbbb.md`).\n" % self.PHRASE)
        self.assertFails("the records it names", "does not contain it")

    def test_naming_a_record_that_does_not_exist_fails(self):
        self.claim('The generator is "%s" (quoted verbatim from '
                   "`sim/lock-time/records/20990101-000000-ccccccc.md`).\n" % self.PHRASE)
        self.assertFails("does not exist")

    def test_verbatim_with_nothing_to_look_in_is_not_graded(self):
        self.claim('This document is emailed verbatim; it says "%s".\n' % "anything")
        self.assertPasses()


class TestRealTree(unittest.TestCase):
    """The check must pass on this repository as committed."""

    def test_the_repository_passes(self):
        result = subprocess.run(
            ["bash", str(CHECK)], capture_output=True, text=True, cwd=str(REPO_ROOT)
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
