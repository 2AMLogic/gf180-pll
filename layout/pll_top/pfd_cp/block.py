"""``pfd_cp`` -- the top-level PFD + charge-pump block: ``pfd`` (issue #300,
Part 2 of #294) assembled with the complete ``cp`` block (issue #385, Part
5a of this decomposition -- ``cp_output_stage`` + ``cp_dumpbuf``) into one
flat, standalone-DRC-clean block matching ``design/pfd_cp.sch``'s top-level
netlist (issue #386, Part 5b -- this is the increment that actually
satisfies #303's and #294's own acceptance criteria; Part 5a is a pure
prerequisite).

WHAT THIS BUILDS
-----------------
``design/pfd_cp.sch`` is just two component instances, ``xpfd`` (``pfd.sym``)
and ``xcp`` (``cp.sym``), wired:

===========  ========================================  =====
Net          Wiring                                     notes
===========  ========================================  =====
``REF``/``FB``  external inputs, ``xpfd`` only.
``UP``/``DN``   ``xpfd``'s outputs feed directly into ``xcp``'s
                ``UP``/``DN`` inputs.                    also brought out to
                                                          the top level "for
                                                          observation only"
                                                          (``design/pfd_cp.sch``'s
                                                          own header comment)
                                                          -- both are already
                                                          top-level pins
                                                          either way, so no
                                                          extra wiring is
                                                          needed for that.
``B0``/``B1``/``IBN``/``ICN``/``IBP``/``ICP``/``VOUT``
                external I/O, ``xcp`` only (straight
                through, no PFD-side wiring).
``VDD``/``VSS`` shared by both instances, tied together.
===========  ========================================  =====

So this block's own boundary pins are exactly :data:`BOUNDARY_PINS` -- the
13 ``ipin``/``iopin``/``opin`` nets ``design/pfd_cp.sch`` itself declares.

COMPOSITION: THE SAME GDS-LEVEL SCRATCH PATTERN ``cp.py`` ALREADY USES
-------------------------------------------------------------------------
``pfd.py`` does **not** subclass the shared ``layout/pll_top/_canvas.Canvas``
every other block in this package does -- it defines its own, separate
``rowgen.Canvas`` dataclass with a different API (``.rect()``/``.label()``/
``.shapes``/``.write_gds()``, but no ``.pin()`` and no ``.at()`` translation
context manager). So the in-process composition mechanism ``vco/block.py``
uses (``canvas.at(dx, dy)``) does not apply to ``pfd`` directly.

The tractable path -- and the one this module uses -- is the GDS-level
technique ``cp_output_stage.py``/``cp.py`` already established: write each
sub-block's own GDS to a scratch path, read it into one fresh
:class:`devgen.Canvas` via ``canvas.layout.read(...)``, place with
``db.CellInstArray``/``db.Trans``, then ``canvas.top.flatten(-1, True)`` --
followed by drawing the top-level ``UP``/``DN``/``VDD``/``VSS`` routing
directly on that shared, now-flat canvas. ``pfd``'s own GDS layer numbers
and ``dbu`` (0.001, ``rowgen.LAYER``) are identical to ``devgen.LAYER``'s,
so reading it into a ``devgen.Canvas``'s ``klayout.db.Layout`` needs no
layer remapping.

FINDING ``pfd``'s OWN PIN LOCATIONS
-------------------------------------
``pfd.py``'s ``PfdLayout`` (returned by ``build()``) does not expose a
``.pins`` dict -- what it exposes is ``.conductors``: every drawn conductor
shape, tagged by net (``(net, layer, x0, y0, x1, y1)`` -- the same model
``layout/tests/test_pfd_layout.py`` runs its own connectivity and no-short
checks on). :func:`_pfd_bus` and :func:`_pfd_rail_landing` below both filter
that list for the net in question, rather than re-deriving ``pfd.py``'s
internal placement/track-assignment order by hand.

REACHING EACH BLOCK'S NETS: THE NATIVE BUS EDGE, NEVER A SECOND VIA ON AN
EXISTING PAD
-----------------------------------------------------------------------------
Both sub-blocks are already fully mesh-routed internally. Landing a *second*
via stack on a pad that already carries one is the documented ``V1.1``/
``V2.1``/``M2.2a`` failure mode (``cp_output_stage.py``'s own "REACHING THE
ARRAY BLOCK'S NETS" section; ``cp.py``'s own module docstring, four routing
designs tried before the one that held). So every connection this module
draws reaches each side through a point that provably carries **no existing
Via2** yet:

* **``UP``/``DN``**: ``pfd``'s own Metal2 bus for each net (:func:`_pfd_bus`)
  never got a Metal3 riser inside ``pfd.py`` itself (that block's own
  internal routing is Metal1/Metal2 only). ``cp``'s own boundary pin for
  ``UP``/``DN`` is a raw Metal1 gate-tab pad (``cp_output_stage``'s own
  glue-inverter ``A`` input), *not* where this module reaches in -- instead
  it uses ``cp_output_stage``'s own Metal2 glue-bus for that net
  (``cp_layout.stage.glue_bus[net]``), at its ``x_lo`` edge. ``x_hi`` is
  where ``cp.py``'s own build() would have landed a riser *if* ``UP``/``DN``
  were in its ``NET_MAP`` -- they are not (``cp_dumpbuf`` has no such nets),
  so in practice neither edge is pre-occupied for these two nets; ``x_lo``
  is used for symmetry with ``VDD``/``VSS`` below, where it matters.
* **``VDD``/``VSS``**: these nets *are* two of ``cp.py``'s own six
  ``NET_MAP`` bridge nets, and ``cp.py``'s own build() already rose a Via2
  riser at ``glue_bus[net]``'s ``x_hi`` edge (linking ``cp_output_stage`` to
  ``cp_dumpbuf``). This module therefore reaches in at the *other* edge,
  ``x_lo`` -- a different point on the same continuous Metal2 bus, carrying
  no via of its own yet (the same "a chosen point on it, not the strip's
  own midpoint" convention ``cp_output_stage.py``'s own ``_riser_box`` uses
  for its rail taps). On ``pfd``'s own side, ``VDD``/``VSS`` are continuous
  Metal1 rails (``pfd.py``'s ``_draw_rails()``) with no Metal2 bus at all --
  any point along either rail is an equally valid landing point
  (:func:`_pfd_rail_landing`), chosen clear of both the periodic well/
  substrate taps and ``pfd``'s own row-to-row Metal3 stitches (which already
  carry a via stack of their own).

ROUTING: A METAL3 RISER AT EACH SIDE'S OWN NATIVE EDGE, JOINED BY A METAL2
TRUNK FAR ABOVE BOTH PLACED BLOCKS
-----------------------------------------------------------------------------
Same two-step technique as ``cp.py``'s own module docstring (which itself
records four earlier designs that failed, and why): a Metal3 riser straight
up from each side's own native edge/landing point -- no shared link column,
no long Metal2 "reach" across either block's own interior -- to a dedicated
per-net Metal2 trunk row, strictly above both placed blocks' own topmost
drawn edge (:data:`BACKBONE_MARGIN_UM` clear of it), then a plain Metal2
trunk joining the two risers' own trunk-row landings
(:func:`cp_output_stage._extend_bus`). Four distinct nets get four distinct
trunk rows (:data:`BACKBONE_PITCH_UM` apart) and four distinct riser
columns (on each side), so no two different nets' risers ever share an X
(the same invariant ``cp_output_stage.check_riser_columns()`` asserts
arithmetically for its own placement, here held by construction rather than
checked, since only four fixed points are involved rather than a device
row).

``VDD``/``VSS`` need one extra step ``UP``/``DN`` do not: ``pfd``'s own
landing point is Metal1, not Metal2, so this module uses
``cp_array._riser()`` (Metal1 pad -> Via1 -> Metal2 -> Via2 -> Metal3 ->
Via2 -> Metal2 trunk landing) in one call, rather than
``cp_output_stage._link_tracks()`` (Metal2 -> Via2 -> Metal3 -> Via2 ->
Metal2, no Via1) which ``UP``/``DN`` use on both sides and ``VDD``/``VSS``
use on the ``cp`` side.

CONNECTIVITY IS CHECKED, NOT ASSUMED
--------------------------------------
:meth:`PfdCpLayout.probe_pads` hands every conductor shape ``pfd`` drew
(one probe point per shape, since ``pfd.py`` records no separate per-net pad
dict) plus every landing pad ``cp`` believes is on each of its own nets
(translated into this block's shared frame) to :func:`netcheck.check_gds`,
which extracts the finished GDS's own Metal1-3 connectivity with KLayout.
That is what proves the four bridge/tie nets above really did connect
across the gap between the two placed blocks, and that nothing else
shorted in the process -- the same technique (and the same caveat: a clean
signoff DRC run cannot see a short or an open on its own) ``cp.py``'s own
module docstring states.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from . import cp, cp_array, devgen, netcheck, pfd
from . import cp_output_stage as cos

try:
    from .. import _canvas
except ImportError:  # this package's own dir (not its "pll_top" parent) is the
    # sys.path root under layout/tests's flat-import convention -- see
    # cp_array.py's own identical try/except for the full citation.
    import _canvas

try:
    from harness import spice_flatten
except ImportError:  # "layout/" itself (harness's own package root) is not
    # on sys.path under either of this module's two call conventions (the
    # flat `python3 -m pfd_cp.block` CLI, run with cwd/sys.path rooted at
    # layout/pll_top/; or layout/tests's own convention, which adds
    # layout/pll_top/ but only conditionally layout/ itself) -- same
    # "try the plain import, fall back to inserting the directory this
    # file's own path implies" shape as the ``_canvas`` import above, one
    # level further up (``parents[2]`` from this file is ``layout/``).
    import sys as _sys

    _LAYOUT_DIR = Path(__file__).resolve().parents[2]
    if str(_LAYOUT_DIR) not in _sys.path:
        _sys.path.insert(0, str(_LAYOUT_DIR))
    from harness import spice_flatten

TOP_CELL = "pfd_cp"

#: design/pfd_cp.sch's own P0-P12 pin declarations, in that order: REF/FB/
#: B0/B1 (ipin), IBN/ICN/IBP/ICP/VOUT (iopin), UP/DN (opin), VDD/VSS (iopin).
BOUNDARY_PINS: tuple[str, ...] = (
    "REF", "FB", "B0", "B1", "IBN", "ICN", "IBP", "ICP", "VOUT", "UP", "DN", "VDD", "VSS",
)

#: Net names shared verbatim between pfd's own probe set and cp's own probe
#: set -- exactly this block's own :data:`BOUNDARY_PINS`. Every *other* net
#: either sub-block's own ``probe_pads()`` names is private to that
#: sub-block (e.g. pfd's own ``UPB``/``DNB`` SR-latch outputs and
#: cp_output_stage's own ``UPB``/``DNB`` glue-inverter outputs are two
#: unrelated physical nets that happen to share a name by coincidence, not
#: PDK convention) -- see :meth:`PfdCpLayout.probe_pads`'s own docstring for
#: why merging those under one shared key would report a false split.
_SHARED_PROBE_NET_NAMES = frozenset(BOUNDARY_PINS)

#: xpfd's own UP/DN outputs feed directly into xcp's UP/DN inputs -- bridged
#: the same way cp.py's own NET_MAP bridges cp_output_stage <-> cp_dumpbuf,
#: except both sides already share one net name (design/pfd_cp.sch's own
#: xcp instance ties UP->UP, DN->DN -- no renaming).
BRIDGED_NETS: tuple[str, ...] = ("UP", "DN")

#: VDD/VSS are shared (tied) between the two instances -- also bridged, but
#: reached via a Metal1 rail landing on pfd's own side rather than a Metal2
#: bus edge (see _pfd_rail_landing()'s docstring).
RAIL_NETS: tuple[str, ...] = ("VDD", "VSS")

BLOCK_GAP_UM = cos.GLUE_GAP_UM
"""Horizontal clearance between pfd's own footprint (placed at the origin)
and cp's own footprint (placed to the right). Same value/rationale as
cp.py's own BLOCK_GAP_UM -- the routing itself needs no dedicated width in
this gap; it only keeps the two placed blocks' own drawn geometry from
touching (every riser lands at its own native edge, inside each block's own
footprint, and the trunk runs far above both footprints)."""

BACKBONE_MARGIN_UM = cos.CONN_COLUMN_MARGIN_UM
"""Vertical clearance from the taller of the two (placed) blocks' own
topmost drawn edge to the lowest Metal3 trunk row -- same value/rationale as
cp.py's own BACKBONE_MARGIN_UM."""

