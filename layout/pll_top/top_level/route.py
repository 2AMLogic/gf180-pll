"""Top-level wiring for ``pll_top``: rule constants, a net-aware shape store, and channel tracks.

Every top-level wire is Metal4 (horizontal, in the routing channels between
and around the blocks) or Metal5 (vertical, from a block port up or down to
its channel or to the chip edge). No block draws either layer, so a top-level
wire can only ever touch a block through the via stack :mod:`access` drops
onto that block's own port net.

:class:`Board` is the single place shapes are added. It keeps every shape
tagged with the net it belongs to and **refuses** a shape that comes within
the layer's clearance of a shape on a different net, so a short cannot be
drawn by accident; :mod:`netcheck` independently re-checks the written GDS.

Rule values (gf180mcu foundry deck, ``rule_decks/metal*.drc``/``via*.drc``):
Metal2-Metal5 0.28 um min width/space (0.30 um next to a > 10 um wide shape);
Via1-Via4 0.26 um square, 0.26 um space (0.36 um inside a 4x4 or larger
array), metal enclosure 0.01 um (0.06 um end-of-line on lines < 0.34 um);
on this 5-metal stack Metal5 is the top metal (``MT.*``, 0.44 um width,
0.46 um space on the 11 kA option). Every value below is at or above those
with margin; the margin is the point, the top level is not area-limited by
its own wiring.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .extract import db

DBU = 0.001  # um per database unit -- every block generator writes 1 nm


def um(v: float) -> int:
    """um -> dbu, snapped to the 5 nm manufacturing grid."""
    return int(round(v / 0.005)) * 5


# --- rule constants (um) ----------------------------------------------------
VIA_UM = 0.26
VIA_PITCH_UM = 0.62  # 0.36 um space: legal even inside a 4x4 array
VIA_CLEAR_UM = 0.40  # a new via to any existing via on the same layer
LAND_ENC_UM = 0.06  # the port net's own shape must enclose the via this much (EOL 0.06)
PAD_ENC_UM = 0.12  # a drawn pad's enclosure of its via (>= 0.34 um pad: no EOL rule)
METAL_CLEAR_UM = 0.40  # a new pad on Metal1-3 to any other-net shape (wide-metal 0.30)
TOP_CLEAR_UM = 1.0  # Metal4/Metal5 wire to any other-net Metal4/Metal5 wire
SIGNAL_W_UM = 0.6  # Metal4/Metal5 signal wire width (MT.1 0.44)
POWER_W_UM = 2.0  # Metal4/Metal5 supply branch width
SIGNAL_VIAS = 1  # n x n via array at a signal junction
POWER_VIAS = 2  # n x n via array at a supply junction
FUSETOP_KEEPOUT_UM = 3.0  # no top-level shape, and no access stack, this close to a MIM top plate

METALS = ("metal1", "metal2", "metal3", "metal4", "metal5")
VIA_ABOVE = {"metal1": "via1", "metal2": "via2", "metal3": "via3", "metal4": "via4"}


def via_array_half_um(n: int) -> float:
    return (n * VIA_UM + (n - 1) * (VIA_PITCH_UM - VIA_UM)) / 2.0


def via_boxes(cx: int, cy: int, n: int) -> list:
    """``n x n`` via boxes (dbu) centred on ``(cx, cy)``."""
    _db = db()
    half = um(via_array_half_um(n))
    v = um(VIA_UM)
    p = um(VIA_PITCH_UM)
    out = []
    for i in range(n):
        for j in range(n):
            x0 = cx - half + i * p
            y0 = cy - half + j * p
            out.append(_db.Box(x0, y0, x0 + v, y0 + v))
    return out


def pad_box(cx: int, cy: int, n: int, enc_um: float = PAD_ENC_UM):
    _db = db()
    h = um(via_array_half_um(n) + enc_um)
    return _db.Box(cx - h, cy - h, cx + h, cy + h)


def compatible(a: str, b: str) -> bool:
    """May shapes keyed ``a`` and ``b`` touch?

    A key is a net name, or ``NET@block`` for one branch of a star-routed
    supply. Branches of one supply may touch that supply's pad (key ``NET``)
    but never each other -- which is exactly the floorplan's "star-connected at
    the pads, never sharing a segment" rule, enforced at drawing time.
    """
    if a == b:
        return True
    base_a, _, br_a = a.partition("@")
    base_b, _, br_b = b.partition("@")
    return base_a == base_b and (not br_a or not br_b)


class RouteConflict(RuntimeError):
    """A shape would come within clearance of another net's shape."""


