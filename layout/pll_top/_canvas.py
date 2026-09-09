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
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import ClassVar, Iterator


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
