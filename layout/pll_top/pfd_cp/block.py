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

THE FOLD: ``pfd`` GOES *INSIDE* ``cp``'s OWN EMPTY BAND, NOT BESIDE IT
-----------------------------------------------------------------------
Through issue #386 this module placed ``pfd`` at the origin and ``cp``
:data:`BLOCK_GAP_UM` to its right, which added ``pfd``'s full 80.90 um of
width to a block whose height was set entirely by ``cp``. The column that
bought was 21.0 % filled, and the 58.24 um of it above ``pfd`` was 2.2 %
filled: 4,712 um^2 of nothing, paid for at full price.

``cp`` has a hole of its own exactly big enough. ``cp_dumpbuf`` (211.10 x
36.00 um) sits beside the much taller ``cp_output_stage`` (130.31 x 66.73
um), so the band above the dump buffer -- 217.10 x 38.72 um, 8,407 um^2 --
is **99.0 % empty**: the only things ``cp`` draws in it are its own six
Metal2 backbone trunk rows and the six Metal3 risers those land on, all of
which stop at ``cp_dumpbuf``'s own native bus edge near the *left* wall of
the band. ``pfd`` is 1,819 um^2 and fits there with room to spare.

So since issue #455 ``cp`` is the block that lands at a zero offset and
``pfd`` is the one that is translated, into that band:

* **horizontally**, :data:`BLOCK_GAP_UM` clear of the rightmost thing ``cp``
  draws above ``cp_dumpbuf`` -- *measured* off ``cp``'s own finished GDS
  (:func:`_cp_band_right_edge`), not re-derived, because the quantity in
  question is ``cp.py``'s own ``d_riser_x`` and that is local to its
  ``build()``;
* **vertically**, :data:`BLOCK_GAP_UM` above ``cp_dumpbuf``'s own topmost
  drawn edge.

The result is a block exactly as wide as ``cp`` itself (347.41 um, down from
434.31) with no change in height, and :func:`build` raises rather than
returning a *larger* block if ``pfd`` ever stops fitting inside ``cp``'s own
extent. The one property the fold costs: this module's own four trunks are
now long runs from ``cp_output_stage``'s glue bus, on the far left, out to
``pfd``'s riser columns on the right. They are still drawn strictly above
every row either sub-block drew, which is the property that makes a trunk
safe (see ROUTING below) -- length is not what made the four failed designs
in ``cp.py``'s own docstring fail.

**Why the trunk band could not simply be merged into ``cp``'s.** ``cp``'s own
six backbone rows and this module's own four trunks are x-disjoint enough,
*before* the fold, to have been interval-graph-coloured into ``cp``'s six
existing rows for free -- with ``pfd`` on the left, the four trunks run x
[-14, +97] and ``cp``'s six rows run x [86, 189], and a four-colouring of
that interval graph exists. The fold destroys it: every one of this module's
trunks then spans from ``cp_output_stage``'s glue bus (x ~ -17) out to
``pfd``'s riser columns (x ~ 120-200), covering all six of ``cp``'s rows.
The two levers genuinely do not compose -- and they are not worth the same.
Taking the row-sharing alone leaves the block 434.31 um wide and 73.23 um
tall (31,803 um^2); taking the fold alone leaves it 347.41 x 80.73 um
(28,045 um^2); the fold plus a trunk band merely *continued* above ``cp``'s
own top row, which is what :func:`build` does, gives 347.41 x 76.23 um
(26,481 um^2). So the four rows stay their own four rows, one track pitch
above ``cp``'s highest instead of a full :data:`BACKBONE_MARGIN_UM` above
``cp``'s footprint. (All three figures are as of #455. Issue #469 then
packed ``cp_output_stage``'s own glue band one track tighter and issue #473
interleaved that block's glue inverters with the switches they drive for
three more, which this block inherits whole: 76.23 -> 75.48 -> 73.23 um.)

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

The fold (above) adds one more thing of this kind to stay clear of, on the
``pfd`` side rather than the ``cp`` side: all four of this module's
``pfd``-side riser columns sit inside ``pfd``'s own translated footprint,
which the fold puts to the *right* of ``cp``'s own six dumpbuf-side Metal3
riser columns. :func:`_cp_band_right_edge` is what guarantees the two sets
never meet -- it is the rightmost extent of everything ``cp`` draws above
``cp_dumpbuf``, which is precisely those risers and the trunk rows they
land on, and ``pfd`` starts :data:`BLOCK_GAP_UM` past it.

