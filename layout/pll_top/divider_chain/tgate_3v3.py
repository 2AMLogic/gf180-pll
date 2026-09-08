"""``tgate_3v3`` -- the complementary transmission-gate representative
``divider_chain`` leaf cell (issue #306, Part 1 of #295).

Device sizes are read directly off ``design/tgate_3v3.sch`` (one
``pfet_03v3`` W=2.5u/L=0.28u + one ``nfet_03v3`` W=1u/L=0.28u pass devices,
independent gates ``GN``/``GP``, shared ``A``/``Y`` diffusion terminals,
bodies tied to ``VDD``/``VSS``) -- not re-derived, the same
"schematic is the single source of truth" convention ``inv_3v3.py`` (this
cell's sibling) documents. Conducts when ``GN=1``/``GP=0``; used for the
master-slave latch pairs of ``dff_tg_3v3`` (Part 3, #308) per
``design/tgate_3v3.sch``'s own text annotation.

Neither ``top_net`` nor ``bottom_net`` is a supply net here (both are the
signal nets ``Y``/``A``) -- unlike ``inv_3v3``, each device sets an explicit
``body_net`` (``VDD`` for ``MP``, ``VSS`` for ``MN``) so ``devgen.py``'s
n-well/p-substrate tap wires to the correct body net instead of shorting it
onto ``Y``/``A``. See ``devgen.py``'s module docstring
("TRANSMISSION-GATE TOPOLOGY") for the full derivation of why this one field
was needed and why ``build_stack_cell()``'s own net-resolution logic (the
part that wires/promotes ``A``/``Y``/``GN``/``GP``) needed no change at all.
"""

from __future__ import annotations

from pathlib import Path

from . import devgen

TOP_CELL = "tgate_3v3"

# design/tgate_3v3.sch's own MP/MN instances -- W/L only (nf=1, m=1 for
# both). top_net/bottom_net are the shared A/Y diffusion terminals; gate_net
# is independent per device (GP/GN); body_net is explicit (see module
# docstring) since neither pass device's own diffusion terminal is a supply
# net.
#
# Net assignment matters here, not just which two net names are used:
# MN.top_net and MP.bottom_net are the *facing* pair (MP is stacked directly
# above MN), so they must share a net ("Y") for devgen.py's default
# facing-pads connector to wire them with a short, safe run. MN.bottom_net
# and MP.top_net are then the stack's two *outer* pads (the very bottom and
# the very top of the whole column) sharing the other net ("A") -- these
# need build_stack_cell()'s bypass_nets router (see build()) instead, since
# a direct straight-line connect between them would run through the Y
# connector and the intervening gates.
TGATE_DEVICES = (
    devgen.Device(
        name="MN", kind="nfet", w_um=1.0, l_um=0.28,
        gate_net="GN", top_net="Y", bottom_net="A", body_net="VSS",
    ),
    devgen.Device(
        name="MP", kind="pfet", w_um=2.5, l_um=0.28,
        gate_net="GP", top_net="A", bottom_net="Y", body_net="VDD",
    ),
)


def build(outdir: Path | None = None) -> devgen.LeafCell:
    # "A" is the stack's two *outer* (non-facing) terminals -- MN's
    # bottom_pad and MP's top_pad -- so it needs devgen.py's bypass-lane
    # router, not the default facing-pads connector; see devgen.py's
    # "TRANSMISSION-GATE TOPOLOGY" docstring section for the concrete LVS
    # mismatch this was caught by before this argument was added.
    leaf = devgen.build_stack_cell(TOP_CELL, TGATE_DEVICES, bypass_nets=frozenset({"A"}))
    if outdir is not None:
        outdir = Path(outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        leaf.write_gds(outdir / f"{TOP_CELL}.gds")
    return leaf


def reference_netlist() -> str:
    """Hand-written LVS reference netlist -- independently stated from the
    layout, per ``layout/harness/cell.py``'s own documented discipline (see
    that module's docstring). Device sizes match ``design/tgate_3v3.sch``
    exactly; body terminals are tied to the rails, matching the schematic's
    own ``B=VDD``/``B=VSS`` instance parameters. Written drain-gate-source-
    body per device (a MOSFET's D/S are symmetric under gf180mcu's own
    extraction, so LVS matches by graph topology, not by which terminal is
    labelled D vs. S here).
    """
    return (
        "* Reference schematic for tgate_3v3 (issue #306).\n"
        "*\n"
        "* Hand-written independently of the layout -- see\n"
        "* layout/harness/cell.py's docstring for why. Device sizes/nodes match\n"
        "* design/tgate_3v3.sch exactly.\n"
        "*\n"
        "* Run LVS with --lvs_sub=VSS (layout/run_pv.py's own default): the NMOS\n"
        "* body ties to the deck's synthesized global substrate net, which this\n"
        "* flag names VSS -- see layout/README.md's \"substrate-net gotcha\".\n"
        "\n"
        ".subckt tgate_3v3 A Y GN GP VDD VSS\n"
        "M_MP Y GP A VDD pfet_03v3 W=2.5u L=0.28u\n"
        "M_MN Y GN A VSS nfet_03v3 W=1u L=0.28u\n"
        ".ends\n"
    )


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    default_outdir = Path(__file__).resolve().parents[2] / "evidence" / "divider-tgate-proof" / "work"
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
