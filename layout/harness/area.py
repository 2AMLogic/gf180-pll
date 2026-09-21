"""Where a drawn block's bounding box actually goes -- the area audit (issue #442).

WHY THIS EXISTS
---------------
``layout/floorplan/PLL-FLOORPLAN.md`` §5.1-§5.4 track a real, growing area
overrun against ``spec/pll.md#area``'s <= 0.15 mm2 target, and each revision
names the next lever to pull. Through §5.4 those levers were named from
*derived* quantities -- most consequentially "at 0.1321 mm2 for 452
transistors the block spends ~292 um2/transistor ... the
diffusion-island-per-device convention" (§5.3), which reads device density as
the cause because um2/transistor is the only number that had been computed.

um2/transistor cannot distinguish "the diffusion islands are too big" from
"the diffusion islands are 1 % of the block and the other 99 % is empty".
This module computes the numbers that can, directly off a committed GDS and
a committed reference netlist -- so a lever is sized before it is spent
(issue #442 acceptance criterion 1) rather than inferred from a ratio.

WHAT IT MEASURES, AND WHY EACH ONE
----------------------------------
:func:`audit_gds`, per block:

* **Per-layer drawn area** (merged, so overlapping shapes are not
  double-counted). Diffusion (``comp``) area is the *whole* budget any
  shared-diffusion / device-stacking lever can ever address: such a lever
  removes diffusion islands and the spacing between them, so its ceiling is
  bounded by the comp area plus the comp-to-comp keep-out around it. If comp
  is 1 % of the block, so is the lever.
* **Fill fraction** -- the union of every drawing layer over the bounding-box
  area. Its complement is whitespace: area that is neither device, nor well,
  nor wire, nor contact. Whitespace is what a packing lever recovers.
* **Device bands vs. routing bands.** The y-intervals that contain diffusion
  (coalesced across the intra-row gaps a generator draws inside one cell --
  see ``coalesce_gap_um``) against the intervals that contain none. A band
  with no diffusion in it is a band whose whole height is being spent on
  routing, and its height is directly comparable to the packed floor below.
* **Metal2 horizontal-track census.** How many distinct Metal2 track y's the
  block actually uses, and therefore the *packed* height those tracks would
  occupy at one track pitch each. Comparing that floor against the measured
  routing-band height separates "this band is full of tracks" from "this band
  is tall for a reason other than track count".
* **Metal2 fill inside the device bands.** Metal2 is a routing layer with no
  DRC relationship to the diffusion under it; if the plane over the devices
  is empty, the track band sits above the devices by generator convention,
  not by any rule. This is the measurement that turns "move the tracks over
  the cells" from an assertion into a sized lever.

:func:`series_junction_census`, per reference netlist: how many source/drain
nodes in the block's *own* independently-stated schematic are genuine
shared-diffusion candidates -- a node touching exactly two source/drain
terminals of two same-flavour devices and no gate. That count, times the
per-merge column-height saving the generator's own constants imply, is the
shared-diffusion lever's own arithmetic rather than an appeal to convention.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
No PDK, no KLayout application binary, no DRC deck -- only the ``klayout.db``
pip wheel (the same dependency ``layout/tests`` already gates on) plus text.
So this runs in CI's headless ``checks`` job, and re-running it is how the
floorplan's own area arithmetic stops being hand-maintained. It measures
drawn geometry; it makes no claim about whether a transformation it sizes is
DRC-legal. That is what ``layout/run_pv.py drc`` is for, and no lever this
module sizes may land without it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

#: The drawing layers every ``layout/pll_top/*`` generator uses, by the name
#: those generators' own ``LAYER`` tables give them. Purpose/label layers
#: (34/10, 36/10) are deliberately absent: a text label occupies no silicon,
#: and counting its bounding box as drawn area would inflate fill.
LAYERS: dict[str, tuple[int, int]] = {
    "comp": (22, 0),
    "nwell": (21, 0),
    "pplus": (31, 0),
    "nplus": (32, 0),
    "poly2": (30, 0),
    "contact": (33, 0),
    "metal1": (34, 0),
    "via1": (35, 0),
    "metal2": (36, 0),
    "via2": (38, 0),
    "metal3": (42, 0),
}

#: Metal2 track pitch, identical in every ``layout/pll_top/*`` generator
#: (``METAL2_TRACK_PITCH_UM``; ``layout/tests/test_canvas_nettracks.py``
#: asserts they agree). One track per distinct y, so a block's track count
#: times this pitch is the height those tracks would occupy packed solid.
METAL2_TRACK_PITCH_UM = 0.75

#: Diffusion y-intervals closer together than this coalesce into one "device
#: band". Sized above the largest intra-cell diffusion gap any generator
#: draws -- ``NWELL_TO_NMOS_GAP_UM`` = 4.0 um, the PMOS-to-NMOS clearance
#: inside a single leaf cell -- and below the smallest inter-row routing band
#: measured on any committed block (34.61 um, ``divider_chain``'s upper row).
#: So one cell row reads as one band, and a band between two rows reads as
#: routing.
COALESCE_GAP_UM = 6.0


@dataclass(frozen=True)
class BlockAudit:
    """One block's measured area decomposition. Every field is um or um2."""

    name: str
    top_cell: str
    width_um: float
    height_um: float
    layer_area_um2: dict[str, float]
    layer_polygons: dict[str, int]
    drawn_um2: float
    device_bands: tuple[tuple[float, float], ...]
    metal2_tracks: int
    metal2_in_device_bands_um2: float
    device_band_area_um2: float

    @property
    def bbox_um2(self) -> float:
        return self.width_um * self.height_um

    @property
    def fill_pct(self) -> float:
        return 100.0 * self.drawn_um2 / self.bbox_um2

    @property
    def whitespace_um2(self) -> float:
        return self.bbox_um2 - self.drawn_um2

    @property
    def device_band_um(self) -> float:
        """Total block height that contains diffusion."""
        return sum(hi - lo for lo, hi in self.device_bands)

    @property
    def routing_band_um(self) -> float:
        """Total block height that contains no diffusion at all."""
        return self.height_um - self.device_band_um

    @property
    def packed_track_floor_um(self) -> float:
        """Height this block's own Metal2 tracks would occupy packed solid."""
        return self.metal2_tracks * METAL2_TRACK_PITCH_UM

    @property
    def metal2_over_devices_pct(self) -> float:
        """Metal2 fill inside the device bands -- how much of the routing
        plane over the cells is already in use."""
        if self.device_band_area_um2 <= 0.0:
            return 0.0
        return 100.0 * self.metal2_in_device_bands_um2 / self.device_band_area_um2


