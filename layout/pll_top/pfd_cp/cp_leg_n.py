"""``cp_leg_n`` -- the charge pump's unit NMOS sink leg (issue #319).

Device sizes/nets read directly off ``design/cp_leg_n.sch``: ``MEN``/
``MDIS`` (the enable-steering pair, W=1u/L=0.3u) + ``MBOT``/``MCASC`` (the
wide-swing cascode mirror, W=4u/L=1u), all ``nfet_03v3``. Topology/wiring
shared with ``cp_leg_p`` via ``cp_leg.build_leg()`` -- see that module's
docstring for the full contract (the hand-routed ``BG`` 3-way net, the
``VSS`` rail strap+tap).
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

TOP_CELL = "cp_leg_n"

SPEC = cp_leg.LegSpec(
    top_cell=TOP_CELL,
    kind="nfet",
    rail_net="VSS",
    bias_net="VBN",
    cascode_net="VCASCN",
    mdis_gate_net="ENB",
    men_gate_net="EN",
    mirror_bottom_name="MBOT",
    w_mirror_um=4.0,
    l_mirror_um=1.0,
    w_steer_um=1.0,
    l_steer_um=0.3,
)


def build(outdir: Path | None = None) -> cp_leg.LegLayout:
    return cp_leg.build(SPEC, outdir)


def reference_netlist() -> str:
    """Hand-written LVS reference netlist -- independently stated from the
    layout, per ``layout/harness/cell.py``'s own documented discipline (see
    that module's docstring). Device sizes/nodes match ``design/cp_leg_n.sch``
    exactly; boundary pin order matches that schematic's own ``P0``-``P5``
    declaration order (``VBN VCASCN EN ENB TAIL VSS``).
    """
    return (
        "* Reference schematic for cp_leg_n (issue #319).\n"
        "*\n"
        "* Hand-written independently of the layout -- see\n"
        "* layout/harness/cell.py's docstring for why. Device sizes/nodes match\n"
        "* design/cp_leg_n.sch exactly.\n"
        "*\n"
        "* Run LVS with --lvs_sub=VSS (layout/run_pv.py's own default): the NMOS\n"
        "* body ties to the deck's synthesized global substrate net, which this\n"
        "* flag names VSS -- see layout/README.md's \"substrate-net gotcha\".\n"
        "\n"
        ".subckt cp_leg_n VBN VCASCN EN ENB TAIL VSS\n"
        "M_MEN BG EN VBN VSS nfet_03v3 W=1u L=0.3u\n"
        "M_MDIS BG ENB VSS VSS nfet_03v3 W=1u L=0.3u\n"
        "M_MBOT MID BG VSS VSS nfet_03v3 W=4u L=1u\n"
        "M_MCASC TAIL VCASCN MID VSS nfet_03v3 W=4u L=1u\n"
        ".ends\n"
    )


def main() -> int:
    return _cli.leaf_cli_main(build, TOP_CELL, reference_netlist, "cp-leg-proof", description=__doc__)


if __name__ == "__main__":
    raise SystemExit(main())
