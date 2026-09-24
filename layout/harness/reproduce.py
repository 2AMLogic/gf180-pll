"""Does a committed block GDS still come out of its own generator? (issue #451)

WHY THIS EXISTS
---------------
Every DRC/LVS claim in ``layout/evidence/`` is a claim about a *committed
file*. The generator that produced that file keeps changing afterwards, and
nothing re-derives the artifact: ``layout/run_pv.py`` runs a deck against
whatever GDS it is handed, and ``layout/lib/check-layout-status-claims.sh``
grades README/proposal prose against the *recorded* deck verdict. Neither
rebuilds anything, so a generator can drift arbitrarily far from the file
that carries its evidence and every check in the repository still passes.

That is not hypothetical. ``layout/evidence/lock-detector-layout/lock_detector.gds``
was committed once (issue #296, 2026-09-08) and its generator changed seven
times over the following fortnight; by the time anyone re-derived it, the
committed file and the generator's output differed on 9 of 11 drawing
layers, and the generator's own output failed the foundry DRC deck with 141
violations where the committed file was clean (issue #451). The block's
"DRC-clean" claim was true of the committed file and of nothing else that
existed.

WHAT THIS MODULE DOES
---------------------
:data:`BLOCKS` names, for every committed block GDS in ``layout/evidence/``,
the generator that is supposed to produce it. :func:`rebuild` runs that
generator into a scratch directory exactly the way each evidence directory's
own PROOF.md documents, and :func:`layer_differences` compares the result
against the committed file **layer by layer, as merged geometry**
(``klayout.db.Region`` XOR) rather than byte by byte -- a GDS carries a
write timestamp in its own header, so two runs of one unchanged generator
are never byte-identical and a checksum would be a permanently red light.

Only the *drawing* datatypes are compared by default. Label/pin purposes
(34/10, 36/10) hold texts, not polygons, and a Region built from them is
empty whatever the labels say -- comparing them would be a check that
silently tests nothing.

No PDK, no KLayout application binary, no DRC deck: only the ``klayout.db``
pip wheel ``layout/tests`` already gates on, plus each generator's own pure
Python. So this runs in CI's headless job, which is the whole point -- the
drift above would have been caught at the commit that introduced it.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

LAYOUT_DIR = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = LAYOUT_DIR / "evidence"


@dataclass(frozen=True)
class Block:
    """One committed GDS and the generator that must reproduce it."""

    #: Path of the committed artifact, relative to ``layout/``.
    gds: str
    #: Importable module implementing the generator. Invoked as
    #: ``python3 -m <module> --outdir <dir>`` -- the same command every
    #: evidence directory's own PROOF.md documents, run as a subprocess so
    #: this checks the *documented* regeneration path rather than some
    #: in-process shortcut around it.
    module: str

    @property
    def committed(self) -> Path:
        return LAYOUT_DIR / self.gds

    @property
    def name(self) -> str:
        return Path(self.gds).name


#: Every committed block GDS under ``layout/evidence/``, with its generator.
#:
#: Deliberately explicit rather than discovered: a discovered list silently
#: shrinks when a generator is renamed, which is precisely the failure this
#: module exists to catch. ``layout/tests/test_gds_reproducibility.py``
#: asserts that this list covers every ``*.gds`` in the evidence tree except
#: the deliberate exclusions below, so adding a block without registering it
#: fails the suite.
BLOCKS: tuple[Block, ...] = (
    Block("evidence/vco-layout/vco_ring.gds", "pll_top.vco.ring"),
    Block("evidence/vco-layout/vco_block.gds", "pll_top.vco.block"),
    Block("evidence/vco-layout/vco_out_buffer.gds", "pll_top.vco.buffer"),
    Block("evidence/vco-layout/vco_bandsel_mirror.gds", "pll_top.vco.mirror"),
    Block("evidence/vco-layout/vco_vtoi_core.gds", "pll_top.vco.vtoi_core"),
    Block("evidence/vco-layout/vco_bias_resistors.gds", "pll_top.vco.bias_resistors"),
    Block("evidence/pfd-layout/pfd.gds", "pll_top.pfd_cp.pfd"),
    Block("evidence/pfd-cp-layout/pfd_cp.gds", "pll_top.pfd_cp.block"),
    Block("evidence/cp-block-layout/cp.gds", "pll_top.pfd_cp.cp"),
    Block("evidence/cp-array-proof/cp_array.gds", "pll_top.pfd_cp.cp_array"),
    Block("evidence/cp-dumpbuf-layout/cp_dumpbuf.gds", "pll_top.pfd_cp.cp_dumpbuf"),
    Block("evidence/cp-layout/cp_output_stage.gds", "pll_top.pfd_cp.cp_output_stage"),
    Block("evidence/cp-leg-proof/cp_leg_n.gds", "pll_top.pfd_cp.cp_leg_n"),
    Block("evidence/cp-leg-proof/cp_leg_p.gds", "pll_top.pfd_cp.cp_leg_p"),
    Block("evidence/pfdcp-inv-proof/pfdcp_inv_3v3.gds", "pll_top.pfd_cp.pfdcp_inv"),
    Block("evidence/divider-chain-layout/divider_chain.gds", "pll_top.divider_chain.divider_chain"),
    Block("evidence/divider-inv-proof/inv_3v3.gds", "pll_top.divider_chain.inv_3v3"),
    Block("evidence/divider-rowcells-proof/inv2x_3v3/inv2x_3v3.gds", "pll_top.divider_chain.inv2x_3v3"),
    Block("evidence/divider-rowcells-proof/nand2_3v3/nand2_3v3.gds", "pll_top.divider_chain.nand2_3v3"),
    Block("evidence/divider-rowcells-proof/nand3_3v3/nand3_3v3.gds", "pll_top.divider_chain.nand3_3v3"),
    Block("evidence/divider-rowcells-proof/nor2_3v3/nor2_3v3.gds", "pll_top.divider_chain.nor2_3v3"),
    Block("evidence/divider-tgate-proof/tgate_3v3.gds", "pll_top.divider_chain.tgate_3v3"),
    Block("evidence/divider-dff-proof/dff_tg_3v3.gds", "pll_top.divider_chain.dff_tg_3v3"),
    Block("evidence/divider-div23-proof/div23_cell.gds", "pll_top.divider_chain.div23_cell"),
    Block("evidence/lock-detector-layout/lock_detector.gds", "pll_top.lock_detector.build"),
    # Not a device block: the floorplan's block-placement skeleton (layer 0/0
    # boundary rectangles). Excluded by name through issue #451 -- its
    # committed file was six merges behind the plan and the module had no
    # ``--outdir`` CLI for ``rebuild()`` to call. Both fixed at issue #461;
    # see layout/evidence/floorplan-skeleton/PROOF.md.
    Block("evidence/floorplan-skeleton/pll_floorplan_skeleton.gds", "floorplan.skeleton"),
)

#: Committed GDS files this module deliberately does not check, each with the
#: reason. An exclusion is a stated liability, not a default: the test suite
#: asserts this mapping covers exactly the unregistered files, so a new
#: unchecked artifact cannot appear by omission.
EXCLUDED: dict[str, str] = {
    # Not generator output at all: the two deliberate negative controls
    # layout/harness/faults.py injects into a scratch copy of inv_tb, kept as
    # evidence that the flow can detect a dirty layout (run_pv.py prove).
    "evidence/inv-tb-proof/drc_fault.gds": "negative control, injected by harness/faults.py",
    "evidence/inv-tb-proof/lvs_fault.gds": "negative control, injected by harness/faults.py",
    # Assembled by harness/cell.py from the PDK's own standard-cell GDS, so
    # reproducing it needs a PDK -- which is exactly what this module is
    # built not to require. run_pv.py build covers it where a PDK exists.
    "evidence/inv-tb-proof/inv_tb.gds": "needs the PDK stdcell GDS (harness/cell.py), not pure Python",
}


def rebuild(block: Block, outdir: Path) -> Path:
    """Run ``block``'s generator into ``outdir`` and return the GDS it wrote.

    Raises ``RuntimeError`` if the generator fails or does not write a file
    named like the committed artifact -- both of which are themselves
    reproducibility failures worth failing a test over.
    """
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [sys.executable, "-m", block.module, "--outdir", str(outdir)],
        cwd=LAYOUT_DIR,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"{block.module} exited {proc.returncode}:\n{proc.stdout}\n{proc.stderr}")

    produced = sorted(outdir.rglob(block.name))
    if not produced:
        wrote = sorted(p.name for p in outdir.rglob("*.gds"))
        raise RuntimeError(f"{block.module} wrote no {block.name} (wrote {wrote})")
    return produced[0]


def _merged_regions(gds: Path, drawing_only: bool = True) -> dict[tuple[int, int], object]:
    """``{(layer, datatype): merged Region}`` for every layer in ``gds``."""
    import klayout.db as db

    layout = db.Layout()
    layout.read(str(gds))
    tops = list(layout.top_cells())
    if len(tops) != 1:
        raise RuntimeError(f"{gds} has {len(tops)} top cells, expected exactly 1")
    regions: dict[tuple[int, int], object] = {}
    for index in layout.layer_indexes():
        info = layout.get_info(index)
        if drawing_only and info.datatype != 0:
            continue
        region = db.Region(tops[0].begin_shapes_rec(index))
        region.merge()
        regions[(info.layer, info.datatype)] = region
    return regions


def layer_differences(committed: Path, rebuilt: Path, drawing_only: bool = True) -> dict[tuple[int, int], float]:
    """``{(layer, datatype): differing area in um^2}`` for every layer that differs.

    Empty means the two layouts are the same geometry. Compares merged
    ``Region`` XOR per layer, not bytes -- see this module's docstring for
    why a checksum cannot be used here.
    """
    import klayout.db as db

    a = _merged_regions(committed, drawing_only)
    b = _merged_regions(rebuilt, drawing_only)
    out: dict[tuple[int, int], float] = {}
    for key in sorted(set(a) | set(b)):
        xor = (a.get(key) or db.Region()) ^ (b.get(key) or db.Region())
        if not xor.is_empty():
            out[key] = xor.area() / 1e6  # dbu^2 (1 nm/dbu) -> um^2
    return out


def committed_gds_files() -> list[str]:
    """Every ``*.gds`` under ``layout/evidence/``, relative to ``layout/``."""
    return sorted(str(p.relative_to(LAYOUT_DIR)) for p in EVIDENCE_DIR.rglob("*.gds"))


def main() -> int:
    """Re-derive every registered block and report which ones drifted."""
    import tempfile

    failures = 0
    for block in BLOCKS:
        with tempfile.TemporaryDirectory() as tmp:
            try:
                rebuilt = rebuild(block, Path(tmp))
            except RuntimeError as exc:
                print(f"FAIL  {block.gds}: {exc}")
                failures += 1
                continue
            diffs = layer_differences(block.committed, rebuilt)
        if diffs:
            detail = ", ".join(f"{layer}/{dt}: {area:.3f} um^2" for (layer, dt), area in diffs.items())
            print(f"DRIFT {block.gds} ({block.module}) -- {detail}")
            failures += 1
        else:
            print(f"ok    {block.gds}")
    for path, why in sorted(EXCLUDED.items()):
        print(f"skip  {path} -- {why}")
    print(f"\n{len(BLOCKS) - failures}/{len(BLOCKS)} committed block GDS files reproduce from their generators")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