def _coalesce(intervals: list[tuple[float, float]], gap: float) -> tuple[tuple[float, float], ...]:
    """Merge y-intervals separated by less than ``gap`` (see :data:`COALESCE_GAP_UM`)."""
    out: list[tuple[float, float]] = []
    for lo, hi in sorted(intervals):
        if out and lo - out[-1][1] < gap:
            out[-1] = (out[-1][0], max(out[-1][1], hi))
        else:
            out.append((lo, hi))
    return tuple(out)


def audit_gds(
    path: str | Path,
    *,
    name: str | None = None,
    top_cell: str | None = None,
    coalesce_gap_um: float = COALESCE_GAP_UM,
) -> BlockAudit:
    """Measure one committed block GDS. Needs only the ``klayout`` pip wheel."""
    import klayout.db as db  # noqa: PLC0415 -- lazy, same convention as layout/pll_top/*

    path = Path(path)
    layout = db.Layout()
    layout.read(str(path))
    cell = layout.cell(top_cell) if top_cell else layout.top_cell()
    if cell is None:
        raise ValueError(f"{path}: no cell named {top_cell!r}")
    dbu = layout.dbu
    bbox = cell.dbbox()

    def region(layer: int, datatype: int) -> "db.Region":
        r = db.Region(cell.begin_shapes_rec(layout.layer(layer, datatype)))
        r.merge()
        return r

    regions = {lname: region(*ld) for lname, ld in LAYERS.items()}
    layer_area = {n: r.area() * dbu * dbu for n, r in regions.items()}
    layer_polys = {n: r.count() for n, r in regions.items()}

    union = db.Region()
    for r in regions.values():
        union += r
    union.merge()

    comp = regions["comp"]
    bands = _coalesce(
        [(p.bbox().bottom * dbu, p.bbox().top * dbu) for p in comp.each()],
        coalesce_gap_um,
    )

    # Metal2 horizontal-track census: a track is a Metal2 shape wider than it
    # is tall (a riser/landing pad is not), counted once per distinct centre y.
    track_ys = set()
    for p in regions["metal2"].each():
        b = p.bbox()
        if b.width() > b.height():
            track_ys.add(round((b.bottom + b.top) / 2.0 * dbu, 3))

    band_window = db.Region()
    for lo, hi in bands:
        band_window.insert(
            db.Box(
                int(round(bbox.left / dbu)),
                int(round(lo / dbu)),
                int(round(bbox.right / dbu)),
                int(round(hi / dbu)),
            )
        )
    m2_in_bands = regions["metal2"] & band_window
    m2_in_bands.merge()

    return BlockAudit(
        name=name or path.stem,
        top_cell=cell.name,
        width_um=bbox.width(),
        height_um=bbox.height(),
        layer_area_um2=layer_area,
        layer_polygons=layer_polys,
        drawn_um2=union.area() * dbu * dbu,
        device_bands=bands,
        metal2_tracks=len(track_ys),
        metal2_in_device_bands_um2=m2_in_bands.area() * dbu * dbu,
        device_band_area_um2=sum(hi - lo for lo, hi in bands) * bbox.width(),
    )


