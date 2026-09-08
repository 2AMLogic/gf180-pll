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
"""

from __future__ import annotations

from dataclasses import dataclass

from . import devices as dev
from . import primitives as prim


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
    # MN's top pad -- a vertical Metal1 run bridging the NMOS-to-PMOS
    # routing gap, landing on both pads. ---
    y_bridge_x = (mn_ports.top_pad[0] + mn_ports.top_pad[2]) / 2.0
    prim.v_wire(canvas, y_bridge_x, mn_ports.top_pad[3], mp_ports.bottom_pad[1])
    canvas.pin(f"{stage_name}.Y", *mp_ports.bottom_pad)

    # --- A: MN's gate pad <-> MP's gate pad, one vertical run (same tab x
    # for both -- see module docstring). ---
    a_x = (mn_ports.gate_pad[0] + mn_ports.gate_pad[2]) / 2.0
    prim.v_wire(canvas, a_x, mn_ports.gate_pad[3], mp_ports.gate_pad[1])

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
