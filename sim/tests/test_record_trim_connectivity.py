#!/usr/bin/env python3
"""Unit tests for ``sim/lib/check-record-trim-connectivity.sh`` (issue #557).

    python3 -m unittest discover -s sim/tests -v

The check exists because DR-026's repository-wide audit of issue #515 was a
text grep -- ``grep -rl 'ldt3_code=1' sim/*/corners/*/`` -- and a grep for the
way one campaign happened to spell a parameter is not an audit of a tree.
Three ``sim/reference-phase-transfer`` records were taken on the same pre-fix
``pll_top`` export, programming a trim code whose MSB the netlist could not
deliver, and that grep could never have returned them: their decks take the
code from ``testbench/tb.json`` through the harness, so the string it looks
for appears in none of their logs. The defect was in those logs the whole
time, as ``ldt3`` at the rail and ``xdut.net1`` at 0 V in the same
operating-point table.

So the properties worth testing are the ones that decide whether this check
repeats that failure:

1. It finds the defect from the ARTIFACTS -- the frozen snapshot's own
   instance line and the frozen log's own node dump -- never from a parameter
   spelling, a manifest, or a campaign name.
2. It needs BOTH halves. A dead port nobody drove is not a finding (that is
   ``sim/lock-window-proxy``, which drives ``delaywin_3v3`` directly), and a
   driven pad on a netlist that wires it is not one either (that is every
   post-DR-026 record).
3. Its one way through is a decision record that exists, is more than a stub,
   and names the campaign back -- and nothing else.

Every test builds a throwaway tree whose answer is known by construction --
miniature snapshots of a dozen lines, logs of a handful -- installs the real
script in it, and runs it. No ngspice, no PDK, no committed evidence.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
CHECK = SIM_DIR / "lib" / "check-record-trim-connectivity.sh"

#: A campaign/record pair the real script's DISCLOSED table names, so the
#: admitted path can be exercised without the test knowing the table's
#: internals.
DISCLOSED_CAMPAIGN = "reference-phase-transfer"
DISCLOSED_RECORD = "20260925-080736-b722f33"
DISCLOSED_DR = (
    "spec/decision-records/"
    "DR-027-reference-phase-transfer-measures-the-exclusions-transfer.md"
)

#: An undisclosed campaign: any name the table does not carry.
PLAIN_CAMPAIGN = "an-experiment"
PLAIN_RECORD = "20260926-101500-abcdef0"


def snapshot(ld_msb_node: str = "LDT3") -> str:
    """A miniature `pll_top` export.

    ``ld_msb_node`` is what the parent wires the lock detector's fourth trim
    terminal to: ``LDT3`` (the real port, post-DR-026) or ``net1`` (xschem's
    auto-generated name for the wire nobody labeled, pre-DR-026).
    """
    return (
        "* a miniature export\n"
        ".subckt lock_detector UP DN LOCK VWIN LDT0 LDT1 LDT2 LDT3 VDD VSS\n"
        "XDLY VWIN LDT0 LDT1 LDT2 LDT3 VDD VSS delaywin_3v3\n"
        ".ends\n"
        ".subckt pll_top REF OUT LOCK LDT0 LDT1 LDT2 LDT3 VDD VSS\n"
        "XLD UP DN LOCK VWIN LDT0 LDT1 LDT2 %s VDD VSS lock_detector\n"
        ".ends\n"
        "xdut ref out lock ldt0 ldt1 ldt2 ldt3 vdd 0 pll_top\n"
        ".end\n" % ld_msb_node
    )


def log(ldt3_volts: str = "3.63", stray_net: bool = True) -> str:
    """A miniature per-corner log carrying ngspice's operating-point table."""
    body = (
        "ngspice-46 done\n"
        "        Node                                   Voltage\n"
        "        ----                                   -------\n"
        "vdd                                       3.63\n"
        "ldt0                                         0\n"
        "ldt2                                         0\n"
        "ldt3                                      %s\n"
        "ldt30                                     1.23\n" % ldt3_volts
    )
    if stray_net:
        body += "xdut.net1                                    0\n"
    return body


class _Tree:
    """A throwaway repo tree with the real check installed."""

    def __init__(self, root: Path):
        self.root = root
        (root / "sim" / "lib").mkdir(parents=True)
        shutil.copy2(CHECK, root / "sim" / "lib" / CHECK.name)

    def write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def campaign(
        self,
        name: str,
        record: str,
        snap_text: str,
        log_text: str | None,
        snap_suffix: str = "",
    ) -> None:
        self.write("sim/%s/records/%s.md" % (name, record), "# a record\n")
        self.write(
            "sim/%s/netlist-snapshots/%s%s.spice" % (name, record, snap_suffix),
            snap_text,
        )
        if log_text is not None:
            self.write(
                "sim/%s/corners/%s/ff_-40c_3.63v.log" % (name, record), log_text
            )

    def disclosure(self, rel: str, campaign: str, size: int = 4000) -> None:
        """A decision record that exists, is not a stub, and names `campaign`."""
        text = "# a disclosure naming sim/%s/\n" % campaign
        text += "x" * max(0, size - len(text))
        self.write(rel, text)

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


