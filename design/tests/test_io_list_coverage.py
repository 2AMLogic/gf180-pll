#!/usr/bin/env python3
"""Unit tests for ``design/lib/check-io-list-coverage.sh`` (issue #237).

    python3 -m unittest discover -s design/tests -v

The check grades the Chipalooza proposal's I/O list -- #237's AC4 deliverable
whose source of truth is not a document but ``design/netlist/pll_top.spice``,
the committed export of ``design/pll_top.sch``.  ``sim/lib/pll_top_dut.sh``
already refuses to run a closed-loop campaign whose netlist port list does not
match its own ``CLOOP_PORTS``, name for name and in order; the document written
to be emailed verbatim to an outside reader had no equivalent guard, and its
reader cannot re-run anything to find out.

The drift is historical, not hypothetical: PR #418 added ``LDT0``-``LDT3`` as
real top-level ports, issue #441 found section 2.2's pad table still had no row
for them three days later ("the proposal described a part that could not be
configured into its own ratified spec", DR-015), and DR-015's own closing
sentence handed the bench-test-plan half of the same fix to "future harness
integration work" that never happened -- so section 4 still named neither the
trim pins nor the four bias-reference currents when this check was written.

The same incident is why the check also grades the proposal's *budget
accounting* (rules 6-9): #441's stale row count came with a stale slot total
("18 of 24" against a real 22) and a stale configuration-bit sentence two
sections away, and neither of those is a number any earlier rule could see.
Those rules found one more omission of their own on 2026-09-25 -- the three
rail rows carried a slot the transcribed budget does not have, and the totals
paragraph, which claims to cover every category, never reported the five
supply/ground pads at all.

Every test builds a throwaway tree whose answer is known and runs the real
script in it, because a check that only ever runs where it passes proves
nothing about what it would have caught.  No PDK, no ngspice, no xschem -- the
script reads one committed netlist and one committed Markdown file.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

DESIGN_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = DESIGN_DIR.parent
CHECK = DESIGN_DIR / "lib" / "check-io-list-coverage.sh"

NETLIST = "design/netlist/pll_top.spice"
PROPOSAL = "docs/chipalooza/challenge-5-proposal.md"

#: A miniature of the real 36-port export, keeping every shape the real one
#: has: a bus the document writes as a range, a bus it writes with an
#: ellipsis, single-pin signals, and rails.
PORTS = (
    "REF",
    "B0",
    "B1",
    "B2",
    "LDT0",
    "LDT1",
    "LDT2",
    "LDT3",
    "IBN",
    "ICP",
    "CLK",
    "LOCK",
    "VDD",
    "VSS",
)

#: (Signal(s) cell, Challenge-slot cell, Count-used cell) -- the three columns
#: the check reads.  Between them the rows carry every shape the real table
#: has: a rail row that states no count, a slot cell that repeats its budget,
#: one that states the budget in prose, and one that states none at all.
PAD_ROWS = (
    ("`VDD`, `VSS`", "supply/ground pad — 3.3 V digital rail", "— (rail)"),
    ("`REF`", "digital control input (budget ≤ 24)", "1 of 24"),
    ("`B0`, `B1`, `B2`", "digital control input", "3 of 24"),
    ("`LDT0`…`LDT3`", "digital control input", "4 of 24"),
    (
        "`IBN`, `ICP`",
        "**does not fit the ≤ 2 bandgap-referenced current-source budget**",
        "2 requested vs. 2 offered",
    ),
    ("`CLK`", "dedicated pad (budget ≤ 4)", "1 of 4"),
    ("`LOCK`", "digital test output (budget ≤ 12)", "1 of 12"),
)

#: Section 2.2's transcribed Challenge budget -- the clause after the colon,
#: which is the only place the check learns the slot taxonomy from.
BUDGET = (
    "one bandgap-referenced bias voltage, up to 2 bandgap-referenced current "
    "sources, up to 24 digital control inputs, up to 12 digital test outputs, "
    "up to 4 dedicated pads, and no transcribed line at all for supply/ground "
    "pads."
)

#: Section 2.2's totals paragraph, which must close over PAD_ROWS above:
#: 1 + 3 + 4 digital control inputs, 1 test output, 1 dedicated pad, 2 rails,
#: 2 requested current sources, and no bandgap bias voltage at all.
TOTALS = (
    "**Totals against the Challenge #5 budget**: 0 of 1 bandgap-referenced "
    "bias voltage, **2 requested vs. 2 offered** bandgap-referenced current "
    "sources (open item), 8 of ≤ 24 digital control inputs, 1 of ≤ 12 digital "
    "test outputs, 1 of ≤ 4 dedicated pads, 2 supply/ground pads."
)

#: Section 2.3's configuration-bit sentence: the seven static levels, with
#: `REF` excluded in the same bullet that does the excluding.
CONFIG_BULLET = (
    "- **`SPI control` does not apply.** This block has no addressable "
    "configuration register — its 7 configuration bits (`B0..B2`, `LDT0..3`) "
    "are static levels, not an SPI-programmed state. (`REF` is deliberately "
    "excluded from this count — it is a continuously toggling clock, not a "
    "static configuration level.)"
)

#: The bench plan, as a list of steps.  Between them these name every port.
BENCH_STEPS = (
    "**Bring-up.** Power `VDD` with `VSS` grounded; supply `IBN` and `ICP`.",
    "**Open-loop.** Sweep `B0..B2` and measure `CLK`.",
    "**Trim.** Program `LDT3:LDT0` per the trim-code rule.",
    "**Lock.** Apply `REF` and observe `LOCK`.",
)


def _netlist(ports=PORTS, subckt=".subckt pll_top") -> str:
    """The export, wrapped onto a `+` continuation line the way ngspice does."""
    head, tail = ports[:8], ports[8:]
    lines = [
        "* gf180-pll :: pll_top -- generated by design/netlist.sh from pll_top.sch",
        "** sch_path: design/pll_top.sch",
        "%s %s" % (subckt, " ".join(head)),
    ]
    if tail:
        lines.append("+ %s" % " ".join(tail))
    lines += ["*.ipin %s" % ports[0], ".ends pll_top"]
    return "\n".join(lines) + "\n"


def _proposal(
    pad_rows=PAD_ROWS,
    bench_steps=BENCH_STEPS,
    quoted=None,
    budget=BUDGET,
    totals=TOTALS,
    config_bullet=CONFIG_BULLET,
    pad_heading="### 2.2 Pad table, mapped to the Challenge #5 slot budget",
    slot_heading="### 2.3 What's dropped, multiplexed, substituted, or new",
    bench_heading="## 4. Bench test plan",
    pad_header="| Signal(s) | Dir | Challenge slot | Count used | Notes |",
) -> str:
    if quoted is None:
        quoted = " ".join(PORTS)
    lines = [
        "# Chipalooza Challenge #5 — integer-N PLL proposal",
        "",
        "## 2. I/O list, including test ports",
        "",
        pad_heading,
        "",
        "`design/pll_top.sch`'s exported port list",
        "(`design/netlist/pll_top.spice`, `.subckt pll_top %s`) is the port" % quoted,
        "list this table maps, unedited, onto the Challenge #5 budget as this",
        "repository understands it: %s **That budget is transcribed here, not" % budget,
        "authored here.**",
        "",
        pad_header,
        "|---|---|---|---|---|",
    ]
    for signal, slot, count in pad_rows:
        lines.append("| %s | in | %s | %s | a note |" % (signal, slot, count))
    lines += ["", totals, ""]
    lines += [
        slot_heading,
        "",
        "- **Nothing in the port list is dropped.**",
        config_bullet,
        "",
        "## 3. Functional description",
        "",
        "Prose naming no pins.",
        "",
        bench_heading,
        "",
        "All measurements below use only the pads in §2.2.",
        "",
    ]
    for n, step in enumerate(bench_steps, start=1):
        lines.append("%d. %s" % (n, step))
    lines += ["", "## 5. Target specification", "", "Text after."]
    return "\n".join(lines) + "\n"


class _Tree:
    """A throwaway repo tree with the real check installed at design/lib/."""

    def __init__(self, root: Path):
        self.root = root
        (root / "design" / "lib").mkdir(parents=True)
        shutil.copy2(CHECK, root / "design" / "lib" / CHECK.name)
        self.write(NETLIST, _netlist())
        self.write(PROPOSAL, _proposal())

    def write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def run(self) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(self.root / "design" / "lib" / CHECK.name)],
            capture_output=True,
            text=True,
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


class TestCoverageRule(_TreeTest):
    def test_a_fully_mapped_port_list_passes(self):
        self.assertPasses()

    def test_the_real_441_drift_shape_is_caught(self):
        """The exact regression: ports added to design/, pad table untouched.

        This is the proposal as it stood between PR #418 and issue #441 --
        `LDT0`-`LDT3` real top-level ports of `pll_top`, with no pad row.
        """
        self.tree.write(
            PROPOSAL,
            _proposal(
                pad_rows=tuple(r for r in PAD_ROWS if "LDT" not in r[0]),
                bench_steps=BENCH_STEPS,
            ),
        )
        self.assertFails(
            "port 'LDT0'",
            "has no row in docs/chipalooza/challenge-5-proposal.md section 2.2",
        )

    def test_every_missing_port_is_reported_not_just_the_first(self):
        self.tree.write(
            PROPOSAL,
            _proposal(pad_rows=tuple(r for r in PAD_ROWS if "LDT" not in r[0])),
        )
        result = self.tree.run()
        for port in ("LDT0", "LDT1", "LDT2", "LDT3"):
            self.assertIn("port %r" % port, result.stderr)

    def test_a_range_covers_its_interior_not_only_its_endpoints(self):
        """`B0`, `B1`, `B2` written as `B0..B2` still maps B1."""
        self.tree.write(
            PROPOSAL,
            _proposal(
                pad_rows=tuple(
                    ("`B0..B2`", slot, c) if s.startswith("`B0`") else (s, slot, c)
                    for s, slot, c in PAD_ROWS
                )
            ),
        )
        self.assertPasses()

    def test_a_short_form_range_covers_its_interior(self):
        """`LDT0..3` -- the form section 4 uses -- expands on the prefix."""
        self.tree.write(
            PROPOSAL,
            _proposal(
                pad_rows=tuple(
                    ("`LDT0..3`", slot, c) if "LDT" in s else (s, slot, c)
                    for s, slot, c in PAD_ROWS
                )
            ),
        )
        self.assertPasses()

    def test_a_descending_bus_range_covers_its_interior(self):
        """`LDT3:LDT0` is the spec's own spelling of the same four bits."""
        self.tree.write(
            PROPOSAL,
            _proposal(
                pad_rows=tuple(
                    ("`LDT3:LDT0`", slot, c) if "LDT" in s else (s, slot, c)
                    for s, slot, c in PAD_ROWS
                )
            ),
        )
        self.assertPasses()


