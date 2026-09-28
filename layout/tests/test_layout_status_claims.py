#!/usr/bin/env python3
"""Unit tests for ``layout/lib/check-layout-status-claims.sh`` (issue #237).

The script exists to make one specific documentation drift a build failure:
README.md and docs/chipalooza/challenge-5-proposal.md both stated that no
PLL block had been drawn for about five weeks after all four sub-blocks
landed with committed GDS and DRC-clean deck output.  A check that only
ever runs against the real tree, where it passes, proves nothing about
whether it would have *caught* that -- so these tests drive it against
synthetic trees where the answer is known, including the exact pre-fix
state of the two real documents.

The script resolves its own repo root from ``${BASH_SOURCE[0]}/../..``, so
each test builds a throwaway tree with the script copied into the same
relative position and runs it there.  No PDK, no KLayout, no layout input.

    python3 -m unittest discover -s layout/tests -t layout/tests -v
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _env import LAYOUT_DIR

SCRIPT = LAYOUT_DIR / "lib" / "check-layout-status-claims.sh"

# The four sub-blocks the script grades, as (evidence dir, block GDS name).
BLOCKS = [
    ("vco-layout", "vco_block.gds"),
    ("pfd-cp-layout", "pfd_cp.gds"),
    ("divider-chain-layout", "divider_chain.gds"),
    ("lock-detector-layout", "lock_detector.gds"),
]

# The block geometry the footprint rule grades against, as it stands in the
# real layout/evidence/area-audit/area-audit.md: top cell -> (width um,
# height um, bbox um2).  Using the repo's own numbers keeps these tests
# readable next to the documents they are about.
AUDIT_GEOMETRY = {
    "vco_block": (172.52, 184.48, 31826),
    "pfd_cp": (344.98, 74.30, 25630),
    "divider_chain": (1317.66, 41.99, 55329),
    "lock_detector": (294.80, 103.75, 30586),
}

LVS_MATCH_LINE = "INFO : Congratulations! Netlists match.\n"
DRC_CLEAN_LINE = "INFO    | Klayout DRC run is clean. GDS has no DRC violations.\n"

# The KLayout application version the fixture's layout/harness/env.py pins.
# The KLAYOUT PIN RULE (issue #127) reads the pin from that module rather than
# restating it, so the fixture must carry one for the rule to have anything to
# grade against -- and a deck log recorded on a different KLayout must fail,
# which is what test_an_undisclosed_off_pin_deck_log_is_caught drives.
PINNED_KLAYOUT = "KLayout 0.28.16"


def _deck_log(klayout: str, top: str, verdict: str) -> str:
    """A deck stdout log shaped like the real gf180mcu DRC/LVS runner's.

    The KLAYOUT PIN RULE reads three things out of a committed log -- the
    engine that produced it, the top cell it ran on, and the deck's own
    verdict line -- so the fixture must carry all three in the real wording.
    """
    return (
        f"INFO    | Your Klayout version is: {klayout}\n"
        f"INFO    | Running Global Foundries 180nm MCU design main on cell {top}:\n"
        f"{verdict}"
    )

# The klt version the fixture's .github/workflows/ci.yml pins. The ERC rule
# (issue #565) reads the pin from that file rather than restating it, so the
# fixture must carry one for the rule to have anything to grade against -- and
# a report claiming a different version must fail, which is what
# test_a_report_from_an_unpinned_klt_is_caught drives.
PINNED_KLT = "0.6.0"

CI_WORKFLOW = """\
name: CI
on: [push]
jobs:
  checks:
    runs-on: ubuntu-latest
    steps:
      - name: Install klt (klayout-tools) for the signoff tier check
        run: pip install 'klayout-tools==%s'
