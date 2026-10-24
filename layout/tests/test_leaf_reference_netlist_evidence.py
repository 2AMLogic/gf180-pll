#!/usr/bin/env python3
"""Every committed leaf-cell LVS reference netlist is still what its own
``reference_netlist()`` produces today (issue #127's 2026-09-27 derivation
pass).

``layout/evidence/<proof-dir>/<cell>.spice`` is the *golden* side of each
leaf cell's LVS run: the deck compared the extracted ``.cir`` against those
exact bytes, and the ``lvs.stdout.log`` beside them says
``Congratulations! Netlists match.`` about that comparison and no other. So
the match log only means something for as long as the committed reference is
still what the generator emits -- the assertion
``test_pfdcp_block_layout.py`` and ``test_lock_detector_layout.py`` each
already make for their own block (issue #440, PR #471: *"so the match log
cannot silently outlive the thing it was compared against"*).

**The gap this file closes.** That assertion existed for exactly **2 of the
17** ``reference_netlist()`` functions under ``layout/pll_top/`` --
``pfd_cp/block.py`` and ``lock_detector/build.py`` -- and for neither of the
other two scored blocks (``vco/block.py``, ``divider_chain/divider_chain.py``)
nor any of the leaf cells. Issue #620 (PR #621, ``73e230ba``) then rewrote the
shared comment header of eight of them, lifting it into
``harness/cell.py::reference_netlist_header`` and routing each call site
through ``pll_top/_cli.py``. That refactor moved the golden reference's own
text while touching no ``.gds``, no ``layout/evidence/`` path and no
``.spice``, which means:

* ``test_gds_reproducibility.py`` cannot see it -- no geometry moved;
* ``layout/lib/check-layout-status-claims.sh`` cannot see it -- it reads the
  committed logs, which are unchanged;
* the existing ``ReferenceNetlistTests`` classes cannot see it -- they grade
  the ``.subckt`` header and the ``M_`` device lines against each cell's own
  device table, and the text #620 moved is *comment* lines, which those
  tests deliberately ignore.

A divergence introduced that way would therefore have left every committed
artifact and every gate green while the golden reference no longer matched
the bytes the deck was run against. It did not diverge -- all 15 match,
verified by hand in that pass and now by this file -- but nothing in CI was
checking, and "nothing was checking" is the finding.

Pure text comparison: no ``klayout.db``, no PDK, no deck. Runs in a
PV-less checkout.
"""

from __future__ import annotations

import importlib
import unittest
from pathlib import Path

from _env import LAYOUT_DIR  # noqa: F401

EVIDENCE = LAYOUT_DIR / "evidence"

#: ``module import path -> committed reference netlist, relative to
#: layout/evidence/``. Written out rather than derived: the evidence path is
#: *not* a function of the module. ``leaf_cli_main``'s ``evidence_subdir``
#: argument gets a cell's proof directory, but the four row cells share one
#: (``divider-rowcells-proof``) and nest a further level under it, three
#: cells' directory name is not their cell name (``divider-inv-proof`` for
#: ``inv_3v3``, ``divider-chain-layout`` for ``divider_chain``), and
#: ``pfdcp_inv``'s module name is not its ``TOP_CELL`` (``pfdcp_inv_3v3``).
#: Deriving it would encode four exceptions as cleverness; a table states
#: them, and a new leaf cell that forgets to add its row here is caught by
#: ``test_every_reference_netlist_in_the_tree_is_covered`` below.
REFERENCES = {
    "divider_chain.inv_3v3": "divider-inv-proof/inv_3v3.spice",
    "divider_chain.inv2x_3v3": "divider-rowcells-proof/inv2x_3v3/inv2x_3v3.spice",
    "divider_chain.nand2_3v3": "divider-rowcells-proof/nand2_3v3/nand2_3v3.spice",
    "divider_chain.nand3_3v3": "divider-rowcells-proof/nand3_3v3/nand3_3v3.spice",
    "divider_chain.nor2_3v3": "divider-rowcells-proof/nor2_3v3/nor2_3v3.spice",
    "divider_chain.tgate_3v3": "divider-tgate-proof/tgate_3v3.spice",
    "divider_chain.dff_tg_3v3": "divider-dff-proof/dff_tg_3v3.spice",
    "divider_chain.div23_cell": "divider-div23-proof/div23_cell.spice",
    "divider_chain.divider_chain": "divider-chain-layout/divider_chain.spice",
    "pfd_cp.cp_leg_n": "cp-leg-proof/cp_leg_n.spice",
    "pfd_cp.cp_leg_p": "cp-leg-proof/cp_leg_p.spice",
    "pfd_cp.pfdcp_inv": "pfdcp-inv-proof/pfdcp_inv_3v3.spice",
    # Two of the four scored blocks. Their own test files grade
    # reference_netlist() thoroughly against devices.py's sizing tables and
    # against each recorded pin (test_vco_layout.py's
    # ReferenceNetlistTests/PinLabelTests, test_divider_chain.py) -- but
    # against the *tables*, never against the committed bytes the deck was
    # actually run on, which is the distinct thing asserted here.
    # Issue #759: the current block reference carries XCDEC1/XCDEC2, so the run
    # it was matched against lives in the dated decap directory; the older
    # lvs-clean/ run (no decap pair) stays as the historical record.
    "vco.block": "vco-layout/decap-20261009/vco_block.spice",
    "vco.ring": "vco-layout/lvs-ring/vco_ring.spice",
    "vco.buffer": "vco-layout/lvs-buffer/vco_out_buffer.spice",
    "loop_filter.block": "loop-filter-layout/loop_filter.spice",
}