class TestOrphanSignalRule(_TreeTest):
    def test_a_pad_row_naming_a_nonexistent_pin_fails(self):
        """Catches a pin renamed or removed in design/ but left in the table."""
        self.tree.write(
            PROPOSAL,
            _proposal(
                pad_rows=PAD_ROWS
                + (("`SPI_CS`", "digital control input", "1 of 24"),),
                totals=TOTALS.replace(
                    "8 of ≤ 24 digital", "9 of ≤ 24 digital"
                ),
            ),
        )
        self.assertFails("names 'SPI_CS', which is not a port")

    def test_a_renamed_pin_fails_in_both_directions(self):
        renamed = tuple("REFCLK" if p == "REF" else p for p in PORTS)
        self.tree.write(NETLIST, _netlist(renamed))
        self.tree.write(PROPOSAL, _proposal(quoted=" ".join(renamed)))
        self.assertFails("port 'REFCLK'", "names 'REF', which is not a port")


class TestQuotedPortListRule(_TreeTest):
    def test_a_stale_quoted_list_fails(self):
        self.tree.write(
            PROPOSAL, _proposal(quoted=" ".join(p for p in PORTS if p != "LDT3"))
        )
        self.assertFails("does not match design/netlist/pll_top.spice")

    def test_a_reordered_quoted_list_fails(self):
        """The order is load-bearing: a positional instance line reads it."""
        swapped = list(PORTS)
        swapped[0], swapped[1] = swapped[1], swapped[0]
        self.tree.write(PROPOSAL, _proposal(quoted=" ".join(swapped)))
        self.assertFails("does not match design/netlist/pll_top.spice")

    def test_a_quoted_continuation_marker_is_allowed(self):
        """The netlist wraps and the document quotes the wrap, `+` and all."""
        with_plus = list(PORTS)
        with_plus.insert(8, "+")
        self.tree.write(PROPOSAL, _proposal(quoted=" ".join(with_plus)))
        self.assertPasses()

    def test_an_unquoted_port_list_fails(self):
        text = _proposal().replace(
            "(`design/netlist/pll_top.spice`, `.subckt pll_top %s`) is the port"
            % " ".join(PORTS),
            "(`design/netlist/pll_top.spice`) is the port",
        )
        self.tree.write(PROPOSAL, text)
        self.assertFails("does not quote the '.subckt pll_top' line anywhere")


