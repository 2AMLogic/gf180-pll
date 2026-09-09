"""Shared ``klayout.db`` layout/cell wrapper for ``layout/pll_top/*`` submodules
(issue #317).

``lock_detector/primitives.py``, ``vco/primitives.py``, and ``pfd_cp/devgen.py``
each independently defined a byte-for-byte-identical ``Canvas`` dataclass (plus
its ``_r()`` rounding helper) -- acknowledged duplication, not accidental: two
of the three docstrings already cross-referenced each other and this package
as "the same convention". This module gives that convention one shared home.

``klayout.db`` is imported lazily (inside ``__post_init__``), so any caller
that only touches a submodule's plain-Python placement math or ``devices.py``
constants stays importable with no PV environment.

The only real per-module deltas, factored out as class attributes a subclass
overrides rather than constructor arguments (so each submodule's own
``Canvas`` keeps its original single-``top_name``-argument call signature,
e.g. ``Canvas("some_top_cell")``, unchanged for every existing call site and
test):

* ``LAYER`` -- the GDS layer table; differs per submodule (each draws a
  different subset of the PDK's layers).
* ``GRID_UM`` -- an optional manufacturing-grid snap step for ``_u()``.
  Only ``vco/primitives.py`` sets this (to ``devices.LAYOUT_GRID_UM``);
  everywhere else it stays ``None`` (no snapping, the original plain
  micron -> dbu rounding).
* ``PIN_LAYER`` -- the default layer ``pin()`` labels a net on. Every
  submodule but ``pfd_cp/devgen.py`` uses the drawing layer ``"metal1"``;
  ``pfd_cp/devgen.py`` uses ``"metal1_label"`` (34/10), the *purpose* layer
  gf180mcu's own LVS deck actually reads net names from. ``vco/primitives.py``
  additionally exposes a per-call ``layer`` override on ``pin()``, which
  composes with this default: an explicit ``layer=...`` argument wins,
  otherwise ``PIN_LAYER`` applies.

``at()`` (the block-assembly translation ``vco/block.py`` places its five
sub-block generators with, issue #293) lives here rather than in
``vco/primitives.py``, because it is generic placement plumbing rather than a
VCO-specific rule: assembling separately-written sub-block generators into one
flat top cell is what every block-level generator in this package will need.
It costs nothing to inherit -- the offset is ``(0, 0)`` for any caller that
never opens the context manager, so every existing standalone build is
byte-identical.

``bbox_union()``, ``_contact_positions()``, ``_via_square()``, and
``_riser()`` (issue #332, a follow-up to #317/#328's ``Canvas``/``_r()``
consolidation) are free functions rather than ``Canvas`` methods, matching
each submodule's original convention: each was independently re-authored
per ``layout/pll_top/*`` submodule with identical (or, for
``_contact_positions()``, near-identical) bodies. ``_contact_positions()``
and ``_riser()`` take their caller's own CO.1/via/wire-size constants as
explicit keyword arguments rather than hardcoding a shared value here, so
each submodule keeps deriving them from its own
``CONTACT_SIZE_UM``/``CONTACT_PITCH_UM``/``CONTACT_ROW_MARGIN_UM`` /
``VIA1_SIZE_UM``/``VIA2_SIZE_UM``/``VIA_ENCLOSURE_UM``/``METAL3_WIRE_WIDTH_UM``
constants, unchanged.

``v_wire()`` (issue #353, a later follow-up in the same wave) joins them the
same way, with its Metal1 wire width taken as an explicit ``width`` argument
rather than defaulted here: ``METAL1_WIRE_WIDTH_UM`` is 0.28 um in
``pfd_cp/devgen.py``, ``divider_chain/devgen.py``, and ``vco/primitives.py``,
but 0.32 um in ``lock_detector/primitives.py``, so each submodule binds its
own default via ``functools.partial`` at its own call site (already imported
everywhere for ``_contact_positions()``/``_riser()`` above) rather than this
module guessing one value that fits all four.

Two of this package's risers are *structurally* different from ``_riser()``
and deliberately stay local, each documented at its own definition:

* ``pfd_cp/cp_dumpbuf.py``'s -- a separate ``_rect_extra()`` helper and a
  different via-landing sequence.
* ``lock_detector/primitives.py``'s -- since issue #322 it moves each
  riser's lane change onto **Metal1** before Via1 (``lane_dx``/``jog_y``,
  driven by that module's ``RiserLanes`` placer and its
  ``Canvas.net()``/``Canvas.via()`` net tagging). That is safe only under
  a module-local invariant -- lock_detector draws no Metal1 shape wider
  than one device pad -- which is **false** for ``divider_chain/devgen.py``
  (``v_wire()``/``h_wire()``/bypass lanes), so the capability must not be
  offered from here: cross-net metal that merges with no via is invisible
  to the DRC deck, which is exactly how issue #322's 114 shorts survived.

``divider_chain/devgen.py`` is therefore ``_riser()``'s only caller today;
``_via_square()``, ``_contact_positions()`` and ``bbox_union()`` are still
shared by all of them, including the two modules above.

``Conductor``, ``Via``, ``VIA_LAYERS``, ``_TOUCH_EPS``, ``_boxes_touch()``,
``_contains()``, ``shorted_pairs()`` and ``disconnected_nets()`` (issue #364)
join the same convention: ``lock_detector/checks.py`` (issue #322) and
``pfd_cp/rowgen.py`` (issue #300) each independently authored a pure-Python
short/open connectivity check over the same ``(net, layer, x0, y0, x1, y1)``
conductor tuples, and the two bodies stayed byte-for-byte identical (down to
``_TOUCH_EPS``'s value and the ``VIA_LAYERS`` dict literal) ever since --
this module gives that logic, too, one shared home. Both submodules re-export
these names under their own original ``checks.shorted_pairs(...)`` /
``rowgen.shorted_pairs(...)`` call signatures, so no call site (including
``layout/tests/test_lock_detector_layout.py`` and
``layout/tests/test_pfd_layout.py``) changed.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Callable, ClassVar, Iterable, Iterator


def _r(v: float) -> float:
    return round(v, 6)


@dataclass
class Canvas:
    """A thin ``klayout.db`` layout/cell wrapper, float-micron coordinates in.

    Subclass and override ``LAYER`` (required -- an empty layer table cannot
    draw anything) and, optionally, ``GRID_UM``/``PIN_LAYER`` to adapt this to
    one submodule's own layer set and grid/pin-labelling convention.
    """

    #: GDS layer table, ``{name: (layer, datatype)}``. Each subclass supplies
    #: its own submodule-specific table.
    LAYER: ClassVar[dict[str, tuple[int, int]]] = {}

    #: Manufacturing-grid snap step in microns for ``_u()``, or ``None`` to
    #: leave coordinates at plain micron->dbu rounding (the default).
    GRID_UM: ClassVar[float | None] = None

    #: Default layer ``pin()`` labels a net on when its own ``layer``
    #: argument is not given.
    PIN_LAYER: ClassVar[str] = "metal1"

    top_name: str
    dbu: float = 0.001  # 1 nm/dbu, matches the PDK's stdcell GDS convention

    def __post_init__(self) -> None:
        import klayout.db as db  # noqa: PLC0415

        self._db = db
        self.layout = db.Layout()
        self.layout.dbu = self.dbu
        self._dbu_per_um = int(round(1.0 / self.dbu))
        self._grid_dbu = int(round(self.GRID_UM / self.dbu)) if self.GRID_UM else None
        self.top = self.layout.create_cell(self.top_name)
        self._layer_index = {name: self.layout.layer(*gds) for name, gds in self.LAYER.items()}
        self.pins: dict[str, list[tuple[float, float, float, float]]] = {}
        self._dx = 0.0
        self._dy = 0.0
        self._pin_scope: dict | None = None

    @contextmanager
    def at(self, dx: float, dy: float) -> Iterator[dict]:
        """Draw everything inside this block translated by ``(dx, dy)``.

        The one mechanism a block assembler (``vco/block.py``) needs to place
        several separately-written sub-block generators into one flat top cell
        without any of them learning about placement: each generator keeps
        computing in its own local coordinates (and stays byte-identically
        correct when built standalone, where the offset is ``(0, 0)``), while
        the assembler chooses where those coordinates land.

        Flat, not hierarchical, deliberately: the assembler's own top-level
        routing has to *merge* with sub-block shapes (a via1 landing on a
        sub-block's own Metal1 pin, a Metal2 track extended past a sub-block's
        boundary), and two shapes that merge into one polygon for DRC must be
        in the same cell -- a cell instance's shapes cannot be grown by the
        parent. Hierarchy would buy compactness and cost exactly the property
        a block's DRC run has to prove.

        Yields a per-scope pin dict, so the assembler can tell *which*
        sub-block a shared net's pin came from (``Canvas.pins`` is a single
        flat registry, and sub-blocks routinely declare the same net).
        Coordinates recorded in both dicts are absolute (post-offset).
        """
        prev = (self._dx, self._dy, self._pin_scope)
        scope: dict[str, list[tuple[float, float, float, float]]] = {}
        self._dx, self._dy, self._pin_scope = dx, dy, scope
        try:
            yield scope
        finally:
            self._dx, self._dy, self._pin_scope = prev

    def _u(self, v: float) -> int:
        """Micron -> database units, optionally snapped to a manufacturing grid.

        Snapping (when ``GRID_UM`` is set) happens here rather than at each
        call site because *derived* coordinates -- a pad midpoint, a bus
        centreline, a device width divided by its finger count -- go
        off-grid routinely, and the PDK's own ``geom.drc`` OFFGRID section
        (``ongrid(0.005)`` per layer) fails every one of them. Snapping is a
        monotone function of the coordinate, so shapes that shared an exact
        edge before still share it after.
        """
        if self._grid_dbu:
            return int(round(v * self._dbu_per_um / self._grid_dbu)) * self._grid_dbu
        return int(round(v * self._dbu_per_um))

    def rect(self, layer: str, x0: float, y0: float, x1: float, y1: float) -> None:
        if x1 < x0:
            x0, x1 = x1, x0
        if y1 < y0:
            y0, y1 = y1, y0
        box = self._db.Box(
            self._u(x0 + self._dx),
            self._u(y0 + self._dy),
            self._u(x1 + self._dx),
            self._u(y1 + self._dy),
        )
        self.top.shapes(self._layer_index[layer]).insert(box)

    def label(self, layer: str, text: str, x: float, y: float) -> None:
        self.top.shapes(self._layer_index[layer]).insert(
            self._db.Text(
                text,
                self._db.Trans(self._db.Vector(self._u(x + self._dx), self._u(y + self._dy))),
            )
        )

    def pin(self, net: str, x0: float, y0: float, x1: float, y1: float, layer: str | None = None) -> None:
        """Record a Metal1 (or override-layer) landing pad as a named net pin.

        Labels on ``PIN_LAYER`` unless ``layer`` is given explicitly.

        The recorded box is **absolute** -- ``at()``'s translation applied --
        so an assembler reading ``pins`` back gets coordinates it can route
        to directly. Standalone builds have a zero offset, so this is
        unchanged for every existing caller.
        """
        box = (_r(x0 + self._dx), _r(y0 + self._dy), _r(x1 + self._dx), _r(y1 + self._dy))
        self.pins.setdefault(net, []).append(box)
        if self._pin_scope is not None:
            self._pin_scope.setdefault(net, []).append(box)
        self.label(layer if layer is not None else self.PIN_LAYER, net, (x0 + x1) / 2.0, (y0 + y1) / 2.0)

    def write_gds(self, path) -> None:
        options = self._db.SaveLayoutOptions()
        options.select_cell(self.top.cell_index())
        options.format = "GDS2"
        self.layout.write(str(path), options)


def bbox_union(boxes: Iterable[tuple[float, float, float, float]]) -> tuple[float, float, float, float]:
    """The smallest axis-aligned box enclosing every box in ``boxes``."""
    boxes = list(boxes)
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


def _contact_positions(
    lo: float,
    hi: float,
    *,
    size_um: float,
    pitch_um: float,
    margin_um: float,
    snap: Callable[[float], float] | None = None,
) -> list[float]:
    """Left-edge x (or y) positions for a row of contacts spanning ``[lo, hi]``.

    ``size_um``/``pitch_um``/``margin_um`` are the caller's own CO.1-derived
    contact size, pitch, and row-inset margin, passed explicitly rather than
    hardcoded here -- each submodule keeps deriving them from its own
    ``CONTACT_SIZE_UM``/``CONTACT_PITCH_UM``/``CONTACT_ROW_MARGIN_UM``
    constants, unchanged.

    ``snap``, when given, rounds each returned coordinate (and the
    intermediate ``start`` position) through a manufacturing-grid snap
    function before returning. ``vco/primitives.py`` is the one caller that
    needs this: ``CO.1`` makes 0.22 um the contact's min **and** max size,
    so an off-grid origin whose far edge rounds the other way is a
    0.215/0.225 um contact and a hard violation, not a cosmetic nudge. Every
    other caller passes nothing and keeps the original, unsnapped behavior.
    """
    snap = snap or (lambda v: v)
    usable_lo = lo + margin_um
    usable_hi = hi - margin_um
    span = usable_hi - usable_lo
    if span < size_um:
        center = (lo + hi) / 2.0
        return [snap(center - size_um / 2.0)]
    n = int((span - size_um) // pitch_um) + 1
    n = max(n, 1)
    total = size_um + (n - 1) * pitch_um
    start = snap(usable_lo + (span - total) / 2.0)
    return [snap(start + i * pitch_um) for i in range(n)]


def _via_square(canvas: Canvas, layer: str, x: float, y: float, size: float, enclosure: float) -> float:
    """Draw one square via centered at ``(x, y)`` and return the half-size of
    its enclosing metal landing pad (``size / 2 + enclosure``)."""
    half_v = size / 2.0
    canvas.rect(layer, x - half_v, y - half_v, x + half_v, y + half_v)
    return half_v + enclosure


def _riser(
    canvas: Canvas,
    x: float,
    y_pad: float,
    track_y: float,
    *,
    via1_size_um: float,
    via2_size_um: float,
    via_enclosure_um: float,
    metal3_width_um: float,
) -> None:
    """Metal1 pad -> Via1 -> Metal2 landing -> Via2 -> Metal3 riser -> Via2 -> Metal2 bus landing.

    The long vertical run (from ``y_pad`` to ``track_y``) is drawn entirely
    on Metal3 -- a layer this package's leaf-cell geometry never otherwise
    uses -- so it can freely cross any other net's Metal2 bus without a via
    (no via, no connection, no short: metal on two different layers
    overlapping with no via between them is not a DRC violation in this
    deck).

    ``via1_size_um``/``via2_size_um``/``via_enclosure_um``/``metal3_width_um``
    are the caller's own via/wire-size constants, passed explicitly so each
    submodule keeps deriving them from its own ``VIA1_SIZE_UM`` /
    ``VIA2_SIZE_UM`` / ``VIA_ENCLOSURE_UM`` / ``METAL3_WIRE_WIDTH_UM``
    constants, unchanged.
    """
    half_m2 = _via_square(canvas, "via1", x, y_pad, via1_size_um, via_enclosure_um)
    canvas.rect("metal2", x - half_m2, y_pad - half_m2, x + half_m2, y_pad + half_m2)
    canvas.rect("metal1", x - half_m2, y_pad - half_m2, x + half_m2, y_pad + half_m2)

    half_m3 = _via_square(canvas, "via2", x, y_pad, via2_size_um, via_enclosure_um)
    canvas.rect("metal3", x - half_m3, y_pad - half_m3, x + half_m3, y_pad + half_m3)

    half_w = metal3_width_um / 2.0
    canvas.rect("metal3", x - half_w, min(y_pad, track_y), x + half_w, max(y_pad, track_y))

    half_m3_top = _via_square(canvas, "via2", x, track_y, via2_size_um, via_enclosure_um)
    canvas.rect("metal3", x - half_m3_top, track_y - half_m3_top, x + half_m3_top, track_y + half_m3_top)
    canvas.rect("metal2", x - half_m3_top, track_y - half_m3_top, x + half_m3_top, track_y + half_m3_top)


def v_wire(canvas: Canvas, x: float, y0: float, y1: float, width: float) -> tuple:
    """A vertical Metal1 wire segment centered on ``x``, spanning ``[y0, y1]``.

    ``width`` is the caller's own Metal1 minimum-wire-width constant, passed
    explicitly (no default here -- see the module docstring's ``v_wire()``
    note on why 0.28 um/0.32 um can't both be this function's default).
    """
    x0, x1 = x - width / 2.0, x + width / 2.0
    canvas.rect("metal1", x0, y0, x1, y1)
    return (x0, min(y0, y1), x1, max(y0, y1))


# ---------------------------------------------------------------------------
# Connectivity checks (pure) -- what a DRC deck structurally cannot do
# ---------------------------------------------------------------------------
#
# A DRC deck checks widths, spaces, enclosures and densities. It does not
# check *connectivity*, and the two failure modes below are both invisible to
# it:
#
#   * a short -- two different nets' shapes overlapping on one layer merge
#     into a single polygon that is perfectly legal by every geometric rule;
#   * an open -- a net drawn as two pieces that never touch is likewise
#     legal.
#
# Both are caught by LVS, but LVS needs an extracted netlist and a reference
# netlist. These two functions run on the plain-Python shape model instead,
# so every build of a ``layout/pll_top/*`` block is checked for shorts and
# opens in the unit test suite with no PDK, no KLayout and no run_pv
# invocation. See #322 for the defect this caught (114 cross-net Metal3
# overlaps, 75 of them VDD/VSS, sitting undetected through a DRC-clean,
# merged ``lock_detector`` layout).

#: (net, layer, x0, y0, x1, y1) -- one Metal1/Metal2/Metal3 shape.
Conductor = tuple[str, str, float, float, float, float]
#: (net, "via1" | "via2", x, y) -- where a net changes layer.
Via = tuple[str, str, float, float]

#: Which two metal layers each via kind joins.
VIA_LAYERS = {"via1": ("metal1", "metal2"), "via2": ("metal2", "metal3")}

_TOUCH_EPS = 1e-6


def _boxes_touch(a: Conductor, b: Conductor) -> bool:
    return (
        a[4] >= b[2] - _TOUCH_EPS
        and b[4] >= a[2] - _TOUCH_EPS
        and a[5] >= b[3] - _TOUCH_EPS
        and b[5] >= a[3] - _TOUCH_EPS
    )


def shorted_pairs(conductors: Iterable[Conductor]) -> list[tuple[str, str, str]]:
    """Every ``(net_a, net_b, layer)`` where two different nets overlap.

    A DRC deck cannot see this: two overlapping same-layer shapes from
    different nets merge into one legal polygon. See issue #322, where this
    exact defect (114 cross-net Metal3 overlaps, 75 of them VDD/VSS) sat
    undetected through a DRC-clean, merged ``lock_detector`` layout.
    """
    items = sorted(conductors, key=lambda c: c[2])
    hits: list[tuple[str, str, str]] = []
    for i, a in enumerate(items):
        for b in items[i + 1 :]:
            if b[2] >= a[4]:
                break
            if a[0] == b[0] or a[1] != b[1]:
                continue
            if a[4] > b[2] and b[4] > a[2] and a[5] > b[3] and b[5] > a[3]:
                hits.append((a[0], b[0], a[1]))
    return sorted(set(hits))


def _contains(box: Conductor, x: float, y: float) -> bool:
    return box[2] - _TOUCH_EPS <= x <= box[4] + _TOUCH_EPS and box[3] - _TOUCH_EPS <= y <= box[5] + _TOUCH_EPS


def disconnected_nets(conductors: Iterable[Conductor], vias: Iterable[Via]) -> list[tuple[str, int]]:
    """Every ``(net, piece_count)`` whose shapes do not form one island.

    Two shapes on the same layer are connected when their boxes touch or
    overlap; a via connects a shape on its lower layer to one on its upper
    layer when both contain the via's centre.
    """
    items = list(conductors)
    parent = list(range(len(items)))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    by_net: dict[str, list[int]] = {}
    for i, c in enumerate(items):
        by_net.setdefault(c[0], []).append(i)

    for idxs in by_net.values():
        ordered = sorted(idxs, key=lambda i: items[i][2])
        for n, i in enumerate(ordered):
            for j in ordered[n + 1 :]:
                if items[j][2] > items[i][4] + _TOUCH_EPS:
                    break
                if items[i][1] == items[j][1] and _boxes_touch(items[i], items[j]):
                    union(i, j)

    for net, kind, x, y in vias:
        lower, upper = VIA_LAYERS[kind]
        below = [i for i in by_net.get(net, []) if items[i][1] == lower and _contains(items[i], x, y)]
        above = [i for i in by_net.get(net, []) if items[i][1] == upper and _contains(items[i], x, y)]
        if not below or not above:
            raise ValueError(f"via {kind} for net {net!r} at ({x}, {y}) lands on no {lower}/{upper} shape")
        for i in below:
            for j in above:
                union(i, j)

    return sorted(
        (net, len({find(i) for i in idxs})) for net, idxs in by_net.items() if len({find(i) for i in idxs}) != 1
    )
