"""Pure-Python short/open connectivity checks for ``lock_detector`` (issue #322).

``layout/evidence/lock-detector-layout/``'s DRC-clean result cannot see a
*short*: two different nets' shapes overlapping on one layer merge into a
single polygon that is perfectly legal by every width/space/enclosure rule.
It cannot see an *open* either: a net drawn as two pieces that never
actually touch is likewise geometrically legal. Only LVS (which needs a
foundry deck and a reference netlist) or an explicit connectivity check over
the design's own net-tagged shapes catches either one -- this module is that
check, ported from ``pfd_cp/rowgen.py``'s ``shorted_pairs()``/
``disconnected_nets()`` (issue #300), which independently proved the same
approach for a different full-custom block in this repo.

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
from typing import Iterable, Iterator

from . import primitives as P

#: (net, layer, x0, y0, x1, y1) -- one Metal1/Metal2/Metal3 shape.
Conductor = tuple[str, str, float, float, float, float]
#: (net, "via1" | "via2", x, y) -- where a net changes layer.
Via = tuple[str, str, float, float]

#: Which two metal layers each via kind joins.
VIA_LAYERS = {"via1": ("metal1", "metal2"), "via2": ("metal2", "metal3")}

_CONDUCTOR_LAYERS = frozenset({"metal1", "metal2", "metal3"})
_TOUCH_EPS = 1e-6


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
