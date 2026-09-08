"""Gate-level cell generators for ``lock_detector``, built from ``primitives.mosfet()``.

Every function below draws directly into a shared ``primitives.Canvas`` (no
GDS-level sub-cell hierarchy -- see the module docstring in ``build.py`` for
why a flat macro-composition model was chosen over ``CellInstArray``
placement) and returns the Metal1 pad centers it created, keyed by the
*global* net name the caller passed in for each port. Callers accumulate
these into one shared ``nets: dict[str, list[(x, y)]]`` and route each net
exactly once (see ``build.py``).

Every PMOS comp bbox drawn anywhere in this package is appended to a shared
``pwells: list[bbox]`` instead of each function drawing its own nwell --
``build.py`` draws exactly **one** nwell rectangle at the end, enclosing
every PMOS comp box + the block's own ntap. This avoids ever having two
separate nwell polygons close enough to trip NW.2a/NW.2b (min nwell space),
by construction: there is only ever one nwell shape in the whole design.
"""

from __future__ import annotations

from . import devices as dev
from .primitives import (
    Canvas,
    bbox_union,
    mosfet,
    pad_center,
)

Nets = dict[str, list[tuple[float, float]]]
PWells = list[tuple[float, float, float, float]]


def _add(nets: Nets, net: str, pad: tuple[float, float, float, float]) -> None:
    nets.setdefault(net, []).append(pad_center(pad))


def draw_inv(
    canvas: Canvas,
    nets: Nets,
    pwells: PWells,
    x0: float,
    y_p: float,
    y_n: float,
    a: str,
    y: str,
    vdd: str,
    vss: str,
    prefix: str = "",
) -> tuple[float, float, float, float]:
    """``inv_3v3``: one PMOS (VDD-side) over one NMOS (VSS-side), gated by ``a``."""
    mp, mn = dev.inv_fets(prefix, a, y, vdd, vss)
    p = mosfet(canvas, mp, x0, y_p, tab_up=False)
    n = mosfet(canvas, mn, x0, y_n, tab_up=True)

    _add(nets, vdd, p.left_pad)
    _add(nets, vss, n.left_pad)
    _add(nets, y, p.right_pad)
    _add(nets, y, n.right_pad)
    _add(nets, a, p.gate_pad)
    _add(nets, a, n.gate_pad)

    pwells.append(p.comp_bbox)
    return bbox_union([p.comp_bbox, n.comp_bbox])


def draw_nand2(
    canvas: Canvas,
    nets: Nets,
    pwells: PWells,
    x0: float,
    y_p: float,
    y_n: float,
    a: str,
    b: str,
    y: str,
    vdd: str,
    vss: str,
    prefix: str = "",
    x_pitch: float = 2.6,
) -> tuple[float, float, float, float]:
    """``nand2_3v3``: two parallel PMOS (VDD-Y) over two series NMOS (Y-NMID-VSS).

    Independent-island convention (see ``primitives.py``'s module docstring):
    ``NMID`` is not a shared-diffusion internal node here, it is an ordinary
    Metal1/Via net between MNA's left pad and MNB's right pad, exactly like
    every other net in this package.
    """
    mpa, mpb, mna, mnb = dev.nand2_fets(prefix, a, b, y, vdd, vss)

    pa = mosfet(canvas, mpa, x0, y_p, tab_up=False)
    pb = mosfet(canvas, mpb, x0 + x_pitch, y_p, tab_up=False)
    na = mosfet(canvas, mna, x0, y_n, tab_up=True)
    nb = mosfet(canvas, mnb, x0 + x_pitch, y_n, tab_up=True)

    # PMOS: both source(left)=VDD, both drain(right)=Y (parallel).
    _add(nets, vdd, pa.left_pad)
    _add(nets, vdd, pb.left_pad)
    _add(nets, y, pa.right_pad)
    _add(nets, y, pb.right_pad)
    _add(nets, a, pa.gate_pad)
    _add(nets, b, pb.gate_pad)

    # NMOS series stack: MNA drain(right)=Y, MNA source(left)=NMID;
    # MNB drain(right)=NMID, MNB source(left)=VSS.
    nmid = f"{prefix}NMID"
    _add(nets, y, na.right_pad)
    _add(nets, nmid, na.left_pad)
    _add(nets, nmid, nb.right_pad)
    _add(nets, vss, nb.left_pad)
    _add(nets, a, na.gate_pad)
    _add(nets, b, nb.gate_pad)

    pwells.extend([pa.comp_bbox, pb.comp_bbox])
    return bbox_union([pa.comp_bbox, pb.comp_bbox, na.comp_bbox, nb.comp_bbox])


