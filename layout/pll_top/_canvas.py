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
