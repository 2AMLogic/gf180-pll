"""Where a top-level wire can land on a block's port (issue #297).

The block generators put their port labels wherever their own routing ended,
mostly in the interior, on Metal1-Metal3. A top-level wire reaches one by a
via stack from the port's own net up to Metal4: Via(k)..Via3 at one point,
with a pad on each metal in between. That point has to satisfy, all at once:

* the via array, grown by :data:`route.LAND_ENC_UM`, lies inside the port
  net's own shape on the landing metal (so no new geometry is drawn on that
  metal at all -- the via simply lands on existing wire);
* every pad drawn on the metals above the landing layer keeps
  :data:`route.METAL_CLEAR_UM` from every *other* net's shape in the block,
  and either overlaps or keeps the same clearance from the port net's own
  shapes (no near-miss notch);
* every via keeps :data:`route.VIA_CLEAR_UM` from every via already on its
  layer, the block's and the top level's;
* nothing comes within :data:`route.FUSETOP_KEEPOUT_UM` of a MIM top plate --
  a Via2 inside ``FuseTop`` would land on the capacitor's top plate, and the
  loop filter's limitations (variant-D ``MIMTM.3``) are carried forward, not
  edited around;
* the Metal5 column the wire then needs, from the point to its channel or to
  the chip edge, does not cross a column another net has already reserved.

:func:`find` searches the port net's own shapes for such a point, nearest to
a caller-given preference first, and raises :class:`NoAccess` if there is
none -- never a silent fallback to a point on some other net.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

from . import extract as X
from . import route as R
from .extract import db

LANDING_ORDER = ("metal3", "metal2", "metal1")
#: preference penalty (um) per step down the landing order -- a deeper stack
#: is more vias and more pads to clear, so a slightly farther Metal3 point wins.
LANDING_PENALTY_UM = {"metal3": 0.0, "metal2": 3.0, "metal1": 8.0}


class NoAccess(RuntimeError):
    pass


@dataclass
class BlockView:
    """One placed block: its cell, placement, and its geometry in top-level dbu."""

    name: str  # subckt name in pll_top.spice, e.g. "pfd_cp"
    cell: object
    trans: object  # db.Trans, block -> top
    ex: X.Extraction  # standalone extraction of the block's own cell (block coords)
    layers: dict = field(default_factory=dict)  # name -> Region (top coords)
    bbox: object = None  # db.Box (top coords)
    _port_cache: dict = field(default_factory=dict)

    def label(self, port: str) -> X.Label:
        for lab in self.ex.labels:
            if lab.text == port:
                return lab
        raise KeyError(f"{self.name}: no label {port!r}")

    def port_regions(self, port: str) -> dict:
        """``{metal: Region}`` of the port's net, top coords (cached)."""
        if port not in self._port_cache:
            lab = self.label(port)
            net = self.ex.net_at(lab.layer, lab.x, lab.y)
            if net is None:
                raise NoAccess(f"{self.name}.{port}: label at ({lab.x}, {lab.y}) on {lab.layer} lands on no shape")
            self._port_cache[port] = {
                m: self.ex.shapes(net, m).transformed(self.trans) for m in ("metal1", "metal2", "metal3")
            }
        return self._port_cache[port]


def make_view(name: str, layout, cell, trans) -> BlockView:
    _db = db()
    ex = X.extract_layout(layout, cell)
    layers = {}
    for lname in ("metal1", "metal2", "metal3", "via1", "via2", "fusetop"):
        idx = layout.find_layer(*X.LAYER[lname])
        r = _db.Region() if idx is None else _db.Region(cell.begin_shapes_rec(idx))
        r.merge()
        layers[lname] = r.transformed(trans)
    bbox = cell.bbox().transformed(trans)
    return BlockView(name=name, cell=cell, trans=trans, ex=ex, layers=layers, bbox=bbox)


@dataclass
class Access:
    block: str
    port: str
    net: str  # top-level net
    key: str  # board key: net, or NET@block for a supply branch
    x: int  # dbu, top coords
    y: int
    landing: str  # metal the stack lands on
    n_via: int

    def stack_layers(self) -> list[str]:
        """Via layers from the landing metal up to Via3."""
        order = list(R.METALS)
        return [R.VIA_ABOVE[m] for m in order[order.index(self.landing) : order.index("metal4")]]

    def pad_metals(self) -> list[str]:
        order = list(R.METALS)
        return list(order[order.index(self.landing) + 1 : order.index("metal4")])


def _touches(region, box) -> bool:
    _db = db()
    return not region.interacting(_db.Region(box)).is_empty()


def _snap(v: float) -> int:
    return int(round(v / 5.0)) * 5


