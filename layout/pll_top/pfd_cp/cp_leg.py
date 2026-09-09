"""``cp_leg_n``/``cp_leg_p`` -- the charge pump's unit N/P sink/source legs
(issue #319, Part 3a of #294's device-layout methodology, a decomposition
of #301).

``design/cp_leg_n.sch``/``design/cp_leg_p.sch`` are each **4 devices with a
3-way net** (``BG`` is ``MDIS``'s drain, ``MEN``'s drain, *and*
``MBOT``/``MTOP``'s gate), which ``devgen.build_stack_cell()``'s own
1-/2-terminal-only auto-wiring (see that module's docstring) cannot resolve
directly -- exactly the gap issue #319 exists to close. Per that module's
own guidance ("compose several ``build_stack_cell`` columns side by side and
wire between them by hand"), and following ``cp_dumpbuf.py``'s identical
precedent (issue #301/#302, calling ``devgen.mosfet()``/``devgen.Device``
directly rather than extending ``build_stack_cell()`` into a general
N-terminal router), this module draws two independent 2-device columns with
``devgen.mosfet()`` and hand-wires the one net ``build_stack_cell()``
couldn't have resolved on its own.

TWO STRUCTURAL SUB-GROUPS
--------------------------
* The **mirror stack** (bottom-to-top: ``MBOT``/``MTOP`` then ``MCASC``,
  current path ``rail -> MID -> TAIL``) is an ordinary 2-device
  ``build_stack_cell()``-shaped column: every net on it is 1- or
  2-terminal *within that column alone* -- ``MID`` (facing pads, 2-terminal)
  and ``rail``/``TAIL``/``VCASCx`` (1-terminal each) -- except ``BG``, which
  is this column's bottom device's *gate*, the net's third terminal (see
  below).
* The **steering pair** (bottom-to-top: ``MDIS`` then ``MEN``, both drive
  ``BG``) is a second, independent 2-device column. Both devices' *drains*
  are the pair's facing pads (by construction: ``MDIS``'s ``top_net`` and
  ``MEN``'s ``bottom_net`` are both ``BG``, matching each schematic's own
  ``D`` label on both instances), so ``BG``'s other two terminals resolve
  exactly like ``MID`` does in the mirror stack -- an ordinary
  ``_connect_pads()`` call.

``BG``'s third terminal -- ``MBOT``/``MTOP``'s own gate, in the *other*
column -- is the one hand-routed capability this module adds.

HAND-ROUTED BG TAP: WHY IT NEEDS NO VERTICAL DETOUR
----------------------------------------------------
This cell's device geometry is fixed by the schematics: every steering
device (``MEN``/``MDIS``) is ``L=0.3 um``; every mirror device (``MBOT``/
``MTOP``/``MCASC``) is ``L=1.0 um``. Both columns are drawn bottom-aligned
at the same ``y_bottom=0.0`` (see :func:`build_leg`). Two consequences of
``devgen.mosfet()``'s own fixed margins (``SD_OVERHANG_UM``,
``CONTACT_ROW_MARGIN_UM``, ``CONTACT_SIZE_UM``, ``METAL1_PAD_MARGIN_UM``)
follow, independent of either device's own ``W``:

* ``MBOT``/``MTOP``'s own ``gate_y_center`` is always
  ``SD_OVERHANG_UM + L_mirror/2 = 0.5 + 0.5 = 1.0`` um.
* ``MDIS``'s own top (drain) pad -- ``BG``'s own already-resolved facing
  pad in the steering column -- always spans Y
  ``[y3 - 0.44, y3 + 0.02]`` where ``y3 = 2*SD_OVERHANG_UM + L_steer =
  1.0 + 0.3 = 1.3``, i.e. ``[0.86, 1.32]``.

``0.86 <= 1.0 <= 1.32`` -- ``MBOT``/``MTOP``'s gate is always reachable with
a single straight horizontal Metal1 jog landing *inside* ``MDIS``'s own
drain pad's existing Y extent, with no separate vertical stub needed at all
(:func:`_route_bg_tap` asserts this holds rather than silently drawing an
unconnected wire if the geometry it depends on ever changes).
``layout/tests/test_cp_leg_devgen.py`` asserts this numerically for both
legs.

The jog runs entirely through the empty gap between the two columns
(:data:`COLUMN_GAP_UM`) -- it starts at ``MDIS``'s own pad (already ``BG``,
so overlapping it is a same-net merge, not a short) and ends inside
``MBOT``/``MTOP``'s own gate pad (ditto) -- clearing every other shape in
both columns because neither column has any drawn geometry in that empty
gap, and the mirror stack's *other* device (``MCASC``) sits well above this
Y band regardless of ``W`` (it starts only after ``MBOT``/``MTOP``'s own
``y3`` plus :data:`devgen.COMP_GAP_UM`).

RAIL STRAP + TAP (``VSS``/``VDD``)
------------------------------------
``MDIS``'s and ``MBOT``/``MTOP``'s own outer (source) pads are *both*
bottom pads at the *same* ``y_bottom=0.0`` -- so, independent of ``W``, they
always share the exact same Y band (``[-0.02, 0.44]``, the fixed
``bottom_pad`` formula), and a single horizontal Metal1 strap joins them
directly (:func:`_route_rail_strap_and_tap`). One substrate/n-well tap
(:func:`devgen._well_tap`, reused directly per issue #319's own guidance --
DRC hygiene for the substrate tie, mandatory for the n-well tie; see
``devgen.py``'s own "WELL/SUBSTRATE TIES" docstring section) is dropped into
the same gap, centred between the two columns' own comp edges with
:data:`devgen.TAP_GAP_UM`-equivalent clearance on both sides (see
:data:`COLUMN_GAP_UM`'s own derivation) so its own opposite-type implant
never touches either column's implant, and merges into the strap by sharing
its Y band -- no separate connecting wire needed.

WHY ``COLUMN_GAP_UM`` IS WIDER THAN ``cp_dumpbuf.py``'s OWN SIDE-BY-SIDE
``DEVICE_GAP_UM``
--------------------------------------------------------------------------
``cp_dumpbuf.py`` places same-kind devices side by side with
``DEVICE_GAP_UM = 2.0`` um, sized to clear a device's own left-hanging gate
tab from its left neighbour's rightmost Metal1 pad -- but that gap carries
no tap. This module's gap additionally has to fit one substrate/n-well tap
in the middle, with ``devgen.TAP_GAP_UM`` (1.0 um, itself
``> 2*devgen.IMPLANT_MARGIN_UM`` so the tap's own opposite-type implant
never touches an adjacent device's implant -- see ``devgen.py``'s own
``TAP_GAP_UM`` citation) of clearance from *each* column's own comp edge:
``1.0 + devgen.TAP_SIZE_UM (0.6) + 1.0 = 2.6`` um minimum. :data:`COLUMN_GAP_UM`
rounds that up to 3.0 um for headroom.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import devgen

#: See module docstring's "WHY COLUMN_GAP_UM IS WIDER..." section.
COLUMN_GAP_UM = 3.0


@dataclass(frozen=True)
class LegSpec:
    """The per-polarity parameters that differ between ``cp_leg_n`` and
    ``cp_leg_p`` -- everything else (topology, wiring, margins) is shared by
    :func:`build_leg`.
    """

    top_cell: str
    kind: str  # "nfet" (cp_leg_n) or "pfet" (cp_leg_p)
    rail_net: str  # VSS (N) / VDD (P) -- MDIS's and MBOT/MTOP's own outer source
    bias_net: str  # VBN (N) / VBP (P) -- MEN's own outer source
    cascode_net: str  # VCASCN / VCASCP
    mdis_gate_net: str  # ENB (N) / EN (P) -- see each schematic's own MDIS instance
    men_gate_net: str  # EN (N) / ENB (P) -- see each schematic's own MEN instance
    mirror_bottom_name: str  # "MBOT" (N) / "MTOP" (P)
    w_mirror_um: float
    l_mirror_um: float = 1.0
    w_steer_um: float = 1.0
    l_steer_um: float = 0.3
    tail_net: str = "TAIL"
    mid_net: str = "MID"
    bg_net: str = "BG"


@dataclass
class LegLayout:
    canvas: devgen.Canvas
    ports: dict[str, devgen.MosfetPorts]
    pins: dict[str, tuple[float, float, float, float]]
    nwell_box: tuple[float, float, float, float] | None
    footprint: tuple[float, float, float, float]

    def write_gds(self, path) -> None:
        self.canvas.write_gds(path)


def _route_bg_tap(
    canvas: devgen.Canvas,
    steer_bottom: devgen.MosfetPorts,
    mirror_bottom: devgen.MosfetPorts,
) -> None:
    """Hand-route ``BG``'s third terminal: ``mirror_bottom``'s own gate pad.

    ``BG``'s other two terminals (``steer_bottom``'s and ``steer_top``'s own
    facing drain pads) are wired by the caller with an ordinary
    ``devgen._connect_pads()`` call *before* this runs -- this function only
    adds the branch onto ``steer_bottom``'s own drain pad (already ``BG``),
    over to ``mirror_bottom``'s own gate pad, in the other column. See the
    module docstring's "HAND-ROUTED BG TAP" section for why a single
    horizontal jog (no vertical detour) always reaches, for this cell's
    fixed device geometry.
    """
    y = mirror_bottom.gate_y_center
    pad_y0, pad_y1 = steer_bottom.top_pad[1], steer_bottom.top_pad[3]
    if not (pad_y0 <= y <= pad_y1):
        raise ValueError(
            f"mirror gate y-center ({y}) is not inside the steering column's "
            f"own BG drain pad Y-range ({pad_y0}, {pad_y1}) -- cp_leg's "
            "hand-routed BG tap assumes fixed l_steer=0.3/l_mirror=1.0 and "
            "both columns bottom-aligned at y=0.0 (see build_leg())"
        )
    x0 = steer_bottom.top_pad[2]
    x1 = mirror_bottom.gate_pad[2]
    half = devgen.METAL1_WIRE_WIDTH_UM / 2.0
    canvas.rect("metal1", x0, y - half, x1, y + half)


def _route_rail_strap_and_tap(
    canvas: devgen.Canvas,
    spec: LegSpec,
    steer_bottom: devgen.MosfetPorts,
    mirror_bottom: devgen.MosfetPorts,
) -> tuple[float, float, float, float]:
    """Join ``steer_bottom``'s and ``mirror_bottom``'s own outer (source)
    pads -- both on ``spec.rail_net`` -- with a straight horizontal Metal1
    strap, and drop one substrate/n-well tap into the same gap, on the same
    Y band (so it merges into the strap with no separate connecting wire).
    See the module docstring's "RAIL STRAP + TAP" section. Returns the tap's
    own drawn Metal1 pad.
    """
    pad_a, pad_b = steer_bottom.bottom_pad, mirror_bottom.bottom_pad
    y_lo = max(pad_a[1], pad_b[1])
    y_hi = min(pad_a[3], pad_b[3])
    if y_hi <= y_lo:
        raise ValueError(
            "rail strap: steer/mirror bottom pads share no Y overlap -- "
            "cp_leg's hand-routed rail strap assumes both columns are "
            "bottom-aligned at the same y_bottom (see build_leg())"
        )
    y_center = (y_lo + y_hi) / 2.0
    half = devgen.METAL1_WIRE_WIDTH_UM / 2.0
    canvas.rect("metal1", pad_a[2], y_center - half, pad_b[0], y_center + half)

    tap_kind = "n" if spec.kind == "pfet" else "p"
    gap_center_x = (steer_bottom.x1 + mirror_bottom.x0) / 2.0
    tap_x0 = gap_center_x - devgen.TAP_SIZE_UM / 2.0
    tap_h_um = devgen.TAP_SIZE_UM + 2.0 * devgen.METAL1_PAD_MARGIN_UM

    # The tap's own X range straddles mirror_bottom's own hand-routed gate
    # pad's X range (both sit centred in the column gap -- see module
    # docstring), so it cannot rely on X clearance alone to satisfy M1.2a's
    # metal1-to-metal1 spacing (0.23 um) against that gate pad -- push the
    # tap's own Y range below it instead, by a clearance well past that
    # minimum, while still keeping enough overlap with [y_lo, y_hi] (the
    # rail strap's own Y band) for the two to merge into one shape.
    m1_clearance_um = 0.35
    tap_y1_max = mirror_bottom.gate_pad[1] - m1_clearance_um
    tap_y0 = tap_y1_max - tap_h_um
    if tap_y0 + tap_h_um <= y_lo:
        raise ValueError(
            "rail tap: no Y position clears mirror_bottom's own gate pad "
            "(M1.2a spacing) while still overlapping the rail strap's own "
            "Y band -- cp_leg's hand-routed tap placement assumes fixed "
            "l_mirror=1.0 geometry (see build_leg())"
        )
    return devgen._well_tap(canvas, tap_kind, tap_x0, tap_y0, spec.rail_net)


def build_leg(spec: LegSpec) -> LegLayout:
    """Draw one ``cp_leg_n``/``cp_leg_p`` unit leg: the steering pair
    (``MDIS``/``MEN``) and the mirror stack (``MBOT``/``MTOP`` + ``MCASC``),
    side by side, with ``BG``'s hand-routed 3-way net and the rail
    strap+tap. See the module docstring for the full topology.
    """
    canvas = devgen.Canvas(spec.top_cell)

    mdis = devgen.Device(
        name="MDIS",
        kind=spec.kind,
        w_um=spec.w_steer_um,
        l_um=spec.l_steer_um,
        gate_net=spec.mdis_gate_net,
        top_net=spec.bg_net,
        bottom_net=spec.rail_net,
    )
    men = devgen.Device(
        name="MEN",
        kind=spec.kind,
        w_um=spec.w_steer_um,
        l_um=spec.l_steer_um,
        gate_net=spec.men_gate_net,
        top_net=spec.bias_net,
        bottom_net=spec.bg_net,
    )
    mirror_bottom_dev = devgen.Device(
        name=spec.mirror_bottom_name,
        kind=spec.kind,
        w_um=spec.w_mirror_um,
        l_um=spec.l_mirror_um,
        gate_net=spec.bg_net,
        top_net=spec.mid_net,
        bottom_net=spec.rail_net,
    )
    mcasc = devgen.Device(
        name="MCASC",
        kind=spec.kind,
        w_um=spec.w_mirror_um,
        l_um=spec.l_mirror_um,
        gate_net=spec.cascode_net,
        top_net=spec.tail_net,
        bottom_net=spec.mid_net,
    )

    steer_bottom = devgen.mosfet(canvas, mdis, 0.0, 0.0)
    steer_top = devgen.mosfet(canvas, men, 0.0, steer_bottom.y3 + devgen.COMP_GAP_UM)

    mirror_x0 = steer_bottom.x1 + COLUMN_GAP_UM
    mirror_bottom = devgen.mosfet(canvas, mirror_bottom_dev, mirror_x0, 0.0)
    mirror_top = devgen.mosfet(canvas, mcasc, mirror_x0, mirror_bottom.y3 + devgen.COMP_GAP_UM)

    # MID: an ordinary 2-terminal facing net, within the mirror column alone.
    devgen._connect_pads(canvas, mirror_bottom.top_pad, mirror_top.bottom_pad)

    # BG: 2 of its 3 terminals (MDIS's/MEN's own facing drains) resolve the
    # same way, within the steering column alone.
    devgen._connect_pads(canvas, steer_bottom.top_pad, steer_top.bottom_pad)

    # BG's third terminal -- mirror_bottom's own gate, in the *other*
    # column -- is this module's one hand-routed capability.
    _route_bg_tap(canvas, steer_bottom, mirror_bottom)

    pins: dict[str, tuple[float, float, float, float]] = {}

    def _pin(net: str, pad: tuple[float, float, float, float]) -> None:
        canvas.pin(net, *pad)
        pins[net] = pad

    _pin(spec.men_gate_net, steer_top.gate_pad)
    _pin(spec.mdis_gate_net, steer_bottom.gate_pad)
    _pin(spec.bias_net, steer_top.top_pad)
    _pin(spec.cascode_net, mirror_top.gate_pad)
    _pin(spec.tail_net, mirror_top.top_pad)

    tap_pad = _route_rail_strap_and_tap(canvas, spec, steer_bottom, mirror_bottom)
    pins[spec.rail_net] = tap_pad

    ports = {
        "MDIS": steer_bottom,
        "MEN": steer_top,
        spec.mirror_bottom_name: mirror_bottom,
        "MCASC": mirror_top,
    }

    nwell_box = None
    if spec.kind == "pfet":
        all_ports = list(ports.values())
        x0 = min(p.x0 for p in all_ports) - devgen.NWELL_MARGIN_UM
        x1 = max(p.x1 for p in all_ports) + devgen.NWELL_MARGIN_UM
        y0 = min(min(p.y0 for p in all_ports), tap_pad[1]) - devgen.NWELL_MARGIN_UM
        y1 = max(p.y3 for p in all_ports) + devgen.NWELL_MARGIN_UM
        nwell_box = (x0, y0, x1, y1)
        canvas.rect("nwell", *nwell_box)

    footprint_x0 = min(p.x0 for p in ports.values()) - devgen.POLY_ENDCAP_UM - devgen.METAL1_PAD_MARGIN_UM
    footprint_x1 = max(p.x1 for p in ports.values())
    footprint_y0 = min(p.y0 for p in ports.values())
    footprint_y1 = max(p.y3 for p in ports.values())
    if nwell_box is not None:
        footprint_x0 = min(footprint_x0, nwell_box[0])
        footprint_x1 = max(footprint_x1, nwell_box[2])
        footprint_y0 = min(footprint_y0, nwell_box[1])
        footprint_y1 = max(footprint_y1, nwell_box[3])
    footprint = (footprint_x0, footprint_y0, footprint_x1, footprint_y1)

    return LegLayout(canvas=canvas, ports=ports, pins=pins, nwell_box=nwell_box, footprint=footprint)


def build(spec: LegSpec, outdir: Path | None = None) -> LegLayout:
    layout = build_leg(spec)
    if outdir is not None:
        outdir = Path(outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        layout.write_gds(outdir / f"{spec.top_cell}.gds")
    return layout
