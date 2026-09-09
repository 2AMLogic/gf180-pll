"""``nand2_3v3`` -- the 2-input static-CMOS NAND ``divider_chain`` leaf cell
(issue #307, Part 2 of #295).

Device sizes are read directly off ``design/nand2_3v3.sch`` (two
``pfet_03v3`` W=2.5u/L=0.28u in parallel over two ``nfet_03v3``
W=2u/L=0.28u in series, gates ``A``/``B``, output ``Y``, sources/bodies tied
to ``VDD``/``VSS``) -- not re-derived, the same "schematic is the single
source of truth for what the layout draws" convention ``inv_3v3.py`` /
``tgate_3v3.py`` document. The NMOS stack is the schematic's own 2x width
(W=2u vs. ``inv_3v3``'s W=1u) so the two-high series pull-down still matches
a 1x inverter's drive, per that schematic's own text annotation.

This is the first ``divider_chain`` cell with real fan-in: ``Y`` lands on
three device terminals (the NMOS stack's top drain plus each parallel PMOS
drain) and ``VDD`` on two, which ``devgen.build_stack_cell()`` refuses by
design. It is drawn with ``devgen.build_row_cell()`` instead -- see that
module's "ROW CELLS" section for the column/row placement model and the
Metal1-strap/Metal2-track routing model.

Columns (left to right):

* **col 0** -- the whole NMOS series branch (``MNB`` bottom, source ``VSS``;
  ``MNA`` top, drain ``Y``; their shared internal node is the schematic's
  own ``NMID``) with ``MPA`` above it in the pull-up row.
* **col 1** -- ``MPB``, the second parallel pull-up branch; pull-down row
  empty.

Neither PMOS needs a ``Device.body_net`` override: each one's own
supply-facing terminal (``top_net=VDD``) already *is* the net its body ties
to, the same case ``inv_3v3.py`` documents.
"""

from __future__ import annotations

from pathlib import Path

from . import devgen

TOP_CELL = "nand2_3v3"

# design/nand2_3v3.sch's own MNA/MNB/MPA/MPB instances -- W/L only (nf=1,
# m=1 for all four). Branches are ordered bottom-to-top, so the NMOS branch
# reads MNB (source at VSS) then MNA (drain at Y).
COLUMNS = (
    devgen.Column(
        pulldown=(
            devgen.Device(name="MNB", kind="nfet", w_um=2.0, l_um=0.28, gate_net="B", top_net="NMID", bottom_net="VSS"),
            devgen.Device(name="MNA", kind="nfet", w_um=2.0, l_um=0.28, gate_net="A", top_net="Y", bottom_net="NMID"),
        ),
        pullup=(
            devgen.Device(name="MPA", kind="pfet", w_um=2.5, l_um=0.28, gate_net="A", top_net="VDD", bottom_net="Y"),
        ),
    ),
    devgen.Column(
        pullup=(
            devgen.Device(name="MPB", kind="pfet", w_um=2.5, l_um=0.28, gate_net="B", top_net="VDD", bottom_net="Y"),
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
    ``design/nand2_3v3.sch`` exactly; body terminals are tied to the rails,
    matching that schematic's own ``B=VDD``/``B=VSS`` instance parameters.
    """
    return (
        "* Reference schematic for nand2_3v3 (issue #307).\n"
        "*\n"
        "* Hand-written independently of the layout -- see\n"
        "* layout/harness/cell.py's docstring for why. Device sizes/nodes match\n"
        "* design/nand2_3v3.sch exactly.\n"
        "*\n"
        "* Run LVS with --lvs_sub=VSS (layout/run_pv.py's own default): the NMOS\n"
        "* body ties to the deck's synthesized global substrate net, which this\n"
        "* flag names VSS -- see layout/README.md's \"substrate-net gotcha\".\n"
        "\n"
        ".subckt nand2_3v3 A B Y VDD VSS\n"
        "M_MPA Y A VDD VDD pfet_03v3 W=2.5u L=0.28u\n"
        "M_MPB Y B VDD VDD pfet_03v3 W=2.5u L=0.28u\n"
        "M_MNA Y A NMID VSS nfet_03v3 W=2u L=0.28u\n"
        "M_MNB NMID B VSS VSS nfet_03v3 W=2u L=0.28u\n"
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