#: The two ``reference_netlist()`` functions deliberately *not* in
#: :data:`REFERENCES`: each already carries this same byte-identity assertion
#: in its own block's test file, against its own ``lvs-clean/`` directory
#: (``test_pfdcp_block_layout.py``, ``test_lock_detector_layout.py``).
#: Listed so the coverage test below can tell "covered elsewhere" from
#: "forgotten".
COVERED_ELSEWHERE = {
    "pfd_cp/block.py",
    "lock_detector/build.py",
}


class CommittedReferenceNetlistTests(unittest.TestCase):
    """Each committed ``.spice`` equals its generator's output, byte for byte."""

    def test_the_committed_reference_is_what_reference_netlist_produces_today(self):
        for module_path, evidence_rel in sorted(REFERENCES.items()):
            with self.subTest(module=module_path):
                module = importlib.import_module(module_path)
                committed = (EVIDENCE / evidence_rel).read_text()
                self.assertEqual(
                    committed,
                    module.reference_netlist(),
                    f"layout/evidence/{evidence_rel} is no longer what "
                    f"{module_path}.reference_netlist() produces -- the LVS log "
                    "beside it was run against the committed bytes, so either "
                    "regenerate the evidence (and re-run the deck) or revert "
                    "the generator change.",
                )

    def test_every_listed_reference_netlist_is_committed(self):
        for module_path, evidence_rel in sorted(REFERENCES.items()):
            with self.subTest(module=module_path):
                self.assertTrue(
                    (EVIDENCE / evidence_rel).is_file(),
                    f"layout/evidence/{evidence_rel} missing -- do not delete a "
                    "reference netlist an LVS match log cites",
                )

    def test_every_reference_netlist_in_the_tree_is_covered(self):
        """A new leaf cell cannot quietly land without a row above.

        Greps ``layout/pll_top/`` for ``def reference_netlist()`` rather than
        trusting :data:`REFERENCES` to be complete, because the failure this
        file exists to prevent is precisely an ungated generator.
        """
        found = {
            str(path.relative_to(LAYOUT_DIR / "pll_top"))
            for path in sorted((LAYOUT_DIR / "pll_top").rglob("*.py"))
            if "def reference_netlist(" in path.read_text()
        }
        listed = {
            str(Path(module_path.replace(".", "/") + ".py")) for module_path in REFERENCES
        }
        self.assertEqual(
            found - listed - COVERED_ELSEWHERE,
            set(),
            "reference_netlist() found with no committed-bytes assertion -- add "
            "a REFERENCES row (or, for a whole block, the assertion its own "
            "test file makes and a COVERED_ELSEWHERE entry)",
        )


if __name__ == "__main__":
    unittest.main()