BACKBONE_PITCH_UM = cp_array.RISER_MIN_PITCH_UM
"""Y pitch between two different nets' own Metal2 trunk rows -- same
value/rationale as cp.py's own BACKBONE_PITCH_UM (parallel, non-touching
same-layer strips; the only thing that ever crosses between rows, a net's
own Metal3 riser, has no DRC relationship to a Metal2 row it merely passes
under)."""

RAIL_LANDING_INSET_UM: dict[str, float] = {"VDD": 3.0, "VSS": 6.0}
"""How far in from the right edge of pfd's own continuous VDD/VSS Metal1
rail (see :func:`_pfd_rail_landing`) each net's landing point sits.

Clear of pfd's own periodic well/substrate taps (out to ``rail_x1 - 1.0``,
``pfd.TAP_PITCH_UM``'s own placement bound) and its row-to-row VDD/VSS
Metal3 stitches (at ``rail_x1 - 0.6``/``rail_x1 - 1.6``,
``pfd.SUPPLY_LINK_INSET_UM``), both of which already carry a via stack of
their own. Two *different* insets (not one shared point) so the VDD and VSS
landing points -- independently chosen on two different rows' rails --
still land at two different X once both rise on Metal3 to their own,
separate trunk rows: landing both at the same X would put two different
nets' Metal3 risers on one column, the exact short
``cp_output_stage.check_riser_columns()`` guards against for its own
placement.
"""


