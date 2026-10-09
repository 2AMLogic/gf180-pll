"""What the *exported* loop-filter GDS actually connects, and what devices it actually draws.

Two checks, both reading only the GDS file (never the generator's in-memory
shapes):

1. :func:`census` -- an independent device census. MOS-cap gates are found as
   ``poly2 AND comp`` interacting ``mos_cap_mk`` inside ``nwell``; MIM caps as
   ``FuseTop`` shapes; plain poly resistors as ``pplus AND poly2 AND sab AND
   res_mk`` -- the LVS deck's own recognition expressions, restated. The
   census also records which forbidden layers appear (the high-Rs ``(62, 0)``
   marker, ``dualgate``, a ``(0, 0)`` boundary box).

2. :func:`extract` + :func:`check_topology` / :func:`check_probes` --
   connectivity. :func:`extract` builds a ``klayout.db.LayoutToNetlist`` over
   diffusion, poly, contacts, metal1-3, Via1/Via2, the n-well and the MIM top
   plate. Two boundaries are deliberate and load-bearing:

   * **The resistor body is cut out of poly** (``poly2 NOT res_mk``), so the
     two ends of each resistor are separate nets -- otherwise the whole chain
     would extract as one node and an open link would be invisible.
   * **The MIM plates are kept apart.** Via2 inside ``FuseTop`` connects Metal3
     to ``FuseTop`` (the top plate) and *not* to the Metal2 underneath it,
     exactly as the foundry LVS deck does (``via2_cap = via2.and(fusetop)``,
     ``connect(fuse_cap, via2_cap)``; ``via2_n_cap = via2.not(fusetop)``,
     ``connect(metal2_con, via2_n_cap)``). A metal-only extraction that lets
     every Via2 join Metal2 to Metal3 -- ``extract(..., plate_aware=False)``
     -- sees the top plate's 1600-via sea land on the bottom plate and reports
     ``VCTRL`` shorted to ``VSS`` on a correct layout. The tests assert that
     too, so this boundary cannot silently regress.

   What it does **not** do: recognise devices or measure their values (that
   is the census above, and the foundry LVS run recorded in the evidence
   directory), or model the substrate as a conductor -- every substrate tap is
   checked to be *wired* to ``VSS`` instead.

:func:`check_topology` derives every device terminal from the census alone and
requires the netlist's topology: the four resistors form one unbranched chain
of five distinct nets; one chain end is shared by all four MOS-cap gates
(``NZ``), the other by the MIM bottom plate and the ``VCTRL`` label; the MIM
top plate, every MOS-cap body diffusion and n-well, every substrate tap and the
``VSS`` label are one net, distinct from all five. :func:`check_probes` checks
the generator's per-terminal expectations (``block.Probe``) against the same
extraction -- named, so a failure says which terminal moved.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

try:
    from . import primitives as prim
except ImportError:  # pragma: no cover - flat-import fallback (layout/tests)
    import primitives as prim  # type: ignore

LABEL_LAYERS = {"metal1_label": "metal1", "metal2_label": "metal2", "metal3_label": "metal3"}


def _db():
    import klayout.db as db  # noqa: PLC0415

    return db


def _read(gds: Path):
    db = _db()
    ly = db.Layout()
    ly.read(str(gds))
    tops = ly.top_cells()
    if len(tops) != 1:
        raise ValueError(f"{gds}: expected exactly one top cell, found {[t.name for t in tops]}")
    return ly, tops[0]


def _region(ly, top, gds_layer: tuple[int, int]):
    db = _db()
    idx = ly.find_layer(*gds_layer)
    if idx is None:
        return db.Region()
    return db.Region(top.begin_shapes_rec(idx))


def _um_box(box, dbu: float) -> tuple[float, float, float, float]:
    return (
        round(box.left * dbu, 6),
        round(box.bottom * dbu, 6),
        round(box.right * dbu, 6),
        round(box.top * dbu, 6),
    )


# ---------------------------------------------------------------------------
# device census
# ---------------------------------------------------------------------------


@dataclass
class Census:
    dbu: float
    mos_gates: list[tuple] = field(default_factory=list)  # um boxes
    mos_polys: list[tuple] = field(default_factory=list)  # poly2 polygon bbox per gate
    mos_body_diffs: list[list[tuple]] = field(default_factory=list)  # per gate: diffusion pieces
    resistor_bodies: list[tuple] = field(default_factory=list)
    resistor_polys: list[tuple] = field(default_factory=list)
    mim_tops: list[tuple] = field(default_factory=list)
    mim_bottoms: list[tuple] = field(default_factory=list)  # metal2 bbox interacting each FuseTop
    substrate_taps: list[tuple] = field(default_factory=list)
    forbidden: dict[str, int] = field(default_factory=dict)
    layer_shapes: dict[tuple[int, int], int] = field(default_factory=dict)
    gate_in_nwell: list[bool] = field(default_factory=list)
    gate_under_nplus: list[bool] = field(default_factory=list)
    mim_has_markers: list[bool] = field(default_factory=list)
    labels: list[tuple[str, str, float, float]] = field(default_factory=list)  # (text, layer, x, y)


def census(gds: Path) -> Census:
    ly, top = _read(gds)
    db = _db()
    dbu = ly.dbu
    R = {name: _region(ly, top, gl) for name, gl in prim.LAYER.items()}
    c = Census(dbu=dbu)

    for li in ly.layer_indexes():
        info = ly.get_info(li)
        n = 0
        it = top.begin_shapes_rec(li)
        while not it.at_end():
            n += 1
            it.next()
        c.layer_shapes[(info.layer, info.datatype)] = n
    for name, gl in prim.FORBIDDEN_LAYERS.items():
        c.forbidden[name] = c.layer_shapes.get(gl, 0)

    # --- MOS caps: the deck's cap_nmos_03v3_b gate expression ---
    gates = (R["poly2"] & R["comp"]).interacting(R["mos_cap_mk"])
    for poly in gates.each():
        box = poly.bbox()
        g = db.Region(poly)
        c.mos_gates.append(_um_box(box, dbu))
        c.gate_in_nwell.append((g - R["nwell"]).is_empty())
        c.gate_under_nplus.append((g - R["nplus"]).is_empty())
        c.mos_polys.append(_um_box(R["poly2"].interacting(g).bbox(), dbu))
        comp = R["comp"].interacting(g)
        diffs = comp - R["poly2"]
        c.mos_body_diffs.append(sorted(_um_box(p.bbox(), dbu) for p in diffs.each()))

    # --- plain ppolyf_u bodies (res_derivations.lvs's ppolyf_u_layer, *before* not_interacting) ---
    bodies = R["pplus"] & R["poly2"] & R["sab"] & R["res_mk"]
    for poly in bodies.each():
        c.resistor_bodies.append(_um_box(poly.bbox(), dbu))
        c.resistor_polys.append(_um_box(R["poly2"].interacting(db.Region(poly)).bbox(), dbu))

    # --- MIM: FuseTop + the metal2 under it ---
    for poly in R["fusetop"].each():
        ft = db.Region(poly)
        c.mim_tops.append(_um_box(poly.bbox(), dbu))
        bottom = (R["metal2"] & ft.sized(int(round(prim.MIM_BOTTOM_ENC_UM / dbu)))).bbox()
        c.mim_bottoms.append(_um_box(bottom, dbu))
        c.mim_has_markers.append(
            not R["cap_mk"].interacting(ft).is_empty()
            and not R["mim_l_mk"].interacting(ft).is_empty()
            and (ft - R["cap_mk"]).is_empty()
            and (ft - R["metal3"]).is_empty()
        )

    # --- substrate taps: every raw comp shape under pplus and outside nwell ---
    comp_idx = ly.find_layer(*prim.LAYER["comp"])
    it = top.begin_shapes_rec(comp_idx)
    while not it.at_end():
        box = it.shape().bbox().transformed(it.trans())
        r = db.Region(box)
        if (r - R["pplus"]).is_empty() and (r & R["nwell"]).is_empty():
            c.substrate_taps.append(_um_box(box, dbu))
        it.next()

    for lname in LABEL_LAYERS:
        idx = ly.find_layer(*prim.LAYER[lname])
        if idx is None:
            continue
        it = top.begin_shapes_rec(idx)
        while not it.at_end():
            s = it.shape()
            if s.is_text():
                t = s.text.transformed(it.trans())
                c.labels.append((t.string, lname, t.x * dbu, t.y * dbu))
            it.next()
    return c


def device_problems(c: Census, *, resistors, mos_caps, mim_caps) -> list[str]:
    """Everything wrong with ``c`` against the ratified device table. Empty means OK."""
    out: list[str] = []
    for name, n in c.forbidden.items():
        if n:
            out.append(f"forbidden layer {name} {prim.FORBIDDEN_LAYERS[name]} carries {n} shape(s)")

    def wh(b):
        return (round(b[2] - b[0], 6), round(b[3] - b[1], 6))

    # MOS caps: count, gate W x L, well and implant
    if len(c.mos_gates) != len(mos_caps):
        out.append(f"{len(c.mos_gates)} MOS-cap gate(s) found, netlist has {len(mos_caps)}")
    want = sorted((m.l_um, m.w_um) for m in mos_caps)
    got = sorted(wh(g) for g in c.mos_gates)
    if got != want[: len(got)] or len(got) != len(want):
        out.append(f"MOS-cap gate extents {got} != netlist {want}")
    for i, (in_nw, under_np) in enumerate(zip(c.gate_in_nwell, c.gate_under_nplus)):
        if not in_nw:
            out.append(f"MOS-cap gate {c.mos_gates[i]} not inside nwell (would not be cap_nmos_03v3_b)")
        if not under_np:
            out.append(f"MOS-cap gate {c.mos_gates[i]} not under nplus")
    for i, diffs in enumerate(c.mos_body_diffs):
        if len(diffs) != 2:
            out.append(f"MOS-cap gate {c.mos_gates[i]} has {len(diffs)} body diffusion strip(s), expected 2")

    # resistors: count and W x L (either orientation of the drawn body is accepted)
    if len(c.resistor_bodies) != len(resistors):
        out.append(f"{len(c.resistor_bodies)} ppolyf_u bodies found, netlist has {len(resistors)}")
    want_r = sorted(tuple(sorted((r.w_um, r.l_um))) for r in resistors)
    got_r = sorted(tuple(sorted(wh(b))) for b in c.resistor_bodies)
    if got_r != want_r:
        out.append(f"ppolyf_u body extents {got_r} != netlist {want_r}")

    # MIM
    if len(c.mim_tops) != len(mim_caps):
        out.append(f"{len(c.mim_tops)} MIM top plate(s) found, netlist has {len(mim_caps)}")
    want_m = sorted((m.w_um, m.l_um) for m in mim_caps)
    got_m = sorted(wh(t) for t in c.mim_tops)
    if got_m != want_m:
        out.append(f"MIM FuseTop extents {got_m} != netlist {want_m}")
    for t, b, ok in zip(c.mim_tops, c.mim_bottoms, c.mim_has_markers):
        enc = min(t[0] - b[0], t[1] - b[1], b[2] - t[2], b[3] - t[3])
        if enc < prim.MIM_BOTTOM_ENC_UM - 1e-9:
            out.append(f"MIM bottom plate encloses FuseTop {t} by only {enc:.3f} um (MIM.3: 0.6)")
        if not ok:
            out.append(f"MIM at {t}: missing cap_mk/mim_l_mk/Metal3 top plate")
    if not c.substrate_taps:
        out.append("no substrate tap found")
    return out


# ---------------------------------------------------------------------------
# connectivity
# ---------------------------------------------------------------------------


@dataclass
class Extraction:
    l2n: object
    layers: dict
    dbu: float

    def net_at(self, layer: str, x: float, y: float):
        """Cluster id of the net under ``(x, y)`` on extraction layer ``layer``, or ``None``."""
        db = _db()
        net = self.l2n.probe_net(self.layers[layer], db.DPoint(x, y))
        return None if net is None else net.cluster_id


def extract(gds: Path, *, plate_aware: bool = True) -> Extraction:
    """See the module docstring. ``plate_aware=False`` is the naive metal-only flood."""
    db = _db()
    ly, top = _read(gds)
    l2n = db.LayoutToNetlist(db.RecursiveShapeIterator(ly, top, []))

    def raw(name):
        return l2n.make_polygon_layer(ly.layer(*prim.LAYER[name]), name)

    comp, poly2, res_mk = raw("comp"), raw("poly2"), raw("res_mk")
    nwell, contact = raw("nwell"), raw("contact")
    m1, v1, m2, v2, m3 = raw("metal1"), raw("via1"), raw("metal2"), raw("via2"), raw("metal3")
    fusetop = raw("fusetop")

    poly = poly2 - res_mk
    l2n.register(poly, "poly")
    diff = comp - poly2
    l2n.register(diff, "diff")
    layers = {
        "poly": poly,
        "diff": diff,
        "nwell": nwell,
        "contact": contact,
        "metal1": m1,
        "via1": v1,
        "metal2": m2,
        "metal3": m3,
        "fusetop": fusetop,
    }
    for r in layers.values():
        l2n.connect(r)
    l2n.connect(contact, poly)
    l2n.connect(contact, diff)
    l2n.connect(contact, m1)
    l2n.connect(nwell, diff)
    l2n.connect(m1, v1)
    l2n.connect(v1, m2)
    if plate_aware:
        v2_ncap = v2 - fusetop
        v2_cap = v2 & fusetop
        l2n.register(v2_ncap, "via2_ncap")
        l2n.register(v2_cap, "via2_cap")
        for r in (v2_ncap, v2_cap):
            l2n.connect(r)
        l2n.connect(m2, v2_ncap)
        l2n.connect(v2_ncap, m3)
        l2n.connect(fusetop, v2_cap)
        l2n.connect(v2_cap, m3)
        layers["via2_ncap"], layers["via2_cap"] = v2_ncap, v2_cap
    else:
        l2n.connect(v2)
        l2n.connect(m2, v2)
        l2n.connect(v2, m3)
        l2n.connect(fusetop, v2)
        layers["via2"] = v2
    l2n.extract_netlist()
    return Extraction(l2n=l2n, layers=layers, dbu=ly.dbu)


@dataclass
class Report:
    problems: list[str] = field(default_factory=list)
    opens: dict[str, int] = field(default_factory=dict)  # net -> number of distinct clusters
    shorts: list[tuple[str, ...]] = field(default_factory=list)  # nets sharing one cluster
    checked: int = 0

    @property
    def ok(self) -> bool:
        return not self.problems and not self.opens and not self.shorts

    def summary(self) -> str:
        if self.ok:
            return f"connectivity: OK ({self.checked} terminal probes)"
        lines = [f"connectivity: FAIL ({self.checked} terminal probes)"]
        lines += [f"  open:  {n} splits into {k} pieces" for n, k in sorted(self.opens.items())]
        lines += [f"  short: {' / '.join(s)}" for s in self.shorts]
        lines += [f"  {p}" for p in self.problems]
        return "\n".join(lines)


def _grade(expected: Iterable[tuple[str, object, str]], report: Report) -> Report:
    """``expected`` = (net, cluster_id or None, description)."""
    by_net: dict[str, set] = {}
    by_cluster: dict[object, set] = {}
    for net, cid, what in expected:
        report.checked += 1
        if cid is None:
            report.problems.append(f"{what}: probe lands on no conductor (expected {net})")
            continue
        by_net.setdefault(net, set()).add(cid)
        by_cluster.setdefault(cid, set()).add(net)
    for net, cids in by_net.items():
        if len(cids) > 1:
            report.opens[net] = len(cids)
    for cid, nets in by_cluster.items():
        if len(nets) > 1:
            report.shorts.append(tuple(sorted(nets)))
    report.shorts.sort()
    return report


def check_probes(gds: Path, probes, *, plate_aware: bool = True) -> Report:
    """Grade the generator's named terminal probes (``block.Probe``) against the GDS."""
    ex = extract(gds, plate_aware=plate_aware)
    expected = [(p.net, ex.net_at(p.layer, p.x, p.y), p.what) for p in probes]
    rep = _grade(expected, Report())
    _grade_labels(gds, ex, rep, expected)
    return rep