def draw_schmitt(
    canvas: Canvas,
    nets: Nets,
    pwells: PWells,
    x0: float,
    y_p: float,
    y_n: float,
    a: str,
    y: str,
    vdd: str,
    vss: str,
    prefix: str = "",
    x_pitch: float = 2.6,
) -> tuple[float, float, float, float]:
    """``schmitt_3v3``: classic 6T inverting CMOS Schmitt trigger.

    MP1-MP2 and MN1-MN2 are each an independent-island 2-device series chain
    (VDD-A-P1-A-Y and VSS-A-N1-A-Y); MP3/MN3 are the hysteresis feedback
    devices, gated by ``y`` and tapping back into P1/N1.
    """
    mp1, mp2, mp3, mn1, mn2, mn3 = dev.schmitt_fets(prefix, a, y, vdd, vss)

    p1 = mosfet(canvas, mp1, x0, y_p, tab_up=False)
    p2 = mosfet(canvas, mp2, x0 + x_pitch, y_p, tab_up=False)
    p3 = mosfet(canvas, mp3, x0 + 2 * x_pitch, y_p, tab_up=False)
    n1 = mosfet(canvas, mn1, x0, y_n, tab_up=True)
    n2 = mosfet(canvas, mn2, x0 + x_pitch, y_n, tab_up=True)
    n3 = mosfet(canvas, mn3, x0 + 2 * x_pitch, y_n, tab_up=True)

    p1_net = f"{prefix}P1"
    n1_net = f"{prefix}N1"

    # MP1: S(left)=VDD, D(right)=P1.  MP2: S(left)=P1, D(right)=Y.
    _add(nets, vdd, p1.left_pad)
    _add(nets, p1_net, p1.right_pad)
    _add(nets, p1_net, p2.left_pad)
    _add(nets, y, p2.right_pad)
    _add(nets, a, p1.gate_pad)
    _add(nets, a, p2.gate_pad)

    # MP3: D=VSS(left), S=P1(right), G=Y.
    _add(nets, vss, p3.left_pad)
    _add(nets, p1_net, p3.right_pad)
    _add(nets, y, p3.gate_pad)

    # MN1: S(left)=VSS, D(right)=N1.  MN2: S(left)=N1, D(right)=Y.
    _add(nets, vss, n1.left_pad)
    _add(nets, n1_net, n1.right_pad)
    _add(nets, n1_net, n2.left_pad)
    _add(nets, y, n2.right_pad)
    _add(nets, a, n1.gate_pad)
    _add(nets, a, n2.gate_pad)

    # MN3: D=VDD(left), S=N1(right), G=Y.
    _add(nets, vdd, n3.left_pad)
    _add(nets, n1_net, n3.right_pad)
    _add(nets, y, n3.gate_pad)

    pwells.extend([p1.comp_bbox, p2.comp_bbox, p3.comp_bbox])
    return bbox_union(
        [p1.comp_bbox, p2.comp_bbox, p3.comp_bbox, n1.comp_bbox, n2.comp_bbox, n3.comp_bbox]
    )


def draw_discrete_fet(
    canvas: Canvas,
    nets: Nets,
    pwells: PWells,
    x0: float,
    y_center: float,
    fet: dev.Fet,
    tab_up: bool = True,
) -> tuple[float, float, float, float]:
    """One standalone transistor (``MDNW``/``MUPW``/an ``MCW``-style MOS cap).

    A lone PMOS still needs to sit in the block's shared nwell (appended to
    ``pwells``, same as every other PMOS in this design) -- its body is
    already tied to ``VDD`` through the same net as one of its own S/D
    terminals (see ``devices.py``'s ``b`` field), so no extra wire is needed
    *for this device*; the block-level ntap in ``build.py`` still exists so
    the well itself has a low-impedance contact, per DF.13's max-tap-
    distance rule.
    """
    m = mosfet(canvas, fet, x0, y_center, tab_up=tab_up)
    _add(nets, fet.s, m.left_pad)
    _add(nets, fet.d, m.right_pad)
    _add(nets, fet.g, m.gate_pad)
    if fet.kind == "pfet":
        pwells.append(m.comp_bbox)
    return m.comp_bbox


