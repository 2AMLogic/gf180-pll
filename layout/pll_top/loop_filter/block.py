"""Assemble the loop filter (``design/netlist/loop_filter.spice``) into one flat cell.

    python3 -m pll_top.loop_filter.block --outdir DIR [--check-connectivity]

(run from ``layout/``). Writes ``DIR/loop_filter.gds``, top cell ``loop_filter``.

FLOORPLAN
---------
::

    y
    184 +-----------------------------+
        | XCF3          | XCF4        |   +---------------+
        |               |             |   | XCF5 (MIM)    |  <- VSS top plate (Metal3)
        |               |             |   |  VCTRL bottom |     VCTRL bottom plate (Metal2)
     92 +---------------+-------------+   +---------------+
        | XCF1          | XCF2        +--- tap band ---+ 117
        |               |             | R4 R3 R2 R1    |
        |               |             | (2 x 107 each) |
      0 +---------------+-------------+----------------+
        0                           186.4            207.6  219.6 x

* **C1** -- four ``cap_nmos_03v3_b``, 87 x 87 um gate each, as a 2 x 2 array
  (PLL-FLOORPLAN.md section 3 allows 2 x 2 or 1 x 4). Every cap sits in its
  own n-well, which is its body and is tied to ``VSS`` through the cap's own
  n+ diffusion strips; around every cap runs a p-substrate tap band (also
  ``VSS``) and neighbouring caps share the band between them. The diffusion
  strips' metal1 is widened into the band's metal1, so each cap's body *and*
  the substrate next to it reach ``VSS`` on metal1 with no via.
* **R** -- four plain ``ppolyf_u`` resistors, 2 x 107 um each, side by side
  (XRF4 nearest the array), chained by metal1 links at alternating ends:
  ``VCTRL -(XRF1)- NR1 -(XRF2)- NR2 -(XRF3)- NR3 -(XRF4)- NZ``. They sit inside
  their own tap ring, which shares its left band with the array's right band;
  the ring is the substrate (third) terminal of every resistor.
* **C2** -- one ``cap_mim_2f0_m2m3_noshield``, 31.4 x 31.4 um, above the
  resistors. Its Metal2 bottom plate is ``VCTRL`` and is reached by a Metal2
  stub from XRF1's free end; its top plate is ``VSS``, reached by a Metal3
  strap down to a Via2/Via1 stack on the resistor ring's top band.
* **NZ** -- each C1 column carries two vertical Metal2 straps over both of
  its caps, landing by Via1 on every gate contact row; one horizontal Metal2
  bus ties all four straps to XRF4's free end.

Routing layers: metal1 (``VSS`` frame, resistor links), metal2 (``NZ``,
``VCTRL``), metal3 (``VSS`` to the MIM top plate only).
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path

from . import devices as dev
from . import primitives as prim

TOP_CELL = "loop_filter"
GDS_NAME = f"{TOP_CELL}.gds"

RING_UM = prim.TAP_WIDTH_UM
#: comp edge -> tap band inner edge, around every MOS cap: the n-well's own
#: MOSCAP_NWELL_ENC_UM (0.6) plus 1.0 um of n-well -> p-tap space (DF.17_LV 0.12).
CAP_TO_TAP_UM = 1.6
CAP_CELL_MARGIN_UM = CAP_TO_TAP_UM + RING_UM  # comp edge -> tap band outer edge
CAP_COLS, CAP_ROWS = 2, 2

#: resistor poly -> tap comp (PRES.3: 0.6) and resistor body -> resistor body.
RES_TO_TAP_UM = 3.0
RES_GAP_UM = 2.0  # PRES.2 0.4; sab-to-sab 2.0 - 2 x 0.28 = 1.44 (SB.2 0.42)
#: left-to-right resistor order; XRF4 (the NZ end) sits next to the C1 array.
RES_ORDER = ("XRF4", "XRF3", "XRF2", "XRF1")
#: which net each resistor's *top* contact carries (the bottom carries the other).
RES_TOP_NET = {"XRF1": "VCTRL", "XRF2": "NR2", "XRF3": "NR2", "XRF4": "NZ"}

NZ_STRAP_W_UM = 2.0
NZ_STRAP_FRACTIONS = (0.25, 0.75)
NZ_BUS_W_UM = 1.0
VCTRL_STUB_W_UM = 1.0
VSS_STRAP_W_UM = prim.STACK_METAL3_UM  # metal3, VSS stack -> MIM top plate (MT30.1a/MT30.6, see primitives)
MIM_ABOVE_RING_UM = 5.0  # resistor ring top band -> MIM FuseTop bottom edge
MIM_X_OFFSET_UM = 1.2  # FuseTop left edge, right of the array's right band outer edge
VSS_STACK_X_UM = 195.0  # x of the VSS Via1/Via2 stack on the resistor ring's top band


def _s(v: float) -> float:
    return dev.snap_um(v)


# ---------------------------------------------------------------------------
# pure-Python placement (no KLayout)
# ---------------------------------------------------------------------------


def cap_pitch_um() -> tuple[float, float]:
    cw, ch = prim.mos_cap_extent(dev.MOS_CAPS[0])
    return (_s(cw + 2 * CAP_CELL_MARGIN_UM - RING_UM), _s(ch + 2 * CAP_CELL_MARGIN_UM - RING_UM))


def cap_origin_um(index: int) -> tuple[float, float]:
    """Comp lower-left corner of MOS cap ``index`` (0..3; row-major from the bottom-left)."""
    px, py = cap_pitch_um()
    i, j = index % CAP_COLS, index // CAP_COLS
    return (_s(i * px + CAP_CELL_MARGIN_UM), _s(j * py + CAP_CELL_MARGIN_UM))


def array_extent_um() -> tuple[float, float]:
    px, py = cap_pitch_um()
    return (_s(CAP_COLS * px + RING_UM), _s(CAP_ROWS * py + RING_UM))


def res_by_name() -> dict[str, dev.PolyRes]:
    return {r.name: r for r in dev.RESISTORS}


def res_origin_um(name: str) -> tuple[float, float]:
    """Body (``res_mk``) lower-left corner of resistor ``name``."""
    ax, _ = array_extent_um()
    x = ax + RES_TO_TAP_UM
    for n in RES_ORDER:
        if n == name:
            return (_s(x), _s(RING_UM + RES_TO_TAP_UM + prim.PRES_LAND_UM))
        x += res_by_name()[n].w_um + RES_GAP_UM
    raise KeyError(name)


def res_ring_um() -> tuple[float, float, float, float]:
    """Outer box of the resistor tap ring (its left band is the array's right band)."""
    ax, _ = array_extent_um()
    last = RES_ORDER[-1]
    rx, ry = res_origin_um(last)
    _, ph = prim.poly_res_extent(res_by_name()[last])
    x1 = rx + res_by_name()[last].w_um + RES_TO_TAP_UM + RING_UM
    poly_top = ry - prim.PRES_LAND_UM + ph
    y1 = poly_top + RES_TO_TAP_UM + RING_UM
    return (_s(ax - RING_UM), 0.0, _s(x1), _s(y1))


def mim_origin_um() -> tuple[float, float]:
    ax, _ = array_extent_um()
    return (_s(ax + MIM_X_OFFSET_UM), _s(res_ring_um()[3] + MIM_ABOVE_RING_UM))


def footprint_um() -> tuple[float, float, float, float]:
    """Pure-Python bounding box of everything ``build()`` draws."""
    ax, ay = array_extent_um()
    mx, my = mim_origin_um()
    mim = dev.MIM_CAPS[0]
    e = prim.MIM_BOTTOM_ENC_UM
    x1 = max(ax, res_ring_um()[2], mx + mim.w_um + e)
    y1 = max(ay, my + mim.l_um + e)
    return (0.0, 0.0, _s(x1), _s(y1))


def check_chain() -> None:
    """``RES_TOP_NET`` must describe the netlist's own series chain, end to end.

    Raises if a resistor's top net is not one of its two netlist terminals,
    or if two side-by-side resistors do not share the net at the end where
    their metal1 link is drawn.
    """
    by = res_by_name()
    for name, top in RES_TOP_NET.items():
        r = by[name]
        if top not in (r.net_a, r.net_b):
            raise ValueError(f"{name}: top net {top} is not one of its terminals {r.net_a}/{r.net_b}")
    for left, right in zip(RES_ORDER, RES_ORDER[1:]):
        if RES_TOP_NET[left] == RES_TOP_NET[right]:
            continue
        if bottom_net(left) != bottom_net(right):
            raise ValueError(f"{left}/{right} share neither end")


def bottom_net(name: str) -> str:
    r = res_by_name()[name]
    return r.net_b if RES_TOP_NET[name] == r.net_a else r.net_a


# ---------------------------------------------------------------------------
# drawing
# ---------------------------------------------------------------------------


@dataclass
class Probe:
    """One device terminal to check in the *exported* GDS (see ``netcheck.py``)."""

    net: str
    layer: str  # a netcheck extraction layer name
    x: float
    y: float
    what: str


@dataclass
class LoopFilterResult:
    canvas: prim.Canvas
    mos_caps: list = field(default_factory=list)
    resistors: list = field(default_factory=list)
    mim: prim.MimCapPorts | None = None
    probes: list[Probe] = field(default_factory=list)
    footprint: tuple = (0.0, 0.0, 0.0, 0.0)
    gds: Path | None = None


def _centre(box) -> tuple[float, float]:
    return ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)


