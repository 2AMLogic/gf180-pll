"""Chip-level conductor extraction for the assembled ``pll_top`` (issue #297).

One ``klayout.db.LayoutToNetlist`` over every conducting layer the five blocks
and the top-level routing draw: diffusion, poly, contact, Metal1-Metal5,
Via1-Via4, the n-well and the MIM top plate (``FuseTop``). It is used twice:

* by :mod:`access`, on one *standalone* block, to find the shapes of the net a
  port label sits on (so a via stack can be dropped onto that net and nowhere
  else), and
* by :mod:`netcheck`, on the written ``pll_top.gds``, to grade what the
  finished layout actually connects.

The boundaries are the ones ``layout/pll_top/loop_filter/netcheck.py``
established for the loop filter, generalised to transistor blocks:

* **Resistor bodies are cut out of poly** (``poly2 NOT res_mk``), so a
  resistor's two ends are two nets.
* **A MOS gate splits its diffusion** (``comp NOT poly2``): source and drain
  are separate nets, and the gate is not joined to either.
* **Only n+ diffusion inside an n-well joins that n-well** (the n-tap). A p+
  source/drain inside the same well does not -- otherwise every PMOS drain
  would read as shorted to its supply.
* **The MIM plates are kept apart.** Via2 inside ``FuseTop`` lands on the top
  plate and not on the Metal2 bottom plate under it, as the foundry LVS deck's
  ``via2_cap``/``via2_n_cap`` split does. A naive flood would report the loop
  filter's ``VCTRL`` shorted to ``VSS`` on a correct layout.
* **The substrate is not a conductor.** Two substrate taps are joined only if
  they are wired together. That is deliberate (see ``netcheck``): ``GND_VCO``
  and ``VSS`` are separate pins of ``pll_top`` that share one p-substrate, and a
  metal-level check must be able to tell whether *the routing* keeps them apart.

Nothing here recognises devices or their values; each block's own foundry LVS
run (its evidence directory) is what does that.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

#: GDS (layer, datatype) of every layer this package reads or draws.
LAYER: dict[str, tuple[int, int]] = {
    "nwell": (21, 0),
    "comp": (22, 0),
    "poly2": (30, 0),
    "pplus": (31, 0),
    "nplus": (32, 0),
    "contact": (33, 0),
    "metal1": (34, 0),
    "via1": (35, 0),
    "metal2": (36, 0),
    "via2": (38, 0),
    "via3": (40, 0),
    "via4": (41, 0),
    "metal3": (42, 0),
    "metal4": (46, 0),
    "fusetop": (75, 0),
    "metal5": (81, 0),
    "res_mk": (110, 5),
}

#: Pin-purpose (text) datatype of each metal, per the PDK layer map
#: (``libs.tech/klayout/tech/gf180mcu.map``: ``MetalN PIN <layer> 10``).
LABEL_LAYER: dict[str, tuple[int, int]] = {
    "metal1": (34, 10),
    "metal2": (36, 10),
    "metal3": (42, 10),
    "metal4": (46, 10),
    "metal5": (81, 10),
}

METALS = ("metal1", "metal2", "metal3", "metal4", "metal5")
#: via layer between METALS[i] and METALS[i + 1]
VIAS = ("via1", "via2", "via3", "via4")


def db():
    import klayout.db as _db  # noqa: PLC0415 -- lazy, same convention as every generator

    return _db


@dataclass(frozen=True)
class Label:
    text: str
    layer: str  # one of METALS
    x: float  # um, in the coordinates of the layout that was extracted
    y: float


@dataclass
class Extraction:
    l2n: object
    layers: dict = field(default_factory=dict)
    dbu: float = 0.001
    labels: list[Label] = field(default_factory=list)

    def net_at(self, layer: str, x: float, y: float):
        net = self.l2n.probe_net(self.layers[layer], db().DPoint(x, y))
        return None if net is None else net

    def cluster_at(self, layer: str, x: float, y: float):
        """A hashable identity of the net under ``(x, y)``, or ``None``.

        The extraction is hierarchical: a net that never leaves a block cell
        is reported in that cell's circuit, and cluster ids restart in every
        circuit, so the identity is ``(circuit name, cluster id)``.
        """
        return net_key(self.net_at(layer, x, y))

    def shapes(self, net, layer: str):
        """Merged ``Region`` (dbu) of ``net`` on extraction layer ``layer``."""
        r = self.l2n.shapes_of_net(net, self.layers[layer], True)
        r.merge()
        return r


def net_key(net):
    return None if net is None else (net.circuit().name, net.cluster_id)


def read_top(gds: Path):
    _db = db()
    ly = _db.Layout()
    ly.read(str(gds))
    tops = ly.top_cells()
    if len(tops) != 1:
        raise ValueError(f"{gds}: expected exactly one top cell, found {[t.name for t in tops]}")
    return ly, tops[0]


def labels_of(ly, top) -> list[Label]:
    """Every text on a metal drawing or pin-purpose layer, in top-cell coordinates.

    Some blocks (``pfd_cp``'s internal nets) put their names on the drawing
    datatype rather than the pin one; both are read, and each label is
    attributed to the metal it is drawn on.
    """
    out: list[Label] = []
    for metal in METALS:
        for gl in (LAYER[metal], LABEL_LAYER[metal]):
            idx = ly.find_layer(*gl)
            if idx is None:
                continue
            it = top.begin_shapes_rec(idx)
            while not it.at_end():
                s = it.shape()
                if s.is_text():
                    t = s.text.transformed(it.trans())
                    out.append(Label(t.string, metal, round(t.x * ly.dbu, 6), round(t.y * ly.dbu, 6)))
                it.next()
    return out


def extract_layout(ly, top) -> Extraction:
    """Extract ``top`` of an in-memory layout. See the module docstring."""
    _db = db()
    l2n = _db.LayoutToNetlist(_db.RecursiveShapeIterator(ly, top, []))

    def raw(name):
        idx = ly.find_layer(*LAYER[name])
        if idx is None:
            idx = ly.layer(*LAYER[name])
        return l2n.make_polygon_layer(idx, name)

    R = {name: raw(name) for name in LAYER}
    poly = R["poly2"] - R["res_mk"]
    diff = R["comp"] - R["poly2"]
    ntap = diff & R["nplus"] & R["nwell"]
    pdiff = diff - ntap
    v2_ncap = R["via2"] - R["fusetop"]
    v2_cap = R["via2"] & R["fusetop"]
    for name, reg in (("poly", poly), ("ntap", ntap), ("pdiff", pdiff), ("via2_ncap", v2_ncap), ("via2_cap", v2_cap)):
        l2n.register(reg, name)

    layers = {
        "poly": poly,
        "ntap": ntap,
        "pdiff": pdiff,
        "nwell": R["nwell"],
        "contact": R["contact"],
        "via2_ncap": v2_ncap,
        "via2_cap": v2_cap,
        "fusetop": R["fusetop"],
    }
    for name in METALS + ("via1", "via3", "via4"):
        layers[name] = R[name]
    for reg in layers.values():
        l2n.connect(reg)

    l2n.connect(R["contact"], poly)
    l2n.connect(R["contact"], ntap)
    l2n.connect(R["contact"], pdiff)
    l2n.connect(R["contact"], R["metal1"])
    l2n.connect(R["nwell"], ntap)
    l2n.connect(R["metal1"], R["via1"])
    l2n.connect(R["via1"], R["metal2"])
    l2n.connect(R["metal2"], v2_ncap)
    l2n.connect(v2_ncap, R["metal3"])
    l2n.connect(R["fusetop"], v2_cap)
    l2n.connect(v2_cap, R["metal3"])
    l2n.connect(R["metal3"], R["via3"])
    l2n.connect(R["via3"], R["metal4"])
    l2n.connect(R["metal4"], R["via4"])
    l2n.connect(R["via4"], R["metal5"])
    l2n.extract_netlist()
    return Extraction(l2n=l2n, layers=layers, dbu=ly.dbu, labels=labels_of(ly, top))


def extract(gds: Path) -> Extraction:
    ly, top = read_top(gds)
    ex = extract_layout(ly, top)
    ex._layout = ly  # keep the layout alive as long as the extraction
    return ex
