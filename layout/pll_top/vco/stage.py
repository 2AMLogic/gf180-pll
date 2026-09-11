"""One ``vco_stage.sch`` instance: MPH-MP-MN-MNT, drawn as a vertical stack.

See ``primitives.py``'s module docstring for the "vertical current flow,
separate diffusion per device, Metal1 jumpers between them" convention this
follows, and ``devices.py`` for where the four devices' W/L/node data comes
from.

Bottom-to-top device order matches the schematic's own current-starved
chain (``GND_VCO`` -> ``MNT`` -> ``NT`` -> ``MN`` -> ``Y`` -> ``MP`` -> ``NH``
-> ``MPH`` -> ``VDD_VCO``), split into two bands with a routing gap between
them wide enough to satisfy DF.16_LV (nwell edge to NMOS comp outside it,
0.43 um min -- ``NWELL_TO_NMOS_GAP_UM`` in ``primitives.py`` uses 2.0 um):

* NMOS band (substrate): ``MNT`` then ``MN``.
* PMOS band (n-well, drawn by the caller -- ``ring.py`` -- around every
  stage's PMOS devices at once): ``MP`` then ``MPH``.

The ``A`` net (both switch gates) is wired as a single vertical Metal1 run
at the column's gate-contact-tab x -- the same x for ``MP`` and ``MN``
regardless of their different ``w`` because every device in this column is
left-aligned at ``x0`` (see ``primitives.mosfet()``'s docstring).

NMOS-TO-PMOS GAP CROSSING (issue #371, root-caused in
``layout/evidence/vco-layout/PROOF-368-rootcause.md``'s status update)
-------------------------------------------------------------------------
``ring.py`` draws its inner n-well tap ring's *bottom* band inside the
``NWELL_TO_NMOS_GAP_UM`` gap this module leaves between ``MN`` and ``MP``
(``ring.py``'s ``TAP_GAP_UM``/``TAP_RING_WIDTH_UM``, measured off this gap's
own top edge) -- the same class of defect ``buffer.py``'s own fix (issue
#372) found first: the tap band is real ``VDD_VCO`` Metal1 sitting directly
across the one gap two of this module's own nets (``Y``, the MN/MP drain
bridge, and ``A``, the MN/MP gate bridge) have to cross to reach the PMOS
band. A plain Metal1 riser here would short every stage's own switching
nodes to ``VDD_VCO`` -- invisible to DRC (two touching same-layer shapes
merge into one polygon before any spacing rule runs) and invisible to
``block.connectivity_report()`` (whose probes only check same-net
continuity, never cross-net separation). Both bridges are hopped over the
gap on Metal2 instead (``_channel_hop()``, mirroring ``buffer.py``'s own
helper of the same name) -- Metal2 has no spacing relationship with Metal1
at all, so the gap is simply jumped rather than trimmed.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import devices as dev
from . import primitives as prim


def _channel_hop(canvas: prim.Canvas, pad_lo: tuple, pad_hi: tuple, y_jog: float) -> None:
    """Bridge two Metal1 pads across the NMOS/PMOS routing gap on Metal2.

    Mirrors ``buffer.py``'s own ``_channel_hop()`` (issue #372) verbatim --
    see this module's own docstring section "NMOS-TO-PMOS GAP CROSSING" for
    why a plain Metal1 riser here is unsafe. Each ``via1_stack()`` is
    centred on its own pad; every pad this is called against here is at
    least 0.46 um tall (``primitives.mosfet()``'s own terminal/gate pad
    construction), which strictly contains the 0.44 um square via1 landing
    pad, so this adds **no** new Metal1 geometry, only via1/Metal2.
    """
    x_lo, y_lo = (pad_lo[0] + pad_lo[2]) / 2.0, (pad_lo[1] + pad_lo[3]) / 2.0
    x_hi, y_hi = (pad_hi[0] + pad_hi[2]) / 2.0, (pad_hi[1] + pad_hi[3]) / 2.0
    prim.via1_stack(canvas, x_lo, y_lo)
    prim.via1_stack(canvas, x_hi, y_hi)
    if abs(x_hi - x_lo) < 1e-9:
        prim.m2_route(canvas, [(x_lo, y_lo), (x_lo, y_hi)])
    else:
        prim.m2_route(
            canvas,
            [(x_lo, y_lo), (x_lo, y_jog), (x_hi, y_jog), (x_hi, y_hi)],
        )


@dataclass
class StagePorts:
    x0: float
    x1: float  # column right edge (== x0 + widest device's w, i.e. MPH's)
    y_bottom: float  # GND_VCO terminal, bottom edge
    y_top: float  # VDD_VCO terminal, top edge
    vdd_pad: tuple
    gnd_pad: tuple
    a_gate_pad_bottom: tuple  # MN's gate pad (lowest point of the A net's vertical run)
    a_gate_pad_top: tuple  # MP's gate pad (highest point of the A net's vertical run)
    a_x: float  # x of the vertical A-net Metal1 run
    y_pad: tuple  # this stage's own Y output landing pad
    vbp_pad: tuple  # MPH's gate pad (VBP net)
    vbn_pad: tuple  # MNT's gate pad (VBN net)
    pmos_x0: float
    pmos_x1: float
    pmos_y0: float  # MP's comp bottom edge -- nwell must enclose from here up
    pmos_y1: float  # MPH's comp top edge -- nwell must enclose up to here


def build_stage(canvas: prim.Canvas, x0: float, y_bottom: float, stage_name: str) -> StagePorts:
    fets = {f.name: f for f in dev.STAGE_FETS}

    mnt_ports = prim.mosfet(canvas, fets["MNT"], x0, y_bottom)
    mn_y0 = mnt_ports.y3 + prim.COMP_GAP_UM
    mn_ports = prim.mosfet(canvas, fets["MN"], x0, mn_y0)

    pmos_y0 = mn_ports.y3 + prim.NWELL_TO_NMOS_GAP_UM
    mp_ports = prim.mosfet(canvas, fets["MP"], x0, pmos_y0)
    mph_y0 = mp_ports.y3 + prim.COMP_GAP_UM
    mph_ports = prim.mosfet(canvas, fets["MPH"], x0, mph_y0)

    # Metal2 jog height for the two bridges that cross the NMOS/PMOS gap
    # (Y, A -- see the module docstring's "NMOS-TO-PMOS GAP CROSSING"
    # section): mid-gap, between MN's own top edge and MP's own bottom edge
    # -- the same "mid-channel" convention ``buffer.py``'s own
    # ``channel_jog_y`` uses, which lands clear of ``ring.py``'s tap band by
    # a comfortable margin there and does here too (the tap band sits close
    # to the gap's *upper* edge, near MP, not centred in it).
    channel_jog_y = dev.snap_um((mn_ports.y3 + mp_ports.y0) / 2.0)

    # --- GND_VCO: MNT's bottom (source) pad is the stage's own ground pin ---
    gnd_pad = mnt_ports.bottom_pad

    # --- NT: MNT's top (drain) <-> MN's bottom (source) ---
    nt_x = (mnt_ports.top_pad[0] + mnt_ports.top_pad[2]) / 2.0
    prim.v_wire(canvas, nt_x, mnt_ports.top_pad[1], mn_ports.bottom_pad[3])

    # --- Y: MN's top (drain) is this stage's own output pin ---
    y_pad = mn_ports.top_pad
    canvas.pin(f"{stage_name}.Y", *y_pad)

    # --- NH: MP's top (source) <-> MPH's bottom (drain) ---
    nh_x = (mp_ports.top_pad[0] + mp_ports.top_pad[2]) / 2.0
    prim.v_wire(canvas, nh_x, mp_ports.top_pad[3], mph_ports.bottom_pad[1])

    # --- VDD_VCO: MPH's top (source) pad ---
    vdd_pad = mph_ports.top_pad

    # --- Y (bottom-side, PMOS): MP's bottom (drain) joins the same Y net as
    # MN's top pad -- hopped across the NMOS-to-PMOS routing gap on Metal2
    # (``_channel_hop()``), not a plain Metal1 riser: ``ring.py``'s own
    # inner n-well tap ring's bottom band sits directly across this gap on
    # Metal1 -- see the module docstring's "NMOS-TO-PMOS GAP CROSSING"
    # section. Only ``y_pad`` (MN's own drain pad, already labelled above)
    # carries the ``"{stage_name}.Y"`` pin text -- MP's bottom pad is now a
    # separate Metal1 island joined only by via1/Metal2, and a second label
    # on it would read as a *different* merged polygon for the same net to
    # this module's own regression test (``layout/tests/test_vco_layout.py``'s
    # per-net "exactly one polygon" check), the same discipline
    # ``buffer.py``'s own ``_channel_hop()`` call sites already use (label
    # only the nfet-side pad, never both sides of a hop). ---
    a_x = (mn_ports.gate_pad[0] + mn_ports.gate_pad[2]) / 2.0
    _channel_hop(canvas, mn_ports.top_pad, mp_ports.bottom_pad, channel_jog_y)

    # --- A: MN's gate pad <-> MP's gate pad, hopped the same way (shared
    # tab x for both, so the hop needs no jog -- see ``_channel_hop()``). ---
    _channel_hop(canvas, mn_ports.gate_pad, mp_ports.gate_pad, channel_jog_y)

    return StagePorts(
        x0=x0,
        x1=x0 + fets["MPH"].w_um,
        y_bottom=y_bottom,
        y_top=mph_ports.y3,
        vdd_pad=vdd_pad,
        gnd_pad=gnd_pad,
        a_gate_pad_bottom=mn_ports.gate_pad,
        a_gate_pad_top=mp_ports.gate_pad,
        a_x=a_x,
        y_pad=y_pad,
        vbp_pad=mph_ports.gate_pad,
        vbn_pad=mnt_ports.gate_pad,
        pmos_x0=x0,
        pmos_x1=x0 + fets["MPH"].w_um,
        pmos_y0=mp_ports.y0,
        pmos_y1=mph_ports.y3,
    )
