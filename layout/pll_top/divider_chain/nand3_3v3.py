"""``nand3_3v3`` -- the 3-input static-CMOS NAND ``divider_chain`` leaf cell
(issue #307, Part 2 of #295).

Device sizes are read directly off ``design/nand3_3v3.sch`` (three
``pfet_03v3`` W=2.5u/L=0.28u in parallel over three ``nfet_03v3``
W=3u/L=0.28u in series, gates ``A``/``B``/``C``, output ``Y``,
sources/bodies tied to ``VDD``/``VSS``) -- not re-derived, the same
"schematic is the single source of truth" convention ``inv_3v3.py`` /
``tgate_3v3.py`` document. The NMOS stack is the schematic's own 3x width
(W=3u) so the three-high series pull-down still matches a 1x inverter's
drive, per that schematic's own text annotation.

This is the tallest and widest cell in the family, and it is what
``devgen``'s fixed row-cell frame is sized for: its three-high NMOS series
branch is the tallest pull-down (5.04 um) any of these four cells has, which
is what sets :data:`devgen.ROW_PU_Y0`. It also needs the most routing
tracks (``A``/``B``/``C``/``Y``, four) of any cell here.

Columns (left to right):

* **col 0** -- the whole three-high NMOS series branch (``MNC`` bottom,
  source ``VSS``; then ``MNB``; then ``MNA`` top, drain ``Y``; the two
  internal nodes are the schematic's own ``NM2``/``NM1``) with ``MPA`` above
  it in the pull-up row.
* **col 1** -- ``MPB``; **col 2** -- ``MPC``. Both pull-down rows empty.
"""

from __future__ import annotations

from pathlib import Path

from . import devgen

TOP_CELL = "nand3_3v3"

# design/nand3_3v3.sch's own MNA/MNB/MNC/MPA/MPB/MPC instances -- W/L only
# (nf=1, m=1 for all six). Branches are ordered bottom-to-top, so the NMOS
# branch reads MNC (source at VSS) -> MNB -> MNA (drain at Y).
COLUMNS = (
    devgen.Column(
        pulldown=(
            devgen.Device(name="MNC", kind="nfet", w_um=3.0, l_um=0.28, gate_net="C", top_net="NM2", bottom_net="VSS"),
            devgen.Device(name="MNB", kind="nfet", w_um=3.0, l_um=0.28, gate_net="B", top_net="NM1", bottom_net="NM2"),
            devgen.Device(name="MNA", kind="nfet", w_um=3.0, l_um=0.28, gate_net="A", top_net="Y", bottom_net="NM1"),
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
    devgen.Column(
        pullup=(
            devgen.Device(name="MPC", kind="pfet", w_um=2.5, l_um=0.28, gate_net="C", top_net="VDD", bottom_net="Y"),
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
    ``design/nand3_3v3.sch`` exactly; body terminals are tied to the rails,
    matching that schematic's own ``B=VDD``/``B=VSS`` instance parameters.
    """
    return (
        "* Reference schematic for nand3_3v3 (issue #307).\n"
        "*\n"
        "* Hand-written independently of the layout -- see\n"
        "* layout/harness/cell.py's docstring for why. Device sizes/nodes match\n"
        "* design/nand3_3v3.sch exactly.\n"
        "*\n"
        "* Run LVS with --lvs_sub=VSS (layout/run_pv.py's own default): the NMOS\n"
        "* body ties to the deck's synthesized global substrate net, which this\n"
        "* flag names VSS -- see layout/README.md's \"substrate-net gotcha\".\n"
        "\n"
        ".subckt nand3_3v3 A B C Y VDD VSS\n"
        "M_MPA Y A VDD VDD pfet_03v3 W=2.5u L=0.28u\n"
        "M_MPB Y B VDD VDD pfet_03v3 W=2.5u L=0.28u\n"
        "M_MPC Y C VDD VDD pfet_03v3 W=2.5u L=0.28u\n"
        "M_MNA Y A NM1 VSS nfet_03v3 W=3u L=0.28u\n"
        "M_MNB NM1 B NM2 VSS nfet_03v3 W=3u L=0.28u\n"
        "M_MNC NM2 C VSS VSS nfet_03v3 W=3u L=0.28u\n"
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