def _axis(lo: int, hi: int, step: int) -> list[int]:
    """Sample ``lo..hi`` (dbu) every ~``step``, always including the midpoint, on the 5 nm grid."""
    n = max(1, (hi - lo) // step + 1)
    pts = {_snap((lo + hi) / 2.0)}
    if n > 1:
        pts.update(_snap(lo + (hi - lo) * k / (n - 1)) for k in range(n))
    return sorted(p for p in pts if lo <= p <= hi)


def _grid_points(region, step: int, limit: int = 60000):
    """Candidate centres (dbu, 5 nm grid) inside ``region``'s polygons.

    Every polygon contributes its own midpoint lines, so a wire that is
    exactly wide enough for a via (an eroded region one grid step wide) still
    yields its centre line rather than falling between two grid points.
    """
    _db = db()
    out = []
    for poly in region.each():
        bb = poly.bbox()
        s2 = step
        nx = max(1, bb.width() // step + 1)
        ny = max(1, bb.height() // step + 1)
        if nx * ny > limit:
            s2 = step * int(math.ceil(math.sqrt(nx * ny / limit)))
        for y in _axis(bb.bottom, bb.top, s2):
            for x in _axis(bb.left, bb.right, s2):
                if poly.inside(_db.Point(x, y)):
                    out.append((x, y))
    return out


def find(
    view: BlockView,
    port: str,
    net: str,
    *,
    key: str | None = None,
    n_via: int = 1,
    score: Callable[[int, int], float],
    column_span: Callable[[int, int], tuple[int, int]],
    column_width_um: float,
    board: R.Board,
    columns: list,
    keepout,
) -> tuple[Access, R.Column]:
    """Best legal access point for ``view``'s ``port``; see the module docstring.

    ``score(x, y)`` ranks candidates (lower is better, um); ``column_span(x, y)``
    gives the (y0, y1) dbu span of the Metal5 column the wire will need from
    there; ``keepout`` is a Region no stack or column may touch.
    """
    key = key or net
    regs = view.port_regions(port)
    half = R.um(R.via_array_half_um(n_via))
    land = R.um(R.LAND_ENC_UM)
    clear = R.um(R.METAL_CLEAR_UM)
    vclear = R.um(R.VIA_CLEAR_UM)
    others = {m: view.layers[m] - regs[m] for m in ("metal1", "metal2", "metal3")}
    cw = R.um(column_width_um)
    _db = db()

    candidates = []
    for landing in LANDING_ORDER:
        r = regs[landing]
        if r.is_empty():
            continue
        centres = r.sized(-(half + land) + 5)  # 5 dbu slack: exact check below
        if centres.is_empty():
            continue
        area_um2 = centres.area() * R.DBU * R.DBU
        step = max(R.um(0.1), R.um(math.sqrt(max(area_um2, 1e-6) / 20000.0)))
        for x, y in _grid_points(centres, step):
            candidates.append((score(x, y) + LANDING_PENALTY_UM[landing], landing, x, y))
    if not candidates:
        raise NoAccess(f"{view.name}.{port}: no shape of the port net is wide enough to land a {n_via}x{n_via} via array on")
    candidates.sort(key=lambda c: c[0])

    reasons: dict[str, int] = {}

    def reject(why: str) -> None:
        reasons[why] = reasons.get(why, 0) + 1

    for _, landing, x, y in candidates:
        acc = Access(view.name, port, net, key, x, y, landing, n_via)
        stack_extent = R.pad_box(x, y, n_via)
        if _touches(keepout, stack_extent):
            reject("MIM keep-out")
            continue
        # landing enclosure, exact (the sized() erosion above is only a pre-filter)
        enc = _db.Box(x - half - land, y - half - land, x + half + land, y + half + land)
        if not (_db.Region(enc) - regs[landing]).is_empty():
            reject("landing enclosure")
            continue
        ok = True
        for vl in acc.stack_layers():
            vb = _db.Box(x - half, y - half, x + half, y + half).enlarged(vclear, vclear)
            if vl in view.layers and _touches(view.layers[vl], vb):
                ok = False
                reject(f"{vl} near a block via")
                break
            if board.conflicts(vl, _db.Box(x - half, y - half, x + half, y + half), key):
                ok = False
                reject(f"{vl} near a top-level via")
                break
        if not ok:
            continue
        for m in acc.pad_metals():
            pad = R.pad_box(x, y, n_via)
            grown = pad.enlarged(clear, clear)
            if _touches(others[m], grown):
                ok = False
                reject(f"{m} pad near another net")
                break
            if _touches(regs[m], grown) and not _touches(regs[m], pad):
                ok = False
                reject(f"{m} pad near-miss on its own net")
                break
            if board.conflicts(m, pad, key):
                ok = False
                reject(f"{m} pad near a top-level pad")
                break
        if not ok:
            continue
        m4 = R.pad_box(x, y, n_via).enlarged(max(0, cw // 2 - R.pad_box(x, y, n_via).width() // 2), max(0, cw // 2 - R.pad_box(x, y, n_via).height() // 2))
        if board.conflicts("metal4", m4, key):
            reject("metal4 pad conflict")
            continue
        y0, y1 = column_span(x, y)
        col = R.Column(key, x, y0, y1, cw)
        if _touches(keepout, col.box()):
            reject("column crosses MIM keep-out")
            continue
        if any(R.columns_conflict(col, c) for c in columns):
            reject("column conflict")
            continue
        return acc, col
    detail = ", ".join(f"{k}: {v}" for k, v in sorted(reasons.items(), key=lambda kv: -kv[1]))
    raise NoAccess(f"{view.name}.{port}: {len(candidates)} candidate point(s), none legal ({detail})")