class TestPerRowCountRule(_TreeTest):
    def test_a_stale_row_count_fails(self):
        """What went stale first in #441: the count beside the changed row."""
        self.tree.write(
            PROPOSAL,
            _proposal(
                pad_rows=tuple(
                    (s, slot, "3 of 24") if "LDT" in s else (s, slot, c)
                    for s, slot, c in PAD_ROWS
                ),
                totals=TOTALS.replace("8 of ≤ 24 digital", "7 of ≤ 24 digital"),
            ),
        )
        self.assertFails("states '3 of 24' but names 4 signal(s)")

    def test_a_requested_vs_offered_count_is_graded_too(self):
        self.tree.write(
            PROPOSAL,
            _proposal(
                pad_rows=tuple(
                    (s, slot, "4 requested vs. 2 offered")
                    if s == "`IBN`, `ICP`"
                    else (s, slot, c)
                    for s, slot, c in PAD_ROWS
                ),
                totals=TOTALS.replace(
                    "**2 requested vs. 2 offered**", "**4 requested vs. 2 offered**"
                ),
            ),
        )
        self.assertFails("but names 2 signal(s)")

    def test_a_rail_row_states_no_count_and_is_exempt(self):
        """"— (rail)" is not a number and must not be read as one."""
        self.assertPasses()

    def test_an_emphasised_count_is_still_graded(self):
        self.tree.write(
            PROPOSAL,
            _proposal(
                pad_rows=tuple(
                    (s, slot, "**2** of 24") if "LDT" in s else (s, slot, c)
                    for s, slot, c in PAD_ROWS
                ),
                totals=TOTALS.replace("8 of ≤ 24 digital", "6 of ≤ 24 digital"),
            ),
        )
        self.assertFails("but names 4 signal(s)")