"""

# The scope rule reads a ~100-character window either side of a negation,
# so a synthetic document needs real distance between the boilerplate
# "no assembled `pll_top` GDS" sentinel (which legitimately carries a scope
# word) and the sentence under test.  Deliberately free of both negations
# and layout nouns.
PAD = "\n" + ("Filler prose that bears on nothing in particular. " * 5) + "\n"

def _footprint_lines(geometry: dict | None = None) -> str:
    """One correct footprint claim per block, in both adjacency shapes.

    Section 6's table writes the mm2 figure after the tuple and section 5's
    area row writes it before, so the fixture alternates between the two --
    both are graded, and both must keep passing.
    """
    geometry = AUDIT_GEOMETRY if geometry is None else geometry
    lines = []
    for i, (top, (w, h, bbox)) in enumerate(geometry.items()):
        mm2 = f"{bbox / 1e6:.4f}"
        if i % 2 == 0:
            lines.append(f"`{top}` measures {w:g} × {h:g} µm ({mm2} mm²).")
        else:
            lines.append(f"`{top}` measures {mm2} mm² ({w:g} × {h:g} µm).")
    return "\n".join(lines) + "\n"


def _area_section(geometry: dict | None = None, *, heading: str = "Area") -> str:
    """A "## <heading>" section carrying one footprint line per block.

    The fifth guard (issue #237) grades spec/pll.md's own "## Area" section
    against layout/evidence/area-audit/area-audit.md, scoped to that section
    so the document's unrelated device dimensions elsewhere are not swept in.
    Every spec fixture below needs a valid one by default so tests aimed at
    the other rules are not incidentally broken by this one.
    """
    return "\n## %s\n\n%s" % (heading, _footprint_lines(geometry))


RATIFIED_SPEC = (
    "# PLL target specification\n\n"
    "- **Status**: **ratified, with amendments** (#1, 2026-09-08)\n"
    + _area_section()
)
UNRATIFIED_SPEC = (
    "# PLL target specification\n\n"
    "- **Status**: proposed, not yet ratified\n"
    + _area_section()
)


# The pin sentence every fixture document carries by default. The PIN
# RESTATEMENT RULE (issue #237) requires the proposal to state the KLayout
# pin, so a fixture that omitted it would fail every unrelated test in this
# file for a reason none of them is about.
def _pin_line(pin: str | None = None) -> str:
    return "This repository pins `%s` for DRC and LVS.\n" % (pin or PINNED_KLAYOUT)


def _doc_text(
    drawn: int,
    lvs: int,
    *,
    no_top: bool = True,
    footprints: bool = True,
    pin: str | None = None,
    state_pin: bool = True,
) -> str:
    """A minimal document that satisfies the script at the given counts."""
    body = [
        f"Layout status: {drawn} of the 4 PLL sub-blocks are drawn and",
        f"DRC-clean, and {lvs} of the 4 are LVS-matched.",
    ]
    if no_top:
        body.append("There is no assembled `pll_top` GDS.")
    text = "\n".join(body) + "\n"
    if state_pin:
        text += _pin_line(pin)
    if footprints:
        text += _footprint_lines()
    return text


class _Tree:
    """A throwaway repo tree with the script installed at layout/lib/."""

    def __init__(self, root: Path):
        self.root = root
        (root / "layout" / "lib").mkdir(parents=True)
        (root / "docs" / "chipalooza").mkdir(parents=True)
        (root / "spec").mkdir(parents=True)
        shutil.copy2(SCRIPT, root / "layout" / "lib" / SCRIPT.name)
        self.write_spec(RATIFIED_SPEC)
        self.write_audit()
        self.write_ci_workflow()
        self.write_harness_env()

    def write_ci_workflow(self, pin: str | None = PINNED_KLT) -> None:
        """Write .github/workflows/ci.yml, the ERC rule's source of truth for
        which klt version a committed klt artifact must come from.

        ``pin=None`` writes a workflow with no ``klayout-tools==`` line at all,
        which the rule must report rather than pass over -- a version claim
        gradeable against nothing is the failure mode, not a free pass.
        """
        base = self.root / ".github" / "workflows"
        base.mkdir(parents=True, exist_ok=True)
        text = CI_WORKFLOW % pin if pin is not None else CI_WORKFLOW.split("      - name")[0]
        (base / "ci.yml").write_text(text)

    def remove_ci_workflow(self) -> None:
        (self.root / ".github" / "workflows" / "ci.yml").unlink()

    def write_spec(self, text: str) -> None:
        (self.root / "spec" / "pll.md").write_text(text)

    def write_audit(self, geometry: dict | None = None, *, body: str | None = None):
        """Write layout/evidence/area-audit/area-audit.md.

        Shaped like the real, machine-generated file: a geometry table
        first, then further tables whose first cell is also a top-cell name
        but whose second cell is not a "W x H" pair.  The parser must take
        its numbers from the first table without counting tables.
        """
        base = self.root / "layout" / "evidence" / "area-audit"
        base.mkdir(parents=True, exist_ok=True)
        if body is None:
            geometry = AUDIT_GEOMETRY if geometry is None else geometry
            rows = [
                "| Block | Footprint (um) | bbox (um2) | Drawn (um2) | Fill | Whitespace |",
                "|---|---|---|---|---|---|",
            ]
            for top, (w, h, bbox) in geometry.items():
                rows.append(f"| `{top}` | {w:.2f} x {h:.2f} | {bbox:,} | 1,000 | 3.1 % | 1 (1.0 %) |")
            rows += [
                "",
                "| Block | comp (um2) | comp share |",
                "|---|---|---|",
            ]
            for top in geometry:
                rows.append(f"| `{top}` | 4,387.1 | 13.78 % |")
            body = "\n".join(rows) + "\n"
        (base / "area-audit.md").write_text(body)

    def remove_audit(self) -> None:
        (self.root / "layout" / "evidence" / "area-audit" / "area-audit.md").unlink()

    def write_harness_env(self, pin: str | None = PINNED_KLAYOUT) -> None:
        """Write layout/harness/env.py, the KLayout pin rule's source of truth.

        ``pin=None`` writes a module with no ``KNOWN_GOOD_KLAYOUT_VERSION``
        assignment at all, which the rule must report rather than pass over --
        an engine claim gradeable against nothing is the failure mode, not a
        free pass, exactly as for the klt pin.
        """
        base = self.root / "layout" / "harness"
        base.mkdir(parents=True, exist_ok=True)
        body = '"""Fixture harness env."""\n'
        if pin is not None:
            body += f'KNOWN_GOOD_KLAYOUT_VERSION = "{pin}"\n'
        (base / "env.py").write_text(body)

    def add_block(
        self,
        evidence_dir: str,
        gds: str,
        *,
        drc: bool,
        lvs: bool,
        erc: bool = True,
        drc_klayout: str = PINNED_KLAYOUT,
        lvs_klayout: str = PINNED_KLAYOUT,
    ) -> None:
        base = self.root / "layout" / "evidence" / evidence_dir
        base.mkdir(parents=True, exist_ok=True)
        (base / gds).write_bytes(b"")
        top = gds[: -len(".gds")]
        if drc:
            (base / "drc-clean").mkdir(exist_ok=True)
            (base / "drc-clean" / "drc.stdout.log").write_text(
                _deck_log(drc_klayout, top, DRC_CLEAN_LINE)
            )
        if lvs:
            (base / "lvs-clean").mkdir(exist_ok=True)
            (base / "lvs-clean" / "lvs.stdout.log").write_text(
                _deck_log(lvs_klayout, top, LVS_MATCH_LINE)
            )
            # An LVS-clean block owes klt erc supply evidence (issue #565), so
            # the default fixture supplies a valid set. Tests that want the
            # missing-evidence failure pass erc=False.
            if erc:
                self.add_erc(evidence_dir, gds)

    def add_deck_log(
        self, rel: str, *, klayout: str, top: str, verdict: str = DRC_CLEAN_LINE
    ) -> Path:
        """Write one extra deck log under layout/evidence/ at ``rel``."""
        path = self.root / "layout" / "evidence" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_deck_log(klayout, top, verdict))
        return path

    def add_erc(
        self,
        evidence_dir: str,
        gds: str,
        *,
        ties: bool = True,
        disclosure_kind: str | None = None,
        disclosure_reason: str = "nothing in this stream to narrow or bound",
        extra_spec_keys: dict | None = None,
        klt_version: str | None = None,
        input_hash: str | None = None,
        antenna_skipped: int = 3,
        proof_antenna_claim: str | None = None,
        proof: bool = True,
    ) -> None:
        """Write a block's ``klt erc`` supply evidence set (issue #565).

        Valid by default -- both provenance hashes computed from the files
        actually written, the pinned klt version, a declared-and-checked tie,
        and a PROOF-erc.md stating the report's own antenna coverage. Every
        keyword exists to break exactly one of those, so each half of the ERC
        rule can be driven to a known failure.
        """
        base = self.root / "layout" / "evidence" / evidence_dir
        base.mkdir(parents=True, exist_ok=True)

        spec: dict = {
            "_description": "fixture supply spec",
            "stackup": [
                {"name": "poly2", "layer": "30/0", "role": "gate"},
                {"name": "metal1", "layer": "34/0", "label_layer": "34/10"},
            ],
            "vias": [
                {"name": "contact", "layer": "33/0", "between": ["poly2", "metal1"]}
            ],
            "nets": [{"name": "VDD", "kind": "supply"}],
        }
        if ties:
            spec["ties"] = [
                {
                    "name": "nwell_vdd",
                    "well_layer": "21/0",
                    "tap_layer": "22/0",
                    "tap_requires": ["32/0"],
                    "connect_to": "metal1",
                    "net": "VDD",
                }
            ]
        if disclosure_kind is not None:
            spec["ties_disclosure"] = {
                "kind": disclosure_kind,
                "reason": disclosure_reason,
            }
        if extra_spec_keys:
            spec.update(extra_spec_keys)
        spec_path = base / "erc-supply-spec.json"
        spec_path.write_text(json.dumps(spec, indent=2) + "\n")

        def digest(path: Path) -> str:
            return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()

        skipped = [
            {"id": 'antenna:["gate%d","metal1"]' % i, "reason": "missing_antenna_pdk"}
            for i in range(antenna_skipped)
        ]
        report = {
            "schema_version": 1,
            "file": "layout/evidence/%s/%s" % (evidence_dir, gds),
            "spec": "layout/evidence/%s/erc-supply-spec.json" % evidence_dir,
            "pdk": None,
            "erc_findings": [],
            "erc_finding_count": 0,
            "erc_status": "clean",
            "status": "not_checked",
            "erc_coverage": {
                "checked": (['erc.missing_tie:["nwell_vdd"]'] if ties else []),
                "skipped": [],
                "inapplicable": (
                    []
                    if ties
                    else [
                        {
                            "id": "erc.missing_tie:[]",
                            "reason": "ties_disclosed_%s"
                            % (disclosure_kind or "unexpressible"),
                        }
                    ]
                ),
                "layers_in_stream_without_declaration": [],
            },
            "coverage": {"scope": "antenna", "checked": [], "skipped": skipped},
            "provenance": {
                "klt_version": klt_version or PINNED_KLT,
                "input": {"content_hash": input_hash or digest(base / gds)},
                "spec": {"content_hash": digest(spec_path)},
                "devices": [],
            },
        }
        (base / "erc-report.json").write_text(json.dumps(report, indent=2) + "\n")

        if proof:
            claim = (
                proof_antenna_claim
                if proof_antenna_claim is not None
                else "checked: 0, skipped: %d" % antenna_skipped
            )
            (base / "PROOF-erc.md").write_text(
                "# fixture ERC proof\n\n"
                "Antenna coverage: %s, reason `missing_antenna_pdk` on every one.\n"
                % claim
            )

    def add_assembled_top(self) -> None:
        base = self.root / "layout" / "evidence" / "pll-top-layout"
        base.mkdir(parents=True, exist_ok=True)
        (base / "pll_top.gds").write_bytes(b"")

    def write_docs(self, text: str) -> None:
        self.write_readme(text)
        self.write_proposal(text)

    def write_readme(self, text: str) -> None:
        (self.root / "README.md").write_text(text)

    def write_proposal(self, text: str) -> None:
        (self.root / "docs" / "chipalooza" / "challenge-5-proposal.md").write_text(text)

    def write_layout_readme(self, text: str) -> None:
        """Write layout/README.md, graded by the PIN RESTATEMENT RULE only.

        Not written by ``__init__``: the rule skips a PIN_DOC that is absent
        (see the script's comment on why), and the vast majority of tests
        here are about rules that never look at this file. Tests that are
        about the pin prose write it explicitly.
        """
        (self.root / "layout" / "README.md").write_text(text)

    def run(self, env: dict | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(self.root / "layout" / "lib" / SCRIPT.name)],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )

    def path_without_python(self) -> dict:
        """An environment whose PATH has every tool the script needs but python3."""
        bindir = self.root / "fakebin"
        bindir.mkdir(exist_ok=True)
        for tool in ("bash", "dirname", "grep", "tr"):
            resolved = shutil.which(tool)
            if resolved is None:  # pragma: no cover - not seen on CI or macOS
                raise unittest.SkipTest(f"{tool} not on PATH")
            target = bindir / tool
            if not target.exists():
                target.symlink_to(resolved)
        return {"PATH": str(bindir)}


class CheckLayoutStatusClaimsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tree = _Tree(Path(self._tmp.name) / "repo")

    def tearDown(self):
        self._tmp.cleanup()

    def _all_four(self, *, lvs_for=("vco-layout", "divider-chain-layout")):
        for evidence_dir, gds in BLOCKS:
            self.tree.add_block(
                evidence_dir, gds, drc=True, lvs=evidence_dir in lvs_for
            )

    def test_matching_documents_pass(self):
        self._all_four()
        self.tree.write_docs(_doc_text(4, 2))
        result = self.tree.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("4/4 drawn", result.stdout)

    def test_the_exact_pre_fix_prose_is_caught(self):
        # Verbatim from README.md and the proposal as they stood on main at
        # 2ddf0c54, with all four blocks already committed.  This is the
        # regression the script was written for; if this test ever passes
        # silently, the check has stopped doing its job.
        self._all_four()
        self.tree.write_docs(
            "No PLL block has been drawn yet, and `measurements/` stays empty\n"
            "until there is silicon.\n\n"
            "**No PLL-block layout exists.** `layout/` holds a proven flow.\n"
        )
        result = self.tree.run()
        self.assertEqual(result.returncode, 1)
        self.assertIn("No PLL block has been drawn yet", result.stderr)
        self.assertIn("No PLL-block layout exists", result.stderr)

    def test_understated_block_count_is_caught(self):
        self._all_four()
        self.tree.write_docs(_doc_text(3, 2))
        result = self.tree.run()
        self.assertEqual(result.returncode, 1)
        self.assertIn("4 of the 4 PLL sub-blocks", result.stderr)

    def test_overstated_lvs_count_is_caught(self):
        # The direction that matters most for a document sent to an outside
        # reader: claiming more verification than the tree records.
        self._all_four()
        self.tree.write_docs(_doc_text(4, 4))
        result = self.tree.run()
        self.assertEqual(result.returncode, 1)
        self.assertIn("2 of the 4 are LVS-matched", result.stderr)

    def test_lvs_log_without_the_match_verdict_does_not_count(self):
        # A committed lvs-clean/ directory is not an LVS pass.  Only the
        # deck's own "Netlists match." verdict is.
        for evidence_dir, gds in BLOCKS:
            self.tree.add_block(evidence_dir, gds, drc=True, lvs=False)
        base = self.tree.root / "layout" / "evidence" / "vco-layout" / "lvs-clean"
        base.mkdir(parents=True)
        (base / "lvs.stdout.log").write_text("ERROR: Netlists don't match.\n")
        self.tree.write_docs(_doc_text(4, 0))
        result = self.tree.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_gds_without_a_drc_log_is_not_a_drawn_block(self):
        for evidence_dir, gds in BLOCKS:
            self.tree.add_block(evidence_dir, gds, drc=False, lvs=False)
        self.tree.write_docs(_doc_text(0, 0))
        result = self.tree.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_missing_no_assembled_top_sentinel_is_caught(self):
        self._all_four()
        self.tree.write_docs(_doc_text(4, 2, no_top=False))
        result = self.tree.run()
        self.assertEqual(result.returncode, 1)
        self.assertIn("no assembled `pll_top` GDS", result.stderr)

    def test_stale_no_assembled_top_sentinel_is_caught_once_a_top_lands(self):
        # The next drift due: when pll_top is assembled, every document
        # still carrying the sentinel becomes wrong in the other direction.
        self._all_four()
        self.tree.add_assembled_top()
        self.tree.write_docs(_doc_text(4, 2, no_top=True))
        result = self.tree.run()
        self.assertEqual(result.returncode, 1)
        self.assertIn("still says", result.stderr)

    def test_an_empty_evidence_tree_does_not_forbid_the_historical_claims(self):
        # With nothing drawn, "no PLL block has been drawn yet" is true
        # again and must not be flagged -- the forbidden list is conditional
        # on the tree, not absolute.
        self.tree.write_docs(
            _doc_text(0, 0) + "No PLL block has been drawn yet.\n"
        )
        result = self.tree.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    # --- The scope rule (issue #237, second pass) -------------------------
    #
    # The tests below are the ones the original hand-written forbidden list
    # could not have passed.  The list named exactly the sentences that had
    # already gone stale; the sentence that was *still* stale in the same
    # document -- section 3's "**No layout exists for this block**" -- was
    # not on it, and the check reported OK on the very commit that shipped
    # the list.

    def test_the_sentence_the_forbidden_list_missed_is_caught(self):
        # Verbatim from docs/chipalooza/challenge-5-proposal.md section 3 as
        # it stood on main at 387d03c6 -- i.e. AFTER the first pass of this
        # check shipped and passed over it.
        self._all_four()
        self.tree.write_docs(
            _doc_text(4, 2)
            + PAD
            + "**No layout exists for this block** -- `layout/` currently\n"
            "contains only the DRC/LVS flow's proof-of-flow test cell (a\n"
            "standard-cell inverter, `layout/evidence/inv-tb-proof/PROOF.md`),\n"
            "proven clean on that trivial circuit but never yet run against\n"
            "any PLL sub-block or the top level.\n"
        )
        result = self.tree.run()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("without saying at what scope", result.stderr)
        self.assertIn("No layout exists for this block", result.stderr)

    def test_an_absence_claim_that_names_its_scope_passes(self):
        # The same grammatical shape, scoped to what is genuinely absent.
        # The rule must not force a document to stop saying true things.
        self._all_four()
        self.tree.write_docs(
            _doc_text(4, 2)
            + "No GDS exists for the assembled top level, so there is no\n"
            "post-layout extracted netlist to re-verify against.\n"
        )
        result = self.tree.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_freshly_invented_unscoped_phrasing_is_caught(self):
        # The point of the rule: it grades the claim, not a remembered
        # sentence.  None of these wordings appears on any forbidden list.
        self._all_four()
        for phrasing in (
            "Nothing has been drawn for this PLL.",
            "This design has never been drawn as layout.",
            "There is no layout for the PLL at this time.",
            "PLL-block GDS: none drawn.",
        ):
            with self.subTest(phrasing=phrasing):
                self.tree.write_docs(_doc_text(4, 2) + PAD + phrasing + "\n")
                result = self.tree.run()
                self.assertEqual(
                    result.returncode, 1, result.stdout + result.stderr
                )
                self.assertIn("without saying at what scope", result.stderr)

    def test_the_scope_rule_is_silent_when_nothing_is_drawn(self):
        # Conditional on the tree, like the forbidden list: with no drawn
        # block, "no layout exists" is simply true.
        self.tree.write_docs(
            _doc_text(0, 0) + "No layout exists for this block.\n"
        )
        result = self.tree.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_top_level_scope_stops_excusing_claims_once_a_top_lands(self):
        # Two-sided, like the assembled-top sentinel: the day a pll_top GDS
        # is committed, every "no assembled top level" sentence in both
        # documents is due for a re-read, and the rule forces it.
        self._all_four()
        self.tree.add_assembled_top()
        self.tree.write_docs(
            _doc_text(4, 2, no_top=False)
            + "No GDS exists for the assembled top level.\n"
        )
        result = self.tree.run()
        self.assertEqual(result.returncode, 1)
        self.assertIn("without saying at what scope", result.stderr)

    def test_a_negation_that_is_not_about_layout_is_not_flagged(self):
        # False positives cost real editorial freedom, so the shapes that
        # nearly match are pinned: "now" is not "no", and a "drawn-band
        # edge" is not a drawn layout.
        self._all_four()
        self.tree.write_docs(
            _doc_text(4, 2)
            + "All four blocks now have a committed block GDS.\n"
            "The closed-loop campaign reaches PASS on none, at either\n"
            "drawn-band edge.\n"
        )
        result = self.tree.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    # --- The deferral half of the scope rule (issue #237) ------------------
    #
    # The scope rule grades NEGATED absence claims, and a claim escaped it by
    # not using a negation: the proposal's section 8 "Flow" bullet deferred
    # layout to the future ("(once drawn)") and named the inverter test cell
    # as what the flow is proven on, three pages after section 6 recorded
    # four blocks DRC-clean and LVS-matched against the foundry signoff
    # decks. Same falsehood, no negation word, so ABSENCE could not see it.

    def test_the_bare_deferral_the_scope_rule_missed_is_caught(self):
        # Verbatim from docs/chipalooza/challenge-5-proposal.md section 8 as
        # it stood on main at ac714b46 -- i.e. AFTER the scope rule, the
        # count rule, the footprint rule and the ERC rule had all shipped
        # and all reported OK over it.
        self._all_four()
        self.tree.write_docs(
            _doc_text(4, 2)
            + PAD
            + "- **Flow**: fully open-source. Schematic capture and netlisting\n"
            "  via xschem; simulation via ngspice; layout, DRC, and LVS (once\n"
            "  drawn) via KLayout driven by klayout-tools (`klt`), proven on\n"
            "  the inverter test cell referenced in §6.\n"
        )
        result = self.tree.run()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("without saying what is deferred", result.stderr)
        self.assertIn("once drawn", result.stderr)

    def test_a_freshly_invented_bare_deferral_is_caught(self):
        # The point of grading the claim rather than the phrase: none of
        # these wordings is the one that went stale, and all of them tell a
        # reader the same untrue thing.
        self._all_four()
        for phrasing in (
            "DRC and LVS will run once drawn.",
            "The flow handles DRC and LVS when drawn.",
            "Layout verification waits until drawn.",
            "The layout's area will be reported after laid out.",
            "The block's GDS extent is unknown if ever drawn.",
            "Metal2 track counts in the layout follow once it is drawn.",
        ):
            with self.subTest(phrasing=phrasing):
                self.tree.write_docs(_doc_text(4, 2) + PAD + phrasing + "\n")
                result = self.tree.run()
                self.assertEqual(
                    result.returncode, 1, result.stdout + result.stderr
                )
                self.assertIn("without saying what is deferred", result.stderr)

    def test_a_deferral_that_names_its_subject_passes(self):
        # This repository says all of these truthfully and repeatedly -- the
        # loop filter really is not drawn, and neither is the top level. A
        # rule that broke them would be forcing the document to stop making
        # checkable statements, which is the opposite of the point.
        self._all_four()
        for phrasing in (
            "The row comes down when the loop filter is drawn.",
            "Overhead becomes a measurement once the top level is drawn.",
            "Extraction follows once an assembled pll_top is drawn.",
        ):
            with self.subTest(phrasing=phrasing):
                self.tree.write_docs(_doc_text(4, 2) + PAD + phrasing + "\n")
                result = self.tree.run()
                self.assertEqual(
                    result.returncode, 0, result.stdout + result.stderr
                )

    def test_a_bare_deferral_that_names_its_scope_nearby_passes(self):
        # The deferral half honours the same scope tokens as the absence
        # half, so a writer may scope the sentence instead of the phrase.
        self._all_four()
        self.tree.write_docs(
            _doc_text(4, 2)
            + PAD
            + "Top-level DRC/LVS closure and extraction run once drawn.\n"
        )
        result = self.tree.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_the_deferral_rule_is_silent_when_nothing_is_drawn(self):
        # Conditional on the tree, like every other rule here: with no drawn
        # block, "(once drawn)" was the honest thing to write, and this
        # check must not retroactively condemn it.
        self.tree.write_docs(
            _doc_text(0, 0) + "DRC and LVS run once drawn.\n"
        )
        result = self.tree.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_deferral_that_is_not_about_layout_is_not_flagged(self):
        # False positives cost editorial freedom, so the near-misses are
        # pinned: "drawn" as a verb about anything else, and the repo's own
        # "drawn-band edge" / "drawn band" phrasings from the sim campaigns.
        self._all_four()
        self.tree.write_docs(
            _doc_text(4, 2)
            + PAD
            + "The band-pair mismatch sample is scored once drawn from the\n"
            "grid, at either drawn-band edge.\n"
        )
        result = self.tree.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    # --- The count rule (issue #237, third pass) ---------------------------
    #
    # drawn_claim/lvs_claim above only require the *correct* "N of the 4
    # ..." sentence to appear somewhere in the document -- so a second,
    # contradicting count elsewhere is invisible to them. That is exactly
    # what happened in the real proposal: the commit (#445) that correctly
    # wrote "4 of the 4 are LVS-matched" in the maturity note and section 6
    # left section 3 saying "2 of the 4 are LVS-matched" a few paragraphs
    # later -- true only before #452/#466 landed the last two LVS matches --
    # and this check reported OK on that tree.

    def test_a_second_stale_lvs_count_elsewhere_in_the_document_is_caught(self):
        # The regression this pass was written for, reproduced with the
        # real shape of the bug: the correct claim once, a contradicting
        # duplicate later, all four blocks actually LVS-matched.
        self._all_four(lvs_for=[d for d, _ in BLOCKS])
        self.tree.write_docs(
            _doc_text(4, 4)
            + PAD
            + "Most of the circuitry also exists as drawn geometry: 4 of\n"
            "the 4 PLL sub-blocks have a committed, DRC-clean GDS, and 2 of\n"
            "the 4 are LVS-matched. No GDS exists for the assembled top\n"
            "level.\n"
        )
        result = self.tree.run()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(
            'states "2 of the 4 LVS-matched", but layout/evidence/ records '
            "4 of the 4",
            result.stderr,
        )

    def test_a_second_stale_drawn_count_elsewhere_in_the_document_is_caught(self):
        # Same shape, the other claim: a stale "N of the 4 sub-blocks"
        # duplicate that disagrees with the tree.
        self._all_four()
        self.tree.write_docs(
            _doc_text(4, 2)
            + PAD
            + "As of the last update, 3 of the 4 sub-blocks were drawn.\n"
        )
        result = self.tree.run()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(
            'states "3 of the 4 sub-blocks drawn and DRC-clean", but '
            "layout/evidence/ records 4 of the 4",
            result.stderr,
        )

    def test_every_repeated_correct_count_passes(self):
        # The real documents state each count several times over (a
        # maturity note, section 3, section 6, section 7, README's own
        # summary paragraph) -- every correct repetition must keep passing,
        # not just the first.
        self._all_four()
        self.tree.write_docs(
            _doc_text(4, 2)
            + PAD
            + "Restated: 4 of the 4 PLL sub-blocks are drawn, and 2 of the\n"
            "4 are LVS-matched, consistent with the summary above.\n"
        )
        result = self.tree.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_an_unrelated_of_the_denominator_is_not_graded_as_a_count(self):
        # "34 of the 45 points" must not be mistaken for a "45" claim about
        # the 4 sub-blocks -- the denominator must literally be "4".
        self._all_four()
        self.tree.write_docs(
            _doc_text(4, 2)
            + PAD
            + "band 6 at 34 of the 45 points, band 7 at the other 11.\n"
        )
        result = self.tree.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    # --- The spec ratification guard --------------------------------------

    def test_a_blanket_unratified_claim_is_caught_once_the_spec_ratifies(self):
        self._all_four()
        self.tree.write_docs(
            _doc_text(4, 2)
            + "`spec/pll.md` is pending engineering ratification through #1.\n"
        )
        result = self.tree.run()
        self.assertEqual(result.returncode, 1)
        self.assertIn("pending engineering ratification", result.stderr)

    def test_a_row_scoped_carve_out_is_not_a_blanket_unratified_claim(self):
        # DR-007 Amendment A1 carves out two rows.  Saying so is true and
        # must stay sayable -- only the blanket claim is forbidden.
        self._all_four()
        self.tree.write_docs(
            _doc_text(4, 2)
            + "`spec/pll.md` is ratified, with two rows still unratified per\n"
            "DR-007 Amendment A1.\n"
        )
        result = self.tree.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_the_guard_is_silent_while_the_spec_is_still_proposed(self):
        self._all_four()
        self.tree.write_spec(UNRATIFIED_SPEC)
        self.tree.write_docs(
            _doc_text(4, 2)
            + "`spec/pll.md` is pending engineering ratification through #1.\n"
        )
        result = self.tree.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_missing_python3_fails_rather_than_downgrading_the_check(self):
        # Without python3 the scope rule cannot run at all.  Passing on the
        # remaining literal-phrase checks would be the same silent downgrade
        # that let section 3 through in the first place.
        self._all_four()
        self.tree.write_docs(_doc_text(4, 2))
        env = self.tree.path_without_python()
        result = self.tree.run(env=env)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("python3 is not on PATH", result.stderr)

    def test_an_unreadable_spec_status_fails_rather_than_skipping(self):
        # A guard that silently no-ops when its input goes missing is how a
        # check rots.  Say so instead.
        self._all_four()
        self.tree.write_spec("# PLL target specification\n\nNo status line.\n")
        self.tree.write_docs(_doc_text(4, 2))
        result = self.tree.run()
        self.assertEqual(result.returncode, 1)
        self.assertIn("could not read a '- **Status**:' line", result.stderr)

    # --- The footprint rule (issue #237, third pass) ----------------------
    #
    # Existence was graded; size was not, and drifted next.  Four area
    # levers landed in one week (#469/#470/#473/#477) and every one of them
    # updated the proposal's section 5 area row while leaving section 6's
    # table on an older number -- so this is drift with a measured
    # recurrence rate, graded here against the machine-generated audit.

    # The two section 6 rows verbatim as they stood on main at e25b3368,
    # trimmed to the cells the rule reads.
    STALE_SECTION_6 = (
        "| Sub-block | Top cell | As-drawn footprint | DRC | LVS |\n"
        "|---|---|---|---|---|\n"
        "| VCO (#293, folded at #324) | `vco_block` | 183.18 × 170.28 µm "
        "(0.0312 mm²) | clean | **matched** |\n"
        "| PFD + charge pump (#294; folded at #455) | `pfd_cp` | "
        "347.41 × 73.23 µm (0.0254 mm²) | clean | **matched** |\n"
    )

    def test_the_stale_section_6_footprints_are_caught(self):
        # The regression this pass was written for.  If this ever passes
        # silently, the footprint rule has stopped doing its job.
        self._all_four()
        self.tree.write_docs(_doc_text(4, 2) + PAD + self.STALE_SECTION_6)
        result = self.tree.run()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("states `vco_block` at 183.18 x 170.28 um", result.stderr)
        self.assertIn("172.52 x 184.48 um", result.stderr)
        self.assertIn("states `pfd_cp` at 347.41 x 73.23 um", result.stderr)
        self.assertIn("344.98 x 74.30 um", result.stderr)

    def test_footprints_that_match_the_audit_pass_in_both_adjacency_shapes(self):
        # Section 6 writes "W x H um (A mm2)" and section 5 writes
        # "A mm2 (W x H um)".  Both must keep passing.
        self._all_four()
        self.tree.write_docs(_doc_text(4, 2))
        result = self.tree.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("every stated block footprint matches", result.stdout)

    def test_a_stale_mm2_after_a_correct_tuple_is_caught(self):
        self._all_four()
        self.tree.write_docs(
            _doc_text(4, 2)
            + PAD
            + "| `vco_block` | 172.52 × 184.48 µm (0.0312 mm²) |\n"
        )
        result = self.tree.run()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("0.0312 mm2 next to its footprint", result.stderr)
        self.assertIn("31,826 um2 = 0.0318 mm2", result.stderr)

    def test_a_stale_mm2_before_a_correct_tuple_is_caught(self):
        self._all_four()
        self.tree.write_docs(
            _doc_text(4, 2)
            + PAD
            + "divider chain 0.0921 mm² (1317.66 × 41.99 µm) as drawn.\n"
        )
        result = self.tree.run()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("0.0921 mm2 next to its footprint", result.stderr)

    def test_the_rule_follows_the_audit_when_a_lever_lands(self):
        # The recurrence case, in the direction it actually recurs: the
        # audit moves because a block got smaller, and the documents do not.
        self._all_four()
        self.tree.write_docs(_doc_text(4, 2))
        moved = dict(AUDIT_GEOMETRY)
        moved["pfd_cp"] = (344.98, 60.00, 20699)
        self.tree.write_audit(moved)
        result = self.tree.run()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("states `pfd_cp` at 344.98 x 74.30 um", result.stderr)
        self.assertIn("344.98 x 60.00 um", result.stderr)

    def test_deleting_a_footprint_from_the_proposal_is_caught(self):
        # Two-sided: a stale number must not be fixable by removing the
        # column it sits in.
        self._all_four()
        geometry = {k: v for k, v in AUDIT_GEOMETRY.items() if k != "lock_detector"}
        self.tree.write_docs(_doc_text(4, 2, footprints=False) + _footprint_lines(geometry))
        result = self.tree.run()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("states no current footprint for `lock_detector`", result.stderr)

    def test_the_readme_is_not_required_to_state_footprints(self):
        # Completeness is the proposal's obligation -- it is the document
        # written for a reader outside this repository.  README carries no
        # block geometry today and must not be forced to.
        self._all_four()
        self.tree.write_readme(_doc_text(4, 2, footprints=False))
        self.tree.write_proposal(_doc_text(4, 2))
        result = self.tree.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_footprint_that_names_no_block_is_caught(self):
        # A size a reader cannot attribute is not a checkable claim, and
        # would otherwise be the easy way around the rule.
        self._all_four()
        self.tree.write_docs(
            _doc_text(4, 2)
            + PAD
            + "The block as drawn is 999.99 × 888.88 µm.\n"
        )
        result = self.tree.run()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("names no block within", result.stderr)

    def test_a_dimension_pair_that_is_not_a_footprint_is_not_graded(self):
        # False positives cost editorial freedom, so the near misses are
        # pinned: a PVT grid is not a footprint, and neither is a track
        # pitch or a device width.
        self._all_four()
        self.tree.write_docs(
            _doc_text(4, 2)
            + "`vco_block` is swept over the full 3 x 3 temperature "
            "× supply grid at a 0.75 µm Metal2 track pitch, with "
            "1.20 × 0.28 µm devices reported per row.\n"
        )
        result = self.tree.run()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertNotIn("3.00 x 3.00", result.stderr)
        # The device pair IS a decimal "W x H um" next to a block name, so
        # it is graded and fails -- the rule's one documented sharp edge.
        self.assertIn("states `vco_block` at 1.20 x 0.28 um", result.stderr)

    def test_the_footprint_rule_is_silent_when_nothing_is_drawn(self):
        # Conditional on the tree, like every other rule in this script.
        self.tree.write_docs(_doc_text(0, 0) + PAD + self.STALE_SECTION_6)
        result = self.tree.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_missing_area_audit_is_a_failure_not_a_silent_pass(self):
        self._all_four()
        self.tree.write_docs(_doc_text(4, 2))
        self.tree.remove_audit()
        result = self.tree.run()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("area-audit.md is missing", result.stderr)

    def test_an_unparseable_area_audit_is_a_failure_not_a_silent_pass(self):
        # The file exists but its geometry table has gone: passing on the
        # remaining checks is the silent downgrade this script keeps
        # refusing to make.
        self._all_four()
        self.tree.write_docs(_doc_text(4, 2))
        self.tree.write_audit(body="# Area audit\n\nRegeneration failed.\n")
        result = self.tree.run()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("parsed to zero block rows", result.stderr)

    def test_a_missing_document_is_a_failure_not_a_silent_pass(self):
        self._all_four()
        (self.tree.root / "README.md").write_text(_doc_text(4, 2))
        result = self.tree.run()
        self.assertEqual(result.returncode, 1)
        self.assertIn("does not exist", result.stderr)

    # --- The fifth guard: spec/pll.md's own "## Area" section (2026-09-25) --
    #
    # README.md and the proposal are graded for the same "W x H um" footprint
    # drift already; spec/pll.md's ratified Area table states the identical
    # four numbers -- DR-016/DR-017's 0.30 mm2 budget row is amended against
    # them -- and nothing graded it. These tests drive that guard on its own,
    # independent of the DOCS-loop rules the default RATIFIED_SPEC/
    # UNRATIFIED_SPEC fixtures already exercise implicitly (every test above
    # this point passes a spec whose "## Area" section states the correct
    # footprints, by construction).

    def test_a_stale_spec_pll_area_footprint_is_caught(self):
        self._all_four()
        self.tree.write_docs(_doc_text(4, 2))
        self.tree.write_spec(
            "# PLL target specification\n\n"
            "- **Status**: **ratified, with amendments** (#1, 2026-09-08)\n"
            + _area_section({**AUDIT_GEOMETRY, "pfd_cp": (344.98, 60.50, 20699)})
        )
        result = self.tree.run()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("spec/pll.md", result.stderr)
        self.assertIn("states `pfd_cp` at 344.98 x 60.50 um", result.stderr)
        self.assertIn("344.98 x 74.30 um", result.stderr)

    def test_spec_pll_area_footprints_must_state_all_four_blocks(self):
        # Two-sided, like the proposal's own completeness rule: a stale
        # number cannot be "fixed" by deleting the row it sits in.
        self._all_four()
        self.tree.write_docs(_doc_text(4, 2))
        geometry = {k: v for k, v in AUDIT_GEOMETRY.items() if k != "lock_detector"}
        self.tree.write_spec(
            "# PLL target specification\n\n"
            "- **Status**: **ratified, with amendments** (#1, 2026-09-08)\n"
            + _area_section(geometry)
        )
        result = self.tree.run()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(
            "states no current footprint for `lock_detector`", result.stderr
        )

    def test_a_missing_spec_pll_area_section_is_caught(self):
        # A document that states no footprints at all (no "## Area" heading)
        # is a parse failure against this rule, not a vacuously clean one --
        # spec/pll.md's Area table is where the row DR-016/DR-017 amend lives.
        self._all_four()
        self.tree.write_docs(_doc_text(4, 2))
        self.tree.write_spec(
            "# PLL target specification\n\n"
            "- **Status**: **ratified, with amendments** (#1, 2026-09-08)\n"
        )
        result = self.tree.run()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("has no '## Area' section", result.stderr)

    def test_a_device_dimension_outside_the_area_section_is_not_graded(self):
        # The reason grading is scoped to the section rather than the whole
        # file: spec/pll.md's Loop bandwidth section states the loop filter's
        # C2 plate size, `31.4 x 31.4 um`, in the identical "W x H um" shape a
        # footprint claim uses, and it names no PLL sub-block. A whole-
        # document scan would misreport it as an unattributable footprint
        # claim (the "names no block within N characters" failure) even
        # though the Area section itself is completely correct.
        self._all_four()
        self.tree.write_docs(_doc_text(4, 2))
        self.tree.write_spec(
            "# PLL target specification\n\n"
            "- **Status**: **ratified, with amendments** (#1, 2026-09-08)\n"
            "\n## Loop bandwidth\n\n"
            "The loop filter's C2 is a single MIM cap, 31.4 x 31.4 um.\n"
            + _area_section()
        )
        result = self.tree.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_spec_pll_area_footprints_are_silent_when_nothing_is_drawn(self):
        # Conditional on the tree, like every other footprint check here.
        self.tree.write_docs(_doc_text(0, 0))
        self.tree.write_spec(
            "# PLL target specification\n\n"
            "- **Status**: **ratified, with amendments** (#1, 2026-09-08)\n"
            + _area_section({"pfd_cp": (999.99, 888.88, 1)})
        )
        result = self.tree.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    # --- The ERC rule (issue #565) ------------------------------------------
    #
    # `layout/evidence/vco-layout/erc-report.json` was the only `klt erc`
    # supply report in the repository, and it had gone stale in three ways at
    # once: a `/tmp` scratch `file` field, a `provenance.klt_version` behind
    # the CI pin, and a free-text `_ties_omitted` rationale citing an upstream
    # bug that had since been fixed. Each of those is a claim about a
    # committed file that a committed file could have been checked against --
    # these tests drive the rule that now does, against synthetic trees where
    # the answer is known.

    def _all_four_erc_ready(self):
        # Every block LVS-matched, so every block is owed -- and, by
        # add_block's default, every block gets a valid erc-supply-spec.json
        # / erc-report.json / PROOF-erc.md set from add_erc. Individual tests
        # then break exactly one artifact on one block.
        self._all_four(lvs_for=[d for d, _ in BLOCKS])

    def test_lvs_matched_block_without_erc_evidence_is_caught(self):
        for evidence_dir, gds in BLOCKS:
            self.tree.add_block(evidence_dir, gds, drc=True, lvs=True, erc=False)
        self.tree.write_docs(_doc_text(4, 4))
        result = self.tree.run()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(
            "layout/evidence/vco-layout is LVS-matched but has no complete "
            "klt erc supply evidence: missing erc-supply-spec.json, "
            "erc-report.json, PROOF-erc.md.",
            result.stderr,
        )

    def test_a_stale_erc_report_input_hash_is_caught(self):
        # The report describes a file that is not the one committed beside
        # it -- exactly the drift a `/tmp` scratch `file` field let through.
        self._all_four_erc_ready()
        self.tree.add_erc(
            "vco-layout", "vco_block.gds", input_hash="sha256:" + "0" * 64
        )
        self.tree.write_docs(_doc_text(4, 4))
        result = self.tree.run()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(
            "layout/evidence/vco-layout/erc-report.json's "
            "provenance.input.content_hash is", result.stderr,
        )
        self.assertIn("re-run `klt erc`", result.stderr)

    def test_a_stale_erc_report_spec_hash_is_caught(self):
        self._all_four_erc_ready()
        self.tree.add_erc(
            "divider-chain-layout",
            "divider_chain.gds",
            input_hash=None,
        )
        # Corrupt only the recorded spec hash, leaving the input hash valid.
        report_path = (
            self.tree.root
            / "layout" / "evidence" / "divider-chain-layout" / "erc-report.json"
        )
        report = json.loads(report_path.read_text())
        report["provenance"]["spec"]["content_hash"] = "sha256:" + "f" * 64
        report_path.write_text(json.dumps(report, indent=2) + "\n")
        self.tree.write_docs(_doc_text(4, 4))
        result = self.tree.run()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(
            "layout/evidence/divider-chain-layout/erc-report.json's "
            "provenance.spec.content_hash is", result.stderr,
        )

    def test_a_report_from_an_unpinned_klt_is_caught(self):
        self._all_four_erc_ready()
        self.tree.add_erc("pfd-cp-layout", "pfd_cp.gds", klt_version="0.5.0")
        self.tree.write_docs(_doc_text(4, 4))
        result = self.tree.run()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(
            "layout/evidence/pfd-cp-layout/erc-report.json was produced on "
            "klt '0.5.0', but .github/workflows/ci.yml pins "
            "klayout-tools==0.6.0.",
            result.stderr,
        )

    def test_a_report_from_a_post_tag_source_build_is_caught(self):
        # The regression this test exists for (issue #127). The rule above used
        # to ask `stated.startswith(pinned)`, so a PEP 440 *local version* --
        # `0.6.0+g<sha>`, a build of the klayout-tools tree *after* the v0.6.0
        # tag -- satisfied it while not being the released wheel at all. All
        # four committed reports sat in that state for three weeks: their JSON
        # carried a top-level `nets[]` block and an
        # `erc_coverage.layers_in_stream_without_declaration` key the released
        # wheel does not emit, at an unchanged `schema_version`, so nothing
        # inside the envelope could have announced it. Only the version string
        # could, and a prefix test threw exactly that away.
        self._all_four_erc_ready()
        self.tree.add_erc(
            "pfd-cp-layout", "pfd_cp.gds", klt_version="0.6.0+gf2d249ab23d4"
        )
        self.tree.write_docs(_doc_text(4, 4))
        result = self.tree.run()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(
            "layout/evidence/pfd-cp-layout/erc-report.json was produced on "
            "klt '0.6.0+gf2d249ab23d4', but .github/workflows/ci.yml pins "
            "klayout-tools==0.6.0.",
            result.stderr,
        )
        # And the message must say *why* a version that looks like the pin is
        # not the pin -- a bare "different klt" reads as a typo here.
        self.assertIn("local-version suffix", result.stderr)
        self.assertIn("source build", result.stderr)

    def test_the_exact_pin_is_still_accepted(self):
        # The negative control for the test above: tightening prefix-match to
        # equality must not reject the version it is supposed to accept.
        self._all_four_erc_ready()
        self.tree.add_erc("pfd-cp-layout", "pfd_cp.gds", klt_version="0.6.0")
        self.tree.write_docs(_doc_text(4, 4))
        result = self.tree.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_ci_workflow_with_no_pin_is_caught(self):
        self._all_four_erc_ready()
        self.tree.write_ci_workflow(pin=None)
        self.tree.write_docs(_doc_text(4, 4))
        result = self.tree.run()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(
            "names no 'klayout-tools==<version>' pin", result.stderr
        )

    def test_a_missing_ci_workflow_is_caught(self):
        self._all_four_erc_ready()
        self.tree.remove_ci_workflow()
        self.tree.write_docs(_doc_text(4, 4))
        result = self.tree.run()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("cannot read", result.stderr)
        self.assertIn("ci.yml", result.stderr)

    def test_a_stray_spec_key_is_caught(self):
        # The structural half of the stale-rationale fix: a free-text
        # rationale key is exactly how the real `_ties_omitted` note went on
        # citing a fixed upstream bug, so it must be unrepresentable.
        self._all_four_erc_ready()
        self.tree.add_erc(
            "vco-layout",
            "vco_block.gds",
            extra_spec_keys={
                "_ties_omitted": "klayout-tools#2169 (fixed upstream)"
            },
        )
        self.tree.write_docs(_doc_text(4, 4))
        result = self.tree.run()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(
            "layout/evidence/vco-layout/erc-supply-spec.json carries "
            "top-level key(s) '_ties_omitted' outside", result.stderr,
        )

    def test_no_ties_and_no_disclosure_is_caught(self):
        self._all_four_erc_ready()
        self.tree.add_erc("lock-detector-layout", "lock_detector.gds", ties=False)
        self.tree.write_docs(_doc_text(4, 4))
        result = self.tree.run()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(
            "layout/evidence/lock-detector-layout/erc-supply-spec.json "
            "declares no `ties[]` and no usable `ties_disclosure`",
            result.stderr,
        )

    def test_a_ties_disclosure_with_an_unrecognized_kind_is_caught(self):
        self._all_four_erc_ready()
        self.tree.add_erc(
            "pfd-cp-layout",
            "pfd_cp.gds",
            ties=False,
            disclosure_kind="citation",
        )
        self.tree.write_docs(_doc_text(4, 4))
        result = self.tree.run()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(
            "declares no `ties[]` and no usable `ties_disclosure` (kind "
            "'citation'", result.stderr,
        )

    def test_a_ties_disclosure_without_a_reason_is_caught(self):
        self._all_four_erc_ready()
        self.tree.add_erc(
            "pfd-cp-layout",
            "pfd_cp.gds",
            ties=False,
            disclosure_kind="tool_limitation",
            disclosure_reason="",
        )
        self.tree.write_docs(_doc_text(4, 4))
        result = self.tree.run()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(
            "layout/evidence/pfd-cp-layout/erc-supply-spec.json's "
            "`ties_disclosure` states no `reason`.",
            result.stderr,
        )

    def test_a_valid_ties_disclosure_passes(self):
        # A block that genuinely cannot express a tie is not the same
        # failure as one that simply never declared it -- kt#2180's
        # first-class `ties_disclosure` field is how a grader tells them
        # apart, and this is the shape `pfd_cp`'s real spec uses.
        self._all_four_erc_ready()
        self.tree.add_erc(
            "pfd-cp-layout",
            "pfd_cp.gds",
            ties=False,
            disclosure_kind="tool_limitation",
            disclosure_reason=(
                "well_requires/well_excludes needs a marker layer this "
                "stream draws none of"
            ),
        )
        self.tree.write_docs(_doc_text(4, 4))
        result = self.tree.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("tie=disclosed", result.stdout)

    def test_proof_erc_that_understates_its_own_antenna_coverage_is_caught(self):
        # The antenna half of `klt erc` has never run in this repository;
        # PROOF-erc.md must say so in the report's own numbers, not a
        # different, incorrect count.
        self._all_four_erc_ready()
        self.tree.add_erc(
            "divider-chain-layout",
            "divider_chain.gds",
            antenna_skipped=3,
            proof_antenna_claim="checked: 0, skipped: 1",
        )
        self.tree.write_docs(_doc_text(4, 4))
        result = self.tree.run()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(
            "layout/evidence/divider-chain-layout/PROOF-erc.md does not "
            'state "checked: 0, skipped: 3"', result.stderr,
        )

    def test_all_four_erc_evidence_passes_and_the_count_is_stated(self):
        self._all_four_erc_ready()
        self.tree.write_docs(
            _doc_text(4, 4) + "4 of the 4 blocks are ERC-checked.\n"
        )
        result = self.tree.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("4 of the 4 blocks ERC-checked", result.stdout)
        self.assertIn("4/4 ERC-checked", result.stdout)

    def test_a_stale_erc_checked_count_is_caught(self):
        # The count rule (issue #237's third pass) extended to this claim:
        # a document may state "N of the 4 blocks ERC-checked", but only the
        # correct N.
        self._all_four_erc_ready()
        self.tree.write_docs(
            _doc_text(4, 4) + "1 of the 4 blocks are ERC-checked.\n"
        )
        result = self.tree.run()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(
            'states "1 of the 4 blocks ERC-checked", but layout/evidence/ '
            "records 4 of the 4", result.stderr,
        )

    def test_an_lvs_mismatched_block_is_not_asked_for_erc_even_with_a_stale_directory(self):
        # The point of the erc_entries plumbing: coverage is owed from the
        # already-derived LVS-matched verdict, not from a looser "an
        # lvs-clean/ directory exists" test. A block whose deck says the
        # netlists do not match is not asked for `klt erc` evidence, even
        # though its lvs-clean/ directory is present.
        for evidence_dir, gds in BLOCKS:
            self.tree.add_block(evidence_dir, gds, drc=True, lvs=False)
        base = self.tree.root / "layout" / "evidence" / "vco-layout" / "lvs-clean"
        base.mkdir(parents=True, exist_ok=True)
        (base / "lvs.stdout.log").write_text("ERROR: Netlists don't match.\n")
        self.tree.write_docs(_doc_text(4, 0))
        result = self.tree.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("0/4 ERC-checked", result.stdout)

    # --- The KLAYOUT PIN RULE (issue #127) ---------------------------------
    #
    # The rule exists because 16 of the 51 committed DRC/LVS deck logs turned
    # out to have been captured on KLayout 0.30.9/0.30.10 rather than on the
    # 0.28.16 pin `layout/harness/env.py` declares -- including `vco_block`'s
    # own block-level DRC-clean and LVS-match logs, the two artifacts T1 items
    # 3 and 4 score the VCO on -- while both layout/README.md and issue #127's
    # body asserted every committed artifact was on the pin. Nothing checked
    # it; the run-time WARNING in env.py grades the binary you are about to
    # use, never the logs already in the tree.

    def test_an_undisclosed_off_pin_deck_log_is_caught(self):
        self._all_four()
        self.tree.add_deck_log(
            "vco-layout/drc-clean/drc-extra.stdout.log",
            klayout="KLayout 0.30.10",
            top="vco_block",
        )
        self.tree.write_docs(_doc_text(4, 2))
        result = self.tree.run()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(
            "vco-layout/drc-clean/drc-extra.stdout.log was produced on "
            "KLayout 0.30.10, but layout/harness/env.py pins KLayout 0.28.16",
            result.stderr,
        )

    def test_a_block_with_only_an_off_pin_drc_log_is_caught(self):
        # The exact pre-fix state of vco_block: drawn and DRC-clean, but the
        # only committed DRC log for that top cell is from 0.30.10.
        for evidence_dir, gds in BLOCKS:
            self.tree.add_block(
                evidence_dir,
                gds,
                drc=True,
                lvs=True,
                drc_klayout=(
                    "KLayout 0.30.10" if evidence_dir == "vco-layout" else PINNED_KLAYOUT
                ),
            )
        self.tree.write_docs(_doc_text(4, 4))
        result = self.tree.run()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(
            "VCO reads as DRC-clean from the evidence tree, but no committed "
            "deck log for top cell `vco_block` carries that verdict on "
            "KLayout 0.28.16",
            result.stderr,
        )

    def test_a_block_with_only_an_off_pin_lvs_log_is_caught(self):
        for evidence_dir, gds in BLOCKS:
            self.tree.add_block(
                evidence_dir,
                gds,
                drc=True,
                lvs=True,
                lvs_klayout=(
                    "KLayout 0.30.10" if evidence_dir == "vco-layout" else PINNED_KLAYOUT
                ),
            )
        self.tree.write_docs(_doc_text(4, 4))
        result = self.tree.run()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(
            "VCO reads as LVS-match from the evidence tree, but no committed "
            "deck log for top cell `vco_block` carries that verdict on "
            "KLayout 0.28.16",
            result.stderr,
        )

    def test_an_off_pin_log_beside_an_on_pin_rerun_passes(self):
        # The fix shape this repository actually uses: the superseded off-pin
        # run stays in the tree (append-only evidence), and a sibling
        # re-check directory carries the same verdict on the pin. "At least
        # one on-pin log", not "all logs on-pin", is what makes that legal --
        # deleting the original to satisfy a checker would be the wrong repair.
        for evidence_dir, gds in BLOCKS:
            self.tree.add_block(
                evidence_dir,
                gds,
                drc=True,
                lvs=True,
                lvs_klayout=(
                    "KLayout 0.30.10" if evidence_dir == "vco-layout" else PINNED_KLAYOUT
                ),
            )
        # Disclose the superseded one under the name the script's
        # OFF_PIN_DISCLOSED already carries, then add the on-pin re-run.
        self.tree.add_deck_log(
            "vco-layout/lvs-recheck-klayout-0.28.16/lvs.stdout.log",
            klayout=PINNED_KLAYOUT,
            top="vco_block",
            verdict=LVS_MATCH_LINE,
        )
        self.tree.write_docs(_doc_text(4, 4))
        result = self.tree.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("1 off-pin", result.stdout)

    def test_a_missing_klayout_pin_fails_rather_than_skipping(self):
        # Same doctrine as the klt pin: a version claim gradeable against
        # nothing is the failure mode, not a free pass.
        self._all_four()
        self.tree.write_harness_env(pin=None)
        self.tree.write_docs(_doc_text(4, 2))
        result = self.tree.run()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("declares no KNOWN_GOOD_KLAYOUT_VERSION", result.stderr)

    def test_the_pin_is_read_from_env_py_not_restated(self):
        # Move the pin and the whole tree's verdict moves with it. If the
        # script had hardcoded "KLayout 0.28.16", this would still pass on the
        # old value and silently stop tracking the repository's real pin.
        for evidence_dir, gds in BLOCKS:
            self.tree.add_block(
                evidence_dir,
                gds,
                drc=True,
                lvs=True,
                drc_klayout="KLayout 0.29.4",
                lvs_klayout="KLayout 0.29.4",
            )
        self.tree.write_harness_env(pin="KLayout 0.29.4")
        # The documents move with the pin too -- that is the PIN RESTATEMENT
        # RULE's whole point, and the test below holds it the other way round.
        self.tree.write_docs(_doc_text(4, 4, pin="KLayout 0.29.4"))
        result = self.tree.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("on the pin (KLayout 0.29.4), 0 off-pin", result.stdout)

    def test_a_log_with_no_version_stamp_is_not_graded(self):
        # Not every committed .log under layout/evidence/ is a deck log --
        # connectivity transcripts and harness notes live there too. Only logs
        # that actually record an engine are graded on one.
        self._all_four()
        (
            self.tree.root / "layout" / "evidence" / "vco-layout" / "drc-clean"
            / "connectivity-block.log"
        ).write_text("connectivity clean: 43 nets, no shorts, no splits\n")
        self.tree.write_docs(_doc_text(4, 2))
        result = self.tree.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        # 4 DRC + 2 LVS deck logs; the connectivity transcript is not one.
        self.assertIn("6 deck logs carry a KLayout version stamp", result.stdout)


class PinRestatementRuleTests(unittest.TestCase):
    """The eighth guard (issue #237): what the *documents* say the pin is.

    The KLAYOUT PIN RULE grades the logs. This one grades the prose about
    them -- which is where the failure #127 found actually lived: a sentence
    asserting the committed DRC/LVS evidence had all been captured on the
    pin, in three places at once, while 16 of the 51 committed deck logs
    were not.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tree = _Tree(Path(self._tmp.name))
        for evidence_dir, gds in BLOCKS:
            self.tree.add_block(evidence_dir, gds, drc=True, lvs=True)

    def test_documents_stating_the_real_pin_pass(self):
        self.tree.write_docs(_doc_text(4, 4))
        self.tree.write_layout_readme(_pin_line())
        result = self.tree.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("state or restate the KLayout pin consistently", result.stdout)

    def test_a_document_naming_a_different_engine_as_the_pin_is_caught(self):
        # The drift a pin bump produces: env.py moves, the prose does not.
        self.tree.write_docs(_doc_text(4, 4, pin="KLayout 0.30.10"))
        result = self.tree.run()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("states `KLayout 0.30.10` as this repository's", result.stderr)
        self.assertIn(PINNED_KLAYOUT, result.stderr)

    def test_the_bare_version_shape_is_graded_too(self):
        # "the `0.30.10` pin" asserts a pin just as squarely as
        # "pins `KLayout 0.30.10`" does, with the program name elided. Real
        # prose in this repository uses both shapes.
        self.tree.write_docs(
            _doc_text(4, 4) + "Every log above was produced on the `0.30.10` pin.\n"
        )
        result = self.tree.run()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("calls `0.30.10` the pin", result.stderr)

    def test_layout_readme_is_graded_even_though_it_is_not_in_DOCS(self):
        # It is the operator manual, not a status narrative, so the count /
        # scope / footprint rules do not apply to it -- but it is where this
        # repository explains the pin, and where the false claim lived.
        self.tree.write_docs(_doc_text(4, 4))
        self.tree.write_layout_readme("This repository pins `KLayout 0.26.1`.\n")
        result = self.tree.run()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("layout/README.md states `KLayout 0.26.1`", result.stderr)

    def test_the_proposal_must_state_the_pin_at_all(self):
        # Deleting the sentence is not a way to stop it being wrong: the
        # proposal's section 6 scores a DRC/LVS verdict table, and a verdict
        # is only evidence about the engine that produced it.
        self.tree.write_readme(_doc_text(4, 4))
        self.tree.write_proposal(_doc_text(4, 4, state_pin=False))
        result = self.tree.run()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("never states this repository's KLayout pin", result.stderr)

    def test_the_root_readme_need_not_state_the_pin(self):
        # Only the proposal owes the positive claim. README.md carries no
        # tool-version detail by design, the same way it carries no block
        # geometry (see FOOTPRINT_COMPLETE_DOC).
        self.tree.write_readme(_doc_text(4, 4, state_pin=False))
        self.tree.write_proposal(_doc_text(4, 4))
        result = self.tree.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_quoting_a_superseded_captured_against_claim_is_not_graded(self):
        # Both documents quote the sentence that was wrong, as history. A
        # check that grades a claim cannot tell asserting it from quoting it,
        # so this rule grades the shape that asserts a pin and leaves the
        # shape that narrates a retired one quotable.
        self.tree.write_docs(
            _doc_text(4, 4)
            + 'An earlier revision said "the committed DRC/LVS evidence was '
            'captured against KLayout 0.30.9", which was false.\n'
        )
        result = self.tree.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_missing_pin_doc_is_skipped_not_failed(self):
        # layout/README.md is absent from this fixture unless a test writes
        # it. That it exists in the real tree is asserted below, against the
        # real tree, for the same reason the disclosure list is.
        self.tree.write_docs(_doc_text(4, 4))
        result = self.tree.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class PinDocumentsExistTests(unittest.TestCase):
    """PIN_DOCS, asserted against the real tree.

    The rule skips a PIN_DOC it cannot find, so that it stays correct on the
    synthetic trees above. The guarantee that the real files are there is
    still owed, so it is asserted here -- same doctrine, and same reason, as
    OffPinDisclosureListTests below.
    """

    def setUp(self):
        text = SCRIPT.read_text()
        block = re.search(r"^PIN_DOCS=\((.*?)^\)", text, re.S | re.M)
        self.assertIsNotNone(block, "PIN_DOCS not found in the script")
        self.docs = re.findall(r'^\s*"([^"]+)"', block.group(1), re.M)
        self.repo_root = LAYOUT_DIR.parent

    def test_the_list_is_not_empty(self):
        self.assertTrue(self.docs)

    def test_every_pin_doc_exists(self):
        missing = [rel for rel in self.docs if not (self.repo_root / rel).is_file()]
        self.assertEqual(
            missing,
            [],
            "PIN_DOCS names documents that do not exist; the rule skips a "
            "missing file, so a renamed document would silently stop being "
            "graded rather than failing",
        )

    def test_the_required_pin_doc_is_one_of_them(self):
        required = re.search(r'^PIN_STATED_DOC="([^"]+)"', SCRIPT.read_text(), re.M)
        self.assertIsNotNone(required, "PIN_STATED_DOC not found in the script")
        self.assertIn(required.group(1), self.docs)


class OffPinDisclosureListTests(unittest.TestCase):
    """The disclosure list, graded against the real evidence tree.

    Deliberately not part of the script: the rule itself has to stay correct
    on the synthetic trees above, which hold none of these files. The
    guarantee is still owed, so it is asserted here instead -- a disclosure
    list that outlives its files stops being a disclosure and becomes a
    blanket excuse.
    """

    def setUp(self):
        text = SCRIPT.read_text()
        block = re.search(
            r"OFF_PIN_DISCLOSED = \{(.*?)^\}", text, re.S | re.M
        )
        self.assertIsNotNone(block, "OFF_PIN_DISCLOSED not found in the script")
        self.entries = re.findall(r'^\s*"([^"]+)":', block.group(1), re.M)

    def test_the_list_is_not_empty(self):
        self.assertTrue(self.entries)

    def test_the_off_pin_disclosure_list_has_no_stale_entries(self):
        evidence = LAYOUT_DIR / "evidence"
        missing = [rel for rel in self.entries if not (evidence / rel).is_file()]
        self.assertEqual(
            missing,
            [],
            "OFF_PIN_DISCLOSED names files that no longer exist; drop the "
            "entries rather than letting the list widen into a blanket excuse",
        )

    def test_every_disclosed_entry_is_actually_off_pin(self):
        # The mirror failure: an entry that has since been re-run on the pin
        # and is now graded, but is still listed as an exception. That would
        # hide a future regression on that same path.
        pin = re.search(
            r'^KNOWN_GOOD_KLAYOUT_VERSION\s*=\s*"([^"]+)"',
            (LAYOUT_DIR / "harness" / "env.py").read_text(),
            re.M,
        ).group(1)
        evidence = LAYOUT_DIR / "evidence"
        still_on_pin = []
        for rel in self.entries:
            path = evidence / rel
            if not path.is_file():
                continue
            found = re.search(
                r"Your Klayout version is: (KLayout [0-9][0-9.]*)",
                path.read_text(errors="replace"),
            )
            if found and found.group(1) == pin:
                still_on_pin.append(rel)
        self.assertEqual(
            still_on_pin,
            [],
            f"OFF_PIN_DISCLOSED names logs that are on the pin ({pin}); they "
            "are graded like any other log now, so the exemption only hides a "
            "future regression",
        )


if __name__ == "__main__":
    unittest.main()