# --- Shared-diffusion candidates, from a reference netlist ------------------

_DEVICE_RE = re.compile(
    r"^M\S*\s+(?P<d>\S+)\s+(?P<g>\S+)\s+(?P<s>\S+)\s+(?P<b>\S+)\s+(?P<kind>[np]fet_\S+)\s+(?P<rest>.*)$"
)


@dataclass(frozen=True)
class JunctionCensus:
    """Shared-diffusion candidates in one block's own reference netlist."""

    devices: int
    merges: int
    merges_by_kind: dict[str, int]
    gate_area_um2: float
    island_area_um2: float
    merge_saving_um2: float


def series_junction_census(
    spice_path: str | Path,
    *,
    sd_overhang_um: float = 0.5,
    comp_gap_um: float = 0.6,
    shared_junction_um: float = 0.5,
) -> JunctionCensus:
    """Count shared-diffusion candidates and size what merging them frees.

    A candidate is a node that touches exactly two source/drain terminals, on
    two *different* devices of the same flavour, and no gate -- i.e. a series
    junction that carries no other connection, so the two devices' diffusion
    islands could become one uncontacted stack.

    The criterion is structural, not name-based: supply rails are excluded by
    their own fan-out rather than by being called ``VSS``/``VDD``. In a real
    block that is the same thing (``divider_chain.spice``'s VSS and VDD_DIV
    each touch hundreds of terminals, and all 40 candidates it reports are
    internal ``_NMID``/``_NM1``/``_PMID`` series nodes); in a two-device toy
    netlist a shared rail does report as a candidate, which is correct --
    abutted source sharing on a rail is a real merge -- and is pinned by
    ``layout/tests/test_area_audit.py`` so nobody reads it as a defect.

    The per-merge saving is the generator's own column geometry
    (``devgen.py``'s ``SD_OVERHANG_UM``/``COMP_GAP_UM``): two separate islands
    cost ``2*(2*overhang + L) + gap`` of column height, one shared stack costs
    ``2*overhang + 2*L + shared_junction``, and the difference is spent over
    the wider of the two devices' widths. ``shared_junction_um`` is the
    uncontacted diffusion left between the two gates; the default matches the
    generator's own source/drain overhang, which is ~2x PL.5_LV's gate-to-gate
    minimum, so this is a conservative (small) estimate of the saving.
    """
    devices: list[dict] = []
    for line in Path(spice_path).read_text().splitlines():
        m = _DEVICE_RE.match(line)
        if not m:
            continue
        rest = m.group("rest")
        w = re.search(r"\bW=([\d.eE+-]+)u", rest)
        length = re.search(r"\bL=([\d.eE+-]+)u", rest)
        if not (w and length):
            continue
        devices.append(
            {
                "d": m.group("d"),
                "g": m.group("g"),
                "s": m.group("s"),
                "kind": m.group("kind"),
                "w": float(w.group(1)),
                "l": float(length.group(1)),
            }
        )

    terminals: dict[str, list[int]] = {}
    gate_nets: set[str] = set()
    for i, dev in enumerate(devices):
        terminals.setdefault(dev["d"], []).append(i)
        terminals.setdefault(dev["s"], []).append(i)
        gate_nets.add(dev["g"])

    merges: list[tuple[int, int]] = []
    for net, owners in terminals.items():
        if len(owners) != 2 or net in gate_nets:
            continue
        i, j = owners
        if i == j or devices[i]["kind"] != devices[j]["kind"]:
            continue
        merges.append((i, j))

    saving = 0.0
    by_kind: dict[str, int] = {}
    for i, j in merges:
        length = devices[i]["l"]
        unshared = 2.0 * (2.0 * sd_overhang_um + length) + comp_gap_um
        shared = 2.0 * sd_overhang_um + 2.0 * length + shared_junction_um
        saving += (unshared - shared) * max(devices[i]["w"], devices[j]["w"])
        by_kind[devices[i]["kind"]] = by_kind.get(devices[i]["kind"], 0) + 1

    return JunctionCensus(
        devices=len(devices),
        merges=len(merges),
        merges_by_kind=by_kind,
        gate_area_um2=sum(d["w"] * d["l"] for d in devices),
        island_area_um2=sum(d["w"] * (2.0 * sd_overhang_um + d["l"]) for d in devices),
        merge_saving_um2=saving,
    )