class TestBenchPlanRule(_TreeTest):
    def test_a_pin_the_bench_plan_never_names_fails(self):
        """The finding this rule was written on, in miniature.

        Section 4 named neither the lock-detector trim nor the four bias
        currents.  Both are load-bearing: without the bias references the
        charge pump passes no current, and `spec/pll.md` says outright that a
        part left untrimmed is outside the specification the plan's
        lock-detector step compares it against.
        """
        self.tree.write(
            PROPOSAL,
            _proposal(
                bench_steps=tuple(s for s in BENCH_STEPS if "`LDT3:LDT0`" not in s)
            ),
        )
        self.assertFails(
            "port 'LDT0' is never named in docs/chipalooza/challenge-5-proposal.md"
            " section 4"
        )

    def test_a_bias_pin_the_bench_plan_never_names_fails(self):
        self.tree.write(
            PROPOSAL,
            _proposal(
                bench_steps=tuple(
                    s.replace("; supply `IBN` and `ICP`", "") for s in BENCH_STEPS
                )
            ),
        )
        self.assertFails("port 'IBN' is never named", "port 'ICP' is never named")

    def test_a_pad_table_mention_does_not_satisfy_the_bench_rule(self):
        """The two sections are graded separately, on purpose.

        `LDT0`-`LDT3` were in the pad table for four days before this check
        existed while section 4 still ignored them; a rule that accepted a
        mention anywhere in the document would have reported that tree clean.
        """
        self.tree.write(
            PROPOSAL,
            _proposal(
                bench_steps=tuple(s for s in BENCH_STEPS if "`LDT3:LDT0`" not in s)
            ),
        )
        self.assertFails("section 4")