@dataclass
class Shape:
    layer: str
    box: object  # db.Box, dbu
    net: str
    role: str  # "wire", "via", "pad", "pin" -- for reports and negative controls
    branch: str = ""  # supply branch id ("VSS@lock_detector"), "" for signals

    @property
    def key(self) -> str:
        return self.branch or self.net


@dataclass
class Board:
    """Every top-level shape, tagged with its net, with a clearance guard."""

    shapes: list[Shape] = field(default_factory=list)

    def _clear_um(self, layer: str) -> float:
        if layer in ("metal4", "metal5"):
            return TOP_CLEAR_UM
        if layer.startswith("via"):
            return VIA_CLEAR_UM
        return METAL_CLEAR_UM

    def conflicts(self, layer: str, box, key: str, clear_um: float | None = None) -> list[Shape]:
        c = um(self._clear_um(layer) if clear_um is None else clear_um)
        grown = box.enlarged(c, c)
        return [s for s in self.shapes if s.layer == layer and not compatible(s.key, key) and s.box.overlaps(grown)]

    def add(self, layer: str, box, net: str, role: str, branch: str = "") -> Shape:
        bad = self.conflicts(layer, box, branch or net)
        if bad:
            raise RouteConflict(
                f"{net} {role} on {layer} at {box} within clearance of "
                + ", ".join(f"{s.net} {s.role} {s.box}" for s in bad[:3])
            )
        s = Shape(layer, box, net, role, branch)
        self.shapes.append(s)
        return s

    def region(self, layer: str, *, net: str | None = None):
        """Every shape on ``layer`` (or only ``net``'s, if given), as one Region."""
        _db = db()
        r = _db.Region()
        for s in self.shapes:
            if s.layer == layer and (net is None or s.net == net):
                r.insert(s.box)
        return r


@dataclass(frozen=True)
class Column:
    """A Metal5 vertical a terminal owns, reserved before any track is placed."""

    net: str  # key: a net, or NET@block for a supply branch
    x: int  # dbu, centre
    y0: int  # dbu, reserved span (y0 < y1)
    y1: int
    width: int  # dbu

    def box(self, clear: int = 0):
        _db = db()
        h = self.width // 2
        return _db.Box(self.x - h - clear, self.y0, self.x + h + clear, self.y1)


def columns_conflict(a: Column, b: Column) -> bool:
    if compatible(a.net, b.net):
        return False
    return a.box(um(TOP_CLEAR_UM)).overlaps(b.box())


@dataclass
class Channel:
    """A horizontal band where Metal4 tracks are packed first-fit from ``start``."""

    name: str
    start: int  # dbu: first track edge
    limit: int  # dbu: tracks may not cross this
    direction: int  # +1 packs upward, -1 packs downward
    used: list[tuple[str, object]] = field(default_factory=list)  # (net, box incl. clearance)

    def place(self, net: str, x0: int, x1: int, width: int) -> int:
        """Lowest-cost track centre y for a ``width`` wire spanning ``x0..x1``."""
        _db = db()
        c = um(TOP_CLEAR_UM)
        step = um(0.5)
        h = width // 2
        edge = self.start
        while True:
            if self.direction > 0:
                yc = edge + h
            else:
                yc = edge - h
            yc = um(yc * DBU)
            box = _db.Box(x0 - h, yc - h, x1 + h, yc + h)
            grown = box.enlarged(c, c)
            if not any(not compatible(n, net) and b.overlaps(grown) for n, b in self.used):
                break
            edge += self.direction * step
            if (self.direction > 0 and yc + h > self.limit) or (self.direction < 0 and yc - h < self.limit):
                raise RouteConflict(f"channel {self.name} is full placing {net}")
        if (self.direction > 0 and yc + h > self.limit) or (self.direction < 0 and yc - h < self.limit):
            raise RouteConflict(f"channel {self.name} is full placing {net}")
        self.used.append((net, box))
        return yc

    def extent(self) -> tuple[int, int] | None:
        if not self.used:
            return None
        ys = [b.bottom for _, b in self.used] + [b.top for _, b in self.used]
        return min(ys), max(ys)