# --- Report rendering -------------------------------------------------------

def render_markdown(audits: list[BlockAudit], censuses: dict[str, JunctionCensus]) -> str:
    """Render the audit as the Markdown table committed under
    ``layout/evidence/area-audit/``. Deliberately plain: no totals a reader
    cannot re-derive from the rows, and no verdict -- interpretation belongs
    in that directory's own ``PROOF.md``, not in generated output."""
    lines: list[str] = []
    lines.append("| Block | Footprint (um) | bbox (um2) | Drawn (um2) | Fill | Whitespace |")
    lines.append("|---|---|---|---|---|---|")
    for a in audits:
        lines.append(
            f"| `{a.name}` | {a.width_um:.2f} x {a.height_um:.2f} | {a.bbox_um2:,.0f} | "
            f"{a.drawn_um2:,.0f} | {a.fill_pct:.1f} % | {a.whitespace_um2:,.0f} ({100 - a.fill_pct:.1f} %) |"
        )

    lines.append("")
    lines.append("| Block | comp (um2) | comp share | Device band (um) | No-device band (um) | Metal2 tracks | Packed track floor (um) | Metal2 fill over devices |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for a in audits:
        comp = a.layer_area_um2["comp"]
        lines.append(
            f"| `{a.name}` | {comp:,.1f} | {100 * comp / a.bbox_um2:.2f} % | "
            f"{a.device_band_um:.2f} | {a.routing_band_um:.2f} | {a.metal2_tracks} | "
            f"{a.packed_track_floor_um:.2f} | {a.metal2_over_devices_pct:.1f} % |"
        )

    if censuses:
        lines.append("")
        lines.append("| Reference netlist | Devices | Shared-diffusion candidates | Column area freed by merging every one (um2) | Sum W*L (um2) |")
        lines.append("|---|---|---|---|---|")
        for name, c in censuses.items():
            kinds = ", ".join(f"{k}: {v}" for k, v in sorted(c.merges_by_kind.items()))
            lines.append(
                f"| `{name}` | {c.devices} | {c.merges} ({kinds}) | "
                f"{c.merge_saving_um2:.1f} | {c.gate_area_um2:.1f} |"
            )

    lines.append("")
    lines.append(
        f"Metal2 track pitch {METAL2_TRACK_PITCH_UM} um; device bands coalesced across "
        f"diffusion gaps < {COALESCE_GAP_UM} um."
    )
    return "\n".join(lines) + "\n"