class TestBudgetCategoryRule(_TreeTest):
    """Rule 6: a pad row's slot must be a category the budget transcribes."""

    def test_the_real_rail_finding_is_caught(self):
        """The finding these rules were written on, in miniature.

        Until 2026-09-25 the three rail rows carried the slot "3.3 V digital
        rail" -- a category the transcribed budget does not have -- so the
        five pads without which nothing on the die powers up sat outside the
        accounting entirely, in a table whose totals claim to cover every
        category.
        """
        self.tree.write(
            PROPOSAL,
            _proposal(
                pad_rows=tuple(
                    (s, "3.3 V digital rail", c) if s.startswith("`VDD`") else (s, slot, c)
                    for s, slot, c in PAD_ROWS
                )
            ),
        )
        self.assertFails(
            "carries the Challenge slot '3.3 v digital rail'",
            "not a category the transcribed budget",
        )

    def test_a_slot_cell_quoting_the_wrong_budget_fails(self):
        self.tree.write(
            PROPOSAL,
            _proposal(
                pad_rows=tuple(
                    (s, "digital control input (budget ≤ 12)", c)
                    if s == "`REF`"
                    else (s, slot, c)
                    for s, slot, c in PAD_ROWS
                )
            ),
        )
        self.assertFails(
            "states a budget of 12 for the 'digital control inputs' slot",
            "transcribes as 24",
        )

    def test_a_count_denominator_quoting_the_wrong_budget_fails(self):
        """The M of "K of M" is a budget claim too, not decoration."""
        self.tree.write(
            PROPOSAL,
            _proposal(
                pad_rows=tuple(
                    (s, slot, "1 of 12") if s == "`REF`" else (s, slot, c)
                    for s, slot, c in PAD_ROWS
                )
            ),
        )
        self.assertFails("states a budget of 12", "transcribes as 24")

    def test_an_offered_count_disagreeing_with_the_transcription_fails(self):
        self.tree.write(
            PROPOSAL,
            _proposal(
                pad_rows=tuple(
                    (s, slot, "2 requested vs. 4 offered")
                    if s == "`IBN`, `ICP`"
                    else (s, slot, c)
                    for s, slot, c in PAD_ROWS
                ),
                totals=TOTALS.replace(
                    "**2 requested vs. 2 offered**", "**2 requested vs. 4 offered**"
                ),
            ),
        )
        self.assertFails("states a budget of 4", "transcribes as 2")

    def test_an_invented_cap_on_an_untranscribed_category_fails(self):
        """The rails have no published slot count; the document may not mint one."""
        self.tree.write(
            PROPOSAL,
            _proposal(
                pad_rows=tuple(
                    (s, "supply/ground pad (budget ≤ 6)", c)
                    if s.startswith("`VDD`")
                    else (s, slot, c)
                    for s, slot, c in PAD_ROWS
                )
            ),
        )
        self.assertFails(
            "states a budget of 6", "transcribed budget has no count for that category"
        )

    def test_singular_plural_and_hyphenation_are_the_same_slot(self):
        """"current-source budget" in a row, "current sources" in the budget."""
        self.tree.write(
            PROPOSAL,
            _proposal(
                pad_rows=tuple(
                    (s, "bandgap referenced current sources (≤ 2)", c)
                    if s == "`IBN`, `ICP`"
                    else (s, slot, c)
                    for s, slot, c in PAD_ROWS
                )
            ),
        )
        self.assertPasses()


