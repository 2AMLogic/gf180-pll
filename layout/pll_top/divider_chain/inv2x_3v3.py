"""``inv2x_3v3`` -- the 2x-strength static-CMOS inverter ``divider_chain``
leaf cell (issue #307, Part 2 of #295).

Device sizes are read directly off ``design/inv2x_3v3.sch`` (one
``pfet_03v3`` W=5u/L=0.28u + one ``nfet_03v3`` W=2u/L=0.28u, gates tied to
``A``, drains tied to ``Y``, sources/bodies tied to ``VDD``/``VSS``) -- not
re-derived, the same "schematic is the single source of truth" convention
``inv_3v3.py`` documents. Used as ``div23_cell``'s clock-output buffer, per
that schematic's own text annotation.

**Only the device widths differ from issue #306's ``inv_3v3``** -- exactly
2x on both devices (5u vs. 2.5u, 2u vs. 1u), same gate length, same two
devices, same nets on the same terminals. It is not a topology change, and
``layout/tests/test_divider_rowcells.py`` asserts that device-table
relationship directly against ``inv_3v3.INV_DEVICES``.

The *layout* does differ, deliberately: ``inv_3v3`` is drawn by
``devgen.build_stack_cell()`` as a single vertical column whose height
follows its own device list, whereas this cell is drawn by
``devgen.build_row_cell()`` as a one-column row cell, so that it shares the
fixed row-cell frame (identical height, identical ``VDD``/``VSS`` rail
y-bands) with ``nand2_3v3``/``nand3_3v3``/``nor2_3v3`` and can abut them in
a row. Expressed as a row cell, the schematic maps onto a single column with
a one-device pull-down branch and a one-device pull-up branch -- the
degenerate, no-fan-in case of ``build_row_cell()``'s model, which is
precisely why it is also the cell that pins down that the frame does not
depend on a cell having fan-in at all.
"""

from __future__ import annotations

from pathlib import Path

from . import devgen

TOP_CELL = "inv2x_3v3"

# design/inv2x_3v3.sch's own MP/MN instances -- W/L only (nf=1, m=1 for
# both). Same three-net assignment as inv_3v3.INV_DEVICES (gate A, drain Y,
# source VDD/VSS); only w_um differs, by exactly 2x on each device.
COLUMNS = (
    devgen.Column(
        pulldown=(
            devgen.Device(name="MN", kind="nfet", w_um=2.0, l_um=0.28, gate_net="A", top_net="Y", bottom_net="VSS"),
        ),
        pullup=(
            devgen.Device(name="MP", kind="pfet", w_um=5.0, l_um=0.28, gate_net="A", top_net="VDD", bottom_net="Y"),
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
    ``design/inv2x_3v3.sch`` exactly; body terminals are tied to the rails,
    matching that schematic's own ``B=VDD``/``B=VSS`` instance parameters.
    """
    return (
        "* Reference schematic for inv2x_3v3 (issue #307).\n"
        "*\n"
        "* Hand-written independently of the layout -- see\n"
        "* layout/harness/cell.py's docstring for why. Device sizes/nodes match\n"
        "* design/inv2x_3v3.sch exactly.\n"
        "*\n"
        "* Run LVS with --lvs_sub=VSS (layout/run_pv.py's own default): the NMOS\n"
        "* body ties to the deck's synthesized global substrate net, which this\n"
        "* flag names VSS -- see layout/README.md's \"substrate-net gotcha\".\n"
        "\n"
        ".subckt inv2x_3v3 A Y VDD VSS\n"
        "M_MP Y A VDD VDD pfet_03v3 W=5u L=0.28u\n"
        "M_MN Y A VSS VSS nfet_03v3 W=2u L=0.28u\n"
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