ROUTING: A METAL3 RISER AT EACH SIDE'S OWN NATIVE EDGE, JOINED BY A METAL2
TRUNK FAR ABOVE BOTH PLACED BLOCKS
-----------------------------------------------------------------------------
Same two-step technique as ``cp.py``'s own module docstring (which itself
records four earlier designs that failed, and why): a Metal3 riser straight
up from each side's own native edge/landing point -- no shared link column,
no long Metal2 "reach" across either block's own interior -- to a dedicated
per-net Metal2 trunk row, above every row either placed block drew, then a
plain Metal2 trunk joining the two risers' own trunk-row landings
(:func:`cp_output_stage._extend_bus`). Four distinct nets get four distinct
trunk rows (:data:`BACKBONE_PITCH_UM` apart) and four distinct riser
columns (on each side), so no two different nets' risers ever share an X
(the same invariant ``cp_output_stage.check_riser_columns()`` asserts
arithmetically for its own placement, here held by construction rather than
checked, since only four fixed points are involved rather than a device
row).

**"Above" is measured against ``cp``'s own top *row*, not its footprint**
(issue #455). ``cp``'s topmost drawn edge *is* the top row of its own Metal2
backbone band, and what one more row of the same band needs above it is one
track pitch, not a block-to-block margin: the two are parallel, non-touching
same-layer strips, exactly as ``cp``'s own six rows are to each other. The
old ``max(pfd_top, cp_top) + BACKBONE_MARGIN_UM`` rule spent 2.00 um of
block height restating a clearance ``cp`` had already applied once, on top
of the 0.25 um per row both modules were losing to a Metal3 *column* pitch
misapplied as a Metal2 *row* pitch (see :data:`cp.BACKBONE_PITCH_UM`).
:data:`BACKBONE_MARGIN_UM` still applies to ``pfd``, whose top is not a
trunk row -- post-fold it sits low enough in ``cp``'s band that it never
binds, but the rule is stated rather than assumed.

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
"""Clearance between pfd's own drawn geometry and the nearest geometry cp
draws, on both axes (issue #455 folded pfd into cp's own empty band, so this
is now a vertical clearance above cp_dumpbuf as well as a horizontal one
clear of cp's own dumpbuf-side riser columns). Same value/rationale as
cp.py's own BLOCK_GAP_UM -- the routing itself needs no dedicated width in
this gap; it only keeps the two placed blocks' own drawn geometry from
touching (every riser lands at its own native edge, inside each block's own
footprint, and the trunk runs above both footprints)."""

BACKBONE_MARGIN_UM = cos.CONN_COLUMN_MARGIN_UM
"""Vertical clearance from a placed block's own topmost drawn edge to the
lowest Metal3 trunk row, for a block whose own top is *not* already a trunk
row -- same value/rationale as cp.py's own BACKBONE_MARGIN_UM.

Since issue #455 this only ever binds against ``pfd``, which the fold puts
low enough that it never does. Against ``cp`` the binding constraint is
:data:`BACKBONE_PITCH_UM`, not this: cp's own topmost drawn edge *is* the
top row of its own Metal2 trunk band, and one more row of the same band at
the same pitch needs a track pitch above it, not a block-to-block margin.
See :func:`build`."""

BACKBONE_PITCH_UM = cp.BACKBONE_PITCH_UM
"""Y pitch between two different nets' own Metal2 trunk rows -- deliberately
*the same object* as cp.py's own BACKBONE_PITCH_UM, not a second constant
that happens to agree, because since issue #455 this block's own trunk rows
continue cp's own band at cp's own pitch rather than starting a fresh band
above it. Two independent constants that silently drifted apart would put
this block's lowest row a fraction of a micron from cp's highest one."""

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


def _cp_band_right_edge(layout, cell, y_floor: float) -> float:
    """The rightmost x of any shape ``cp`` draws strictly above ``y_floor``,
    read off ``cp``'s own finished (flat) GDS as read into ``layout``.

    This is the left wall of the empty band issue #455 folds ``pfd`` into,
    measured rather than re-derived. Above ``cp_dumpbuf``'s own topmost drawn
    edge ``cp`` draws exactly three things: ``cp_output_stage`` (whose own
    footprint ends well to the left), its six Metal2 backbone trunk rows, and
    the six Metal3 risers those rows land on at ``cp_dumpbuf``'s side. The
    last two share one right-hand extreme -- ``cp.py``'s own ``d_riser_x``,
    which is ``cp_dumpbuf``'s own native bus edge stepped left by
    ``cp.DUMPBUF_REACH_MARGIN_UM`` -- and ``cp.py`` exposes neither, because
    both are local to its ``build()``'s routing loop.

    Measuring the finished cell is the same "read the geometry back out of
    its own finished GDS" convention :func:`cp._dumpbuf_bus_track` already
    established for the mirror-image problem one level down, and for the same
    reason: it needs no cooperation from -- and cannot drift out of sync with
    -- ``cp.py``'s own implementation.

    ``y_floor`` is compared against each shape's own *top*, so a shape that
    merely reaches up to the floor (``cp_dumpbuf``'s own topmost geometry,
    which defines it) is excluded and the band's own wall is not mistaken for
    the block's full width.
    """
    dbu = layout.dbu
    floor_dbu = int(round((y_floor + 1e-6) / dbu))
    right = None
    for layer_index in layout.layer_indexes():
        for shape in cell.shapes(layer_index).each():
            box = shape.bbox()
            if box.empty() or box.top <= floor_dbu:
                continue
            if right is None or box.right > right:
                right = box.right
    if right is None:
        raise ValueError(f"cp: no geometry at all above y={y_floor}")
    return right * dbu


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
    #: Where ``cp`` was placed. ``(0.0, 0.0)`` since issue #455 folded ``pfd``
    #: into ``cp``'s own empty band -- ``cp`` is now the block that lands at a
    #: zero offset, so every coordinate ``cp.py`` itself records (its own
    #: ``footprint``/``pins``/``backbone_rows``/``stage.glue_bus``) stays valid
    #: unmodified in this block's own frame. Kept as a field rather than
    #: dropped: it is what :meth:`probe_pads` and the boundary-pin promotion
    #: translate by, and pinning it to a literal zero in those call sites
    #: would hide the assumption instead of stating it.
    cp_offset: tuple[float, float]
    #: Where ``pfd`` was placed -- inside ``cp``'s own band above
    #: ``cp_dumpbuf`` (issue #455). See :func:`build`.
    pfd_offset: tuple[float, float] = (0.0, 0.0)
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
        pdx, pdy = self.pfd_offset
        for net, layer, x0, y0, x1, y1 in self.pfd.conductors:
            if layer != "metal1":
                continue
            key = net if net in _SHARED_PROBE_NET_NAMES else f"pfd.{net}"
            pads.setdefault(key, []).append((x0 + pdx, y0 + pdy, x1 + pdx, y1 + pdy))
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

        dbu_per_um = int(round(1.0 / canvas.dbu))

        def _place(index, x: float, y: float) -> None:
            trans = db.Trans(db.Vector(int(round(x * dbu_per_um)), int(round(y * dbu_per_um))))
            canvas.top.insert(db.CellInstArray(index, trans))

        canvas.layout.read(str(pfd_gds))
        canvas.layout.read(str(cp_gds))
        pfd_index = canvas.layout.cell_by_name(pfd.TOP_CELL)
        cp_index = canvas.layout.cell_by_name(cp.TOP_CELL)

        # --- THE FOLD (issue #455). cp lands at a zero offset; pfd is placed
        # inside cp's own empty band above cp_dumpbuf, not beside cp. See the
        # module docstring's "THE FOLD" section for the measurement. ---
        dx, dy = 0.0, 0.0
        dumpbuf_top = cp_array._translate_box(
            cp_layout.dumpbuf.footprint, *cp_layout.dumpbuf_offset
        )[3] + dy
        band_x0 = _cp_band_right_edge(canvas.layout, canvas.layout.cell(cp_index), dumpbuf_top)
        pfd_dx = (band_x0 + BLOCK_GAP_UM) - pfd_layout.footprint()[0]
        pfd_dy = (dumpbuf_top + BLOCK_GAP_UM) - pfd_layout.footprint()[1]

        _place(pfd_index, pfd_dx, pfd_dy)
        _place(cp_index, dx, dy)
        canvas.top.flatten(-1, True)

    pfd_box_g = cp_array._translate_box(pfd_layout.footprint(), pfd_dx, pfd_dy)
    cp_footprint_g = cp_array._translate_box(cp_layout.footprint, dx, dy)
    # Fail loud rather than silently give back a block that is taller or
    # wider than the one the fold set out to shrink: the whole point of
    # placing pfd in this band is that the band already exists, so pfd must
    # fit inside cp's own extent on both axes. (Its *height* has one micron
    # of subtlety -- the band's ceiling is cp's own backbone band, whose
    # rows stop well to the left of pfd's own column -- so the test is
    # against cp's footprint, the quantity the block's own bbox is made of.)
    if pfd_box_g[2] > cp_footprint_g[2] or pfd_box_g[3] > cp_footprint_g[3]:
        raise ValueError(
            f"pfd {pfd_box_g} does not fit inside cp's own band {cp_footprint_g} -- "
            "the fold would grow the block rather than shrink it"
        )
    # Both sub-blocks label their own boundary nets for their own standalone
    # LVS claims, and ``pfd`` additionally labels its own VDD/VSS rails once
    # per row. This level owns this block's 13 boundary-pin names and draws
    # every one of them below; anything inherited is at best a duplicate and
    # at worst names the wrong net (issue #440) -- see
    # _canvas.Canvas.clear_inherited_labels().
    canvas.clear_inherited_labels()

    # --- Metal2 trunk rows: one dedicated Y per bridged/tied net, above
    # every routing channel either placed block already uses on its own
    # (including cp's own internal array<->glue and stage<->dumpbuf trunk
    # rows). Since issue #455 these four rows *continue cp's own backbone
    # band* at cp's own pitch instead of starting a fresh band a full
    # BACKBONE_MARGIN_UM above it: cp's topmost drawn edge is the top row of
    # that band, and what one more row of the same band needs above it is a
    # track pitch, not a block-to-block margin. BACKBONE_MARGIN_UM still
    # binds against pfd, which (post-fold) sits far below and never does. ---
    trunk_base_y = max(
        max(cp_layout.backbone_rows.values()) + dy + BACKBONE_PITCH_UM,
        pfd_box_g[3] + BACKBONE_MARGIN_UM,
    )
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
        p_riser_x = (p_x_lo if abs(p_x_lo) > abs(p_x_hi) else p_x_hi) + pfd_dx
        cos._link_tracks(canvas, p_riser_x, p_track_y + pfd_dy, trunk_y)

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
        p_x, p_y = p_x + pfd_dx, p_y + pfd_dy
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
        canvas.pin(net, *cp_array._translate_box(boxes[0], pfd_dx, pfd_dy))
    for net in ("B0", "B1", "IBN", "ICN", "IBP", "ICP", "VOUT"):
        canvas.pin(net, *cp_array._translate_box(cp_layout.pins[net][0], dx, dy))
    for net in BRIDGED_NETS:
        # Metal2 geometry, so the label goes on the Metal2 *pin* purpose
        # (36/10), not Metal1's (34/10). A 34/10 text here attaches to
        # whatever Metal1 lies under the bus -- which for both UP and DN is
        # pfd's own RB row-0 bus, extracting it as ``DN,UP`` and leaving the
        # real UP/DN nets anonymous (issue #440).
        canvas.pin(
            net,
            *cp_array._translate_box(_pfd_bus_box(pfd_layout, net), pfd_dx, pfd_dy),
            layer="metal2_label",
        )
    for net in RAIL_NETS:
        p_x, p_y = _pfd_rail_landing(pfd_layout, net, RAIL_LANDING_INSET_UM[net])
        p_x, p_y = p_x + pfd_dx, p_y + pfd_dy
        half = cp_array.VIA1_SIZE_UM / 2.0 + cp_array.VIA_ENCLOSURE_UM
        canvas.pin(net, p_x - half, p_y - half, p_x + half, p_y + half)

    footprint = _canvas.bbox_union(
        (
            pfd_box_g,
            cp_footprint_g,
            (
                cp_footprint_g[0],
                cp_footprint_g[1],
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
        pfd_offset=(pfd_dx, pfd_dy),
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