def _pfd_bus(pfd_layout: "pfd.PfdLayout", net: str) -> tuple[float, float, float]:
    """``(track_y, x_lo, x_hi)`` of ``net``'s own routed Metal2 bus in
    ``pfd``'s own standalone build, read directly off ``PfdLayout.conductors``
    (see module docstring) -- the union bounding box of every Metal2 shape on
    that net, which coincides exactly with the bus rectangle ``pfd.py``'s own
    ``_draw_net()`` drew (every Via1 landing square on the net is a subset of
    that rectangle).
    """
    boxes = [
        (x0, y0, x1, y1)
        for n, layer, x0, y0, x1, y1 in pfd_layout.conductors
        if n == net and layer == "metal2"
    ]
    if not boxes:
        raise ValueError(f"pfd: net {net!r} has no Metal2 shapes")
    x_lo = min(b[0] for b in boxes)
    x_hi = max(b[2] for b in boxes)
    track_y = (min(b[1] for b in boxes) + max(b[3] for b in boxes)) / 2.0
    return (track_y, x_lo, x_hi)


def _pfd_bus_box(pfd_layout: "pfd.PfdLayout", net: str) -> tuple[float, float, float, float]:
    """The real drawn Metal2 bus box for ``net`` (see :func:`_pfd_bus`) --
    handed to :func:`devgen.Canvas.pin` as this block's own boundary pin
    geometry for ``UP``/``DN``."""
    track_y, x_lo, x_hi = _pfd_bus(pfd_layout, net)
    half = cp_array.METAL2_WIRE_WIDTH_UM / 2.0
    return (x_lo, track_y - half, x_hi, track_y + half)