def build(outdir: Path | None = None) -> LoopFilterResult:
    check_chain()
    c = prim.Canvas(TOP_CELL)
    res = LoopFilterResult(canvas=c)
    probes = res.probes
    ax, ay = array_extent_um()
    px, py = cap_pitch_um()

    # --- C1 array: tap grid (horizontal bands full width, vertical bands between) ---
    for j in range(CAP_ROWS + 1):
        prim.tap_strip(c, 0.0, j * py, ax, j * py + RING_UM)
    for i in range(CAP_COLS + 1):
        for j in range(CAP_ROWS):
            prim.tap_strip(c, i * px, j * py + RING_UM, i * px + RING_UM, (j + 1) * py)

    for k, cap in enumerate(dev.MOS_CAPS):
        x0, y0 = cap_origin_um(k)
        p = prim.mos_cap(c, cap, x0, y0)
        res.mos_caps.append(p)
        # body: widen each diffusion column's metal1 out to the tap band next to it
        (lx0, _, lx1, _), (rx0, _, rx1, _) = p.body_cols
        band_lo = p.comp[1] - CAP_TO_TAP_UM
        band_hi = p.comp[3] + CAP_TO_TAP_UM
        c.rect("metal1", p.comp[0] - CAP_TO_TAP_UM, band_lo, lx1, band_hi)
        c.rect("metal1", rx0, band_lo, p.comp[2] + CAP_TO_TAP_UM, band_hi)
        for row in p.gate_rows:
            probes.append(Probe(cap.gate_net, "poly", *_centre(row), f"{cap.name} gate contact row"))
        for col in p.body_cols:
            cx = (col[0] + col[2]) / 2.0
            probes.append(Probe(cap.body_net, "diff", cx, (p.comp[1] + p.comp[3]) / 2.0, f"{cap.name} body diffusion"))
        probes.append(Probe(cap.body_net, "nwell", *_centre(p.gate), f"{cap.name} n-well (body)"))
        probes.append(
            Probe("VSS", "diff", p.comp[0] - CAP_TO_TAP_UM - RING_UM / 2.0, _centre(p.gate)[1], f"{cap.name} substrate tap")
        )

    # --- NZ straps: two per column, over both caps, Via1 onto every gate row ---
    strap_xs = []
    for i in range(CAP_COLS):
        bottom = res.mos_caps[i]
        top = res.mos_caps[i + CAP_COLS * (CAP_ROWS - 1)]
        for f in NZ_STRAP_FRACTIONS:
            xc = _s(bottom.comp[0] + f * (bottom.comp[2] - bottom.comp[0]))
            sx0, sx1 = xc - NZ_STRAP_W_UM / 2.0, xc + NZ_STRAP_W_UM / 2.0
            c.rect("metal2", sx0, bottom.gate_rows[0][1], sx1, top.gate_rows[1][3])
            strap_xs.append((sx0, sx1))
            for j in range(CAP_ROWS):
                cap_p = res.mos_caps[i + CAP_COLS * j]
                for row in cap_p.gate_rows:
                    prim.via_grid(c, "via1", sx0, row[1], sx1, row[3], margin=0.08)
    c.label("metal2_label", "NZ", (strap_xs[0][0] + strap_xs[0][1]) / 2.0, ay / 2.0)

    # --- R: four ppolyf_u, chained by metal1 links ---
    rp = {}
    for name in RES_ORDER:
        r = res_by_name()[name]
        x0, y0 = res_origin_um(name)
        p = prim.poly_res(c, r, x0, y0)
        rp[name] = p
        res.resistors.append(p)
        xc = (p.body[0] + p.body[2]) / 2.0
        probes.append(Probe(RES_TOP_NET[name], "poly", xc, p.poly[3] - prim.PRES_LAND_UM / 2.0, f"{name} top contact"))
        probes.append(Probe(bottom_net(name), "poly", xc, p.poly[1] + prim.PRES_LAND_UM / 2.0, f"{name} bottom contact"))
    for left, right in zip(RES_ORDER, RES_ORDER[1:]):
        if RES_TOP_NET[left] == RES_TOP_NET[right]:
            a, b, net = rp[left].top_pad, rp[right].top_pad, RES_TOP_NET[left]
        else:
            a, b, net = rp[left].bottom_pad, rp[right].bottom_pad, bottom_net(left)
        c.rect("metal1", a[0], a[1], b[2], a[3])
        c.label("metal1_label", net, (a[2] + b[0]) / 2.0, (a[1] + a[3]) / 2.0)

    rx0, ry0, rx1, ry1 = res_ring_um()
    prim.tap_strip(c, ax, 0.0, rx1, RING_UM)  # bottom (its left end abuts the array's band)
    prim.tap_strip(c, ax, ry1 - RING_UM, rx1, ry1)  # top
    prim.tap_strip(c, rx1 - RING_UM, RING_UM, rx1, ry1 - RING_UM)  # right
    mid_y = (ry0 + ry1) / 2.0
    for r in dev.RESISTORS:
        probes.append(Probe(r.sub_net, "diff", rx1 - RING_UM / 2.0, mid_y, f"{r.name} substrate tap (ring, right)"))
        probes.append(Probe(r.sub_net, "diff", ax - RING_UM / 2.0, mid_y, f"{r.name} substrate tap (ring, left)"))

    # --- NZ bus: XRF4's free end -> every strap ---
    nz_name = next(n for n, t in RES_TOP_NET.items() if t == "NZ")
    nz_pad = rp[nz_name].top_pad
    nzx, nzy = _centre(nz_pad)
    prim.via1_stack(c, nzx, nzy)
    c.rect("metal2", strap_xs[0][0], nzy - NZ_BUS_W_UM / 2.0, nzx + prim.METAL_PAD_UM / 2.0, nzy + NZ_BUS_W_UM / 2.0)

    # --- C2 MIM ---
    mx, my = mim_origin_um()
    mim = dev.MIM_CAPS[0]
    mp = prim.mim_cap(c, mim, mx, my)
    res.mim = mp
    probes.append(Probe(mim.bottom_net, "metal2", (mp.bottom_plate[0] + mp.bottom_plate[2]) / 2.0, mp.bottom_plate[1] + 0.3, f"{mim.name} bottom plate (outside FuseTop)"))
    probes.append(Probe(mim.bottom_net, "metal2", *_centre(mp.fusetop), f"{mim.name} bottom plate (under FuseTop)"))
    probes.append(Probe(mim.top_net, "fusetop", *_centre(mp.fusetop), f"{mim.name} top plate (FuseTop)"))

    # VCTRL: XRF1's free end -> Metal2 stub -> MIM bottom plate
    vname = next(n for n, t in RES_TOP_NET.items() if t == "VCTRL")
    vx, vy = _centre(rp[vname].top_pad)
    prim.via1_stack(c, vx, vy)
    c.rect("metal2", vx - VCTRL_STUB_W_UM / 2.0, vy - prim.METAL_PAD_UM / 2.0, vx + VCTRL_STUB_W_UM / 2.0, mp.bottom_plate[1])
    c.pin("VCTRL", vx - VCTRL_STUB_W_UM / 2.0, vy, vx + VCTRL_STUB_W_UM / 2.0, mp.bottom_plate[1], layer="metal2_label")

    # VSS: MIM top plate (Metal3) -> strap -> Via2 -> Via1 -> resistor ring top band
    sy = ry1 - RING_UM / 2.0
    prim.metal1_to_metal3_stack(c, VSS_STACK_X_UM, sy)
    c.rect("metal3", VSS_STACK_X_UM - VSS_STRAP_W_UM / 2.0, sy, VSS_STACK_X_UM + VSS_STRAP_W_UM / 2.0, mp.fusetop[1])
    c.pin("VSS", 0.0, 0.0, RING_UM, RING_UM)

    res.footprint = footprint_um()
    if outdir is not None:
        outdir = Path(outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        res.gds = outdir / GDS_NAME
        c.write_gds(res.gds)
    return res


def reference_netlist() -> str:
    """The flat LVS reference, one primitive card per netlist instance.

    Written from :mod:`devices`, whose table ``layout/tests/
    test_loop_filter_layout.py`` pins to ``design/netlist/loop_filter.spice``.
    The xschem export calls each device as a subcircuit (``XRF1 ... ppolyf_u``);
    gf180mcu's LVS reader (``custom_classes.lvs``) instead reads ``R``/``C``
    primitive cards and turns a capacitor's ``W``/``L`` into the ``A``/``P``
    parameters its extractor measures, so the reference restates each line in
    that form -- the same convention ``vco/block.py`` uses for its resistors.
    Terminal order is the netlist's own.

    Identical capacitors in parallel (C1's four ``cap_nmos_03v3_b``) are
    written as **one card with** ``M=<count>``. The PDK's LVS runset simplifies
    the *extracted* netlist by default, which merges the four drawn caps into
    one device of four times the area, but simplifies the reference only under
    ``--schematic_simplify`` (which this repository's harness does not pass);
    four separate reference cards then cannot match the one merged layout
    device. ``M`` is what the runset's own reader multiplies into ``A``/``P``
    (``custom_classes.lvs``). That four separate devices are *drawn* is
    established independently by ``netcheck.census()``, not by this card.
    """
    lines = [
        f"* {TOP_CELL}: flat LVS reference for layout/pll_top/loop_filter (issue #748),",
        "* generated from layout/pll_top/loop_filter/devices.py, which the tests pin to",
        "* design/netlist/loop_filter.spice (DR-006).",
        f".SUBCKT {TOP_CELL} {' '.join(dev.PORTS)}",
    ]
    for r in dev.RESISTORS:
        lines.append(f"R_{r.name} {r.net_a} {r.net_b} {r.sub_net} {r.model} W={r.w_um}u L={r.l_um}u")
    groups: dict[tuple, list[str]] = {}
    for m in dev.MOS_CAPS:
        groups.setdefault((m.gate_net, m.body_net, m.model, m.w_um, m.l_um), []).append(m.name)
    for (g, b, model, w, l), names in groups.items():
        lines.append(f"* {' '.join(names)} in parallel")
        lines.append(f"C_{names[0]} {g} {b} {model} W={w}u L={l}u M={len(names)}")
    for m in dev.MIM_CAPS:
        lines.append(f"C_{m.name} {m.bottom_net} {m.top_net} {m.model} W={m.w_um}u L={m.l_um}u")
    lines.append(f".ENDS {TOP_CELL}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the loop_filter layout (issue #748).")
    parser.add_argument(
        "--outdir",
        default=str(Path(__file__).resolve().parents[2] / "evidence" / "work" / "loop-filter"),
    )
    parser.add_argument(
        "--reference-netlist",
        action="store_true",
        help=f"also write OUTDIR/{TOP_CELL}.spice, the flat LVS reference (see reference_netlist())",
    )
    parser.add_argument(
        "--check-connectivity",
        action="store_true",
        help="extract the written GDS and check every device terminal's net (netcheck.py)",
    )
    args = parser.parse_args(argv)
    result = build(Path(args.outdir))
    x0, y0, x1, y1 = result.footprint
    print(f"wrote {result.gds}")
    print(f"footprint: {x1 - x0:.3f} x {y1 - y0:.3f} um  ({(x1 - x0) * (y1 - y0):.1f} um^2)")
    print(f"device area: {dev.device_area_um2():.1f} um^2")
    if args.reference_netlist:
        ref = Path(args.outdir) / f"{TOP_CELL}.spice"
        ref.write_text(reference_netlist())
        print(f"wrote {ref}")
    if args.check_connectivity:
        from . import netcheck

        report = netcheck.check(result.gds, result.probes)
        print(report.summary())
        return 0 if report.ok else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
