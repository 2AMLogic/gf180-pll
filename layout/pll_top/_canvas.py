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

``pfd_cp/cp_array.py`` and ``pfd_cp/cp_dumpbuf.py`` (issue #666) bind
``_riser()`` with ``use_extra_layers=True`` (their ``devgen.Canvas`` has no
Via1/Metal2/Via2/Metal3 layers, so those are drawn with the shared
``_rect_extra()``/``_EXTRA_LAYER`` below); the drawn geometry is identical to
their earlier per-module copies.

One package riser is *structurally* different from ``_riser()`` and
deliberately stays local, documented at its own definition:

* ``lock_detector/primitives.py``'s -- since issue #322 it moves each
  riser's lane change onto **Metal1** before Via1 (``lane_dx``/``jog_y``,
  driven by that module's ``RiserLanes`` placer and its
  ``Canvas.net()``/``Canvas.via()`` net tagging). That is safe only under
  a module-local invariant -- lock_detector draws no Metal1 shape wider
  than one device pad -- which is **false** for ``divider_chain/devgen.py``
  (``v_wire()``/``h_wire()``/bypass lanes), so the capability must not be
  offered from here: cross-net metal that merges with no via is invisible
  to the DRC deck, which is exactly how issue #322's 114 shorts survived.

``_via_square()``, ``_contact_positions()`` and ``bbox_union()`` are also
shared by ``lock_detector``.