def _pfd_rail_landing(pfd_layout: "pfd.PfdLayout", net: str, inset: float) -> tuple[float, float]:
    """A landing point ``inset`` um in from the right edge of ``net``'s own
    continuous Metal1 rail in ``pfd``'s own standalone build.

    ``VDD``/``VSS`` are drawn as continuous Metal1 rails (``pfd.py``'s own
    ``_draw_rails()``), not single pads -- any point along either rail is an
    equally valid landing point (the same "the ring's Metal1 is continuous"
    convention ``vco/block.py``'s own guard-ring strap uses). The rail's own
    *widest* Metal1 box on this net is that continuous strip (every other
    Metal1 box on the net is a small per-tap or per-stitch pad, all much
    narrower) -- see module docstring / :data:`RAIL_LANDING_INSET_UM` for why
    ``inset`` matters.
    """
    boxes = [
        (x0, y0, x1, y1)
        for n, layer, x0, y0, x1, y1 in pfd_layout.conductors
        if n == net and layer == "metal1"
    ]
    if not boxes:
        raise ValueError(f"pfd: net {net!r} has no Metal1 shapes")
    main = max(boxes, key=lambda b: b[2] - b[0])
    return (main[2] - inset, (main[1] + main[3]) / 2.0)


@dataclass
class PfdCpLayout:
    canvas: devgen.Canvas
    footprint: tuple[float, float, float, float]
    pins: dict[str, list[tuple[float, float, float, float]]]
    pfd: "pfd.PfdLayout"
    cp: cp.CpLayout
    cp_offset: tuple[float, float]
    trunk_rows: dict[str, float] = field(default_factory=dict)

    def write_gds(self, path) -> None:
        self.canvas.write_gds(path)

    def probe_pads(self) -> dict[str, list[tuple[float, float, float, float]]]:
        """``net -> [Metal1 landing box, ...]`` for every point either
        sub-block believes is on that net, ``cp``'s own pads translated into
        this block's shared coordinate frame -- handed to
        :func:`netcheck.check_gds` to prove the composition itself
        introduced no short and no open (see module docstring).

        ``pfd``'s own ``PfdLayout`` has no ``probe_pads()`` of its own --
        its connectivity model is the plain ``conductors`` list, not a
        per-net pad dict -- so this method builds pfd's own probe set
        directly from that list instead, one probe point per drawn
        conductor shape (which ``layout/tests/test_pfd_layout.py`` already
        proves catches pfd's own shorts/opens). Restricted to ``metal1``
        shapes only: ``netcheck.check_gds`` always probes on
        ``netcheck.PROBE_LAYER`` ("metal1"), so a Metal2/Metal3 conductor's
        own box centre is not a meaningful probe point -- that point often
        has no Metal1 underneath it at all (``unresolved``), and on the rare
        coordinate where it does, that Metal1 belongs to whatever real net
        physically sits there, not necessarily the Metal2/Metal3 shape's own
        net -- a false short with no bearing on this block's own wiring.

        Every net name outside :data:`_SHARED_PROBE_NET_NAMES` is namespaced
        by which sub-block drew it (``pfd.``/``cp.`` prefix) before being
        merged. ``pfd``'s own internal ``UPB``/``DNB`` (the SR-latch outputs)
        and ``cp_output_stage``'s own internal ``UPB``/``DNB`` (the glue
        inverters' own outputs) are two unrelated physical nets that happen
        to share a name -- each sub-block picked it independently, with no
        shared naming authority between them (unlike this block's own
        boundary nets, which both come from ``design/pfd_cp.sch``'s single
        netlist). Merging them under one key would make
        :func:`netcheck.check_gds` report a false ``split`` (one probed
        "net" landing on two unconnected components) with no bearing on
        this block's own wiring -- reproduced during this module's own
        development.
        """
        pads: dict[str, list[tuple[float, float, float, float]]] = {}
        for net, layer, x0, y0, x1, y1 in self.pfd.conductors:
            if layer != "metal1":
                continue
            key = net if net in _SHARED_PROBE_NET_NAMES else f"pfd.{net}"
            pads.setdefault(key, []).append((x0, y0, x1, y1))
        dx, dy = self.cp_offset
        for net, boxes in self.cp.probe_pads().items():
            key = net if net in _SHARED_PROBE_NET_NAMES else f"cp.{net}"
            pads.setdefault(key, []).extend(cp_array._translate_box(box, dx, dy) for box in boxes)
        return pads