class TestTotalsRule(_TreeTest):
    """Rules 7-8: the totals paragraph is the sum of the rows above it."""

    def test_the_441_shape_a_stale_category_total_fails(self):
        """The exact #441 drift: rows changed, the total left behind."""
        self.tree.write(
            PROPOSAL,
            _proposal(totals=TOTALS.replace("8 of ≤ 24", "7 of ≤ 24")),
        )
        self.assertFails(
            "reports 7 for 'digital control inputs'", "sum to 8"
        )

    def test_a_total_quoting_the_wrong_budget_fails(self):
        self.tree.write(
            PROPOSAL, _proposal(totals=TOTALS.replace("8 of ≤ 24", "8 of ≤ 20"))
        )
        self.assertFails("against a budget of 20", "transcribes as 24")

    def test_an_optional_row_is_reported_as_a_range(self):
        """"(proposed)" rows count toward the upper figure only."""
        self.tree.write(
            PROPOSAL,
            _proposal(
                pad_rows=tuple(
                    (s, slot, "1 of 12 (proposed)") if s == "`LOCK`" else (s, slot, c)
                    for s, slot, c in PAD_ROWS
                ),
                totals=TOTALS.replace(
                    "1 of ≤ 12 digital test outputs", "0–1 of ≤ 12 digital test outputs"
                ),
            ),
        )
        self.assertPasses()

    def test_an_optional_row_reported_as_mandatory_fails(self):
        self.tree.write(
            PROPOSAL,
            _proposal(
                pad_rows=tuple(
                    (s, slot, "1 of 12 (proposed)") if s == "`LOCK`" else (s, slot, c)
                    for s, slot, c in PAD_ROWS
                )
            ),
        )
        self.assertFails("reports 1 for 'digital test outputs'", "0 of them not marked")

    def test_a_rail_row_contributes_the_pins_it_names(self):
        """A row that states no count is not a row that counts for nothing."""
        self.tree.write(
            PROPOSAL,
            _proposal(totals=TOTALS.replace("2 supply/ground pads", "3 supply/ground pads")),
        )
        self.assertFails("reports 3 for 'supply/ground pads'", "sum to 2")

    def test_a_category_with_no_rows_is_still_totalled(self):
        """0 of 1 is how the bandgap bias voltage is reported, and must stay."""
        self.tree.write(
            PROPOSAL,
            _proposal(
                totals=TOTALS.replace(
                    "0 of 1 bandgap-referenced bias voltage", "1 of 1 bandgap-referenced bias voltage"
                )
            ),
        )
        self.assertFails("reports 1 for 'bandgap-referenced bias voltage'", "sum to 0")

    def test_a_category_the_totals_never_report_fails(self):
        self.tree.write(
            PROPOSAL,
            _proposal(totals=TOTALS.replace("1 of ≤ 4 dedicated pads, ", "")),
        )
        self.assertFails("never reports 'dedicated pads'")

    def test_a_total_for_a_category_the_budget_does_not_name_fails(self):
        self.tree.write(
            PROPOSAL,
            _proposal(totals=TOTALS.replace(".", ", 1 of ≤ 4 shared analog lines.")),
        )
        self.assertFails(
            "reports 'shared analog lines'", "not a category the transcribed budget names"
        )

    def test_a_missing_totals_paragraph_fails(self):
        self.tree.write(
            PROPOSAL, _proposal(totals="Every pin above fits the budget somewhere.")
        )
        self.assertFails("has no paragraph starting '**Totals'")

    def test_a_parenthetical_aside_is_not_read_as_an_entry(self):
        """The paragraph explains itself in parentheses; those are prose."""
        self.tree.write(
            PROPOSAL,
            _proposal(
                totals=TOTALS.replace(
                    "8 of ≤ 24 digital control inputs",
                    "8 of ≤ 24 digital control inputs (4 without the trim; "
                    "`LDT0`–`LDT3` add 4, leaving 16 slots of headroom)",
                )
            ),
        )
        self.assertPasses()