class TestBothHalvesAreRequired(_TreeTest):
    """The finding is the PAIR: this pin is driven, and it goes nowhere."""

    def test_a_dead_port_and_a_driven_pad_is_the_defect(self):
        self.tree.campaign(PLAIN_CAMPAIGN, PLAIN_RECORD, snapshot("net1"), log())
        result = self.assertFails(
            "drove a pin its netlist could not deliver",
            "'LDT3'",
            "3.630 V",
        )
        self.assertIn("#557", result.stderr)

    def test_a_wired_port_with_the_same_driven_pad_is_not(self):
        """Every post-DR-026 record drives `ldt3`; that alone is no finding."""
        self.tree.campaign(PLAIN_CAMPAIGN, PLAIN_RECORD, snapshot("LDT3"), log())
        result = self.assertPasses()
        self.assertIn("0 dead declared port", result.stdout)

    def test_a_dead_port_nobody_drove_is_reported_and_passes(self):
        """`sim/lock-window-proxy`'s shape: broken export, unused pin."""
        self.tree.campaign(
            PLAIN_CAMPAIGN, PLAIN_RECORD, snapshot("net1"), log(ldt3_volts="0")
        )
        result = self.assertPasses()
        self.assertIn("nothing that record measured passed through", result.stdout)
        self.assertIn("1 did not drive it at all", result.stdout)

    def test_a_pad_absent_from_the_log_entirely_is_not_a_finding(self):
        self.tree.campaign(
            PLAIN_CAMPAIGN,
            PLAIN_RECORD,
            snapshot("net1"),
            "ngspice-46 done\nno operating point here\n",
        )
        self.assertPasses()


class TestItReadsArtifactsNotParameterSpellings(_TreeTest):
    """The failure mode this check replaces: grepping for one deck's spelling."""

    def test_a_log_that_never_says_ldt3_code_is_still_caught(self):
        """The exact blind spot of `grep -rl 'ldt3_code=1'` (#557)."""
        text = log()
        self.assertNotIn("ldt3_code", text)
        self.tree.campaign(PLAIN_CAMPAIGN, PLAIN_RECORD, snapshot("net1"), text)
        self.assertFails("drove a pin its netlist could not deliver")

    def test_a_longer_node_sharing_the_pads_prefix_is_not_matched(self):
        """`ldt3` must not be read off `ldt30`'s row."""
        text = log(ldt3_volts="0")
        self.assertIn("ldt30", text)
        self.tree.campaign(PLAIN_CAMPAIGN, PLAIN_RECORD, snapshot("net1"), text)
        self.assertPasses()

    def test_a_campaign_with_no_committed_record_is_not_graded(self):
        """A declared campaign that has measured nothing claims nothing."""
        self.tree.write(
            "sim/%s/netlist-snapshots/%s.spice" % (PLAIN_CAMPAIGN, PLAIN_RECORD),
            snapshot("net1"),
        )
        self.tree.write(
            "sim/%s/corners/%s/ff_-40c_3.63v.log" % (PLAIN_CAMPAIGN, PLAIN_RECORD),
            log(),
        )
        self.assertPasses()

    def test_a_campaign_with_records_and_no_snapshots_is_named_not_passed(self):
        self.tree.write(
            "sim/%s/records/%s.md" % (PLAIN_CAMPAIGN, PLAIN_RECORD), "# a record\n"
        )
        result = self.assertPasses()
        self.assertIn("ungradeable by this check, not graded clean", result.stdout)
        self.assertIn(PLAIN_CAMPAIGN, result.stdout)

    def test_a_device_level_deck_with_no_subcircuit_is_named_not_passed(self):
        """`sim/devchar-*`: no hierarchy, so no declared port to lose."""
        self.tree.write(
            "sim/%s/records/%s.md" % (PLAIN_CAMPAIGN, PLAIN_RECORD), "# a record\n"
        )
        self.tree.write(
            "sim/%s/netlist-snapshots/%s.spice" % (PLAIN_CAMPAIGN, PLAIN_RECORD),
            "* a device-level deck\nvdd vdd 0 dc 3.3\n.end\n",
        )
        result = self.assertPasses()
        self.assertIn("define no subcircuit at all", result.stdout)