def build(outdir: Path | None = None) -> PfdCpLayout:  # noqa: PLR0915 -- one linear assembly
    import klayout.db as db  # noqa: PLC0415 -- lazy, same convention as every module in this package

    pfd_layout = pfd.build()
    cp_layout = cp.build()

    canvas = devgen.Canvas(TOP_CELL)

    with tempfile.TemporaryDirectory() as tmp:
        pfd_gds = Path(tmp) / f"{pfd.TOP_CELL}.gds"
        cp_gds = Path(tmp) / f"{cp.TOP_CELL}.gds"
        pfd_layout.write_gds(pfd_gds)
        cp_layout.write_gds(cp_gds)

        # --- place cp far enough right that its own footprint never
        # overlaps pfd's own (BLOCK_GAP_UM's own docstring). dy aligns the
        # two blocks' own footprint bottoms purely for a tidy combined bbox;
        # nothing depends on it. ---
        dx = pfd_layout.footprint()[2] - cp_layout.footprint[0] + BLOCK_GAP_UM
        dy = pfd_layout.footprint()[1] - cp_layout.footprint[1]

        dbu_per_um = int(round(1.0 / canvas.dbu))

        def _place(index, x: float, y: float) -> None:
            trans = db.Trans(db.Vector(int(round(x * dbu_per_um)), int(round(y * dbu_per_um))))
            canvas.top.insert(db.CellInstArray(index, trans))

        canvas.layout.read(str(pfd_gds))
        canvas.layout.read(str(cp_gds))
        pfd_index = canvas.layout.cell_by_name(pfd.TOP_CELL)
        cp_index = canvas.layout.cell_by_name(cp.TOP_CELL)
        _place(pfd_index, 0.0, 0.0)
        _place(cp_index, dx, dy)
        canvas.top.flatten(-1, True)

    # --- Metal2 trunk rows: one dedicated Y per bridged/tied net, strictly
    # above every routing channel either placed block already uses on its
    # own (including cp's own internal array<->glue and
    # stage<->dumpbuf trunk rows, all below cp_footprint_g[3]). ---
    cp_footprint_g = cp_array._translate_box(cp_layout.footprint, dx, dy)
    trunk_base_y = max(pfd_layout.footprint()[3], cp_footprint_g[3]) + BACKBONE_MARGIN_UM
    bridge_nets = (*BRIDGED_NETS, *RAIL_NETS)
    trunk_rows = {net: trunk_base_y + i * BACKBONE_PITCH_UM for i, net in enumerate(bridge_nets)}

    # --- UP/DN: pfd's own native Metal2 bus edge <-> cp's own native Metal2
    # glue-bus edge (x_lo -- see module docstring for why x_lo, not x_hi).
    # Same Riser+Trunk technique as cp.py's own build(). ---
    for net in BRIDGED_NETS:
        trunk_y = trunk_rows[net]

        p_track_y, p_x_lo, p_x_hi = _pfd_bus(pfd_layout, net)
        # Of the bus's own two native edges, rise from whichever sits
        # farther from the mirror axis (AXIS_X = 0.0). pfd.py's own RB/NRST
        # row-to-row Metal3 links land close to the axis (x in [-1.52,
        # -1.08] and [-0.22, 0.22] respectively -- reproduced directly
        # during this module's own development: UP's own near-axis edge
        # (x_hi = -1.08) sits exactly on NRST's own link column, a real
        # Metal3 short). The far edge is clear of both by construction: the
        # branch chains (where each net's own far-edge lane lives) are well
        # outboard of the axis-straddling reset NAND/delay-row nets.
        p_riser_x = p_x_lo if abs(p_x_lo) > abs(p_x_hi) else p_x_hi
        cos._link_tracks(canvas, p_riser_x, p_track_y, trunk_y)

        c_track_y, c_x_lo, _c_x_hi = cp_layout.stage.glue_bus[net]
        c_x_lo_g, c_track_y_g = c_x_lo + dx, c_track_y + dy
        cos._link_tracks(canvas, c_x_lo_g, c_track_y_g, trunk_y)

        cos._extend_bus(canvas, trunk_y, p_riser_x, c_x_lo_g)

    # --- VDD/VSS: a fresh full riser (Metal1 -> Via1 -> Metal2 -> Via2 ->
    # Metal3 -> Via2 -> Metal2) from a clear point on pfd's own continuous
    # rail, <-> cp's own native glue-bus edge (x_lo, same "already-occupied
    # x_hi" reasoning as UP/DN's own choice -- see module docstring). ---
    for net in RAIL_NETS:
        trunk_y = trunk_rows[net]

        p_x, p_y = _pfd_rail_landing(pfd_layout, net, RAIL_LANDING_INSET_UM[net])
        cp_array._riser(canvas, p_x, p_y, trunk_y)

        c_track_y, c_x_lo, _c_x_hi = cp_layout.stage.glue_bus[net]
        c_x_lo_g, c_track_y_g = c_x_lo + dx, c_track_y + dy
        cos._link_tracks(canvas, c_x_lo_g, c_track_y_g, trunk_y)

        cos._extend_bus(canvas, trunk_y, p_x, c_x_lo_g)

    # --- boundary pins. REF/FB are pfd-only; B0/B1/IBN/ICN/IBP/ICP/VOUT are
    # cp-only, straight through; UP/DN/VDD/VSS are the bridged/tied nets --
    # pinned on pfd's own side (an arbitrary but valid choice: both sides are
    # now the same electrical net, proven by netcheck below). ---
    for net in ("REF", "FB"):
        boxes = [
            (x0, y0, x1, y1)
            for n, layer, x0, y0, x1, y1 in pfd_layout.conductors
            if n == net and layer == "metal1"
        ]
        canvas.pin(net, *boxes[0])
    for net in ("B0", "B1", "IBN", "ICN", "IBP", "ICP", "VOUT"):
        canvas.pin(net, *cp_array._translate_box(cp_layout.pins[net][0], dx, dy))
    for net in BRIDGED_NETS:
        canvas.pin(net, *_pfd_bus_box(pfd_layout, net))
    for net in RAIL_NETS:
        p_x, p_y = _pfd_rail_landing(pfd_layout, net, RAIL_LANDING_INSET_UM[net])
        half = cp_array.VIA1_SIZE_UM / 2.0 + cp_array.VIA_ENCLOSURE_UM
        canvas.pin(net, p_x - half, p_y - half, p_x + half, p_y + half)

    footprint = _canvas.bbox_union(
        (
            pfd_layout.footprint(),
            cp_footprint_g,
            (
                pfd_layout.footprint()[0],
                pfd_layout.footprint()[1],
                cp_footprint_g[2],
                trunk_base_y + len(bridge_nets) * BACKBONE_PITCH_UM,
            ),
        )
    )

    layout = PfdCpLayout(
        canvas=canvas,
        footprint=footprint,
        pins=canvas.pins,
        pfd=pfd_layout,
        cp=cp_layout,
        cp_offset=(dx, dy),
        trunk_rows=dict(trunk_rows),
    )
    if outdir is not None:
        outdir = Path(outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        layout.write_gds(outdir / f"{TOP_CELL}.gds")
    return layout


#: The per-record ``design/netlist.sh --top pfd_cp <outdir>`` export, frozen
#: verbatim under this block's own evidence directory (issue #440) -- the
#: same "freeze the per-record export, do not commit a
#: ``design/netlist/pfd_cp.spice`` that does not exist by this convention"
#: discipline ``sim/*/netlist-snapshots/`` already uses, per
#: ``design/netlist.sh``'s own header comment ("PER-RECORD (pfd_cp) ... is
#: deliberately NOT committed[; instead] each evidence record freezes its
#: own copy"). Regenerate with:
#:
#:     ./design/netlist.sh --top pfd_cp <tmpdir>
#:     cp <tmpdir>/dut.spice layout/evidence/pfd-cp-layout/lvs-clean/pfd_cp.schematic-export.spice
#:
#: -- only if ``design/pfd_cp.sch`` (or a cell it instantiates) actually
#: changes; this file is a frozen snapshot, not regenerated on every call.
SCHEMATIC_EXPORT_PATH = (
    Path(__file__).resolve().parents[2]
    / "evidence"
    / "pfd-cp-layout"
    / "lvs-clean"
    / "pfd_cp.schematic-export.spice"
)


def reference_netlist() -> str:
    """This block's own flattened LVS reference netlist (issue #440).

    Mechanically flattened (:mod:`harness.spice_flatten`) from
    :data:`SCHEMATIC_EXPORT_PATH` -- the frozen ``design/netlist.sh --top
    pfd_cp`` export of ``design/pfd_cp.sch``'s own full nine-``.subckt``
    hierarchy (``pfd_cp`` -> ``pfd``/``cp`` -> ``edgedet``/``srlatch``/
    ``cp_leg_n``/``cp_leg_p``/``cp_dumpbuf`` -> ``pfdcp_inv_3v3``/
    ``pfdcp_nand2_3v3``) -- not a hand transcription: every device size and
    connection below traces directly to that frozen export's own text, via
    a generic, unit-tested flattener (:mod:`layout.tests.test_spice_flatten`)
    rather than a fresh 168-transistor-by-hand re-derivation. See
    ``spice_flatten``'s own module docstring for *why* a flat reference is
    needed at all (gf180mcu's LVS deck does not flatten a hierarchical
    reference to match this block's own flat GDS on its own -- the same
    finding ``divider_chain.py``'s ``reference_netlist()`` already recorded
    for that block).

    Top-level ports are exactly :data:`BOUNDARY_PINS`' own order (the frozen
    export's own ``.subckt pfd_cp REF FB B0 B1 IBN ICN IBP ICP VOUT UP DN
    VDD VSS`` line), matching every boundary pin this module's own
    :func:`build` already pins under that name.
    """
    text = SCHEMATIC_EXPORT_PATH.read_text()
    return spice_flatten.flatten_text(text, TOP_CELL)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    default_outdir = Path(__file__).resolve().parents[2] / "evidence" / "pfd-cp-layout" / "work"
    parser.add_argument("--outdir", default=str(default_outdir))
    parser.add_argument(
        "--no-netcheck",
        action="store_true",
        help="skip the Metal1-3 connectivity check (see netcheck.py)",
    )
    args = parser.parse_args()
    outdir = Path(args.outdir)
    layout = build(outdir)
    netlist_path = outdir / f"{TOP_CELL}.spice"
    netlist_path.write_text(reference_netlist())
    x0, y0, x1, y1 = layout.footprint
    print(f"wrote {outdir}/{TOP_CELL}.gds")
    print(f"wrote {netlist_path}")
    print(f"footprint: {x1 - x0:.3f} x {y1 - y0:.3f} um  ({(x1 - x0) * (y1 - y0):.2f} um^2)")
    print(f"cp offset: {layout.cp_offset}")
    print(f"trunk rows: {layout.trunk_rows}")
    print(f"boundary pins: {sorted(layout.pins)}")
    if args.no_netcheck:
        return 0
    report = netcheck.check_gds(
        outdir / f"{TOP_CELL}.gds", TOP_CELL, netcheck.pad_probe_points(layout.probe_pads())
    )
    print(report.summary())
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
