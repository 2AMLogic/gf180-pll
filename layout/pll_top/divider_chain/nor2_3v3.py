"""``nor2_3v3`` -- the 2-input static-CMOS NOR ``divider_chain`` leaf cell
(issue #307, Part 2 of #295).

Device sizes are read directly off ``design/nor2_3v3.sch`` (two
``pfet_03v3`` W=5u/L=0.28u in *series* over two ``nfet_03v3`` W=1u/L=0.28u
in *parallel*, gates ``A``/``B``, output ``Y``, sources/bodies tied to
``VDD``/``VSS``) -- not re-derived, the same "schematic is the single source
of truth" convention ``inv_3v3.py``/``tgate_3v3.py`` document. The PMOS
stack is the schematic's own 2x width (W=5u vs. ``inv_3v3``'s W=2.5u) so
the two-high series pull-up still matches a 1x inverter's drive, per that
schematic's own text annotation.

This is the family's mirror-image case: it is the only cell here whose
*pull-up* network is the series stack and whose *pull-down* network is the
one with fan-in, so it exercises ``devgen.build_row_cell()``'s pullup-side
series wiring and multi-branch pulldown placement that the NAND cells never
touch. Its two-high PMOS branch is the tallest pull-up (topping out at 13.16
um) in this family, which is what sets :data:`devgen.ROW_NTAP_Y0`.

Columns (left to right):

* **col 0** -- ``MNA`` (pull-down, source ``VSS``, drain ``Y``) with the
  whole PMOS series branch above it: ``MPB`` bottom (drain ``Y``) then
  ``MPA`` top (source ``VDD``); their shared internal node is the
  schematic's own ``PMID``.
* **col 1** -- ``MNB``, the second parallel pull-down branch; pull-up row
  empty.

Both PMOS devices keep the ``Device.body_net`` default: ``MPA``'s own
supply-facing terminal already *is* ``VDD``, and ``MPB``'s body ties through
the shared n-well the whole pull-up row sits in (``build_row_cell()`` draws
exactly one n-well tap per cell, on the ``VDD`` rail -- see that function's
docstring).
"""

from __future__ import annotations

from pathlib import Path

from . import devgen

TOP_CELL = "nor2_3v3"

# design/nor2_3v3.sch's own MNA/MNB/MPA/MPB instances -- W/L only (nf=1, m=1
# for all four). Branches are ordered bottom-to-top, so the PMOS series
# branch reads MPB (drain at Y, nearest the inter-row channel) then MPA
# (source at VDD, nearest the rail).
COLUMNS = (
    devgen.Column(
        pulldown=(
            devgen.Device(name="MNA", kind="nfet", w_um=1.0, l_um=0.28, gate_net="A", top_net="Y", bottom_net="VSS"),
        ),
        pullup=(
            devgen.Device(name="MPB", kind="pfet", w_um=5.0, l_um=0.28, gate_net="B", top_net="PMID", bottom_net="Y"),
            devgen.Device(name="MPA", kind="pfet", w_um=5.0, l_um=0.28, gate_net="A", top_net="VDD", bottom_net="PMID"),
        ),
    ),
    devgen.Column(
        pulldown=(
            devgen.Device(name="MNB", kind="nfet", w_um=1.0, l_um=0.28, gate_net="B", top_net="Y", bottom_net="VSS"),
        ),
    ),
)


def build(outdir: Path | None = None) -> devgen.LeafCell:
    leaf = devgen.build_row_cell(TOP_CELL, COLUMNS)
    if outdir is not None:
        outdir = Path(outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        leaf.write_gds(outdir / f"{TOP_CELL}.gds")
    return leaf


def reference_netlist() -> str:
    """Hand-written LVS reference netlist -- stated independently of the
    layout, per ``layout/harness/cell.py``'s own documented discipline (see
    that module's docstring). Device sizes/nodes match
    ``design/nor2_3v3.sch`` exactly; body terminals are tied to the rails,
    matching that schematic's own ``B=VDD``/``B=VSS`` instance parameters.
    """
    return (
        "* Reference schematic for nor2_3v3 (issue #307).\n"
        "*\n"
        "* Hand-written independently of the layout -- see\n"
        "* layout/harness/cell.py's docstring for why. Device sizes/nodes match\n"
        "* design/nor2_3v3.sch exactly.\n"
        "*\n"
        "* Run LVS with --lvs_sub=VSS (layout/run_pv.py's own default): the NMOS\n"
        "* body ties to the deck's synthesized global substrate net, which this\n"
        "* flag names VSS -- see layout/README.md's \"substrate-net gotcha\".\n"
        "\n"
        ".subckt nor2_3v3 A B Y VDD VSS\n"
        "M_MPA PMID A VDD VDD pfet_03v3 W=5u L=0.28u\n"
        "M_MPB Y B PMID VDD pfet_03v3 W=5u L=0.28u\n"
        "M_MNA Y A VSS VSS nfet_03v3 W=1u L=0.28u\n"
        "M_MNB Y B VSS VSS nfet_03v3 W=1u L=0.28u\n"
        ".ends\n"
    )


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    default_outdir = Path(__file__).resolve().parents[2] / "evidence" / "divider-rowcells-proof" / "work"
    parser.add_argument("--outdir", default=str(default_outdir))
    args = parser.parse_args()
    outdir = Path(args.outdir)
    leaf = build(outdir)
    netlist_path = outdir / f"{TOP_CELL}.spice"
    netlist_path.write_text(reference_netlist())
    x0, y0, x1, y1 = leaf.footprint
    print(f"wrote {outdir}/{TOP_CELL}.gds")
    print(f"wrote {netlist_path}")
    print(f"footprint: {x1 - x0:.3f} x {y1 - y0:.3f} um  ({(x1 - x0) * (y1 - y0):.2f} um^2)")
    print(f"pins: {sorted(leaf.pins)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
