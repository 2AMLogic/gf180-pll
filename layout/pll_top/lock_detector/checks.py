"""Pure-Python short/open connectivity checks for ``lock_detector`` (issue #322).

``layout/evidence/lock-detector-layout/``'s DRC-clean result cannot see a
*short*: two different nets' shapes overlapping on one layer merge into a
single polygon that is perfectly legal by every width/space/enclosure rule.
It cannot see an *open* either: a net drawn as two pieces that never
actually touch is likewise geometrically legal. Only LVS (which needs a
foundry deck and a reference netlist) or an explicit connectivity check over
the design's own net-tagged shapes catches either one -- this module's
``shorted_pairs()``/``disconnected_nets()`` are that check, re-exported from
``layout/pll_top/_canvas.py`` (issue #364), which also backs
``pfd_cp/rowgen.py``'s identically-named functions: the two implementations
started as an intentional port (issue #300 for ``rowgen.py``, #322 for this
module) proving the same approach independently for two different
full-custom blocks, then stayed byte-for-byte identical ever since, so #364
consolidated them into one shared body.

``RecordingCanvas`` is the other half: a duck-typed stand-in for
``primitives.Canvas`` (implements ``rect()``/``label()``/``pin()``/``net()``/
``via()``) that records every Metal1/Metal2/Metal3 shape drawn inside a
``with canvas.net(name): ...`` block instead of ever touching ``klayout.db``
-- so ``build.build_lock_detector(canvas_cls=RecordingCanvas)`` builds the
exact same geometry ``primitives.mosfet()``/``tap_strip()``/``route_net()``
draw for a real GDS, and this module's checks run on every build with no PDK
and no KLayout dependency at all (mirrors ``pfd_cp/rowgen.py``'s own
plain-Python ``Canvas``, whose ``klayout.db`` import is confined to
``write_gds()``).
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator

try:
    from .. import _canvas
except ImportError:  # this package's own dir (not its "pll_top" parent) is the
    # sys.path root under layout/tests's flat-import convention (see
    # floorplan/skeleton.py and every layout/tests/test_*.py's own
    # sys.path.insert(..., ".../pll_top") -- "vco"/"lock_detector"/"pfd_cp"
    # are then each their own top-level package, one level short of "..").
    import _canvas
from . import primitives as P

#: (net, layer, x0, y0, x1, y1) -- one Metal1/Metal2/Metal3 shape.
Conductor = _canvas.Conductor
#: (net, "via1" | "via2", x, y) -- where a net changes layer.
Via = _canvas.Via

#: Which two metal layers each via kind joins.
VIA_LAYERS = _canvas.VIA_LAYERS

#: Shared connectivity-check implementation (issue #364) -- see
#: ``layout/pll_top/_canvas.py``'s module docstring for the consolidation
#: rationale; re-exported here so ``checks.shorted_pairs(...)`` and
#: ``checks.disconnected_nets(...)`` keep working unchanged.
shorted_pairs = _canvas.shorted_pairs
disconnected_nets = _canvas.disconnected_nets

_CONDUCTOR_LAYERS = frozenset({"metal1", "metal2", "metal3"})


def _r(v: float) -> float:
    return round(v, 6)


@dataclass
class RecordingCanvas:
    """A ``primitives.Canvas``-shaped shape recorder; never imports ``klayout``.

    Only the methods ``primitives.mosfet()``/``tap_strip()``/``route_net()``/
    ``nwell_over()`` actually call are implemented: ``rect()``, ``label()``,
    ``pin()``, ``net()`` and ``via()``. Every non-metal ``rect()`` call
    (comp/poly/contact/implant/nwell) is silently dropped -- this module
    only checks connectivity of the Metal1-3 routing, the same scope
    ``pfd_cp/rowgen.py``'s ``shorted_pairs()``/``disconnected_nets()`` check.
    """

    top_name: str
    conductors: list[Conductor] = field(default_factory=list)
    vias: list[Via] = field(default_factory=list)
    pins: dict[str, list[tuple[float, float, float, float]]] = field(default_factory=dict)
    _current_net: str | None = field(default=None, init=False, repr=False)

    def rect(self, layer: str, x0: float, y0: float, x1: float, y1: float) -> None:
        if layer not in P.LAYER:
            raise KeyError(f"unknown layer {layer!r}")
        if x1 < x0:
            x0, x1 = x1, x0
        if y1 < y0:
            y0, y1 = y1, y0
        if self._current_net is not None and layer in _CONDUCTOR_LAYERS:
            self.conductors.append((self._current_net, layer, _r(x0), _r(y0), _r(x1), _r(y1)))

    def label(self, layer: str, text: str, x: float, y: float) -> None:
        pass

    def pin(self, net: str, x0: float, y0: float, x1: float, y1: float, layer: str | None = None) -> None:
        self.pins.setdefault(net, []).append((_r(x0), _r(y0), _r(x1), _r(y1)))

    @contextmanager
    def net(self, name: str) -> Iterator[None]:
        prev = self._current_net
        self._current_net = name
        try:
            yield
        finally:
            self._current_net = prev

    def via(self, net: str, kind: str, x: float, y: float) -> None:
        self.vias.append((net, kind, _r(x), _r(y)))