class TestTheSingleConnectionSignature(_TreeTest):
    """An auto-named net with two connections is a real net, not a loose end."""

    def test_an_auto_named_net_read_somewhere_else_is_not_dead(self):
        text = snapshot("net1").replace(
            "xdut ref out lock ldt0 ldt1 ldt2 ldt3 vdd 0 pll_top\n",
            "xdut ref out lock ldt0 ldt1 ldt2 ldt3 vdd 0 pll_top\n"
            "xprobe net1 vdd 0 lock_detector\n",
        )
        self.tree.campaign(PLAIN_CAMPAIGN, PLAIN_RECORD, text, log())
        self.assertPasses()

    def test_a_named_net_is_never_the_signature(self):
        """Only xschem's `net<N>` shape counts; a labeled wire is deliberate."""
        self.tree.campaign(
            PLAIN_CAMPAIGN, PLAIN_RECORD, snapshot("spare_trim"), log()
        )
        result = self.assertPasses()
        self.assertIn("0 dead declared port", result.stdout)


class TestTheDisclosedTableIsTheOnlyWayThrough(_TreeTest):
    def _disclosed_tree(self, **kwargs) -> None:
        self.tree.campaign(
            DISCLOSED_CAMPAIGN, DISCLOSED_RECORD, snapshot("net1"), log()
        )
        self.tree.disclosure(DISCLOSED_DR, DISCLOSED_CAMPAIGN, **kwargs)

    def test_a_named_decision_record_admits_the_finding(self):
        self._disclosed_tree()
        result = self.assertPasses()
        self.assertIn("DISCLOSED:", result.stdout)
        self.assertIn(DISCLOSED_DR, result.stdout)

    def test_an_admitted_finding_is_still_counted_and_named(self):
        """The allowance buys `accounted for`, never `invisible`."""
        self._disclosed_tree()
        result = self.assertPasses()
        self.assertIn("1 record/pin pair(s) drove one", result.stdout)

    def test_a_missing_decision_record_fails(self):
        self.tree.campaign(
            DISCLOSED_CAMPAIGN, DISCLOSED_RECORD, snapshot("net1"), log()
        )
        self.assertFails("that file does not exist")

    def test_a_stub_decision_record_fails(self):
        self._disclosed_tree(size=200)
        self.assertFails("under this check's 1500-byte floor")

    def test_a_decision_record_that_does_not_name_the_campaign_fails(self):
        self.tree.campaign(
            DISCLOSED_CAMPAIGN, DISCLOSED_RECORD, snapshot("net1"), log()
        )
        self.tree.disclosure(DISCLOSED_DR, "some-other-campaign")
        self.assertFails("never mentions")

    def test_the_table_is_keyed_on_the_record_not_the_campaign(self):
        """A LATER record of a disclosed campaign is a new, undisclosed fact."""
        self.tree.campaign(
            DISCLOSED_CAMPAIGN, "20261001-120000-0000000", snapshot("net1"), log()
        )
        self.tree.disclosure(DISCLOSED_DR, DISCLOSED_CAMPAIGN)
        self.assertFails("drove a pin its netlist could not deliver")

    def test_no_environment_variable_opens_a_second_way_through(self):
        self.tree.campaign(PLAIN_CAMPAIGN, PLAIN_RECORD, snapshot("net1"), log())
        for var in ("SKIP", "LOOM_FORCE_SCOPE", "ALLOW_TRIM_DEFECT"):
            with self.subTest(var=var):
                result = subprocess.run(
                    ["bash", str(self.tree.root / "sim" / "lib" / CHECK.name)],
                    capture_output=True,
                    text=True,
                    env=dict(os.environ, **{var: "1"}),
                )
                self.assertEqual(result.returncode, 1)


class TestSnapshotToRecordResolution(_TreeTest):
    def test_a_suffixed_snapshot_resolves_to_its_own_record(self):
        """`...-0f91a9b-dyn.spice` is a second snapshot of one record."""
        self.tree.campaign(
            PLAIN_CAMPAIGN,
            PLAIN_RECORD,
            snapshot("net1"),
            log(),
            snap_suffix="-dyn",
        )
        self.assertFails("sim/%s/records/%s.md" % (PLAIN_CAMPAIGN, PLAIN_RECORD))

    def test_a_snapshot_with_no_record_id_in_its_name_fails_loudly(self):
        self.tree.write(
            "sim/%s/records/%s.md" % (PLAIN_CAMPAIGN, PLAIN_RECORD), "# a record\n"
        )
        self.tree.write(
            "sim/%s/netlist-snapshots/whatever.spice" % PLAIN_CAMPAIGN,
            snapshot("net1"),
        )
        self.assertFails("cannot tell which record it froze")


if __name__ == "__main__":
    unittest.main()