``NetTracks`` (issue #429) joins the same convention: ``divider_chain/devgen.py``,
``pfd_cp/cp_array.py``, ``pfd_cp/cp_dumpbuf.py``, and
``lock_detector/primitives.py`` each independently defined a byte-for-byte
identical Metal2 track-Y allocator class -- two of the four docstrings already
cross-referenced each other as "whose behaviour is identical". Its ``pitch``
default, ``0.75`` um, is what every one of those four modules' own
``METAL2_TRACK_PITCH_UM`` already independently evaluates to (``pfd_cp/rowgen.py``
separately defines an unrelated ``0.8`` for a different helper, not a fifth
value for this one). Unlike ``v_wire()``'s ``width`` below, that default is a
literal here rather than each caller's constant, because all four values agree
and ``NetTracks`` is named in type-annotation and ``:class:`` positions that a
``functools.partial`` re-binding would stop satisfying. The equality is
therefore asserted, not assumed: ``layout/tests/test_canvas_nettracks.py``
fails if any of the four constants (or this default) is changed alone, which
is the propagation the per-module copies used to get for free (issue #432).

``pad_center()`` (issue #475) joins the same convention:
``lock_detector/primitives.py``, ``divider_chain/devgen.py``,
``pfd_cp/cp_dumpbuf.py``, and ``pfd_cp/cp_array.py`` each independently
defined the same one-line box-midpoint helper, byte-for-byte identical in all
four. Each re-exports it under its own original module-level name
(``pad_center = _canvas.pad_center``), so every call site is unchanged --
including the ``from .devgen import pad_center`` importers
``divider_chain/divider_chain.py``, ``divider_chain/div23_cell.py``, and
``divider_chain/dff_tg_3v3.py``, and the ``cp_array.pad_center(...)`` /
``cp_output_stage``/``cp.py`` qualified call sites.

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
from dataclasses import dataclass, field
from typing import Any, Callable, ClassVar, Iterable, Iterator, Sequence


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

    def clear_inherited_labels(self, layers: Sequence[str] | None = None) -> int:
        """Delete every *text* on ``layers`` from every cell, and return how
        many were removed.

        Default (``layers=None``): every ``"*_label"`` purpose this canvas's
        own ``LAYER`` table defines -- **not** only ``PIN_LAYER`` (issue
        #453; see "WHY THE DEFAULT COVERS EVERY ``_label`` PURPOSE" below).

        WHY AN ASSEMBLER HAS TO CALL THIS (issue #440)
        ----------------------------------------------
        A sub-block written for its own standalone LVS claim labels its own
        boundary nets with its own *local* port names (``cp_leg_n``'s
        ``EN``/``ENB``/``VBN``/``VCASCN``/``TAIL``, say). Those names are
        only meaningful inside that sub-block's own reference netlist. When
        an assembler composes the sub-block by reading its GDS and calling
        ``top.flatten(-1, True)`` (the pattern ``pfd_cp``'s own
        ``cp_array``/``cp_output_stage``/``cp``/``block`` all use), those
        label *shapes* are flattened in with the geometry -- and gf180mcu's
        LVS deck reads top-level net names straight off them
        (``connect(metal1_con, metal1_label)``). The parent's net then
        extracts under a merged name: the array ties a base leg's ``ENB``
        permanently to the block's ground rail, so that rail extracts as
        ``ENB,VSS`` rather than ``VSS``.

        That is not cosmetic. The deck synthesizes the p-substrate as a
        *global* net named by ``--lvs_sub`` (``VSS`` here -- see
        ``layout/README.md``'s "substrate-net gotcha"), and a global net
        merges into the drawn net that carries **exactly** that name. A net
        named ``ENB,VSS`` is not that name, so the merge silently does not
        happen: every n-channel bulk terminal lands on a net of its own,
        disconnected from the ground rail it is drawn on, and the whole
        block mismatches. ``pfd_cp``'s first block-level LVS run failed this
        way and no other (84 of 93 nets, 69 of 168 devices) -- removing the
        eight inherited ``ENB`` labels alone turned it into a match.

        So the rule this method exists to enforce is: **the level doing the
        assembling owns the net names.** Call it immediately after the
        composing ``flatten()``, before the assembler promotes its own
        boundary pins with :meth:`pin`; the sub-block's own standalone GDS
        (and its own standalone LVS claim) is untouched.

        WHY THE DEFAULT COVERS EVERY ``_label`` PURPOSE (issue #453)
        --------------------------------------------------------------
        The original (issue #440) default cleared only ``PIN_LAYER`` --
        every submodule's own default label purpose, ``"metal1_label"``
        (34/10). That is not the *only* purpose layer gf180mcu's LVS deck
        reads names from: ``pfd_cp``'s own ``UP``/``DN`` boundary pins are
        Metal2 geometry, so ``block.py`` labels them on ``"metal2_label"``
        (36/10, ``connect(metal2_con, metal2_label)``) via ``pin()``'s
        ``layer=`` override -- correctly, for ``pfd_cp``'s own standalone
        claim. A *future* assembler composing ``pfd_cp`` the same
        read-GDS-and-flatten way and calling the bare
        ``clear_inherited_labels()`` would strip the 34/10 texts (the case
        the narrow default covered) but inherit ``pfd_cp``'s two 36/10
        ``UP``/``DN`` texts untouched -- reintroducing exactly #440's bug
        class one level up, in the harder-to-see direction: a label that
        *is* on a purpose layer the deck reads, just not the one the narrow
        default checked. Defaulting to every ``"*_label"``-suffixed key in
        ``LAYER`` closes that: it is the naming convention every submodule's
        own ``LAYER`` table already uses for gf180mcu's LVS-purpose layers
        (``"metal1_label"``, ``"metal2_label"``; see ``pfd_cp/devgen.py``'s
        own ``LAYER`` table comments citing the deck's
        ``layers_definitions.lvs``), so no submodule has to opt in per call
        site. A ``LAYER`` table with no such key (none exist today, but a
        defensive fallback costs nothing) falls back to the original
        ``(PIN_LAYER,)`` behavior instead of silently clearing nothing.
        """
        if layers is not None:
            names = tuple(layers)
        else:
            names = tuple(name for name in self.LAYER if name.endswith("_label"))
            if not names and self.PIN_LAYER in self.LAYER:
                names = (self.PIN_LAYER,)
        removed = 0
        for name in names:
            gds = self.LAYER.get(name)
            if gds is None:
                continue
            index = self.layout.layer(*gds)
            for cell in self.layout.each_cell():
                shapes = cell.shapes(index)
                doomed = [s for s in shapes.each() if s.is_text()]
                for shape in doomed:
                    shapes.erase(shape)
                removed += len(doomed)
        return removed

    def write_gds(self, path) -> None:
        options = self._db.SaveLayoutOptions()
        options.select_cell(self.top.cell_index())
        options.format = "GDS2"
        self.layout.write(str(path), options)


@dataclass
class MosfetPorts:
    """Port/geometry record :func:`mosfet` returns for one drawn device
    (issue #444; previously duplicated in ``pfd_cp/devgen.py`` and
    ``divider_chain/devgen.py``)."""

    name: str
    kind: str
    x0: float
    x1: float
    y0: float
    y3: float
    bottom_pad: tuple[float, float, float, float]
    top_pad: tuple[float, float, float, float]
    gate_pad: tuple[float, float, float, float]
    gate_y_center: float


@dataclass
class LeafCell:
    """The finished-cell record every ``build_stack_cell()``-style generator
    returns: a drawn :class:`Canvas` plus the port/pin/well bookkeeping a
    caller composing several such cells needs, without re-deriving it.

    ``pfd_cp/devgen.py`` and ``divider_chain/devgen.py`` each independently
    defined a byte-for-byte-identical copy of this dataclass (issue #639,
    a follow-up in the same wave as this module's ``Canvas``/``_r()``
    (#317), ``bbox_union()``/``_contact_positions()``/``_via_square()``/
    ``_riser()`` (#332), ``v_wire()`` (#353), ``pad_center()`` (#475), and
    ``NetTracks`` (#429) consolidations).

    ``ports``'s element type is this module's own :class:`MosfetPorts`
    (consolidated here by issue #444; both submodules re-export it).
    """

    canvas: Canvas
    ports: list[MosfetPorts] = field(default_factory=list)
    pins: dict[str, tuple[float, float, float, float]] = field(default_factory=dict)
    nwell_box: tuple[float, float, float, float] | None = None
    footprint: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)

    def write_gds(self, path) -> None:
        self.canvas.write_gds(path)


def bbox_union(boxes: Iterable[tuple[float, float, float, float]]) -> tuple[float, float, float, float]:
    """The smallest axis-aligned box enclosing every box in ``boxes``."""
    boxes = list(boxes)
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


def nwell_over(
    view: Any,
    boxes: Iterable[tuple[float, float, float, float]],
    *,
    margin: float,
) -> tuple[float, float, float, float]:
    """Draw one nwell rectangle on ``view`` (anything with a ``rect()``, i.e. a
    ``Canvas`` or a ``rowgen`` view) enclosing every PMOS comp / ntap box in
    ``boxes``, ``margin`` clear on every side, and return it. ``margin`` is
    each caller's own ``NWELL_MARGIN_UM``.
    """
    x0, y0, x1, y1 = bbox_union(boxes)
    well = (x0 - margin, y0 - margin, x1 + margin, y1 + margin)
    view.rect("nwell", *well)
    return well


def net_x_extent(
    xs: Iterable[float],
    *,
    wire_width: float,
    via2_size: float,
    via_enclosure: float,
) -> tuple[float, float]:
    """The x range one net's drawn Metal2 geometry occupies at its own
    ``track_y``, given every x that net has a riser or a bus end at.

    Not simply the bus rectangle (``x_lo - wire_width/2 .. x_hi +
    wire_width/2``): at each extreme x the widest drawn shape is that riser's
    own Metal2 landing square (``_riser``'s ``via2_size/2 + via_enclosure``),
    which is wider than half the bus wire's width, so taking the wider of the
    two keeps a net's true leftmost/rightmost drawn edge from being
    under-reported. Raises ``ValueError`` when ``xs`` is empty.
    """
    xs = list(xs)
    if not xs:
        raise ValueError("net_x_extent(): no x coordinates")
    half = max(wire_width / 2.0, via2_size / 2.0 + via_enclosure)
    return (min(xs) - half, max(xs) + half)


def check_track_separation(
    track_y: Any,
    extents: Any,
    clearance: float,
) -> None:
    """Raise unless every two nets assigned the *same* ``track_y`` keep at
    least ``clearance`` between their drawn x extents.

    :func:`pack_tracks` produces an assignment with this property by
    construction and calls this on its own output; it is also public because
    the property has to survive the *caller's* own later geometry (e.g.
    ``cp_output_stage.build()`` re-checks the x values its link loop really
    extended each bus to).
    """
    by_track: dict[float, list[str]] = {}
    for net, y in track_y.items():
        by_track.setdefault(round(y, 6), []).append(net)
    for y, nets in sorted(by_track.items()):
        ordered = sorted(nets, key=lambda n: extents[n][0])
        for a, b in zip(ordered, ordered[1:]):
            gap = extents[b][0] - extents[a][1]
            if gap < clearance - 1e-9:
                raise ValueError(
                    f"track packing: nets {a!r} {extents[a]} and {b!r} {extents[b]} share "
                    f"track_y={y} but are only {gap:.3f} um apart; needs >= {clearance}"
                )


def pack_tracks(
    nets: Any,
    base_y: float,
    *,
    pitch: float,
    clearance: float,
    wire_width: float,
    via2_size: float,
    via_enclosure: float,
) -> dict[str, float]:
    """Assign every net in ``nets`` (net -> every x its own Metal2 geometry
    reaches) a ``track_y``, reusing one track across any nets whose extents
    (:func:`net_x_extent`) stay ``clearance`` apart -- the left-edge
    algorithm, optimal for this 1-D placement problem.

    Deterministic: nets are processed in increasing left-edge order with the
    net name as the tie-break, so the same geometry always yields the same
    band. Each submodule binds ``pitch``/``clearance`` and the via/wire
    constants from its own ``METAL2_*``/``VIA*`` values (``clearance`` is
    ``METAL2_TRACK_PITCH_UM - METAL2_WIRE_WIDTH_UM``, the margin
    ``NetTracks`` already keeps between two tracks in y, reused along x).
    """
    extents = {
        net: net_x_extent(xs, wire_width=wire_width, via2_size=via2_size, via_enclosure=via_enclosure)
        for net, xs in nets.items()
    }

    # Left-edge algorithm: place each net on the first track whose
    # most-recent occupant ends early enough to clear this net's own left
    # edge by `clearance`; open a new track only when none does.
    order = sorted(extents, key=lambda n: (extents[n][0], n))
    track_right: list[float] = []
    track_of: dict[str, int] = {}
    for net in order:
        lo, hi = extents[net]
        for i, right in enumerate(track_right):
            if lo >= right + clearance:
                track_right[i] = hi
                track_of[net] = i
                break
        else:
            track_right.append(hi)
            track_of[net] = len(track_right) - 1

    assignment = {net: base_y + i * pitch for net, i in track_of.items()}
    check_track_separation(assignment, extents, clearance)
    return assignment


def pad_center(pad: tuple[float, float, float, float]) -> tuple[float, float]:
    """The centre point of an axis-aligned pad box ``(x0, y0, x1, y1)``."""
    return ((pad[0] + pad[2]) / 2.0, (pad[1] + pad[3]) / 2.0)


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


#: GDS layers for the four routing layers a submodule's own ``Canvas.LAYER``
#: table may not carry (``pfd_cp``'s ``devgen.Canvas`` stops at Metal1). Used
#: by :func:`_rect_extra` / ``_riser(use_extra_layers=True)`` (issue #666).
#: Same layer/datatype numbers every submodule's own ``LAYER`` table cites
#: from ``libs.tech/klayout/drc/rule_decks/layers_def.drc``.
_EXTRA_LAYER = {
    "via1": (35, 0),
    "metal2": (36, 0),
    "via2": (38, 0),
    "metal3": (42, 0),
}


def _rect_extra(canvas: Canvas, layer: str, x0: float, y0: float, x1: float, y1: float) -> None:
    """Draw a rectangle on one of :data:`_EXTRA_LAYER`'s layers (not one of
    the canvas's own named layers) directly against the underlying
    ``klayout.db`` objects the canvas already exposes (``.layout``, ``.top``).
    Lazy-imports ``klayout.db`` itself, so this module stays importable with no
    PV environment. The 0.001 um database unit is fixed, as in ``Canvas``.
    """
    import klayout.db as db  # noqa: PLC0415

    idx = canvas.layout.layer(*_EXTRA_LAYER[layer])
    if x1 < x0:
        x0, x1 = x1, x0
    if y1 < y0:
        y0, y1 = y1, y0
    u = lambda v: int(round(v * 1000))  # noqa: E731
    canvas.top.shapes(idx).insert(db.Box(u(x0), u(y0), u(x1), u(y1)))


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
    use_extra_layers: bool = False,
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

    The Metal1 landing square under Via1 (sized to fully enclose it, ``V1.3a``)
    is always drawn. ``use_extra_layers`` (default ``False``) is for a caller
    whose ``Canvas.LAYER`` has no Via1/Metal2/Via2/Metal3 entries
    (``pfd_cp``'s ``devgen.Canvas``): those four layers are then drawn with
    :func:`_rect_extra` instead of ``canvas.rect``. Metal1 always goes through
    ``canvas.rect``. The drawn geometry is identical either way.
    """
    draw = _rect_extra if use_extra_layers else (lambda c, layer, *box: c.rect(layer, *box))

    half_m2 = via1_size_um / 2.0 + via_enclosure_um
    canvas.rect("metal1", x - half_m2, y_pad - half_m2, x + half_m2, y_pad + half_m2)
    half_v1 = via1_size_um / 2.0
    draw(canvas, "via1", x - half_v1, y_pad - half_v1, x + half_v1, y_pad + half_v1)
    draw(canvas, "metal2", x - half_m2, y_pad - half_m2, x + half_m2, y_pad + half_m2)

    half_v2 = via2_size_um / 2.0
    half_m3 = half_v2 + via_enclosure_um
    draw(canvas, "via2", x - half_v2, y_pad - half_v2, x + half_v2, y_pad + half_v2)
    draw(canvas, "metal3", x - half_m3, y_pad - half_m3, x + half_m3, y_pad + half_m3)

    half_w = metal3_width_um / 2.0
    draw(canvas, "metal3", x - half_w, min(y_pad, track_y), x + half_w, max(y_pad, track_y))

    draw(canvas, "via2", x - half_v2, track_y - half_v2, x + half_v2, track_y + half_v2)
    draw(canvas, "metal3", x - half_m3, track_y - half_m3, x + half_m3, track_y + half_m3)
    draw(canvas, "metal2", x - half_m3, track_y - half_m3, x + half_m3, track_y + half_m3)


def v_wire(canvas: Canvas, x: float, y0: float, y1: float, width: float) -> tuple:
    """A vertical Metal1 wire segment centered on ``x``, spanning ``[y0, y1]``.

    ``width`` is the caller's own Metal1 minimum-wire-width constant, passed
    explicitly (no default here -- see the module docstring's ``v_wire()``
    note on why 0.28 um/0.32 um can't both be this function's default).
    """
    x0, x1 = x - width / 2.0, x + width / 2.0
    canvas.rect("metal1", x0, y0, x1, y1)
    return (x0, min(y0, y1), x1, max(y0, y1))


def mosfet(
    canvas: Canvas,
    device: Any,
    x0: float,
    y_bottom: float,
    *,
    sd_overhang_um: float,
    poly_endcap_um: float,
    gate_tab_w_um: float,
    gate_tab_h_um: float,
    gate_tab_overlap_um: float,
    contact_size_um: float,
    contact_pitch_um: float,
    contact_row_margin_um: float,
    metal1_pad_margin_um: float,
    implant_margin_um: float,
) -> MosfetPorts:
    """Draw one vertical-current-flow ``nfet_03v3``/``pfet_03v3`` instance.

    Identical geometry/margins to ``vco/primitives.py``'s ``mosfet()`` --
    see that function's docstring for the full per-shape DRC citation. ``x0``
    is the device's comp left edge; ``y_bottom`` is the bottom terminal
    comp's bottom edge.

    ``device`` is any object with ``name``, ``kind`` (``"nfet"``/``"pfet"``),
    ``w_um`` and ``l_um`` attributes (each submodule's own ``Device``). The
    keyword-only ``*_um`` arguments are the caller's own DRC-derived
    geometry constants (each submodule keeps its own copy, with its own
    rule citations, and binds them via ``functools.partial``).
    """
    w, l = device.w_um, device.l_um
    implant_layer = "pplus" if device.kind == "pfet" else "nplus"

    x1 = x0 + w
    y1 = y_bottom + sd_overhang_um
    y2 = y1 + l
    y3 = y2 + sd_overhang_um

    canvas.rect("comp", x0, y_bottom, x1, y3)

    gate_x0 = x0 - poly_endcap_um
    gate_x1 = x1 + poly_endcap_um
    canvas.rect("poly2", gate_x0, y1, gate_x1, y2)

    gate_y_center = (y1 + y2) / 2.0
    tab_x1 = gate_x0 + gate_tab_overlap_um
    tab_x0 = tab_x1 - gate_tab_w_um
    tab_y0 = gate_y_center - gate_tab_h_um / 2.0
    tab_y1 = gate_y_center + gate_tab_h_um / 2.0
    canvas.rect("poly2", tab_x0, tab_y0, tab_x1, tab_y1)

    gate_contact_x0 = tab_x0 + (gate_tab_w_um - contact_size_um) / 2.0
    gate_contact_y0 = tab_y0 + (gate_tab_h_um - contact_size_um) / 2.0
    canvas.rect(
        "contact",
        gate_contact_x0,
        gate_contact_y0,
        gate_contact_x0 + contact_size_um,
        gate_contact_y0 + contact_size_um,
    )
    gate_pad = (
        tab_x0 - metal1_pad_margin_um,
        tab_y0 - metal1_pad_margin_um,
        tab_x1 + metal1_pad_margin_um,
        tab_y1 + metal1_pad_margin_um,
    )
    canvas.rect("metal1", *gate_pad)

    def _terminal_pad(y_outer_edge: float, *, outer_is_max: bool) -> tuple[float, float, float, float]:
        xs = _contact_positions(
            x0, x1, size_um=contact_size_um, pitch_um=contact_pitch_um, margin_um=contact_row_margin_um
        )
        if outer_is_max:
            cy1 = y_outer_edge - contact_row_margin_um
            cy0 = cy1 - contact_size_um
        else:
            cy0 = y_outer_edge + contact_row_margin_um
            cy1 = cy0 + contact_size_um
        for cx in xs:
            canvas.rect("contact", cx, cy0, cx + contact_size_um, cy1)
        pad_x0 = min(xs) - metal1_pad_margin_um
        pad_x1 = max(xs) + contact_size_um + metal1_pad_margin_um
        pad_y0 = cy0 - metal1_pad_margin_um
        pad_y1 = cy1 + metal1_pad_margin_um
        canvas.rect("metal1", pad_x0, pad_y0, pad_x1, pad_y1)
        return (pad_x0, pad_y0, pad_x1, pad_y1)

    bottom_pad = _terminal_pad(y_bottom, outer_is_max=False)
    top_pad = _terminal_pad(y3, outer_is_max=True)

    canvas.rect(
        implant_layer,
        x0 - implant_margin_um,
        y_bottom - implant_margin_um,
        x1 + implant_margin_um,
        y3 + implant_margin_um,
    )

    return MosfetPorts(
        name=device.name,
        kind=device.kind,
        x0=x0,
        x1=x1,
        y0=y_bottom,
        y3=y3,
        bottom_pad=bottom_pad,
        top_pad=top_pad,
        gate_pad=gate_pad,
        gate_y_center=gate_y_center,
    )


class NetTracks:
    """Hands out a fresh, never-reused Metal2 track_y per net name.

    Because every track is unique (monotonically increasing by ``pitch``),
    two nets' buses can never be closer than the pitch on the Y axis --
    eliminating same-layer Metal2 collisions between different nets by
    construction, independent of each net's Metal2 bus's X extent (see
    ``route_net``/``_riser``'s docstrings).

    ``pitch``'s ``0.75`` um default is what each consuming module's own
    ``METAL2_TRACK_PITCH_UM`` evaluates to -- an equality
    ``layout/tests/test_canvas_nettracks.py`` asserts rather than assumes
    (issue #432). A caller whose Metal2 pitch differs must pass it
    explicitly; the default is not a claim that 0.75 um is safe everywhere.
    """

    def __init__(self, base_y: float, pitch: float = 0.75) -> None:
        self._next_y = base_y
        self._pitch = pitch
        self._assigned: dict[str, float] = {}

    def get(self, net: str) -> float:
        if net not in self._assigned:
            self._assigned[net] = self._next_y
            self._next_y += self._pitch
        return self._assigned[net]


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