def draw_xor2(
    canvas: Canvas,
    nets: Nets,
    pwells: PWells,
    x0: float,
    y_p: float,
    y_n: float,
    a: str,
    b: str,
    y: str,
    vdd: str,
    vss: str,
    prefix: str,
    x_pitch: float = 2.6,
    gate_pitch: float = 7.0,
) -> tuple[tuple[float, float, float, float], list[float]]:
    """``xor2_3v3.sch``: 4x ``nand2_3v3`` -- the classic 4-NAND XOR.

    ``N1 = NAND(A,B)``; ``N2 = NAND(A,N1)``; ``N3 = NAND(B,N1)``;
    ``Y = NAND(N2,N3)`` -- transcribed directly from
    ``design/netlist/lock_detector.spice``'s ``xor2_3v3`` subckt.

    Returns ``(bbox, tap_xs)`` -- ``tap_xs`` is the list of X positions in
    the gaps *between* the 4 sub-gates, clear of every device's own comp/
    poly/pad geometry, for the caller to hand to ``build.py``'s
    ``_finish()``: this whole macro spans ~4x ``gate_pitch`` (28 um at the
    default pitch), well past DF.13_LV/DF.14_LV's 20 um well/substrate-tap
    distance cap on its own.
    """
    n1 = f"{prefix}N1"
    n2 = f"{prefix}N2"
    n3 = f"{prefix}N3"
    b1 = draw_nand2(
        canvas, nets, pwells, x0, y_p, y_n, a, b, n1, vdd, vss, prefix=f"{prefix}G1_", x_pitch=x_pitch
    )
    b2 = draw_nand2(
        canvas,
        nets,
        pwells,
        x0 + gate_pitch,
        y_p,
        y_n,
        a,
        n1,
        n2,
        vdd,
        vss,
        prefix=f"{prefix}G2_",
        x_pitch=x_pitch,
    )
    b3 = draw_nand2(
        canvas,
        nets,
        pwells,
        x0 + 2 * gate_pitch,
        y_p,
        y_n,
        b,
        n1,
        n3,
        vdd,
        vss,
        prefix=f"{prefix}G3_",
        x_pitch=x_pitch,
    )
    b4 = draw_nand2(
        canvas,
        nets,
        pwells,
        x0 + 3 * gate_pitch,
        y_p,
        y_n,
        n2,
        n3,
        y,
        vdd,
        vss,
        prefix=f"{prefix}G4_",
        x_pitch=x_pitch,
    )
    boxes = [b1, b2, b3, b4]
    tap_xs = [boxes[i][2] + (boxes[i + 1][0] - boxes[i][2]) / 2.0 for i in range(len(boxes) - 1)]
    return bbox_union(boxes), tap_xs


def draw_delaywin(
    canvas: Canvas,
    nets: Nets,
    pwells: PWells,
    x0: float,
    y_p: float,
    y_n: float,
    y_cap: float,
    a: str,
    y: str,
    vdd: str,
    vss: str,
    prefix: str,
    gate_pitch: float = 6.0,
) -> tuple[tuple[float, float, float, float], list[float]]:
    """``delaywin_3v3.sch``: 4x ``inv_3v3`` (non-inverting overall), each
    loaded by an ``nfet_03v3`` MOS cap (``W=8u L=2u``, D=S=B=VSS) on its
    output node.

    Returns ``(bbox, tap_xs)`` -- see ``draw_xor2``'s docstring; this macro
    spans ~4x ``gate_pitch`` (16.8 um at the default pitch), close enough to
    DF.13_LV/DF.14_LV's 20 um cap that a caller placing it next to other
    geometry (``build_lock_detector``) should still use these gaps rather
    than assume a single external tap reaches every stage.
    """
    nodes = [a, f"{prefix}D1", f"{prefix}D2", f"{prefix}D3", y]
    stage_boxes = []
    for i in range(4):
        stage_in, stage_out = nodes[i], nodes[i + 1]
        inv_box = draw_inv(
            canvas,
            nets,
            pwells,
            x0 + i * gate_pitch,
            y_p,
            y_n,
            stage_in,
            stage_out,
            vdd,
            vss,
            prefix=f"{prefix}I{i + 1}_",
        )
        cap = dev.moscap_fet(f"{prefix}MC{i + 1}", 8.0, 2.0, stage_out, vss)
        cap_box = draw_discrete_fet(canvas, nets, pwells, x0 + i * gate_pitch, y_cap, cap, tab_up=False)
        stage_boxes.append(bbox_union([inv_box, cap_box]))

    tap_xs = [
        stage_boxes[i][2] + (stage_boxes[i + 1][0] - stage_boxes[i][2]) / 2.0
        for i in range(len(stage_boxes) - 1)
    ]
    return bbox_union(stage_boxes), tap_xs
