"""GDS-level metal connectivity check for the ``pfd_cp`` block family
(issue #321).

WHY A DRC-CLEAN RESULT IS NOT A CORRECTNESS CLAIM
--------------------------------------------------
A signoff DRC deck cannot see a **short**: two different nets' shapes that
overlap on one layer merge into a single polygon which is perfectly legal by
every width/space/enclosure rule in the deck. It cannot see an **open**
either -- a net drawn as two pieces that never touch is likewise legal.
``layout/pll_top/lock_detector/checks.py`` already states this for its own
block (issue #322, where 114 real cross-net shorts survived a clean DRC
run), and ``pfd_cp/rowgen.py``'s own ``shorted_pairs()``/
``disconnected_nets()`` proved the same point earlier still (issue #300).

Both of those check a *build-time model*: they record each shape as it is
drawn, inside a ``with canvas.net(...)`` scope, and reason about the boxes
in plain Python. That works only for a generator that tags every shape it
draws with a net -- which ``devgen.py``/``cp_leg.py``/``cp_array.py`` do
not, and cannot cheaply be made to, since they compose already-built leaf
GDS instances (``cp_leg_n``, ``pfdcp_inv_3v3``) whose internal shapes were
never tagged in the first place.

This module checks the **finished GDS** instead, which needs no cooperation
from any generator: it runs KLayout's own connectivity extraction over the
Metal1/Via1/Metal2/Via2/Metal3 stack, then asks which extracted net each of
a caller-supplied set of *probe points* landed on. Two nets that come back
on one extracted net are shorted; one net that comes back on several is
open. Nothing about the PDK is required -- only ``klayout.db`` -- so this
runs anywhere the geometry itself can be built.

WHY METAL ONLY, AND WHY THAT IS THE RIGHT SCOPE
-------------------------------------------------
Comp and Poly2 are deliberately **excluded** from the connectivity graph. A
MOSFET's comp island is one rectangle spanning source, gate and drain, so a
model that conducts through comp merges every device's own two diffusion
terminals -- which is why real LVS extracts devices *first* and splits the
diffusion at each gate. Reproducing that here would be re-implementing the
foundry's LVS deck; running the real one is ``layout/run_pv.py lvs``'s job
and needs a reference netlist this block does not yet have (see
``cp_output_stage.py``'s own docstring on why).

What is left -- the Metal1-to-Metal3 routing graph -- is exactly where this
block family's own composition work happens, and therefore exactly where a
composition bug can be. Every net named below is a metal net: if two of them
share a metal component, they are shorted no matter what the devices do.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Sequence

#: The routing stack this module extracts. Layer numbers are the same
#: gf180mcuD ``layers_def.drc`` values ``devgen.LAYER`` and
#: ``cp_array._EXTRA_LAYER`` already cite.
METAL_LAYERS: dict[str, tuple[int, int]] = {
    "metal1": (34, 0),
    "via1": (35, 0),
    "metal2": (36, 0),
    "via2": (38, 0),
    "metal3": (42, 0),
}

#: Which two metal layers each via joins.
VIA_CONNECTS: tuple[tuple[str, str, str], ...] = (
    ("metal1", "via1", "metal2"),
    ("metal2", "via2", "metal3"),
)

#: The layer probe points are looked up on (every pad in this family is a
#: Metal1 landing pad).
PROBE_LAYER = "metal1"


@dataclass(frozen=True)
class ConnectivityReport:
    """The outcome of :func:`check_gds`.

    ``components`` maps each probed net to the set of extracted-net
    identifiers its own probe points landed on. ``shorts`` lists each group
    of two-or-more probed nets that share one extracted net; ``splits``
    lists each probed net whose points landed on more than one.
    ``unresolved`` lists probe points that landed on no metal at all -- a
    caller bug (a stale coordinate), not a layout finding.
    """

    components: dict[str, frozenset[str]] = field(default_factory=dict)
    shorts: tuple[frozenset[str], ...] = ()
    splits: tuple[str, ...] = ()
    unresolved: tuple[tuple[str, float, float], ...] = ()

    @property
    def ok(self) -> bool:
        return not self.shorts and not self.splits and not self.unresolved

    def summary(self) -> str:
        if self.ok:
            return f"connectivity clean: {len(self.components)} nets, no shorts, no splits"
        parts = []
        if self.shorts:
            parts.append("shorts=" + "; ".join("+".join(sorted(g)) for g in self.shorts))
        if self.splits:
            parts.append(f"splits={list(self.splits)}")
        if self.unresolved:
            parts.append(f"unresolved={list(self.unresolved)}")
        return "connectivity FAILED: " + ", ".join(parts)


def check_gds(
    gds_path: Path | str,
    top_cell: str,
    probes: Mapping[str, Sequence[tuple[float, float]]],
) -> ConnectivityReport:
    """Extract ``gds_path``'s metal connectivity and resolve ``probes``.

    ``probes`` maps a net name to one or more ``(x, y)`` micron coordinates
    that must all land on that net's own metal -- typically the centre of
    every Metal1 landing pad the generator believes belongs to it. A net with
    a single probe point can still be caught shorting to another net; a net
    with several also proves it is not *open*, which is why callers should
    probe every pad rather than one representative.
    """
    import klayout.db as db  # noqa: PLC0415 -- lazy, same convention as every module in this package

    layout = db.Layout()
    layout.read(str(gds_path))
    cell = layout.cell(top_cell)
    if cell is None:
        raise ValueError(f"{gds_path} has no cell named {top_cell!r}")

    l2n = db.LayoutToNetlist(db.RecursiveShapeIterator(layout, cell, []))
    regions = {
        name: l2n.make_polygon_layer(layout.layer(*gds), name) for name, gds in METAL_LAYERS.items()
    }
    for region in regions.values():
        l2n.connect(region)
    for lower, via, upper in VIA_CONNECTS:
        l2n.connect(regions[lower], regions[via])
        l2n.connect(regions[via], regions[upper])
    l2n.extract_netlist()

    probe_layer = regions[PROBE_LAYER]
    components: dict[str, frozenset[str]] = {}
    unresolved: list[tuple[str, float, float]] = []
    for net, points in probes.items():
        found: set[str] = set()
        for x, y in points:
            hit = l2n.probe_net(probe_layer, db.DPoint(x, y))
            if hit is None:
                unresolved.append((net, x, y))
            else:
                found.add(hit.expanded_name())
        components[net] = frozenset(found)

    by_component: dict[str, set[str]] = {}
    for net, ids in components.items():
        for ident in ids:
            by_component.setdefault(ident, set()).add(net)

    shorts = sorted(
        {frozenset(nets) for nets in by_component.values() if len(nets) > 1},
        key=lambda g: sorted(g),
    )
    splits = tuple(sorted(net for net, ids in components.items() if len(ids) > 1))
    return ConnectivityReport(
        components=components,
        shorts=tuple(shorts),
        splits=splits,
        unresolved=tuple(unresolved),
    )


def pad_probe_points(
    pads: Mapping[str, Iterable[tuple[float, float, float, float]]],
) -> dict[str, list[tuple[float, float]]]:
    """``net -> [pad box, ...]`` (the shape every generator in this package
    already records) -> ``net -> [(x, y), ...]`` probe points at each pad's
    own centre."""
    return {
        net: [((b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0) for b in boxes]
        for net, boxes in pads.items()
    }