class TestConfigurationBitRule(_TreeTest):
    """Rule 9: section 2.3's bit count is its own bus list, expanded."""

    def test_the_441_off_by_one_shape_is_caught(self):
        """"The prior revision of this sentence read 18 configuration bits."""
        self.tree.write(
            PROPOSAL,
            _proposal(
                config_bullet=CONFIG_BULLET.replace(
                    "its 7 configuration bits", "its 6 configuration bits"
                )
            ),
        )
        self.assertFails("states 6 configuration bits", "expands to 7")

    def test_a_bit_with_no_pad_row_fails(self):
        self.tree.write(
            PROPOSAL,
            _proposal(
                config_bullet=CONFIG_BULLET.replace(
                    "its 7 configuration bits (`B0..B2`, `LDT0..3`)",
                    "its 8 configuration bits (`B0..B2`, `LDT0..3`, `SPI_CS`)",
                )
            ),
        )
        self.assertFails("counts 'SPI_CS' as a configuration bit", "no pad row")

    def test_a_pin_dropped_from_the_count_in_silence_fails(self):
        self.tree.write(
            PROPOSAL,
            _proposal(
                config_bullet=CONFIG_BULLET.replace(
                    "its 7 configuration bits (`B0..B2`, `LDT0..3`)",
                    "its 3 configuration bits (`B0..B2`)",
                )
            ),
        )
        self.assertFails("leaves out 'LDT0'", "without naming")

    def test_ref_is_excluded_only_because_the_bullet_says_so(self):
        """Delete the sentence that excludes it and the count stops being legal."""
        self.tree.write(
            PROPOSAL,
            _proposal(
                config_bullet=CONFIG_BULLET.split(" (`REF` is deliberately")[0]
            ),
        )
        self.assertFails("leaves out 'REF'", "without naming it")

    def test_an_explanation_in_another_bullet_does_not_count(self):
        """The exclusion has to be where the count is, not elsewhere in 2.3."""
        text = _proposal(
            config_bullet=CONFIG_BULLET.split(" (`REF` is deliberately")[0]
        ).replace(
            "- **Nothing in the port list is dropped.**",
            "- **Nothing in the port list is dropped.** `REF` is a clock.",
        )
        self.tree.write(PROPOSAL, text)
        self.assertFails("leaves out 'REF'")

    def test_a_missing_configuration_bit_sentence_fails(self):
        self.tree.write(
            PROPOSAL, _proposal(config_bullet="- **`SPI control` does not apply.**")
        )
        self.assertFails("has no 'N configuration bits (...)' sentence")


