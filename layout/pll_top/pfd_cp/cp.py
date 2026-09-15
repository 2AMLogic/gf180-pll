"""``cp`` -- the complete charge pump: ``cp_output_stage`` (issue #321, Part
3c) assembled with ``cp_dumpbuf`` (issue #302, Part 4) into one flat,
standalone-DRC-clean block matching ``design/cp.sch``'s full netlist
(issue #385, Part 5a of #294/#303).

WHAT THIS BUILDS
-----------------
``cp_output_stage.py``'s own module docstring names exactly what it leaves
undone: *"``cp_dumpbuf`` (``xbuf``) is Part 4 ... and its instantiation into
this block is Part 5"*. This module is that instantiation -- the
``design/cp.sch`` ``xbuf`` instance (lines ~275-281), read directly off that
schematic's own ``lab_pin`` labels:

===================  =======================  =====
``cp_dumpbuf`` net    ``cp_output_stage`` pin   notes
===================  =======================  =====
``VREF``              ``VOUT``                  ``VOUT`` stays external (loop filter)
``VBN``               ``IBN``                   ``IBN`` stays external (shared bias)
``VBP``                ``IBP``                   ``IBP`` stays external (shared bias)
``VDUMP``              ``VDUMP``                 becomes fully **internal**
``VDD``                ``VDD``                   tied, stays external
``VSS``                ``VSS``                   tied, stays external
===================  =======================  =====

So this block's own boundary pins are ``cp_output_stage``'s current twelve
(:data:`cp_output_stage.BOUNDARY_PINS`) minus ``VDUMP`` -- exactly
:data:`BOUNDARY_PINS` below, the eleven ``ipin``/``iopin`` nets
``design/cp.sch`` itself declares.

COMPOSITION: SAME SCRATCH-GDS PATTERN ``cp_output_stage.py`` ALREADY USES
---------------------------------------------------------------------------
Both sub-blocks are built standalone (each already proven DRC-clean and
short-free on its own -- ``layout/evidence/cp-layout/`` and
``layout/evidence/cp-dumpbuf-layout/``), written to a scratch GDS, read back
into one fresh :class:`devgen.Canvas` via ``canvas.layout.read(...)``, placed
with ``db.CellInstArray``/``db.Trans``, then ``canvas.top.flatten(-1, True)``
-- the identical technique ``cp_output_stage.build()`` already uses to
assemble ``cp_array`` + ``pfdcp_inv``. ``cp_output_stage`` lands at a zero
offset (so its own recorded ``footprint``/``pins``/``glue_bus``/
``array.n_bus``/``.p_bus`` stay valid, unmodified); ``cp_dumpbuf`` is placed
to the right, far enough that its own footprint clears every column this
module draws in the gap between the two blocks (see :func:`build`).

ROUTING: A DIRECT METAL3 RISER AT EACH BUS'S OWN NATIVE EDGE, JOINED BY A
METAL2 TRUNK FAR ABOVE BOTH BLOCKS
--------------------------------------------------------------------------
Both sub-blocks are already **fully mesh-routed**: every pad either side
believes belongs to a shared net already carries a Via1/Metal2/Via2/Metal3
riser up to that net's own dedicated Metal2 track (``cp_output_stage``'s own
"REACHING THE ARRAY BLOCK'S NETS" docstring section states the exact DRC
failure -- ``V1.1``/``V2.1``/``M2.2a`` -- from landing a *second* via stack on
a pad that already carries one; ``cp_dumpbuf``'s own external pins are no
different, each one already riser-routed by its own ``build()``). So this
module never lands a fresh via directly on either side's own pad.

Four designs were tried before this one held, each instructively:

1. **A single shared Metal2 link column per net**, directly mirroring
   ``cp_output_stage.build()``'s own array<->glue link. ``cp_dumpbuf``'s own
   six external nets' Metal2 tracks sit within one dense ~5.5 um Y band
   (issue #391 packed them as tightly as ``M2.2a`` allows), so reaching a
   shared column from either side's own bus edge meant a *long* horizontal
   Metal2 run that crossed every *other* net's own link column too --
   :mod:`netcheck` caught the long run reaching ``VREF``'s own link column
   physically overlapping ``IBP``'s own nearby via2 landing pad.
2. **A short link column per side, then a Metal3 riser up to a per-net
   backbone row, then a Metal3 horizontal trunk across the gap.** Moved the
   collision rather than removing it: a riser for a net whose own bus sits
   at a low native Y (e.g. ``IBN`` at Y=16.72) has to climb, on Metal3,
   straight through every *other* net's own trunk row along the way to its
   own (every trunk spans nearly the whole gap) -- fixing defect 1 turned one
   two-net short into a nine-net short spanning every bridged net.
3. **The riser on Metal2 instead of Metal3**, reasoning that a Metal2 riser
   has no DRC relationship to another net's Metal3 trunk. True, but the
   riser's own *column* sits well inside ``cp_output_stage``'s own footprint
   (a net's native bus edge is nowhere near that footprint's own right
   edge), so a tall Metal2 riser climbing from there crosses straight through
   the block's *own* internal glue-mesh Metal2 routing -- :mod:`netcheck`
   reported the worst result of all three: every internal net of
   ``cp_output_stage`` (``B0``, ``B1``, ``UP``, ``DN``, ...) merged into one
   node with all six bridged nets.
4. **A "Reach" (Metal2, native track Y, out to a link column clustered at
   each side's own footprint edge) + Metal3 riser + Metal2 trunk**, believed
   safe because design 1's own failure was blamed entirely on
   ``cp_dumpbuf``'s long reach across its own dense Y band, not on
   ``cp_output_stage``'s side. That was wrong: ``cp_output_stage``'s own
   per-net buses are *not* near its footprint's edge either (``IBN``'s bus,
   for one, spans only X=[-13.34, 12.27] inside a footprint that runs to
   X=102.52) -- so "Reach" still drew a Metal2 rectangle most of the way
   across the block's own interior, and :func:`layout.run_pv.py drc`
   (**not** :mod:`netcheck` -- two *parallel, non-overlapping* Metal2 shapes
   on different nets are exactly the class of defect a connectivity
   extraction cannot see, only a spacing check can) caught it landing 0.16
   um from an unrelated internal Metal2 run: three ``M2.2a`` violations.

The fix that actually holds removes the Reach step entirely -- there is no
reason to walk a net's own bus over to a shared far-away column before
rising, when the riser itself (Metal3) is already immune to every *other*
net's Metal2, wherever it is. Two thin steps, again built from this
package's own precedent:

1. **Riser** (:func:`cp_output_stage._link_tracks`, Metal3 in the middle,
   Metal2 landings at both ends): straight from each side's own bus, at its
   own *native* edge coordinate (``x_hi``/``x_lo`` from :func:`_stage_bus` /
   :func:`_dumpbuf_bus_track` -- no extension, no shared column), up to a
   dedicated per-net trunk row (:data:`BACKBONE_PITCH_UM` apart, strictly
   above both placed blocks' own topmost drawn edge). This riser necessarily
   climbs straight through the footprint's own interior, but the only layer
   it draws there is Metal3, which design 3's own failure already showed
   crosses Metal2 freely -- so every internal Metal2 shape it passes near
   (`cp_output_stage`'s own glue mesh, another net's own bus) is invisible to
   it. It cannot repeat design 1's mistake either: each net's riser sits at
   its own distinct native X, never a shared column, so no two different
   nets' risers land on the same Metal3 column the way design 1's shared
   Metal2 columns did.
2. **Trunk** (:func:`cp_output_stage._extend_bus`, Metal2): a plain Metal2
   rectangle joining the two risers' own trunk-row Metal2 landings
   (:func:`cp_output_stage._link_tracks` already drew both). Entirely above
   both blocks' own footprints (:data:`BACKBONE_MARGIN_UM` above the taller
   one), so it is free to span the full native-edge-to-native-edge distance
   without crossing anything either block itself drew. Safe from every
   *other* net's own trunk (a different, pitch-separated Y -- parallel
   Metal2 strips that never touch), and safe from every *other* net's own
   riser (different layer, no via).

``cp_output_stage``'s own boundary pin for each of the four nets that stay
external (``IBN``, ``IBP``, ``VOUT``, ``VDD``, ``VSS``) is untouched by this
process -- a riser landing on a bus's own edge only adds metal *there*, so
the pad the pin promotion already points at keeps exactly the geometry
``cp_output_stage.build()`` drew for it.

WHAT THIS BLOCK IS: A COMPLETE-CIRCUIT MATCH TO ``design/cp.sch``
--------------------------------------------------------------------
Unlike ``cp_output_stage`` (a *subset* of ``cp.sch``, ``xbuf`` excluded, by
its own docstring's admission), this block corresponds 1:1 to
``design/cp.sch``'s full netlist: every device either sub-block draws, wired
per the net map above. The full-circuit LVS claim belongs to a follow-up (see
this issue's own "Out of scope"); what this module proves directly, via
:mod:`netcheck` against the finished flat GDS, is that the composition itself
introduced no short and no open -- in particular, that ``VDUMP`` (now fully
internal) forms exactly **one** connected island spanning both sub-blocks'
own pads, with no accidental short to any other net.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import cp_array, cp_dumpbuf, devgen, netcheck
from . import cp_output_stage as cos

try:
    from .. import _canvas
except ImportError:  # this package's own dir (not its "pll_top" parent) is the
    # sys.path root under layout/tests's flat-import convention -- see
    # cp_array.py's own identical try/except for the full citation.
    import _canvas

TOP_CELL = "cp"

#: ``design/cp.sch``'s own ``ipin``/``iopin`` declarations (lines 24-35) --
#: ``cp_output_stage.BOUNDARY_PINS`` minus ``VDUMP`` (now internal, tied to
#: ``cp_dumpbuf``'s own ``VDUMP`` -- see module docstring's net-map table).
BOUNDARY_PINS: tuple[str, ...] = (
    "UP", "DN", "B0", "B1", "IBN", "ICN", "IBP", "ICP", "VOUT", "VDD", "VSS",
)

#: (``cp_output_stage`` net, ``cp_dumpbuf`` net) -- read directly off
#: ``design/cp.sch``'s own ``xbuf`` instance (lines 275-281). Order matches
#: ``cp_dumpbuf.EXTERNAL_NETS``' own declaration order.
NET_MAP: tuple[tuple[str, str], ...] = (
    ("VOUT", "VREF"),
    ("IBN", "VBN"),
    ("IBP", "VBP"),
    ("VDUMP", "VDUMP"),
    ("VDD", "VDD"),
    ("VSS", "VSS"),
)

#: Horizontal clearance between cp_output_stage's own footprint (as placed,
#: at the origin) and cp_dumpbuf's own footprint (placed to the right).
#: Generous on purpose (matches ``cp_output_stage.GLUE_GAP_UM``'s own
#: "sufficiently separated blocks" precedent): the routing itself (module
#: docstring's Riser/Trunk steps) needs no dedicated width in this gap at
#: all -- every riser lands at its own bus's *native* edge, inside each
#: block's own footprint, and the trunk runs far above both footprints, not
#: through this gap -- so this constant only exists to keep the two placed
#: blocks' own drawn geometry from touching.
BLOCK_GAP_UM = cos.GLUE_GAP_UM

#: How far past cp_dumpbuf's own native bus edge (:func:`_dumpbuf_bus_track`)
#: the stage-to-dumpbuf riser's own Metal2 landing sits, so it does not merge
#: with the Via2 stack already on that edge (see the routing loop's own
#: comment in :func:`build`). Same value as
#: ``cp_output_stage.CONN_COLUMN_MARGIN_UM`` -- both exist to keep a fresh
#: riser landing clear of already-drawn geometry, not to cross any
#: meaningful distance.
DUMPBUF_REACH_MARGIN_UM = cos.CONN_COLUMN_MARGIN_UM

#: Vertical clearance from the taller of the two (placed) blocks' own
#: topmost drawn edge to the lowest Metal3 trunk row. Keeps every trunk row
#: clear of every routing channel either sub-block already uses on its own.
BACKBONE_MARGIN_UM = cos.CONN_COLUMN_MARGIN_UM

#: Y pitch between two different nets' own Metal2 trunk rows -- same value
#: (and the same minimum-metal-pitch citation) as
#: ``cp_array.RISER_MIN_PITCH_UM``. Trunk rows may be stacked this tightly
#: because they are parallel, non-touching same-layer strips (each net's own
#: trunk never touches a neighbour's, the same invariant
#: ``cp_output_stage``'s own ``NetTracks`` already guarantees for its own
#: per-net Metal2 tracks) and the only thing that ever crosses *between*
#: rows -- a net's own Metal3 riser -- has no DRC relationship to a Metal2
#: row it merely passes under.
BACKBONE_PITCH_UM = cp_array.RISER_MIN_PITCH_UM


def _dumpbuf_bus_track(
    gds_path: Path, net: str, probe_xy: tuple[float, float]
) -> tuple[float, float, float]:
    """``(track_y, x_lo, x_hi)`` of ``net``'s own routed Metal2 bus in
    ``cp_dumpbuf``'s own standalone GDS (local, pre-placement coordinates),
    found by extracting the finished GDS's own Metal1-3 connectivity --
    the same technique :func:`netcheck.check_gds` uses -- rather than
    re-deriving ``cp_dumpbuf.py``'s own internal ``NetTracks`` assignment
    order by hand.

    ``cp_dumpbuf.py`` (unlike ``cp_output_stage.py``'s ``glue_bus``/
    ``array.n_bus``/``.p_bus``) does not return its own per-net bus geometry,
    and this issue's own "Affected Files" list marks it read-only -- adding a
    return value there is out of scope. Re-implementing its placement/routing
    order here instead would silently drift out of sync with any future
    change to that module. Reading the geometry back out of its own finished
    GDS needs no cooperation from -- and cannot drift out of sync with --
    ``cp_dumpbuf.py``'s own implementation.

    ``cp_dumpbuf.NetTracks`` hands every net exactly one dedicated Metal2
    track_y, always the highest Y any of that net's own pads reach (the
    routing channel sits in a dedicated band above both device rows -- see
    ``cp_dumpbuf.py``'s own "ROUTING" docstring section). A net's Metal2
    shapes are therefore a mix of small per-riser landing squares (one at
    each pad's own low Y, one at the shared high track_y) plus, when the net
    has more than one riser, a wide bus rectangle spanning between them --
    all at that *one* shared track_y. Bucketing every one of the net's own
    Metal2 shapes by Y-center and taking the most common value is therefore a
    layout-agnostic way to find track_y (it holds regardless of whether a
    wide bus rectangle was drawn at all), and the union of every shape at
    that Y gives the bus's own real ``[x_lo, x_hi]`` extent -- verified
    directly against a real build in this module's own test suite.
    """
    import klayout.db as db  # noqa: PLC0415 -- lazy, same convention as netcheck.py

    layout = db.Layout()
    layout.read(str(gds_path))
    cell = layout.cell(cp_dumpbuf.TOP_CELL)
    if cell is None:
        raise ValueError(f"{gds_path} has no cell named {cp_dumpbuf.TOP_CELL!r}")

    l2n = db.LayoutToNetlist(db.RecursiveShapeIterator(layout, cell, []))
    regions = {
        name: l2n.make_polygon_layer(layout.layer(*gds), name)
        for name, gds in netcheck.METAL_LAYERS.items()
    }
    for region in regions.values():
        l2n.connect(region)
    for lower, via, upper in netcheck.VIA_CONNECTS:
        l2n.connect(regions[lower], regions[via])
        l2n.connect(regions[via], regions[upper])
    l2n.extract_netlist()

    found = l2n.probe_net(regions[netcheck.PROBE_LAYER], db.DPoint(*probe_xy))
    if found is None:
        raise ValueError(f"cp_dumpbuf: no metal net found at probe point {probe_xy} for {net!r}")
    m2 = l2n.shapes_of_net(found, regions["metal2"], True)
    boxes = [poly.bbox() for poly in m2.each()]
    if not boxes:
        raise ValueError(f"cp_dumpbuf: net {net!r} has no Metal2 shapes")

    dbu = layout.dbu

    def _cy(box) -> float:
        return round((box.top + box.bottom) / 2.0 * dbu, 3)

    counts: dict[float, int] = {}
    for box in boxes:
        counts[_cy(box)] = counts.get(_cy(box), 0) + 1
    track_y = max(counts, key=lambda y: counts[y])
    at_track = [box for box in boxes if _cy(box) == track_y]
    x_lo = min(box.left for box in at_track) * dbu
    x_hi = max(box.right for box in at_track) * dbu
    return (track_y, x_lo, x_hi)


@dataclass
class CpLayout:
    canvas: devgen.Canvas
    footprint: tuple[float, float, float, float]
    pins: dict[str, list[tuple[float, float, float, float]]]
    stage: cos.CpOutputStageLayout
    dumpbuf: cp_dumpbuf.DumpBufCell
    dumpbuf_offset: tuple[float, float]
    backbone_rows: dict[str, float] = field(default_factory=dict)

    def write_gds(self, path) -> None:
        self.canvas.write_gds(path)

    def probe_pads(self) -> dict[str, list[tuple[float, float, float, float]]]:
        """``net -> [Metal1 landing box, ...]`` for every pad either
        sub-block believes is on that net, ``cp_dumpbuf``'s own pads
        translated into this block's shared coordinate frame -- handed to
        :func:`netcheck.check_gds` to prove the composition itself introduced
        no short and no open (see module docstring).

        ``cp_dumpbuf``'s own six external nets are aliased to their
        ``cp_output_stage``-side name (:data:`NET_MAP`) before merging, so
        the two sides' pads for what is now, post-bridge, physically one net
        (e.g. ``VOUT``/``VREF``) land under one canonical key instead of
        reporting a same-net naming mismatch as a spurious "short".
        """
        dx, dy = self.dumpbuf_offset
        alias = {dumpbuf_net: stage_net for stage_net, dumpbuf_net in NET_MAP}
        pads: dict[str, list[tuple[float, float, float, float]]] = {}
        for net, boxes in self.stage.probe_pads().items():
            pads.setdefault(net, []).extend(boxes)
        for net, boxes in self.dumpbuf.probe_pads().items():
            canonical = alias.get(net, net)
            pads.setdefault(canonical, []).extend(cp_array._translate_box(box, dx, dy) for box in boxes)
        return pads


#: Which of ``cp_output_stage``'s own already-computed bus tables (see module
#: docstring, step 2) each stage-side net's Metal2 bus lives in.
_STAGE_BUS_SOURCE: dict[str, str] = {
    "VOUT": "glue", "VDUMP": "glue", "VDD": "glue", "VSS": "glue",
    "IBN": "n", "IBP": "p",
}


def _stage_bus(stage: cos.CpOutputStageLayout, net: str) -> tuple[float, float, float]:
    source = _STAGE_BUS_SOURCE[net]
    if source == "glue":
        return stage.glue_bus[net]
    if source == "n":
        assert stage.array is not None
        return stage.array.n_bus[net]
    assert stage.array is not None
    return stage.array.p_bus[net]


def build(outdir: Path | None = None) -> CpLayout:
    import klayout.db as db  # noqa: PLC0415 -- lazy, same convention as every module in this package
    import tempfile

    stage = cos.build()
    dumpbuf = cp_dumpbuf.build()

    canvas = devgen.Canvas(TOP_CELL)

    with tempfile.TemporaryDirectory() as tmp:
        stage_gds = Path(tmp) / f"{cos.TOP_CELL}.gds"
        dumpbuf_gds = Path(tmp) / f"{cp_dumpbuf.TOP_CELL}.gds"
        stage.write_gds(stage_gds)
        dumpbuf.write_gds(dumpbuf_gds)

        # --- cp_dumpbuf's own per-net bus geometry, read back from its own
        # standalone GDS (_dumpbuf_bus_track's own docstring), in
        # cp_dumpbuf's own LOCAL coordinate frame. ---
        dumpbuf_buses_local = {
            b: _dumpbuf_bus_track(dumpbuf_gds, b, cp_array.pad_center(dumpbuf.pins[b]))
            for _a, b in NET_MAP
        }

        # --- place cp_dumpbuf far enough right that its own footprint never
        # overlaps cp_output_stage's own (BLOCK_GAP_UM's own docstring). dy
        # aligns the two blocks' own footprint bottoms purely for a tidy
        # combined bbox; nothing depends on it. ---
        dx = (stage.footprint[2] - dumpbuf.footprint[0]) + BLOCK_GAP_UM
        dy = stage.footprint[1] - dumpbuf.footprint[1]

        dbu_per_um = int(round(1.0 / canvas.dbu))

        def _place(index, x: float, y: float) -> None:
            trans = db.Trans(db.Vector(int(round(x * dbu_per_um)), int(round(y * dbu_per_um))))
            canvas.top.insert(db.CellInstArray(index, trans))

        canvas.layout.read(str(stage_gds))
        canvas.layout.read(str(dumpbuf_gds))
        stage_index = canvas.layout.cell_by_name(cos.TOP_CELL)
        dumpbuf_index = canvas.layout.cell_by_name(cp_dumpbuf.TOP_CELL)
        _place(stage_index, 0.0, 0.0)
        _place(dumpbuf_index, dx, dy)
        canvas.top.flatten(-1, True)

    # --- Metal2 trunk rows: one dedicated Y per net, strictly above every
    # routing channel either placed block already uses on its own. ---
    dumpbuf_footprint_g = cp_array._translate_box(dumpbuf.footprint, dx, dy)
    backbone_base_y = max(stage.footprint[3], dumpbuf_footprint_g[3]) + BACKBONE_MARGIN_UM
    backbone_rows = {a: backbone_base_y + i * BACKBONE_PITCH_UM for i, (a, _b) in enumerate(NET_MAP)}

    # --- rise on a Metal3 riser from each side's own bus, up to that net's
    # own trunk row (module docstring, step 1), then join the two risers'
    # own trunk-row Metal2 landings with a plain Metal2 horizontal, high
    # above both footprints (step 2). No long Metal2 "reach" -- see module
    # docstring, design 4. ---
    #
    # cp_output_stage's own native bus edge (s_x_hi below) is a bare wire
    # end with no via already on it, so the stage-side riser lands directly
    # there. cp_dumpbuf's own native bus edge (_dumpbuf_bus_track's own
    # docstring: the union of the bus rectangle *and* every one of that
    # net's own per-riser landing squares) is not -- it coincides with an
    # existing riser's own Via2 landing, and a second stack there merges
    # into one oversized via (``V2.1``, the exact failure mode
    # ``cp_output_stage.py``'s "REACHING THE ARRAY BLOCK'S NETS" docstring
    # section names). So the dumpbuf side gets one short Metal2 step, just
    # past that edge and well within the empty :data:`BLOCK_GAP_UM` gap
    # (nothing else is drawn there), before rising -- long enough to clear
    # the existing via, nowhere near long enough to reproduce design 4's own
    # ``M2.2a`` defect (that one crossed the full footprint interior; this
    # is :data:`DUMPBUF_REACH_MARGIN_UM`, a couple of microns).
    for stage_net, dumpbuf_net in NET_MAP:
        trunk_y = backbone_rows[stage_net]

        s_track_y, _s_x_lo, s_x_hi = _stage_bus(stage, stage_net)
        cos._link_tracks(canvas, s_x_hi, s_track_y, trunk_y)

        d_track_y_local, d_x_lo_local, _d_x_hi_local = dumpbuf_buses_local[dumpbuf_net]
        d_track_y = d_track_y_local + dy
        d_x_lo = d_x_lo_local + dx
        d_riser_x = d_x_lo - DUMPBUF_REACH_MARGIN_UM
        cos._extend_bus(canvas, d_track_y, d_riser_x, d_x_lo)
        cos._link_tracks(canvas, d_riser_x, trunk_y, d_track_y)

        # The trunk itself: a plain Metal2 rect joining the two risers' own
        # trunk-row landings, which cp_output_stage._link_tracks already
        # drew (Metal2, half_v2 + VIA_ENCLOSURE_UM wide) at (s_x_hi, trunk_y)
        # and (d_riser_x, trunk_y) above -- merges into both, same net, same
        # layer, safe. Entirely above both footprints (BACKBONE_MARGIN_UM),
        # so this run is free to span the full native-edge-to-native-edge
        # distance without crossing anything either block itself drew.
        cos._extend_bus(canvas, trunk_y, s_x_hi, d_riser_x)

    # --- boundary pins: cp_output_stage's own twelve, minus VDUMP (module
    # docstring's net-map table) -- the exact same absolute pad every one of
    # those pins already promoted, since cp_output_stage sits at a zero
    # offset in this block's own coordinate frame. ---
    for net in BOUNDARY_PINS:
        canvas.pin(net, *stage.pins[net][0])

    footprint = _canvas.bbox_union(
        [stage.footprint, dumpbuf_footprint_g, (stage.footprint[0], stage.footprint[1], dumpbuf_footprint_g[2], backbone_base_y + len(NET_MAP) * BACKBONE_PITCH_UM)]
    )

    layout = CpLayout(
        canvas=canvas,
        footprint=footprint,
        pins=canvas.pins,
        stage=stage,
        dumpbuf=dumpbuf,
        dumpbuf_offset=(dx, dy),
        backbone_rows=dict(backbone_rows),
    )
    if outdir is not None:
        outdir = Path(outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        layout.write_gds(outdir / f"{TOP_CELL}.gds")
    return layout


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    default_outdir = Path(__file__).resolve().parents[2] / "evidence" / "cp-block-layout" / "work"
    parser.add_argument("--outdir", default=str(default_outdir))
    parser.add_argument(
        "--no-netcheck",
        action="store_true",
        help="skip the Metal1-3 connectivity check (see netcheck.py)",
    )
    args = parser.parse_args()
    outdir = Path(args.outdir)
    layout = build(outdir)
    x0, y0, x1, y1 = layout.footprint
    print(f"wrote {outdir}/{TOP_CELL}.gds")
    print(f"footprint: {x1 - x0:.3f} x {y1 - y0:.3f} um  ({(x1 - x0) * (y1 - y0):.2f} um^2)")
    print(f"dumpbuf offset: {layout.dumpbuf_offset}")
    print(f"backbone rows: {layout.backbone_rows}")
    print(f"boundary pins: {sorted(layout.pins)}")
    if args.no_netcheck:
        return 0
    report = netcheck.check_gds(
        outdir / f"{TOP_CELL}.gds", TOP_CELL, netcheck.pad_probe_points(layout.probe_pads())
    )
    print(report.summary())
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
