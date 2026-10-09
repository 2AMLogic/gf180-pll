"""Grade a written ``pll_top.gds``: blocks present, nets joined, nothing shorted (issue #297).

Reads only the GDS file and ``design/netlist/pll_top.spice`` -- never the
assembler's in-memory state -- so a defect the router did not know it made is
still caught.

1. **Blocks.** The top cell instantiates exactly the five block cells, once
   each, and every one of them draws geometry on the device layers
   (``comp``/``poly2``/``contact``/``metal1``). A missing block, or a box
   standing in for one, fails here.
2. **Connectivity, differential.** Each block cell is extracted *standalone*
   (:mod:`extract`), and every label in it is put in a group: the standalone
   net it sits on. A group containing one of the block's ports takes that
   port's top-level net from the netlist (``pfd_cp.VOUT`` -> ``VCTRL``);
   any other group is block-internal (``pfd_cp:<id>``). The whole chip is then
   extracted, every label is probed again in top-level coordinates, and:

   * a chip-level net carrying two different identities is a **short**
     (including a top-level via stack that landed on a block's internal net);
   * a top-level net whose identities fall on more than one chip-level net is
     an **open**;
   * every ``pll_top`` pin must be labelled at the top level, on the same net.

   Because the reference is each block's own standalone extraction, what a
   block already connects through device-level layers is never re-litigated
   here -- that is each block's own LVS evidence. This checks what assembly
   adds.
3. **Star supplies.** For ``VDD`` and ``VSS``, the top-level wiring alone
   (Metal4/Via4/Metal5, without the pad bar) must fall apart into exactly one
   piece per block that uses the supply, each piece carrying one riser into
   one block: the branches meet only at the pad (``PLL-FLOORPLAN.md`` §2).
4. **Keep-outs.** No top-level shape of a non-VCO net within the VCO's 15 um
   keep-out, and no top-level shape near a MIM top plate.

What it does not do: model the substrate as a conductor. ``GND_VCO`` and
``VSS`` are separate pins on one p-substrate; this check shows the *routing*
keeps them apart. Whether a foundry LVS run merges them through the substrate
is an LVS question this check does not answer (see the evidence record).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import extract as X
from . import netlist as NL
from . import route as R
from .extract import db

VCO_GUARD_MARGIN_UM = 15.0
STAR_NETS = ("VDD", "VSS")


@dataclass
class Report:
    problems: list[str] = field(default_factory=list)
    shorts: list[tuple[str, ...]] = field(default_factory=list)
    opens: dict[str, int] = field(default_factory=dict)
    star: dict[str, list[str]] = field(default_factory=dict)  # net -> branch descriptions
    nets_checked: int = 0
    labels_checked: int = 0
    pin_nets: int = 0  # top-level nets that reach at least one block through a subcircuit pin

    @property
    def ok(self) -> bool:
        return not self.problems and not self.shorts and not self.opens

    def summary(self) -> str:
        head = (
            f"pll_top netcheck: {'OK' if self.ok else 'FAIL'} "
            f"({self.labels_checked} labels, {self.nets_checked} top-level nets, "
            f"{self.pin_nets} chip nets reaching a block pin)"
        )
        lines = [head]
        lines += [f"  short: {' / '.join(s)}" for s in self.shorts]
        lines += [f"  open:  {n} splits into {k} pieces" for n, k in sorted(self.opens.items())]
        lines += [f"  {p}" for p in self.problems]
        for net, branches in sorted(self.star.items()):
            lines.append(f"  star {net}: {len(branches)} branch(es): {', '.join(branches)}")
        return "\n".join(lines)


def _blocks():
    from .assemble import BLOCKS  # noqa: PLC0415 -- avoid an import cycle at module load

    return BLOCKS


def check(gds: Path, netlist: NL.TopNetlist | None = None) -> Report:
    _db = db()
    nl = netlist or NL.read()
    rep = Report()
    ly, top = X.read_top(gds)
    if top.name != "pll_top":
        rep.problems.append(f"top cell is {top.name!r}, expected 'pll_top'")

    # --- 1. blocks --------------------------------------------------------------
    specs = {s.cell: s for s in _blocks()}
    insts: dict[str, list] = {}
    for inst in top.each_inst():
        insts.setdefault(ly.cell(inst.cell_index).name, []).append(inst)
    for cell_name, spec in specs.items():
        found = insts.get(cell_name, [])
        if len(found) != 1:
            rep.problems.append(f"block {spec.subckt} (cell {cell_name}): {len(found)} instance(s) in pll_top, expected 1")
    for cell_name in insts:
        if cell_name not in specs:
            rep.problems.append(f"unexpected instance of cell {cell_name!r} in pll_top")
    placed = {name: lst[0] for name, lst in insts.items() if name in specs and len(lst) == 1}
    for cell_name, inst in placed.items():
        cell = ly.cell(inst.cell_index)
        for lname in ("comp", "poly2", "contact", "metal1"):
            idx = ly.find_layer(*X.LAYER[lname])
            if idx is None or cell.bbox_per_layer(idx).empty():
                rep.problems.append(
                    f"block {specs[cell_name].subckt}: cell {cell_name} draws nothing on {lname} -- "
                    "a boundary or placement box is not a block layout"
                )

    # --- 2. connectivity --------------------------------------------------------
    chip = X.extract_layout(ly, top)
    identities: dict[tuple, set] = {}  # chip net (circuit, cluster) -> identities
    where: dict[str, set] = {}  # identity -> chip clusters

    def note(identity: str, cluster) -> None:
        identities.setdefault(cluster, set()).add(identity)
        where.setdefault(identity, set()).add(cluster)

    port_nets: dict[str, dict[str, str]] = {}
    standalone: dict[str, tuple] = {}  # cell name -> (extraction, {standalone net key: identity})
    for cell_name, inst in placed.items():
        spec = specs[cell_name]
        cell = ly.cell(inst.cell_index)
        pmap = nl.instance(spec.subckt).port_net()
        port_nets[spec.subckt] = pmap
        alone = X.extract_layout(ly, cell)
        groups: dict[tuple, list[X.Label]] = {}
        standalone[cell_name] = (alone, {})
        for lab in alone.labels:
            cid = alone.cluster_at(lab.layer, lab.x, lab.y)
            if cid is None:
                rep.problems.append(f"{spec.subckt}: label {lab.text} at ({lab.x}, {lab.y}) on {lab.layer} lands on no shape")
                continue
            groups.setdefault(cid, []).append(lab)
        for cid, labs in groups.items():
            ports = sorted({lab.text for lab in labs if lab.text in pmap})
            nets = sorted({pmap[p] for p in ports})
            if len(nets) > 1:
                rep.shorts.append(tuple(f"{spec.subckt}.{p}" for p in ports))
                continue
            identity = nets[0] if nets else f"{spec.subckt}:{cid[1]}"
            standalone[cell_name][1][cid] = identity
            for lab in labs:
                p = inst.dcplx_trans * _db.DPoint(lab.x, lab.y)
                net = chip.l2n.probe_net(chip.layers[lab.layer], p)
                rep.labels_checked += 1
                if net is None:
                    rep.problems.append(f"{spec.subckt}: label {lab.text} lands on no shape after placement at {p}")
                    continue
                note(identity, X.net_key(net))

    # top-level pin labels (the top cell's own texts only)
    top_pins: dict[str, list] = {}
    for metal in X.METALS:
        idx = ly.find_layer(*X.LABEL_LAYER[metal])
        if idx is None:
            continue
        for s in top.shapes(idx).each():
            if s.is_text():
                txt = s.text
                p = _db.DPoint(txt.x * ly.dbu, txt.y * ly.dbu)
                net = chip.l2n.probe_net(chip.layers[metal], p)
                rep.labels_checked += 1
                if net is None:
                    rep.problems.append(f"top-level pin {txt.string} at {p} lands on no shape")
                    continue
                top_pins.setdefault(txt.string, []).append(X.net_key(net))
                note(txt.string, X.net_key(net))
    for pin in nl.pins:
        if pin not in top_pins:
            rep.problems.append(f"pll_top pin {pin} has no top-level label")
    for pin in top_pins:
        if pin not in nl.pins:
            rep.problems.append(f"top-level label {pin!r} is not a pll_top pin")

    for cluster, ids in identities.items():
        if len(ids) > 1:
            rep.shorts.append(tuple(sorted(ids)))
    top_nets = set(nl.pins) | set(nl.terminals())
    for identity, clusters in where.items():
        if identity in top_nets and len(clusters) > 1:
            rep.opens[identity] = len(clusters)
    rep.nets_checked = len([n for n in where if n in top_nets])
    for net, terms in nl.terminals().items():
        if net not in where:
            rep.problems.append(f"net {net} ({terms}) has no label anywhere in the layout")

    # --- 2b. every net the top level touches, labelled or not ------------------
    _pin_audit(chip, ly, specs, standalone, rep)

    # --- 3. star supplies ---------------------------------------------------------
    for net in STAR_NETS:
        _star(ly, top, net, nl, placed, specs, rep)

    # --- 4. keep-outs ---------------------------------------------------------------
    _keepouts(ly, top, chip, placed, specs, port_nets, identities, rep)
    return rep


def _interior_point(region):
    """Some point strictly inside ``region`` (dbu), or ``None``."""
    for poly in region.each():
        for trap in poly.decompose_trapezoids():
            bb = trap.bbox()
            if bb.width() > 0 and bb.height() > 0:
                return bb.center()
    return None


def _pin_audit(chip, ly, specs, standalone, rep: Report) -> None:
    """Every block net the top level connects to must be a port, and one port per top net.

    The label check above only sees nets that carry a label. This one walks the
    chip netlist itself: each top-level net lists the block-circuit nets it
    reaches through subcircuit pins, and each of those is identified by probing
    the block's standalone extraction at a point on it. A top-level wire that
    touched an unlabelled internal net of a block shows up here as a pin on a
    net with no port identity.
    """
    _db = db()
    netlist = chip.l2n.netlist()
    top_c = netlist.circuit_by_name("pll_top")
    if top_c is None:
        rep.problems.append("chip netlist has no pll_top circuit")
        return
    probe_layers = ("metal3", "metal2", "metal1", "poly", "ntap", "pdiff", "nwell")
    for net in top_c.each_net():
        ids = set()
        for sp in net.each_subcircuit_pin():
            sc = sp.subcircuit()
            circ = sc.circuit_ref()
            inner = circ.net_for_pin(sp.pin())
            if circ.name not in standalone or inner is None:
                ids.add(f"?{circ.name}")
                continue
            alone, ident = standalone[circ.name]
            found = None
            for lname in probe_layers:
                r = chip.l2n.shapes_of_net(inner, chip.layers[lname], True)
                pt = _interior_point(r)
                if pt is None:
                    continue
                key = alone.cluster_at(lname, pt.x * ly.dbu, pt.y * ly.dbu)
                if key is not None:
                    found = key
                    break
            if found is None:
                ids.add(f"{specs[circ.name].subckt}:unprobed")
            else:
                ids.add(ident.get(found, f"{specs[circ.name].subckt}:internal-{found[1]}"))
        if not ids:
            continue
        internal = sorted(i for i in ids if ":" in i or i.startswith("?"))
        if len(ids) > 1 or internal:
            short = tuple(sorted(ids))
            if short not in rep.shorts:
                rep.shorts.append(short)
        rep.pin_nets += 1


def _top_only_region(ly, top, lname: str):
    _db = db()
    idx = ly.find_layer(*X.LAYER[lname])
    r = _db.Region()
    if idx is not None:
        r.insert(top.shapes(idx))
    return r


def _star(ly, top, net, nl, placed, specs, rep: Report) -> None:
    """Top-level wiring of ``net`` minus its pad must split into one branch per block."""
    _db = db()
    users = sorted(b for b, _ in nl.terminals().get(net, []))
    pin_xy = None
    idx = ly.find_layer(*X.LABEL_LAYER["metal5"])
    if idx is not None:
        for s in top.shapes(idx).each():
            if s.is_text() and s.text.string == net:
                pin_xy = _db.Point(s.text.x, s.text.y)
    if pin_xy is None:
        rep.problems.append(f"star {net}: no pad label")
        return
    m5 = _top_only_region(ly, top, "metal5")
    m4 = _top_only_region(ly, top, "metal4")
    v4 = _top_only_region(ly, top, "via4")
    v3 = _top_only_region(ly, top, "via3")
    pad = _db.Region([p for p in m5.each() if p.inside(pin_xy)])
    if pad.is_empty():
        rep.problems.append(f"star {net}: the pad label is not on a Metal5 shape")
        return
    # the wiring of this supply: top-level shapes connected to the pad, through
    # Metal5 <-> Via4 <-> Metal4, the pad itself included
    layers = {"m5": m5, "m4": m4, "v4": v4, "v3": v3}
    wiring = _flood(layers, pad)
    # remove the pad, then flood again from each remaining piece
    rest = {k: (v - pad if k == "m5" else v) for k, v in wiring.items()}
    pieces = []
    seen = _db.Region()
    for poly in rest["m5"].each():
        seed = _db.Region(poly)
        if not (seed & seen).is_empty():
            continue
        comp = _flood({k: rest[k] for k in rest}, seed)
        seen += comp["m5"]
        pieces.append(comp)
    descr = []
    risers_total = 0
    for comp in pieces:
        hits = []
        for cell_name, inst in placed.items():
            bb = ly.cell(inst.cell_index).bbox().transformed(inst.cplx_trans)
            if not comp["v3"].interacting(_db.Region(bb)).is_empty():
                hits.append(specs[cell_name].subckt)
        risers_total += len(hits)
        descr.append("+".join(hits) if hits else "(no riser)")
    rep.star[net] = descr
    if sorted(descr) != users:
        rep.problems.append(
            f"star {net}: top-level wiring minus the pad splits into {descr}, expected one branch per block {users}"
        )


def _flood(layers: dict, seed) -> dict:
    """Shapes of ``layers`` (m5/m4/v4/v3) transitively connected to ``seed`` (on m5)."""
    _db = db()
    got = {k: _db.Region() for k in layers}
    got["m5"] = layers["m5"].interacting(seed)
    while True:
        v4 = layers["v4"].interacting(got["m5"]) + layers["v4"].interacting(got["m4"])
        m4 = layers["m4"].interacting(v4)
        m5 = layers["m5"].interacting(v4) + got["m5"]
        v3 = layers["v3"].interacting(m4)
        m4.merge()
        m5.merge()
        grew = (m4.area() != got["m4"].area()) or (m5.area() != got["m5"].area())
        got.update(m4=m4, m5=m5, v4=v4, v3=v3)
        if not grew:
            return got


def _keepouts(ly, top, chip, placed, specs, port_nets, identities, rep: Report) -> None:
    _db = db()
    vco_nets = set(port_nets.get("vco", {}).values())
    vco_cell = next((c for c, s in specs.items() if s.subckt == "vco"), None)
    fusetop = _db.Region()
    fidx = ly.find_layer(*X.LAYER["fusetop"])
    if fidx is not None:
        fusetop = _db.Region(top.begin_shapes_rec(fidx))
    zone = None
    if vco_cell in placed:
        inst = placed[vco_cell]
        bb = ly.cell(inst.cell_index).bbox().transformed(inst.cplx_trans)
        m = R.um(VCO_GUARD_MARGIN_UM)
        zone = _db.Region(bb.enlarged(m, m))
    mim_zone = fusetop.sized(R.um(R.FUSETOP_KEEPOUT_UM) - 5)
    for lname in ("metal4", "metal5", "via3", "via4"):
        for poly in _top_only_region(ly, top, lname).each():
            r = _db.Region(poly)
            if not (r & mim_zone).is_empty():
                rep.problems.append(f"top-level {lname} shape {poly.bbox()} within the MIM keep-out")
            if zone is None or (r & zone).is_empty() or not lname.startswith("metal"):
                continue
            c = poly.bbox().center()
            net = chip.l2n.probe_net(chip.layers[lname], _db.DPoint(c.x * ly.dbu, c.y * ly.dbu))
            ids = identities.get(X.net_key(net), set()) if net is not None else set()
            if not ids or not ids <= vco_nets:
                rep.problems.append(
                    f"top-level {lname} shape {poly.bbox()} of {sorted(ids) or 'an unlabelled net'} "
                    f"inside the VCO's {VCO_GUARD_MARGIN_UM:g} um keep-out"
                )
