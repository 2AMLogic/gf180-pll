"""``pfdcp_inv_3v3`` -- the representative PFD/CP leaf cell (issue #299).

Device sizes are read directly off ``design/pfdcp_inv_3v3.sch`` (one
``pfet_03v3`` W=1.5u/L=0.3u + one ``nfet_03v3`` W=0.5u/L=0.3u, gates and
drains tied to ``A``/``Y``, per that schematic's own text annotation) -- not
re-derived, the same "schematic is the single source of truth for what the
layout draws" convention ``vco/devices.py`` documents for the VCO block.

Stack order (bottom to top): ``MN`` (nfet, source=``VSS``) then ``MP``
(pfet, source=``VDD``) -- see ``devgen.py``'s module docstring for why a
static inverter is exactly the two-device vertical-stack topology
``build_stack_cell()`` supports directly.
"""

from __future__ import annotations

from pathlib import Path

from . import devgen

TOP_CELL = "pfdcp_inv_3v3"

# design/pfdcp_inv_3v3.sch's own MP/MN instances -- W/L only (nf=1 for both).
INV_DEVICES = (
    devgen.Device(name="MN", kind="nfet", w_um=0.5, l_um=0.3, gate_net="A", top_net="Y", bottom_net="VSS"),
    devgen.Device(name="MP", kind="pfet", w_um=1.5, l_um=0.3, gate_net="A", top_net="VDD", bottom_net="Y"),
)


def build(outdir: Path | None = None) -> devgen.LeafCell:
    leaf = devgen.build_stack_cell(TOP_CELL, INV_DEVICES)
    if outdir is not None:
        outdir = Path(outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        leaf.write_gds(outdir / f"{TOP_CELL}.gds")
    return leaf


def reference_netlist() -> str:
    """Hand-written LVS reference netlist -- independently stated from the
    layout, per ``layout/harness/cell.py``'s own documented discipline (see
    that module's docstring). Device sizes match ``design/pfdcp_inv_3v3.sch``
    exactly; body terminals are tied to the rails, matching the schematic's
    own ``B=VDD``/``B=VSS`` instance parameters.
    """
    return (
        "* Reference schematic for pfdcp_inv_3v3 (issue #299).\n"
        "*\n"
        "* Hand-written independently of the layout -- see\n"
        "* layout/harness/cell.py's docstring for why. Device sizes/nodes match\n"
        "* design/pfdcp_inv_3v3.sch exactly.\n"
        "*\n"
        "* Run LVS with --lvs_sub=VSS (layout/run_pv.py's own default): the NMOS\n"
        "* body ties to the deck's synthesized global substrate net, which this\n"
        "* flag names VSS -- see layout/README.md's \"substrate-net gotcha\".\n"
        "\n"
        ".subckt pfdcp_inv_3v3 A Y VDD VSS\n"
        "M_MP Y A VDD VDD pfet_03v3 W=1.5u L=0.3u\n"
        "M_MN Y A VSS VSS nfet_03v3 W=0.5u L=0.3u\n"
        ".ends\n"
    )


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    default_outdir = Path(__file__).resolve().parents[2] / "evidence" / "pfdcp-inv-proof" / "work"
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