class TestSelfDefence(_TreeTest):
    def test_a_missing_netlist_fails(self):
        (self.tree.root / NETLIST).unlink()
        self.assertFails("%s does not exist" % NETLIST)

    def test_a_missing_proposal_fails(self):
        (self.tree.root / PROPOSAL).unlink()
        self.assertFails("%s does not exist" % PROPOSAL)

    def test_a_netlist_without_the_subckt_line_fails(self):
        self.tree.write(NETLIST, _netlist(subckt=".subckt pll_toplevel"))
        self.assertFails("has no '.subckt pll_top' line")

    def test_a_truncated_port_list_fails_rather_than_reading_clean(self):
        """A `+` continuation the parser dropped must not look like a pass.

        The first draft of this check did exactly that: it read the `.subckt`
        line and stopped at the newline, so pll_top's real 36 ports parsed as
        27 and the nine on the continuation line went ungraded.
        """
        self.tree.write(NETLIST, _netlist(PORTS[:6]))
        self.assertFails("too few to be real")

    def test_a_renamed_pad_section_fails(self):
        self.tree.write(PROPOSAL, _proposal(pad_heading="### 2.2b Pad table"))
        self.assertFails("has no '### 2.2' section")

    def test_a_renumbered_bench_section_fails(self):
        self.tree.write(PROPOSAL, _proposal(bench_heading="## 4A. Bench test plan"))
        self.assertFails("has no '## 4.' section")

    def test_a_pad_table_that_stops_parsing_fails(self):
        self.tree.write(PROPOSAL, _proposal(pad_rows=PAD_ROWS[:2]))
        self.assertFails("too few to be real")

    def test_a_missing_signal_column_fails(self):
        self.tree.write(
            PROPOSAL,
            _proposal(pad_header="| Pin | Dir | Challenge slot | Count used | Notes |"),
        )
        self.assertFails("has no 'signal(s)' column")

    def test_a_renamed_slot_section_fails(self):
        self.tree.write(PROPOSAL, _proposal(slot_heading="### 2.3b What's dropped"))
        self.assertFails("has no '### 2.3' section")

    def test_a_budget_transcription_that_stops_parsing_fails(self):
        """The taxonomy comes out of that sentence; an unread one is not a pass."""
        self.tree.write(PROPOSAL, _proposal(budget="the usual Challenge slots."))
        self.assertFails("too few to be real", "where rules 6-8 read the slot taxonomy")

    def test_a_missing_slot_column_fails(self):
        self.tree.write(
            PROPOSAL,
            _proposal(pad_header="| Signal(s) | Dir | Slot | Count used | Notes |"),
        )
        self.assertFails("has no 'challenge slot' column")

    def test_a_missing_count_column_fails(self):
        self.tree.write(
            PROPOSAL,
            _proposal(pad_header="| Signal(s) | Dir | Challenge slot | Slots | Notes |"),
        )
        self.assertFails("has no 'count used' column")


class TestFalsePositives(_TreeTest):
    def test_a_path_in_backticks_is_not_a_pin(self):
        self.tree.write(
            PROPOSAL,
            _proposal(
                bench_steps=BENCH_STEPS
                + ("Compare against `spec/pll.md#kvco` and `sim/lock-time`.",)
            ),
        )
        self.assertPasses()

    def test_a_lowercase_net_name_is_not_a_pin(self):
        self.tree.write(
            PROPOSAL,
            _proposal(
                pad_rows=PAD_ROWS,
                bench_steps=BENCH_STEPS + ("`vdd_ref` is this domain's name.",),
            ),
        )
        self.assertPasses()

    def test_a_decision_record_id_is_not_a_range(self):
        self.tree.write(
            PROPOSAL, _proposal(bench_steps=BENCH_STEPS + ("Per DR-014: trim once.",))
        )
        self.assertPasses()


class TestTheRealTree(unittest.TestCase):
    def test_the_committed_tree_passes(self):
        result = subprocess.run(
            ["bash", str(CHECK)], capture_output=True, text=True, cwd=str(REPO_ROOT)
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("are mapped in", result.stdout)

    def test_the_real_port_list_is_the_36_the_sim_harness_pins(self):
        """Cross-checks the parser against sim/lib/pll_top_dut.sh's CLOOP_PORTS.

        That list is the other place in this repository that must agree with
        the export, and it aborts a closed-loop run when it does not.  If this
        check's parser ever disagrees with it, one of the two is wrong about
        what `pll_top`'s ports are.
        """
        lib = (REPO_ROOT / "sim" / "lib" / "pll_top_dut.sh").read_text(encoding="utf-8")
        block = lib.split("CLOOP_PORTS=(", 1)[1].split(")", 1)[0]
        cloop = block.split()
        netlist = (REPO_ROOT / NETLIST).read_text(encoding="utf-8")
        declared = netlist.split(".subckt pll_top", 1)[1].splitlines()
        ports = declared[0].split()
        for line in declared[1:]:
            if not line.startswith("+"):
                break
            ports += line[1:].split()
        self.assertEqual(ports, cloop)


if __name__ == "__main__":
    unittest.main()
