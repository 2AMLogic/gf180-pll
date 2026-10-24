#!/usr/bin/env python3
"""Bounded `pll_top` area-feasibility sweep (issue #792).

Re-runs the real top-level assembly (``pll_top.top_level.assemble``) with the
two cost terms ``PLL-FLOORPLAN.md`` section 5.16 names changed in isolation and
then together, and records for each case the assembled bounding box, the
top-level connectivity verdict (``netcheck``) and the foundry DRC verdict. It
changes no default: every lever is applied by overriding a module constant for
the duration of one case.

Levers
------
``spacing``  the gap between neighbouring blocks (``assemble.DOMAIN_SPACING_UM``,
             a planning value from ``floorplan/skeleton.py``, not a foundry rule),
             or, with ``gaps``, each gap on its own (``assemble.GAP_OVERRIDES_UM``)
``guard``    the VCO keep-out (``assemble.VCO_GUARD_MARGIN_UM`` and, so the
             checker agrees with the drawing, ``netcheck.VCO_GUARD_MARGIN_UM``)
``fold``     the divider chain re-folded into ``k`` stacked bands

The fold is an AREA PROBE, not a layout: the committed divider GDS is cut into
``k`` equal-width vertical slabs that are stacked ``FOLD_GAP_UM`` apart, with
labels carried along. Devices and wires that straddle a cut are severed, so the
folded block is electrically meaningless (the netcheck verdict of a folded case
is reported but says nothing about a real re-fold). What it does measure is
what the assembler does with a block of that outline: where the middle channel
goes, whether the ports remain reachable, and the resulting bounding box.

    cd layout && python3 -m harness.area_feasibility --outdir /tmp/area-study \
        --drc --report /tmp/area-study/results.json

Needs the ``klayout`` Python wheel (assembly) and, with ``--drc``, the PDK and
a PV python as ``run_pv.py check-env`` describes.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

LAYOUT_DIR = Path(__file__).resolve().parents[1]
if str(LAYOUT_DIR) not in sys.path:
    sys.path.insert(0, str(LAYOUT_DIR))

from pll_top.top_level import assemble as asm_mod  # noqa: E402
from pll_top.top_level import netcheck  # noqa: E402

FOLD_GAP_UM = 3.0  # divider_chain.ROW_GAP_Y_UM, the gap between its own cell rows
BASELINE_SPACING_UM = 40.0
BASELINE_GUARD_UM = 15.0
ROW_UM2 = 300_000.0  # the ratified <= 0.30 mm^2 row


@dataclass(frozen=True)
class Case:
    name: str
    spacing: float = BASELINE_SPACING_UM
    guard: float = BASELINE_GUARD_UM
    fold: int = 1
    gaps: tuple = ()  # ((gap key, um), ...) -> assemble.GAP_OVERRIDES_UM

    @property
    def is_baseline(self) -> bool:
        return (self.spacing, self.guard, self.fold, self.gaps) == (BASELINE_SPACING_UM, BASELINE_GUARD_UM, 1, ())


@contextlib.contextmanager
def _levers(case: Case):
    saved = (asm_mod.DOMAIN_SPACING_UM, asm_mod.VCO_GUARD_MARGIN_UM, netcheck.VCO_GUARD_MARGIN_UM)
    asm_mod.GAP_OVERRIDES_UM.clear()
    asm_mod.GAP_OVERRIDES_UM.update(dict(case.gaps))
    asm_mod.DOMAIN_SPACING_UM = case.spacing
    asm_mod.VCO_GUARD_MARGIN_UM = case.guard
    netcheck.VCO_GUARD_MARGIN_UM = case.guard
    try:
        yield
    finally:
        asm_mod.GAP_OVERRIDES_UM.clear()
        asm_mod.DOMAIN_SPACING_UM, asm_mod.VCO_GUARD_MARGIN_UM, netcheck.VCO_GUARD_MARGIN_UM = saved


def fold_gds(src: Path, dst: Path, k: int) -> tuple[float, float]:
    """Cut ``src`` into ``k`` vertical slabs and stack them; returns (w, h) um."""
    db = asm_mod.db()
    ly = db.Layout()
    ly.read(str(src))
    top = ly.top_cell()
    bb = top.bbox()
    dbu = ly.dbu
    width, height = bb.width(), bb.height()
    slab = -(-width // k)  # ceil
    gap = int(round(FOLD_GAP_UM / dbu))
    out = db.Layout()
    out.dbu = dbu
    ocell = out.create_cell(top.name)
    for li in ly.layer_indexes():
        info = ly.get_info(li)
        oli = out.layer(info)
        full = db.Region(top.begin_shapes_rec(li))
        for i in range(k):
            x0 = bb.left + i * slab
            clip = db.Region(db.Box(x0, bb.bottom, min(x0 + slab, bb.right), bb.top))
            piece = (full & clip).moved(-i * slab, i * (height + gap))
            ocell.shapes(oli).insert(piece)
        for sh in top.shapes(li).each():
            if sh.is_text():
                t = sh.text
                i = min(max((t.x - bb.left) // slab, 0), k - 1)
                ocell.shapes(oli).insert(db.Text(t.string, t.x - i * slab, t.y + i * (height + gap)))
    out.write(str(dst))
    return (slab * dbu, (k * height + (k - 1) * gap) * dbu)


def run_case(case: Case, blocks: dict[str, Path], workdir: Path, *, drc: bool) -> dict:
    res: dict = {"case": case.name, "spacing_um": case.spacing, "guard_um": case.guard, "fold": case.fold,
                "gaps_um": dict(case.gaps)}
    outdir = workdir / case.name
    use = dict(blocks)
    if case.fold > 1:
        folded = workdir / f"divider_chain_fold{case.fold}.gds"
        w, h = fold_gds(blocks["divider_chain"], folded, case.fold)
        res["divider_outline_um"] = [round(w, 2), round(h, 2)]
        use["divider_chain"] = folded
    with _levers(case):
        try:
            asm = asm_mod.assemble(use)
            asm_mod.write(asm, outdir)
        except Exception as exc:  # noqa: BLE001 -- report the refusal, do not hide it
            res.update(status="unroutable", reason=f"{type(exc).__name__}: {exc}")
            return res
        x0, y0, x1, y1 = asm.boundary
        res.update(
            status="assembled",
            width_um=round(x1 - x0, 2),
            height_um=round(y1 - y0, 2),
            area_um2=round(asm.report["area_um2"], 1),
            area_mm2=round(asm.report["area_um2"] / 1e6, 4),
            block_sum_um2=round(asm.report["block_sum_um2"], 1),
            meets_row=asm.report["area_um2"] <= ROW_UM2,
        )
        rep = netcheck.check(asm.gds)
        res["netcheck_ok"] = bool(rep.ok)
        res["netcheck"] = rep.summary().splitlines()[0]
    if drc:
        from harness import drc as drc_mod  # noqa: PLC0415

        r = drc_mod.run(outdir / asm_mod.GDS_NAME, asm_mod.TOP_CELL, outdir / "drc", offgrid=True)
        res["drc_status"] = r.status
        res["drc_rules"] = dict(sorted(r.rule_counts.items()))
        res["drc_new_vs_baseline_rules"] = sorted(set(r.rule_counts) - {"MIMTM.3"})
    return res


PAD_GAP_UM = 36.0  # the lock_detector | pfd_cp gap must hold the six supply pad slots (assemble.py: 34 um)


def _gaps(horizontal: float, vertical: float | None = None) -> tuple:
    """The lock_detector | pfd_cp gap stays at ``PAD_GAP_UM``; the other two row gaps (and,
    with ``vertical``, the row-to-divider gap) move."""
    g = [("pfd_cp", horizontal), ("loop_filter", horizontal), ("lock_detector", PAD_GAP_UM)]
    if vertical is not None:
        g.append(("divider_chain", vertical))
    return tuple(g)


def default_cases() -> list[Case]:
    cases = [Case("baseline")]
    # lever (b), isolated: the uniform spacing (refused by the assembler below ~34 um), the
    # two spacings the pad slots do not constrain, the row-to-divider gap, and the keep-out
    cases += [Case(f"spacing-{s:g}", spacing=s) for s in (30, 20, 10, 2)]
    cases += [Case(f"hgap-{h:g}", gaps=_gaps(h)) for h in (40, 20, 10, 5, 3, 2, 1, 0.5, 0)]
    cases += [Case(f"vgap-{v:g}", gaps=(("divider_chain", v),)) for v in (30, 20, 10, 5, 2, 0)]
    cases += [Case(f"vgap-{v:g}-g0", gaps=(("divider_chain", v),), guard=0) for v in (18, 16, 14, 12, 11, 10, 9, 8, 6, 4)]
    cases += [Case(f"guard-{g:g}", guard=g) for g in (10, 5, 2, 0)]
    # lever (a), isolated: the divider folded into k bands (an area probe, see the docstring)
    cases += [Case(f"fold-{k}", fold=k) for k in (2, 3)]
    return cases


def combined_cases(h: float, v: float, guard: float) -> list[Case]:
    """Lever (b) at its measured floor, alone and with each fold."""
    g = _gaps(h, v)
    return [Case(f"floor-b", gaps=g, guard=guard)] + [
        Case(f"floor-b-fold{k}", gaps=g, guard=guard, fold=k) for k in (2, 3)
    ]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--report", help="write the results as JSON")
    ap.add_argument("--drc", action="store_true", help="also run the foundry DRC deck on each assembled case")
    ap.add_argument("--case", action="append", help="run only the named case(s)")
    ap.add_argument("--floor", nargs=3, type=float, metavar=("H", "V", "GUARD"),
                    help="also run the combined cases with horizontal gap H, row-to-divider gap V and keep-out GUARD (um)")
    args = ap.parse_args(argv)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    cases = default_cases()
    if args.floor:
        cases += combined_cases(*args.floor)
    if args.case:
        cases = [c for c in cases if c.name in set(args.case)]
    results = []
    with tempfile.TemporaryDirectory() as tmp:
        blocks = asm_mod.generate_blocks(Path(tmp))
        for case in cases:
            r = run_case(case, blocks, outdir, drc=args.drc)
            results.append(r)
            print(json.dumps(r, sort_keys=True), flush=True)
    if args.report:
        Path(args.report).write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
