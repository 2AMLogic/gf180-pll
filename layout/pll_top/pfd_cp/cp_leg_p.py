"""``cp_leg_p`` -- the charge pump's unit PMOS source leg (issue #319).

Device sizes/nets read directly off ``design/cp_leg_p.sch``: ``MEN``/
``MDIS`` (the enable-steering pair, W=1u/L=0.3u) + ``MTOP``/``MCASC`` (the
wide-swing cascode mirror, W=12u/L=1u -- 3x the NMOS unit so both polarities
run at a comparable overdrive at the same unit current, per that
schematic's own text annotation), all ``pfet_03v3``. Topology/wiring shared
with ``cp_leg_n`` via ``cp_leg.build_leg()`` -- see that module's docstring
for the full contract (the hand-routed ``BG`` 3-way net, the ``VDD`` rail
strap+tap).
"""

from __future__ import annotations

from pathlib import Path

from . import cp_leg

try:
    from .. import _cli
except ImportError:  # this package's own dir (not its "pll_top" parent) is the
    # sys.path root under layout/tests's flat-import convention -- see
    # devgen.py's own ``_canvas`` import for the full explanation.
    import _cli

TOP_CELL = "cp_leg_p"

SPEC = cp_leg.LegSpec(
    top_cell=TOP_CELL,
    kind="pfet",
    rail_net="VDD",
    bias_net="VBP",
    cascode_net="VCASCP",
    mdis_gate_net="EN",
    men_gate_net="ENB",
    mirror_bottom_name="MTOP",
    w_mirror_um=12.0,
    l_mirror_um=1.0,
    w_steer_um=1.0,
    l_steer_um=0.3,
)


def build(outdir: Path | None = None) -> cp_leg.LegLayout:
    return cp_leg.build(SPEC, outdir)


def reference_netlist() -> str:
    """Hand-written LVS reference netlist -- independently stated from the
    layout, per ``layout/harness/cell.py``'s own documented discipline (see
    that module's docstring). Device sizes/nodes match ``design/cp_leg_p.sch``
    exactly; boundary pin order matches that schematic's own ``P0``-``P5``
    declaration order (``VBP VCASCP EN ENB TAIL VDD``).
    """
    return (
        "* Reference schematic for cp_leg_p (issue #319).\n"
        "*\n"
        "* Hand-written independently of the layout -- see\n"
        "* layout/harness/cell.py's docstring for why. Device sizes/nodes match\n"
        "* design/cp_leg_p.sch exactly.\n"
        "*\n"
        "* The PMOS body's n-well tie is not a global connection in this deck\n"
        "* (unlike the NMOS substrate tie) -- devgen.py always draws and wires\n"
        "* a small n-well tap for it (see cp_leg.py's docstring's \"RAIL STRAP\n"
        "* + TAP\" section), so no --lvs-sub override is needed for this leg.\n"
        "\n"
        ".subckt cp_leg_p VBP VCASCP EN ENB TAIL VDD\n"
        "M_MEN BG ENB VBP VDD pfet_03v3 W=1u L=0.3u\n"
        "M_MDIS BG EN VDD VDD pfet_03v3 W=1u L=0.3u\n"
        "M_MTOP MID BG VDD VDD pfet_03v3 W=12u L=1u\n"
        "M_MCASC TAIL VCASCP MID VDD pfet_03v3 W=12u L=1u\n"
        ".ends\n"
    )


def main() -> int:
    return _cli.leaf_cli_main(build, TOP_CELL, reference_netlist, "cp-leg-proof", description=__doc__)


if __name__ == "__main__":
    raise SystemExit(main())