def _grade_labels(gds: Path, ex: Extraction, rep: Report, expected) -> None:
    """Every label must sit on metal of the cluster its own name was probed on."""
    clusters: dict[str, set] = {}
    for net, cid, _ in expected:
        if cid is not None:
            clusters.setdefault(net, set()).add(cid)
    for text, lname, x, y in census(gds).labels:
        cid = ex.net_at(LABEL_LAYERS[lname], x, y)
        if cid is None:
            rep.problems.append(f"label {text!r} at ({x:.3f}, {y:.3f}) sits on no {LABEL_LAYERS[lname]}")
        elif text in clusters and cid not in clusters[text]:
            rep.problems.append(f"label {text!r} at ({x:.3f}, {y:.3f}) is not on the net its terminals extract to")


def check_topology(gds: Path, *, plate_aware: bool = True) -> Report:
    """Netlist topology from the GDS alone -- see the module docstring."""
    c = census(gds)
    ex = extract(gds, plate_aware=plate_aware)
    rep = Report()
    eps = 0.05

    # resistor ends: the poly beyond each end of the body, along its long axis
    res_ends: list[tuple] = []
    for body, poly in zip(c.resistor_bodies, c.resistor_polys):
        vertical = (body[3] - body[1]) >= (body[2] - body[0])
        if vertical:
            xc = (body[0] + body[2]) / 2
            a = ex.net_at("poly", xc, poly[1] + eps)
            b = ex.net_at("poly", xc, poly[3] - eps)
        else:
            yc = (body[1] + body[3]) / 2
            a = ex.net_at("poly", poly[0] + eps, yc)
            b = ex.net_at("poly", poly[2] - eps, yc)
        if a is None or b is None:
            rep.problems.append(f"resistor {body}: an end lands on no poly")
            continue
        res_ends.append((a, b))
    rep.checked += 2 * len(res_ends)

    gate_nets = []
    for gate, poly in zip(c.mos_gates, c.mos_polys):
        xc = (gate[0] + gate[2]) / 2
        for y in (poly[1] + eps, poly[3] - eps):
            gate_nets.append(ex.net_at("poly", xc, y))
    body_nets = []
    for gate, diffs in zip(c.mos_gates, c.mos_body_diffs):
        for d in diffs:
            body_nets.append(ex.net_at("diff", (d[0] + d[2]) / 2, (d[1] + d[3]) / 2))
        body_nets.append(ex.net_at("nwell", (gate[0] + gate[2]) / 2, (gate[1] + gate[3]) / 2))
    tap_nets = [ex.net_at("diff", (t[0] + t[2]) / 2, (t[1] + t[3]) / 2) for t in c.substrate_taps]
    mim_bot, mim_top = [], []
    for t in c.mim_tops:
        xc, yc = (t[0] + t[2]) / 2, (t[1] + t[3]) / 2
        mim_top.append(ex.net_at("fusetop", xc, yc))
        mim_bot.append(ex.net_at("metal2", xc, t[1] - prim.MIM_BOTTOM_ENC_UM / 2))
    rep.checked += len(gate_nets) + len(body_nets) + len(tap_nets) + len(mim_bot) + len(mim_top)
    for label, nets in (("MOS-cap gate", gate_nets), ("MOS-cap body", body_nets), ("substrate tap", tap_nets),
                        ("MIM bottom plate", mim_bot), ("MIM top plate", mim_top)):
        if any(n is None for n in nets):
            rep.problems.append(f"a {label} terminal lands on no conductor")
    if rep.problems:
        return rep

    # --- the series chain ---
    degree: dict = {}
    for a, b in res_ends:
        if a == b:
            rep.shorts.append(("resistor shorted end-to-end",))
        for n in (a, b):
            degree[n] = degree.get(n, 0) + 1
    chain_nets = set(degree)
    ends = sorted((n for n, d in degree.items() if d == 1), key=str)
    if len(chain_nets) != len(res_ends) + 1 or len(ends) != 2 or any(d > 2 for d in degree.values()):
        rep.opens["R chain"] = len(chain_nets)
        rep.problems.append(
            f"resistor ends do not form one unbranched chain: {len(res_ends)} resistors, "
            f"{len(chain_nets)} distinct end nets, {len(ends)} free ends"
        )
        return rep

    names: dict = {}
    vss = set(body_nets) | set(tap_nets) | set(mim_top)
    if len(vss) != 1:
        rep.opens["VSS"] = len(vss)
    gates = set(gate_nets)
    if len(gates) != 1:
        rep.opens["NZ"] = len(gates)
    bots = set(mim_bot)
    if len(bots) != 1:
        rep.opens["VCTRL"] = len(bots)
    if rep.opens:
        return rep
    (vss_n,), (nz_n,), (vctrl_n,) = vss, gates, bots
    named = (("VSS", vss_n), ("NZ", nz_n), ("VCTRL", vctrl_n))
    for i, (na, ca) in enumerate(named):
        for nb, cb in named[i + 1 :]:
            if ca == cb:
                rep.shorts.append(tuple(sorted((na, nb))))
    if rep.shorts:
        return rep
    if set(ends) != {nz_n, vctrl_n}:
        rep.problems.append("the chain's free ends are not NZ (MOS-cap gates) and VCTRL (MIM bottom plate)")
    if vss_n in chain_nets:
        rep.shorts.append(("VSS", "resistor chain"))
    # labels: VCTRL / VSS must name what the devices say they are
    for text, lname, x, y in c.labels:
        cid = ex.net_at(LABEL_LAYERS[lname], x, y)
        if text in ("VCTRL", "VSS", "NZ") and cid != {"VCTRL": vctrl_n, "VSS": vss_n, "NZ": nz_n}[text]:
            rep.problems.append(f"label {text!r} is not on the {text} net the devices define")
    for port in ("VCTRL", "VSS"):
        if not any(t == port for t, *_ in c.labels):
            rep.problems.append(f"no {port} label")
    return rep


def check(gds: Path, probes) -> Report:
    """Both checks, merged (``block.py --check-connectivity``)."""
    a = check_topology(gds)
    b = check_probes(gds, probes)
    merged = Report(problems=a.problems + b.problems, opens={**a.opens, **b.opens}, shorts=sorted(set(a.shorts + b.shorts)))
    merged.checked = a.checked + b.checked
    return merged
