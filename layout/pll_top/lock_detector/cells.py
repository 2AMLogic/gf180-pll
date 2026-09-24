"""Gate-level cell generators for ``lock_detector``, built from ``primitives.mosfet()``.

Every function below draws directly into a shared ``primitives.Canvas`` (no
GDS-level sub-cell hierarchy -- see the module docstring in ``build.py`` for
why a flat macro-composition model was chosen over ``CellInstArray``
placement) and returns the Metal1 pad *boxes* it created, keyed by the
*global* net name the caller passed in for each port. Callers accumulate
these into one shared ``nets: dict[str, list[bbox]]`` and route each net
exactly once (see ``build.py``). Boxes, not just centers (issue #322):
``route_all_nets()``'s ``RiserLanes`` needs each pad's real footprint, not
just its center point, to keep a moved riser's own Metal1 jog from crossing
some *other* net's own, possibly much wider than a via, S/D pad.

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
)

Nets = dict[str, list[tuple[float, float, float, float]]]
PWells = list[tuple[float, float, float, float]]


def _add(nets: Nets, net: str, pad: tuple[float, float, float, float]) -> None:
    nets.setdefault(net, []).append(pad)


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

    # MP3: S(left)=P1, D(right)=VSS, G=Y (issue #322: this used to register
    # left_pad/right_pad the other way around -- mosfet()'s own convention
    # is source=left/drain=right, dev.schmitt_fets()'s MP3 has s=p1/d=vss,
    # so the pad mosfet() actually draws and tags "P1" at x0's own left
    # terminal was being registered into nets['VSS'] for routing instead,
    # and vice versa for the right terminal -- an unconditional short
    # between P1 and VSS wherever that riser and that pad's real net tag
    # ended up close enough to touch, independent of any routing choice).
    _add(nets, p1_net, p3.left_pad)
    _add(nets, vss, p3.right_pad)
    _add(nets, y, p3.gate_pad)

    # MN1: S(left)=VSS, D(right)=N1.  MN2: S(left)=N1, D(right)=Y.
    _add(nets, vss, n1.left_pad)
    _add(nets, n1_net, n1.right_pad)
    _add(nets, n1_net, n2.left_pad)
    _add(nets, y, n2.right_pad)
    _add(nets, a, n1.gate_pad)
    _add(nets, a, n2.gate_pad)

    # MN3: S(left)=N1, D(right)=VDD, G=Y (issue #322: same left/right swap
    # as MP3 above, shorting N1 to VDD).
    _add(nets, n1_net, n3.left_pad)
    _add(nets, vdd, n3.right_pad)
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


#: X pitch between two adjacent device columns in ``draw_delaywin``'s trim
#: array. The widest device the array places is the always-on base load
#: (``L=2u`` -> ``2 * SD_OVERHANG_UM + 2.0`` = 4.0 um of comp), so any pitch
#: past ~4.6 um is legal on comp-spacing grounds alone (``COMP_GAP_UM``).
#:
#: What actually sets it is a different, non-obvious constraint: **Metal3
#: riser lanes, not comp, are this block's scarce resource.** Every device
#: pad in the block needs its own riser up to its net's Metal2 bus above the
#: whole block, so every riser's Y range overlaps every other's and two of
#: them must sit ``ROW_LANE_OFFSET_UM`` (0.7 um) apart -- the block needs
#: roughly ``0.7 um x (riser groups)`` of *width* whatever the devices
#: themselves would fit in. DR-014's trim network takes this block from 45
#: devices / 161 riser groups to 117 / 409, i.e. from 113 um of lane demand
#: to 286 um, so a pitch chosen to pack comp tightly hands ``RiserLanes`` an
#: unsolvable problem (``ValueError: no free Metal3 riser lane near x=...``)
#: rather than a dense layout. At 5.0 um the block is 294.8 um wide against
#: that 286 um of demand.
#:
#: **If a future change adds devices here and the build starts raising that
#: ValueError, raise this constant** -- it is the one lever that buys lanes.
#: Measured on this block: 4.6 (the comp-spacing floor) -> 278.6 um wide,
#: 5.0 -> 294.8, 5.5 -> 314.0, 6.0 -> 333.2, 6.5 -> 352.8, all of which
#: route; 4.6 and 5.0 were additionally confirmed DRC-clean and LVS-matched
#: on the PDK's own decks (issue #449). The failure is loud, not silent:
#: ``layout/tests/test_lock_detector_layout.py`` builds this block on every
#: test run. See ``primitives.RiserLanes`` and issues #322/#347/#451.
TRIM_COL_PITCH_UM = 5.0


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
    t_bits: tuple[str, str, str, str],
    col_pitch: float = TRIM_COL_PITCH_UM,
    tap_every: int = 2,
) -> tuple[tuple[float, float, float, float], list[float]]:
    """``delaywin_3v3.sch``: the DR-014-trimmed window-delay cell (issue #449).

    Four ``inv_3v3`` stages (even count, so the block is non-inverting), each
    loaded by

    * one **always-on** ``nfet_03v3`` MOS cap (``W=6.2u L=2u``, D=S=B=VSS,
      gate on the delayed node), and
    * **four binary-weighted switched segments** (``dev.TRIM_WEIGHTS`` =
      1:2:4:8). Segment ``j`` is tied to the delayed node by a full
      transmission gate (``MSN``/``MSP``, gated by ``Tj``/``TjB``), clamped
      to ``VSS`` by a kill device (``MK``, gated by ``TjB``) so a deselected
      segment is a defined LOW node rather than a floating one, and carries
      its own MOS cap (``MC``, gate on the segment node).

    plus four shared trim-bit complement inverters (``XIT0``-``XIT3``)
    driving ``TjB`` from the block's four ``t_bits`` inputs. 84 transistors
    in all -- ``4x2`` stage inverters, ``4`` base caps, ``4x4x4`` segment
    devices and ``4x2`` trim inverters -- exactly the device set
    ``design/gen_delaywin.py`` emits into ``design/delaywin_3v3.sch`` and
    ``design/netlist/lock_detector.spice`` exports. Before issue #449 this
    function drew the pre-DR-014 cell (12 devices, fixed loads, no trim
    network at all) and the block could not pass LVS against its own
    committed schematic.

    ``t_bits`` is the caller's own four trim nets, LSB first -- ``"T0".."T3"``
    for the standalone cell, ``"LDT0".."LDT3"`` (the block's own boundary
    pins) for ``build_lock_detector``.

    Placement is a plain column grid at ``col_pitch``: four columns of trim
    inverters, then nine columns per stage -- the stage inverter and its base
    cap, then, per segment, one column carrying ``MSP`` (PMOS row), ``MSN``
    (NMOS row) and ``MC`` (cap row) followed by one carrying ``MK`` (NMOS
    row). Only three Y bands are ever used (``y_p``/``y_n``/``y_cap``), and
    every PMOS stays in the ``y_p`` band on purpose: ``build.py`` draws
    exactly **one** nwell rectangle enclosing every PMOS comp in the block
    (see this module's own docstring), so a PMOS placed in the cap row would
    stretch that single rectangle straight over the NMOS rows in between.

    Returns ``(bbox, tap_xs)`` -- see ``draw_xor2``'s docstring. ``tap_xs``
    is one position every ``tap_every`` columns (~13 um at the defaults),
    comfortably inside DF.13_LV/DF.14_LV's 20 um well/substrate-tap distance
    cap across a macro that is now ~250 um wide on its own.
    """
    n_bits = len(dev.TRIM_WEIGHTS)
    if len(t_bits) != n_bits:
        raise ValueError(f"delaywin needs exactly {n_bits} trim bits, got {t_bits!r}")
    tb = [f"{prefix}T{j}B" for j in range(n_bits)]

    boxes: list[tuple[float, float, float, float]] = []
    col = 0

    def _x(k: int) -> float:
        return x0 + k * col_pitch

    # --- XIT0-XIT3: the trim-bit complement inverters, shared by every stage ---
    for j, t_bit in enumerate(t_bits):
        boxes.append(
            draw_inv(canvas, nets, pwells, _x(col), y_p, y_n, t_bit, tb[j], vdd, vss, prefix=f"{prefix}IT{j}_")
        )
        col += 1

    nodes = [a, f"{prefix}D1", f"{prefix}D2", f"{prefix}D3", y]
    for i in range(4):
        stage_in, stage_out = nodes[i], nodes[i + 1]
        stage = i + 1

        # --- the delay stage itself, plus its always-on base load ---
        boxes.append(
            draw_inv(
                canvas, nets, pwells, _x(col), y_p, y_n, stage_in, stage_out, vdd, vss,
                prefix=f"{prefix}I{stage}_",
            )
        )
        base_cap = dev.base_cap_fet(f"{prefix}MB{stage}", stage_out, vss)
        boxes.append(draw_discrete_fet(canvas, nets, pwells, _x(col), y_cap, base_cap, tab_up=False))
        col += 1

        # --- the four binary-weighted switched trim segments ---
        for j in range(n_bits):
            seg = f"{prefix}S{stage}{j}"
            msn, msp, mk, mc = dev.trim_segment_fets(
                prefix, stage, j, stage_out, seg, t_bits[j], tb[j], vdd, vss
            )
            boxes.append(draw_discrete_fet(canvas, nets, pwells, _x(col), y_p, msp, tab_up=False))
            boxes.append(draw_discrete_fet(canvas, nets, pwells, _x(col), y_n, msn, tab_up=True))
            boxes.append(draw_discrete_fet(canvas, nets, pwells, _x(col), y_cap, mc, tab_up=False))
            col += 1
            boxes.append(draw_discrete_fet(canvas, nets, pwells, _x(col), y_n, mk, tab_up=True))
            col += 1

    # Tap positions sit in the *gaps* between columns -- never inside any
    # device's own comp/poly/pad footprint, which is the one thing
    # ``build._finish()`` cannot verify for itself (see its docstring).
    tap_xs = [_x(k) - col_pitch / 2.0 for k in range(tap_every, col, tap_every)]
    return bbox_union(boxes), tap_xs
