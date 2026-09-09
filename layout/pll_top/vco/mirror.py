"""``vco_bias.sch``'s 3-cascade band-select mirror, laid out common-centroid.

WHY THIS BLOCK IS DRAWN SEPARATELY FROM THE REST OF ``vco_bias.sch``
--------------------------------------------------------------------
``vco_bias.sch`` contains two structurally different things: a V-to-I core
(``MP1``/``MP2``/``MN1``/``MN2``/``MSU*``/``MPR``/``MD1``/``MD2``/``MOFF``/
``MVI``/``MSUM``, plus **three ``ppolyf_u_3k`` poly resistors**
``RCG``/``ROFF``/``RDEG``) that turns ``VCTRL`` into the summing-node current
``VBP0``, and the band-select mirror that scales ``VBP0`` by the 3-bit band
code. This module draws the second (``vtoi_core.py``/``bias_resistors.py``
draw the first).

WHY COMMON-CENTROID IS A GENERATOR FEATURE HERE, NOT A PLACEMENT HABIT
----------------------------------------------------------------------
``layout/floorplan/PLL-FLOORPLAN.md`` §1 makes this an explicit requirement,
with the risk named: DR-003 cascades the mirror rather than paralleling
weighted legs so that "the largest device ratio in any single mirror [is]
6.4:1 instead of 41:1, which matters for matching and for area — that
headroom is only real if the mirror legs are laid out to exploit it … a
mismatch between an always-on and a switched leg shows up directly as
adjacent-band-step error". So each cascade is drawn as one interdigitated
finger array whose two legs share a centroid, and
``check_common_centroid()`` *proves* that property arithmetically (both legs'
finger centroids equal the array's own centre) rather than leaving it to
visual inspection.

The patterns come from ``devices.py`` and are palindromes, which is what
makes the centroids coincide even though the two legs have different finger
widths:

===========  =========================================  =====================
Cascade      Pattern (left → right, A = always-on)      Netlist ``nf``
===========  =========================================  =====================
A (pfet)     ``A S S A``                                2 / 2, drawn as-is
B (nfet)     ``A S S A``                                1 / 1, **folded to 2**
C (pfet)     ``S S S S A S S S S``                      1 / 8, drawn as-is
===========  =========================================  =====================

Cascade B is the one place the drawn finger count deviates from the frozen
netlist's ``nf``: two single-finger devices cannot be interdigitated at all
(a one-finger leg's centroid *is* that finger's centre, which can never
coincide with a different one-finger leg's centre), so each leg is folded
into two fingers of exactly half its schematic ``W``. Total ``W``, ``L`` and
device count are preserved exactly; only ``nf`` differs. See
``devices.CASCADE_B``'s comment.

TWO TIERS, NOT ONE ROW (issue #324)
------------------------------------
PR #325 (issue #293's own final increment) recorded that this block, drawn
as a single PMOS row over a single NMOS row, is 269.86 µm wide — wider than
every other VCO sub-block combined — and set the whole assembled ``vco_block``
footprint's width. That PR's own follow-up, issue #324, asks for at least one
sub-block to be "refolded ... into multiple rows" to recover width, which the
block-level ``VDD_VCO``-tied n-well guard-ring band (``PLL-FLOORPLAN.md``
§1's other open item) is funded from. This module is that refold.

The netlist is a signal-flow ladder (``vco_bias.sch``'s own comment: ``VBP0``
→ cascade A → ``VBN1`` → cascade B → ``VBP2`` → cascade C → ``VBN``/``VBP``),
so the natural place to cut it in two is wherever the fewest nets cross the
cut. Tracing every device's own nets (``devices.py``) shows exactly one such
net at the boundary between cascade B and cascade C: ``VBP2`` (cascade B's own
drain, feeding ``MDB``/``MSWC0``/cascade C's always-on gate). Every other net
touching either half — ``B0``/``B0B``/``B1``/``B1B``/``VBP0``/``GA``/``VBN1``/
``GB`` on one side, ``B2``/``B2B``/``GC``/``VBN``/``VBP`` on the other — is
entirely local to it. So:

* **Tier 1** (bottom): the band-code-0/1 inverters, cascade A, cascade B, and
  their muxes — ``TIER1_PMOS_ROW``/``TIER1_NMOS_ROW``.
* **Tier 2** (stacked above tier 1, its own gap): the band-code-2 inverter,
  ``MDB``, cascade C, its mux, and the ``VBN``/``VBP`` output-mirror loads —
  ``TIER2_PMOS_ROW``/``TIER2_NMOS_ROW``.

Each tier is built with exactly the same machinery the single-row generator
used (``_build_row_plan()``, ``_Builder.draw_devices()``/``draw_tracks()``):
its own PMOS row, its own NMOS row, its own Metal2 mesh channel between them
(see "ROUTING" below), and its own local ``VDD_VCO``-tied n-well tap band
above its own PMOS row. What is genuinely new for two tiers instead of one:

* **A local ``GND_VCO`` substrate tap** between the two tiers
  (``mid_gnd_tap``): tier 1's own NMOS row can still reach the shared outer
  ring's *bottom* band (as before), but tier 2's NMOS row sits well outside
  ``DF.13_MV``/``DF.14_MV``'s 15 µm bound from that same band, so a second,
  local p+ tap strip sits between tier 1's n-well and tier 2's NMOS row
  (``Plan.gnd_tap_edge_y`` records, per tier, which of these two a `GND_VCO`
  source pad rail-stubs to).
* **One cross-tier Metal2 riser** for ``VBP2``, the only net either tier's
  own local channel does not carry end-to-end. Both tiers draw their own
  (single-lane, since ``VBP2`` is nfet-only in tier 1 and pfet-only in tier
  2) local ``VBP2`` track exactly as before; ``build()`` extends both to one
  shared column (``MirrorPlan.link_vbp2_x``) clear of every other column in
  either tier, the same "top-level route is Metal2, which has no spacing
  relationship with Metal1/comp/poly/implant in this deck" reasoning
  ``block.py`` uses for its own inter-sub-block routes (see that module's
  docstring) — this riser freely crosses tier 1's own PMOS row, its tap band,
  and the mid ``GND_VCO`` tap without any DRC relationship to any of them.
* **One shared outer ``GND_VCO`` guard ring**, around both tiers and the mid
  tap, instead of one ring per tier — this is still one sub-block, not two.

ROUTING: WHY THIS BLOCK USES METAL2 AND ``ring.py`` DID NOT
-----------------------------------------------------------
Within *one* tier, an interdigitated array has to get four nets across the
same span: the shared source bus, the shared drain bus, and *two* gate buses
(one per leg). ``primitives.mosfet()``'s S/D pads sit at the top and bottom
of each finger, so the source and drain buses consume both of those tracks,
and the two gate buses have to cross the array in the corridor between them.
Widening the S/D comp overhang (``primitives.mosfet(sd_overhang=...)``, added
for exactly this) opens that corridor — but the array's own drain/gate nets
still have to reach devices in the *other* transistor row, and every such net
would then have to cross every other one. That is not planar in a single
metal. So each tier routes all of its own inter-device nets as Metal2 tracks
in the channel between its NMOS and PMOS rows, with Metal1 only for the short
vertical escapes from each device pad up/down to its track, and for the one
Metal1 "link" column a net needs when it touches devices in *both* rows of
the *same* tier (see ``NET_ORDER``'s comment below — unchanged from the
single-row design). ``ring.py``'s ring is a chain, not a mesh, so it needed
none of this.

Every Metal1 escape column is registered with ``Plan.reserve()``, which fails
the build if two different nets' columns come within ``M1.2a``'s 0.23 µm — a
spacing bug in a generated 150+ µm-wide block is much cheaper to catch as a
Python exception than as one of several thousand DRC markers.

Standalone-DRC scope: like ``ring.py``'s and ``buffer.py``'s blocks, this one
draws its own dedicated guard ring (outer substrate ``p`` ring tied
``GND_VCO``; two ``VDD_VCO``-tied n-well tap bands, one per tier) so it is
provable on its own. ``VBP0``/``B0``/``B1``/``B2`` are input pins and
``VBP``/``VBN`` output pins at the block boundary — ``VBP``/``VBN`` are
exactly the nets ``ring.py``'s block already exposes as Metal1 pins, which is
what lets ``block.py``'s integration increment route to them rather than
re-derive them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import devices as dev
from . import primitives as prim

TOP_CELL = "vco_bandsel_mirror"

VDD_NET = "VDD_VCO"
GND_NET = "GND_VCO"

# --- generator geometry (um) -----------------------------------------------
SD_OVERHANG_UM = 1.5
"""Source/drain comp overhang for *every* device in this block.

Deliberately much wider than ``primitives.SD_OVERHANG_UM`` (0.5): it moves
each device's S/D contact rows away from its gate, which (a) opens the
Metal1 corridor the two gate buses of a common-centroid array need, and
(b) gives every device the same ~0.48 um of clear y between its gate pad and
each S/D pad, so a gate escape column never has to thread a gap narrower
than M1.2a's 0.23 um minimum. It changes no device parameter -- W and L are
untouched -- only the diffusion overhang, which is a free layout choice
above DF.6_LV's 0.24 um minimum.
"""

DEVICE_GAP_UM = 3.4  # comp right edge -> next comp left edge, ordinary devices
ARRAY_GAP_UM = 4.5  # ... when the next item is a common-centroid array (its
# always-on gate bus escapes in this gap, see ARRAY_LEFT_ESCAPE_UM)
CC_FINGER_GAP_UM = 3.0  # between two fingers of one common-centroid array;
# wide enough that the array's own drain/source escape columns fit in an
# inter-finger gap without crowding the next finger's gate contact tab.
ARRAY_LEFT_ESCAPE_UM = 2.2  # always-on gate bus escape, left of the array
ARRAY_RIGHT_ESCAPE_UM = 1.1  # switched gate bus escape, right of the array
JOG_ESCAPE_UM = 1.1  # escape column for a terminal that faces the wrong rail

ESCAPE_WIRE_W_UM = 0.44  # == via1_stack()'s pad, so a column is one clean width
TRACK_PITCH_UM = 0.8  # 0.44 metal2 width + 0.36 space (M2.2a min is 0.28)
CHANNEL_MARGIN_UM = 1.0
LINK_PITCH_UM = 1.0  # between two adjacent net-link columns (see below)
LINK_MARGIN_UM = 3.0  # from the rows' right edge to the first link column

TAP_GAP_UM = 0.6
TAP_BAND_WIDTH_UM = 0.6
RING_WIDTH_UM = 1.2
OUTER_MARGIN_LEFT_UM = 3.0
OUTER_MARGIN_RIGHT_UM = 3.0
OUTER_MARGIN_BELOW_UM = 2.5
OUTER_MARGIN_ABOVE_UM = 2.5

# --- the two-tier fold (issue #324) -----------------------------------------
MID_TAP_GAP_BELOW_UM = OUTER_MARGIN_ABOVE_UM - RING_WIDTH_UM  # tier 1's own
# n-well top edge -> the mid GND tap's comp bottom edge; the same DF.4c_LV
# clearance-with-margin the outer ring's own top band uses against tier 2's
# nwell (see plan()), reused here since it is the identical relationship
# (p+ comp near an n-well edge).
MID_TAP_GAP_ABOVE_UM = prim.COMP_GAP_UM  # mid tap's own comp top edge -> tier
# 2's NMOS row comp bottom edge -- ordinary comp-to-comp clearance between two
# separate diffusion islands, same constant every other device-to-device gap
# in this module already uses.
LINK_VBP2_MARGIN_UM = 2.0  # clear of both tiers' own rightmost metal (rows,
# escapes, and each tier's own intra-tier link columns) before the shared
# cross-tier VBP2 riser's own column.
LINK_VDD_MARGIN_UM = 2.0  # clear of both tiers' own leftmost metal before the
# shared cross-tier VDD_VCO riser's own column (left, not right, so its
# horizontal jogs at each tap band's own y never cross the VBP2 riser's).

# Inter-device net order, used for track assignment *within one tier*.
# Ordering is arbitrary for DRC (two tracks never touch) and chosen here to
# read in signal order: band code first, then the cascade chain.
#
# THE CHANNEL IS SPLIT INTO TWO TRACK GROUPS, AND THAT IS LOad-BEARING.
# A Metal1 escape column from the NMOS row runs *upward* from a device pad to
# its track; one from the PMOS row runs *downward*. If both groups' tracks
# were interleaved, an NMOS column reaching a high track and a PMOS column
# reaching a low track would overlap in y -- and if their x happened to
# coincide (which it did, on the first build of this generator: MDN's drain
# pad landed on MSWA0's gate tab), that is a hard M1.2a short between two
# different nets. So every net that needs escapes in *both* rows of *one*
# tier gets two tracks: a "lo" one in the lower group, reachable only from
# that tier's NMOS row, and a "hi" one in the upper group, reachable only
# from its PMOS row. By construction every NMOS column ends below every
# PMOS column starts, so the two rows' columns can never interact whatever
# their x.
#
# The two tracks of such a net are tied together by one Metal1 "link" column
# in a dedicated strip to the right of both rows (``LINK_MARGIN_UM`` past the
# rows' right edge), where no device escape exists -- the one place a
# lo-to-hi column is safe.
TIER1_NET_ORDER = (
    "B0",
    "B0B",
    "B1",
    "B1B",
    "VBP0",
    "GA",
    "VBN1",
    "GB",
    "VBP2",  # produced here (cascade B's drain); consumed in tier 2 -- see
    # the module docstring's cross-tier riser.
)
TIER2_NET_ORDER = (
    "B2",
    "B2B",
    "VBP2",  # consumed here; nfet-only in tier 1, pfet-only here, so neither
    # tier needs an intra-tier link for it -- only the cross-tier riser.
    "GC",
    "VBN",
    "VBP",
)
NET_ORDER = TIER1_NET_ORDER + tuple(n for n in TIER2_NET_ORDER if n not in TIER1_NET_ORDER)
"""The full 14-net union, for callers that want "every net this block routes"
without caring which tier -- the per-tier plans are what ``build()`` and
``plan()`` actually route from."""

# Row contents, left to right, per tier. Names index devices.py's own tables.
TIER1_PMOS_ROW = ("MIP0", "A", "MSWA0", "MSWA1", "MIP1")
TIER1_NMOS_ROW = ("MIN0", "MDA", "B", "MSWB0", "MSWB1", "MIN1")
TIER2_PMOS_ROW = ("MDB", "MIP2", "MSWC0", "MSWC1", "C", "MDP")
TIER2_NMOS_ROW = ("MDN", "MMN", "MIN2")

# Which tier each block-boundary pin belongs to (see build()'s pin section).
_IN_NET_TIER = {"VBP0": 1, "B0": 1, "B1": 1, "B2": 2}
_OUT_NET_TIER = {"VBP": 2, "VBN": 2}


def _device_index() -> dict[str, dev.Fet]:
    table: dict[str, dev.Fet] = {}
    for inv in dev.MIRROR_INVERTERS:
        table[inv.pfet.name] = inv.pfet
        table[inv.nfet.name] = inv.nfet
    for mux in dev.MIRROR_MUXES:
        table[mux.on.name] = mux.on
        table[mux.off.name] = mux.off
    for load in dev.MIRROR_LOADS:
        table[load.name] = load
    return table


DEVICES = _device_index()
CASCADES = {c.name: c for c in dev.MIRROR_CASCADES}


def device_height_um(l_um: float) -> float:
    return 2 * SD_OVERHANG_UM + l_um


# ---------------------------------------------------------------------------
# Common-centroid arithmetic -- pure Python, no KLayout, so the property this
# whole block exists to guarantee is checkable by layout/tests/.
# ---------------------------------------------------------------------------


def finger_x0_um(cascade: dev.CascadePair, x0: float = 0.0) -> tuple[float, ...]:
    """Left comp edge of each drawn finger, left to right, from ``x0``."""
    xs = []
    x = x0
    for w in cascade.finger_widths():
        xs.append(x)
        x += w + CC_FINGER_GAP_UM
    return tuple(xs)


def array_width_um(cascade: dev.CascadePair) -> float:
    widths = cascade.finger_widths()
    return sum(widths) + (len(widths) - 1) * CC_FINGER_GAP_UM


def leg_centroid_um(cascade: dev.CascadePair, leg: str, x0: float = 0.0) -> float:
    """Centroid (mean finger centre, area-weighted) of one leg's fingers.

    Area-weighted and plain-mean coincide here because every finger of a
    given leg has the same width -- the weighting is written out anyway so
    the function stays correct if a leg ever gets unequal fingers.
    """
    xs = finger_x0_um(cascade, x0)
    widths = cascade.finger_widths()
    sel = [(x, w) for x, w, tag in zip(xs, widths, cascade.pattern) if tag == leg]
    total_w = sum(w for _, w in sel)
    return sum((x + w / 2.0) * w for x, w in sel) / total_w


def check_common_centroid(cascade: dev.CascadePair, tol_um: float = 1e-9) -> None:
    """Raise unless both legs' centroids coincide with the array's centre.

    This is the acceptance criterion "band-select mirror cascades laid out
    common-centroid (always-on leg interdigitated with switched leg per
    cascade), not row-placed" reduced to something a build can fail on.
    """
    if tuple(cascade.pattern) != tuple(reversed(cascade.pattern)):
        raise ValueError(f"cascade {cascade.name}: pattern {cascade.pattern} is not a palindrome")
    if cascade.pattern.count("A") != cascade.always_on.fingers:
        raise ValueError(f"cascade {cascade.name}: pattern has the wrong always-on finger count")
    if cascade.pattern.count("S") != cascade.switched.fingers:
        raise ValueError(f"cascade {cascade.name}: pattern has the wrong switched finger count")
    centre = array_width_um(cascade) / 2.0
    for leg in ("A", "S"):
        c = leg_centroid_um(cascade, leg)
        if abs(c - centre) > tol_um:
            raise ValueError(
                f"cascade {cascade.name}: leg {leg} centroid {c:.6f} um != array centre {centre:.6f} um"
            )
    # Interdigitation, not two blobs: a "row-placed" pair is exactly two
    # maximal runs (all of one leg, then all of the other). Any genuinely
    # interleaved pattern -- ABBA, SSSSASSSS -- has three or more.
    runs = 1 + sum(1 for a, b in zip(cascade.pattern, cascade.pattern[1:]) if a != b)
    if runs < 3:
        raise ValueError(
            f"cascade {cascade.name}: pattern {cascade.pattern} is row-placed "
            f"({runs} runs), not interdigitated"
        )


def gate_bus_y_um(l_um: float, y_bottom: float) -> tuple[float, float]:
    """The two gate-bus track y's inside one array's own S/D corridor.

    Returns ``(y_always_on, y_switched)``, both centred in the clear band
    between an S/D pad and the gate pad, with at least M1.2a's 0.23 um to
    each. Raises if ``SD_OVERHANG_UM`` is ever tightened past the point where
    two buses still fit -- the failure mode this module must never ship
    silently.
    """
    pad_h = prim.CONTACT_SIZE_UM + 2 * prim.METAL1_PAD_MARGIN_UM
    pad_lo_top = y_bottom + prim.CONTACT_ROW_MARGIN_UM - prim.METAL1_PAD_MARGIN_UM + pad_h
    pad_hi_bot = y_bottom + device_height_um(l_um) - prim.CONTACT_ROW_MARGIN_UM + prim.METAL1_PAD_MARGIN_UM - pad_h
    gate_c = y_bottom + SD_OVERHANG_UM + l_um / 2.0
    gate_half = prim.GATE_TAB_H_UM / 2.0 + prim.METAL1_PAD_MARGIN_UM
    clear = dev.DRC_METAL1_MIN_SPACE_UM + prim.METAL1_WIRE_WIDTH_UM / 2.0

    lo_min, lo_max = pad_lo_top + clear, gate_c - gate_half - clear
    hi_min, hi_max = gate_c + gate_half + clear, pad_hi_bot - clear
    if lo_min > lo_max or hi_min > hi_max:
        raise ValueError(
            f"no room for two gate buses at L={l_um} um with SD_OVERHANG_UM={SD_OVERHANG_UM} um"
        )
    return ((lo_min + lo_max) / 2.0, (hi_min + hi_max) / 2.0)


# ---------------------------------------------------------------------------
# Placement plan -- pure Python (no KLayout import), so footprint_um() and the
# tests derive the block's extents from the same arithmetic build() draws
# from, instead of a second copy of it.
# ---------------------------------------------------------------------------


@dataclass
class Item:
    name: str
    kind: str  # "fet" or "cc"
    x0: float
    width: float
    fet: dev.Fet | None = None
    cascade: dev.CascadePair | None = None
    finger_x0: tuple[float, ...] = ()


@dataclass
class Plan:
    """One tier's own row-pair plan: a PMOS row over an NMOS row, its own
    inter-device Metal2 channel, and its own local ``VDD_VCO`` n-well tap
    band. Everything above/below this tier (the shared outer ring, the mid
    ``GND_VCO`` tap between tiers, the cross-tier ``VBP2`` riser) is
    ``MirrorPlan``'s concern, not this one's.
    """

    pmos: list[Item] = field(default_factory=list)
    nmos: list[Item] = field(default_factory=list)
    net_order: tuple[str, ...] = ()
    net_rows: dict[str, set] = field(default_factory=dict)
    track_lo: dict[str, float] = field(default_factory=dict)
    track_hi: dict[str, float] = field(default_factory=dict)
    link_x: dict[str, float] = field(default_factory=dict)
    channel: tuple[float, float] = (0.0, 0.0)
    pmos_top: float = 0.0
    pmos_bottom: float = 0.0
    nwell: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    tap_band: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    y0: float = 0.0  # this tier's own NMOS row bottom edge, absolute
    gnd_tap_edge_y: float = 0.0  # where a GND_VCO source pad rail-stubs to
    # (the shared outer ring's bottom band for tier 1, the mid tap for tier 2)
    gnd_tap_comp_edge_y: float = 0.0  # same edge, without the metal pad's
    # own margin -- the actual comp edge DF.13_MV/DF.14_MV measures from.
    left_metal_x: float = 0.0  # this tier's own leftmost drawn geometry
    right_metal_x: float = 0.0  # ... and rightmost (rows + escapes + links)
    _columns: list = field(default_factory=list)

    # -- Metal1 escape-column bookkeeping (see the module docstring) --
    def track_y(self, net: str, row: str) -> float:
        """The Metal2 track ``row``'s Metal1 escape columns may land ``net`` on."""
        return self.track_lo[net] if row == "nfet" else self.track_hi[net]

    def reserve(self, net: str, x0: float, y0: float, x1: float, y1: float) -> None:
        s = dev.DRC_METAL1_MIN_SPACE_UM
        for other_net, ox0, oy0, ox1, oy1 in self._columns:
            if other_net == net:
                continue
            if x0 - s < ox1 and ox0 < x1 + s and y0 - s < oy1 and oy0 < y1 + s:
                raise ValueError(
                    f"Metal1 escape columns for {net!r} and {other_net!r} are closer than "
                    f"M1.2a's {s} um: ({x0:.3f},{y0:.3f})-({x1:.3f},{y1:.3f}) vs "
                    f"({ox0:.3f},{oy0:.3f})-({ox1:.3f},{oy1:.3f})"
                )
        self._columns.append((net, x0, y0, x1, y1))


@dataclass
class MirrorPlan:
    """The whole (two-tier) block's own plan: two ``Plan``s plus the geometry
    that joins them (the mid GND tap, the cross-tier VBP2 riser column, and
    the shared outer guard ring)."""

    tier1: Plan
    tier2: Plan
    mid_gnd_tap: tuple[float, float, float, float]
    link_vbp2_x: float
    link_vdd_x: float
    outer: tuple[float, float, float, float]


def _row_items(names: tuple[str, ...]) -> list[Item]:
    items: list[Item] = []
    x = 0.0
    for i, name in enumerate(names):
        if name in CASCADES:
            cascade = CASCADES[name]
            if i > 0:
                x += ARRAY_GAP_UM - DEVICE_GAP_UM
            w = array_width_um(cascade)
            items.append(
                Item(
                    name=name,
                    kind="cc",
                    x0=x,
                    width=w,
                    cascade=cascade,
                    finger_x0=finger_x0_um(cascade, x),
                )
            )
        else:
            fet = DEVICES[name]
            w = fet.w_um
            items.append(Item(name=name, kind="fet", x0=x, width=w, fet=fet))
        x += w + DEVICE_GAP_UM
    return items


def _net_rows(pmos: list[Item], nmos: list[Item]) -> dict[str, set]:
    """Which transistor row(s) each inter-device net is escaped from.

    Derived from the device tables, not from the drawing pass, so track
    assignment is known before any geometry exists. A pfet's source is the
    ``VDD_VCO`` tap band and an nfet's source the ``GND_VCO`` guard ring --
    those two nets are rails, never channel tracks, so they are excluded.
    """
    rows: dict[str, set] = {}

    def add(net: str, row: str) -> None:
        if net in (VDD_NET, GND_NET):
            return
        rows.setdefault(net, set()).add(row)

    for items, row in ((pmos, "pfet"), (nmos, "nfet")):
        for it in items:
            if it.kind == "cc":
                c = it.cascade
                add(c.always_on.bottom_net if row == "pfet" else c.always_on.top_net, row)
                add(c.always_on.gate_net, row)
                add(c.switched.gate_net, row)
            else:
                f = it.fet
                add(f.gate_net, row)
                add(f.top_net, row)
                add(f.bottom_net, row)
    return rows


def _build_row_plan(
    pmos_names: tuple[str, ...], nmos_names: tuple[str, ...], net_order: tuple[str, ...], y0: float
) -> Plan:
    """One tier's own row-pair plan, its NMOS row bottom-aligned at ``y0``.

    Identical arithmetic to the single-row generator this replaces, just
    parameterized by which devices go in each row, which nets that subset
    routes, and where the tier's own local origin sits -- everything above
    (the shared ring, the mid tap, cross-tier routing) is ``plan()``'s own
    concern, not this function's.
    """
    p = Plan(net_order=net_order, y0=y0)
    p.pmos = _row_items(pmos_names)
    p.nmos = _row_items(nmos_names)
    p.net_rows = _net_rows(p.pmos, p.nmos)

    missing = set(p.net_rows) - set(net_order)
    if missing:
        raise ValueError(f"nets with no track assignment: {sorted(missing)}")

    def _l(it: Item) -> float:
        return it.fet.l_um if it.kind == "fet" else it.cascade.always_on.l_um

    nmos_h = max(device_height_um(_l(it)) for it in p.nmos)
    pmos_h = max(device_height_um(_l(it)) for it in p.pmos)

    # --- lower track group (NMOS-row escapes), then upper group (PMOS-row) ---
    lo_nets = [n for n in net_order if "nfet" in p.net_rows.get(n, ())]
    hi_nets = [n for n in net_order if "pfet" in p.net_rows.get(n, ())]
    ch_y0 = y0 + nmos_h + CHANNEL_MARGIN_UM
    for i, net in enumerate(lo_nets):
        p.track_lo[net] = ch_y0 + TRACK_PITCH_UM / 2.0 + i * TRACK_PITCH_UM
    base_hi = ch_y0 + len(lo_nets) * TRACK_PITCH_UM
    for j, net in enumerate(hi_nets):
        p.track_hi[net] = base_hi + TRACK_PITCH_UM / 2.0 + j * TRACK_PITCH_UM
    ch_y1 = base_hi + len(hi_nets) * TRACK_PITCH_UM
    p.channel = (ch_y0, ch_y1)
    # A net escaped from only one row still needs a value for the other, so
    # escape() can be row-agnostic; with no column ever reaching it, aliasing
    # is harmless.
    for net in net_order:
        if net not in p.track_lo:
            p.track_lo[net] = p.track_hi[net]
        elif net not in p.track_hi:
            p.track_hi[net] = p.track_lo[net]

    p.pmos_bottom = ch_y1 + CHANNEL_MARGIN_UM
    p.pmos_top = p.pmos_bottom + pmos_h

    pmos_x0 = p.pmos[0].x0
    pmos_x1 = p.pmos[-1].x0 + p.pmos[-1].width
    p.tap_band = (
        pmos_x0,
        p.pmos_top + TAP_GAP_UM,
        pmos_x1,
        p.pmos_top + TAP_GAP_UM + TAP_BAND_WIDTH_UM,
    )
    m = prim.NWELL_MARGIN_UM
    p.nwell = (pmos_x0 - m, p.pmos_bottom - m, pmos_x1 + m, p.tap_band[3] + m)

    # --- lo/hi link columns, right of both rows ---
    rows_right = (
        max(pmos_x1, p.nmos[-1].x0 + p.nmos[-1].width)
        + ARRAY_RIGHT_ESCAPE_UM
        + max(JOG_ESCAPE_UM, ARRAY_RIGHT_ESCAPE_UM)
        + ESCAPE_WIRE_W_UM / 2.0
    )
    link_nets = [n for n in net_order if p.net_rows.get(n, set()) == {"nfet", "pfet"}]
    for k, net in enumerate(link_nets):
        p.link_x[net] = rows_right + LINK_MARGIN_UM + k * LINK_PITCH_UM

    # Leftmost Metal1 in either row: a gate contact tab's own pad, or (for a
    # row that starts with an array) that array's always-on gate escape.
    tab_dx = prim.POLY_ENDCAP_UM - prim.GATE_TAB_OVERLAP_UM + prim.GATE_TAB_W_UM + prim.METAL1_PAD_MARGIN_UM
    left_metal = -tab_dx
    right_metal = max([rows_right] + [x + ESCAPE_WIRE_W_UM / 2.0 for x in p.link_x.values()])

    p.left_metal_x = min(p.nwell[0], left_metal)
    p.right_metal_x = max(p.nwell[2], right_metal)
    return p


def plan() -> MirrorPlan:
    for cascade in dev.MIRROR_CASCADES:
        check_common_centroid(cascade)

    # --- tier 1: input stage through cascade B, NMOS row bottom at y=0, same
    # as the single-row generator's own origin convention. ---
    t1 = _build_row_plan(TIER1_PMOS_ROW, TIER1_NMOS_ROW, TIER1_NET_ORDER, y0=0.0)

    gnd_pad_y0 = prim.CONTACT_ROW_MARGIN_UM - prim.METAL1_PAD_MARGIN_UM
    outer_y0 = gnd_pad_y0 - OUTER_MARGIN_BELOW_UM - RING_WIDTH_UM
    t1.gnd_tap_comp_edge_y = outer_y0 + RING_WIDTH_UM
    t1.gnd_tap_edge_y = t1.gnd_tap_comp_edge_y + prim.METAL1_PAD_MARGIN_UM

    # --- the mid GND_VCO tap: tier 2's own local substrate tie, since the
    # shared ring's bottom band (tier 1's own tie) is well past 15 um from
    # tier 2's NMOS row -- see the module docstring. Spans the union of both
    # tiers' own n-well/NMOS-row extents so every device either tier ever
    # places is comfortably within DF.13_MV/DF.14_MV's bound of *some* tap. ---
    mid_tap_y0 = dev.snap_um(t1.nwell[3] + MID_TAP_GAP_BELOW_UM)
    mid_tap_y1 = dev.snap_um(mid_tap_y0 + TAP_BAND_WIDTH_UM)
    tier2_y0 = dev.snap_um(mid_tap_y1 + MID_TAP_GAP_ABOVE_UM)

    # --- tier 2: cascade C and its output mirror, stacked above tier 1. ---
    t2 = _build_row_plan(TIER2_PMOS_ROW, TIER2_NMOS_ROW, TIER2_NET_ORDER, y0=tier2_y0)
    t2.gnd_tap_comp_edge_y = mid_tap_y1
    t2.gnd_tap_edge_y = mid_tap_y1 + prim.METAL1_PAD_MARGIN_UM

    mid_tap_x0 = min(t1.nwell[0], t2.left_metal_x)
    mid_tap_x1 = max(t1.nwell[2], t2.right_metal_x)
    mid_gnd_tap = (mid_tap_x0, mid_tap_y0, mid_tap_x1, mid_tap_y1)

    link_vbp2_x = dev.snap_um(max(t1.right_metal_x, t2.right_metal_x) + LINK_VBP2_MARGIN_UM)

    # tier 1's own VDD_VCO n-well tap band and tier 2's own are two separate
    # Metal1 islands (same net name, no metal path between them) unless tied
    # together explicitly -- same "prove it" rationale as the mid GND tap's
    # own strap below. This riser has to reach *up*, through tier 1's own
    # tap-band-height strip and tier 2's, which is exactly the y range the
    # VBP2 riser's own column occupies on the *right* -- so this one runs on
    # the *left* instead, clear of it (see build()'s own comment).
    link_vdd_x = dev.snap_um(min(t1.left_metal_x, t2.left_metal_x) - LINK_VDD_MARGIN_UM)

    outer = (
        min(t1.left_metal_x, t2.left_metal_x, link_vdd_x - ESCAPE_WIRE_W_UM / 2.0) - OUTER_MARGIN_LEFT_UM,
        outer_y0,
        max(t1.right_metal_x, t2.right_metal_x, link_vbp2_x + ESCAPE_WIRE_W_UM / 2.0)
        + OUTER_MARGIN_RIGHT_UM,
        t2.nwell[3] + OUTER_MARGIN_ABOVE_UM,
    )

    return MirrorPlan(
        tier1=t1,
        tier2=t2,
        mid_gnd_tap=mid_gnd_tap,
        link_vbp2_x=link_vbp2_x,
        link_vdd_x=link_vdd_x,
        outer=outer,
    )


def footprint_um() -> tuple:
    return plan().outer


def max_pmos_tap_distance_um() -> float:
    """Worst-case pfet-to-nearest-n-well-tap distance (DF.13_MV/DF.14_MV),
    across both tiers -- each tier's own tap band runs the full length of its
    own PMOS row along its top edge, so the worst case per tier is a device's
    own bottom (drain) edge, same as the single-row generator's formula."""
    p = plan()
    return max((t.pmos_top - t.pmos_bottom) + TAP_GAP_UM for t in (p.tier1, p.tier2))


def max_nmos_tap_distance_um() -> float:
    """Worst-case nfet-to-nearest-substrate-tap distance, across both tiers:
    tier 1 to the shared outer ring's bottom band, tier 2 to the mid tap."""
    p = plan()
    worst = 0.0
    for t in (p.tier1, p.tier2):
        def _l(it: Item) -> float:
            return it.fet.l_um if it.kind == "fet" else it.cascade.always_on.l_um

        nmos_h = max(device_height_um(_l(it)) for it in t.nmos)
        worst = max(worst, (t.y0 + nmos_h) - t.gnd_tap_comp_edge_y)
    return worst


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------


@dataclass
class MirrorResult:
    canvas: prim.Canvas
    plan: MirrorPlan
    footprint: tuple = (0.0, 0.0, 0.0, 0.0)
    net_x: dict = field(default_factory=dict)


class _Builder:
    """Draws one tier's own devices, channel routing, and n-well tap band.

    ``build.py``'s top-level ``build()`` function makes one of these per
    tier, then adds the geometry that is not any single tier's concern (the
    mid GND tap, the cross-tier VBP2 riser, the shared outer ring, and the
    block's own boundary pins).
    """

    def __init__(self, tier_plan: Plan, canvas: prim.Canvas) -> None:
        self.plan = tier_plan
        self.canvas = canvas
        self.net_x: dict[tuple[str, str], list[float]] = {}
        self.track_x1: dict[str, float] = {}

    # -- escapes -------------------------------------------------------------
    def escape(self, net: str, x: float, y_pad_edge: float, row: str) -> None:
        """Metal1 column from a device pad edge to ``net``'s Metal2 track."""
        y_track = self.plan.track_y(net, row)
        y0, y1 = min(y_pad_edge, y_track), max(y_pad_edge, y_track)
        half = ESCAPE_WIRE_W_UM / 2.0
        self.plan.reserve(net, x - half, y0, x + half, y1)
        prim.v_wire(self.canvas, x, y0, y1, width=ESCAPE_WIRE_W_UM)
        prim.via1_stack(self.canvas, x, y_track)
        self.net_x.setdefault((net, row), []).append(x)

    def jog_escape(self, net: str, pad: tuple, x_jog: float, row: str) -> None:
        """As ``escape()``, for a terminal whose pad faces the wrong way.

        Runs Metal1 sideways out of the pad first, at the pad's own height
        (so the joint is a full-width overlap, not a notch), then drops the
        column from there.
        """
        y_c = (pad[1] + pad[3]) / 2.0
        width = pad[3] - pad[1]
        half = ESCAPE_WIRE_W_UM / 2.0
        prim.h_wire(self.canvas, pad[0], x_jog + half, y_c, width=width)
        self.plan.reserve(net, min(pad[2], x_jog - half), pad[1], x_jog + half, pad[3])
        self.escape(net, x_jog, y_c, row)

    def rail_stub(self, net: str, x: float, y_from: float, y_to: float) -> None:
        """Plain Metal1 stub from a source pad to the block's own rail band."""
        y0, y1 = min(y_from, y_to), max(y_from, y_to)
        half = ESCAPE_WIRE_W_UM / 2.0
        self.plan.reserve(net, x - half, y0, x + half, y1)
        prim.v_wire(self.canvas, x, y0, y1, width=ESCAPE_WIRE_W_UM)

    # -- devices -------------------------------------------------------------
    def _y_bottom(self, row: str, l_um: float) -> float:
        if row == "pfet":
            return self.plan.pmos_top - device_height_um(l_um)
        return self.plan.y0

    def draw_fet(self, item: Item, row: str) -> None:
        fet = item.fet
        ports = prim.mosfet(
            self.canvas,
            fet,
            item.x0,
            self._y_bottom(row, fet.l_um),
            sd_overhang=SD_OVERHANG_UM,
        )
        x_pad_c = (ports.bottom_pad[0] + ports.bottom_pad[2]) / 2.0
        x_jog = item.x0 + item.width + JOG_ESCAPE_UM

        if row == "pfet":
            # source (top): to the n-well tap band if it is VDD, else jog out
            if fet.top_net == VDD_NET:
                self.rail_stub(VDD_NET, x_pad_c, ports.top_pad[3], self.plan.tap_band[1])
            else:
                self.jog_escape(fet.top_net, ports.top_pad, x_jog, row)
            self.escape(fet.bottom_net, x_pad_c, ports.bottom_pad[1], row)
            self.escape(fet.gate_net, ports.gate_tab_x_center, ports.gate_pad[1], row)
        else:
            if fet.bottom_net == GND_NET:
                self.rail_stub(GND_NET, x_pad_c, ports.bottom_pad[1], self.plan.gnd_tap_edge_y)
            else:
                self.jog_escape(fet.bottom_net, ports.bottom_pad, x_jog, row)
            self.escape(fet.top_net, x_pad_c, ports.top_pad[3], row)
            self.escape(fet.gate_net, ports.gate_tab_x_center, ports.gate_pad[3], row)

    def draw_cc_array(self, item: Item, row: str) -> None:
        """One cascade, interdigitated per ``devices.CascadePair.pattern``."""
        cascade = item.cascade
        legs = {"A": cascade.always_on, "S": cascade.switched}
        l_um = cascade.always_on.l_um
        y_bottom = self._y_bottom(row, l_um)
        y_lo, y_hi = gate_bus_y_um(l_um, y_bottom)
        bus_y = {"A": y_lo, "S": y_hi}

        finger_ports = []
        for x0, w, tag in zip(item.finger_x0, cascade.finger_widths(), cascade.pattern):
            finger_ports.append(
                (
                    tag,
                    prim.mosfet(
                        self.canvas, legs[tag], x0, y_bottom, w_um=w, sd_overhang=SD_OVERHANG_UM
                    ),
                )
            )

        # --- shared source and drain buses: one Metal1 rectangle each, drawn
        # at exactly the pads' own y so the merged polygon has no notch (the
        # same rule ring.py's rails follow). ---
        pads_lo = [p.bottom_pad for _, p in finger_ports]
        pads_hi = [p.top_pad for _, p in finger_ports]
        bus_x0 = min(p[0] for p in pads_lo)
        bus_x1 = max(p[2] for p in pads_lo)
        self.canvas.rect("metal1", bus_x0, pads_lo[0][1], bus_x1, pads_lo[0][3])
        self.canvas.rect("metal1", bus_x0, pads_hi[0][1], bus_x1, pads_hi[0][3])

        # --- two gate buses in the corridor, one per leg ---
        left_x = item.x0 - ARRAY_LEFT_ESCAPE_UM
        right_x = item.x0 + item.width + ARRAY_RIGHT_ESCAPE_UM
        bus_end = {"A": left_x, "S": right_x}
        for leg in ("A", "S"):
            tabs = [p.gate_tab_x_center for tag, p in finger_ports if tag == leg]
            y = bus_y[leg]
            prim.h_wire(
                self.canvas,
                min(tabs + [bus_end[leg]]) - prim.METAL1_WIRE_WIDTH_UM / 2.0,
                max(tabs + [bus_end[leg]]) + prim.METAL1_WIRE_WIDTH_UM / 2.0,
                y,
            )
            for tag, p in finger_ports:
                if tag != leg:
                    continue
                if y < p.gate_pad[1]:
                    prim.v_wire(self.canvas, p.gate_tab_x_center, y, p.gate_pad[1])
                else:
                    prim.v_wire(self.canvas, p.gate_tab_x_center, p.gate_pad[3], y)
            self.escape(legs[leg].gate_net, bus_end[leg], y, row)

        # --- source / drain escapes, placed in inter-finger gaps so they
        # never crowd a finger's own gate contact tab ---
        drain_x = finger_ports[0][1].x1 + CC_FINGER_GAP_UM / 3.0
        source_x = finger_ports[1][1].x1 + CC_FINGER_GAP_UM / 3.0
        if row == "pfet":
            self.escape(cascade.always_on.bottom_net, drain_x, pads_lo[0][1], row)
            self.rail_stub(VDD_NET, source_x, pads_hi[0][3], self.plan.tap_band[1])
        else:
            self.escape(cascade.always_on.top_net, drain_x, pads_hi[0][3], row)
            self.rail_stub(GND_NET, source_x, pads_lo[0][1], self.plan.gnd_tap_edge_y)

    # -- per-tier assembly -----------------------------------------------------
    def draw_devices(self) -> None:
        p = self.plan
        for item in p.pmos:
            (self.draw_cc_array if item.kind == "cc" else self.draw_fet)(item, "pfet")
        for item in p.nmos:
            (self.draw_cc_array if item.kind == "cc" else self.draw_fet)(item, "nfet")

    def draw_tracks(self) -> None:
        """This tier's own Metal2 tracks (one per (net, row) group it uses)
        plus its own intra-tier lo<->hi link columns (see ``NET_ORDER``'s
        comment) -- a net that also crosses tiers (``VBP2``) still gets its
        own local track here; ``build()`` extends it further, separately."""
        p = self.plan
        pad = ESCAPE_WIRE_W_UM / 2.0
        for net in p.net_order:
            for row in ("nfet", "pfet"):
                xs = self.net_x.get((net, row))
                if not xs:
                    continue
                x_link = p.link_x.get(net)
                x1 = max(xs + ([x_link] if x_link is not None else []))
                prim.m2_wire(self.canvas, min(xs) - pad, x1 + pad, p.track_y(net, row))
                self.track_x1[net] = max(self.track_x1.get(net, x1), x1)

        for net, x in p.link_x.items():
            y0, y1 = p.track_lo[net], p.track_hi[net]
            p.reserve(net, x - pad, y0, x + pad, y1)
            prim.v_wire(self.canvas, x, y0, y1, width=ESCAPE_WIRE_W_UM)
            prim.via1_stack(self.canvas, x, y0)
            prim.via1_stack(self.canvas, x, y1)

    def draw_nwell_tap(self) -> None:
        p = self.plan
        self.canvas.rect("nwell", *p.nwell)
        prim.tap_strip(self.canvas, "n", *p.tap_band, VDD_NET)

    def draw_all(self) -> None:
        self.draw_devices()
        self.draw_tracks()
        self.draw_nwell_tap()


def build(outdir: Path | None = None, canvas: prim.Canvas | None = None) -> MirrorResult:
    """``canvas`` draws into a caller-supplied canvas -- see ``ring.build()``."""
    mp = plan()
    canvas = prim.Canvas(TOP_CELL) if canvas is None else canvas

    b1 = _Builder(mp.tier1, canvas)
    b2 = _Builder(mp.tier2, canvas)
    b1.draw_all()
    b2.draw_all()

    # --- the mid GND_VCO tap: tier 2's own local substrate tie ---
    prim.tap_strip(canvas, "p", *mp.mid_gnd_tap, GND_NET)

    # --- the one cross-tier net: VBP2. Both tiers already drew their own
    # local (single-lane) VBP2 track; extend each to the shared riser column
    # -- pure Metal2, so it is free to cross tier 1's PMOS row, its own tap
    # band, and the mid GND tap without any DRC relationship to any of them
    # (see the module docstring). ---
    pad = ESCAPE_WIRE_W_UM / 2.0
    y1 = mp.tier1.track_lo["VBP2"]
    y2 = mp.tier2.track_hi["VBP2"]
    x1_end = b1.track_x1["VBP2"]
    x2_end = b2.track_x1["VBP2"]
    prim.m2_route(
        canvas,
        [(x1_end, y1), (mp.link_vbp2_x, y1), (mp.link_vbp2_x, y2), (x2_end, y2)],
    )

    # --- tie tier 1's own VDD_VCO n-well tap band to tier 2's, same "prove
    # it" rationale as the mid GND tap strap below. Also Metal2, and also a
    # dedicated column clear of every other one -- on the *left* rather than
    # the right, because a column reaching both tap bands necessarily spans
    # the same y range the VBP2 riser's own vertical run does, and two nets
    # cannot share a column. Via1 down to each tap band's own Metal1 pad,
    # a Metal2 jog (at the tap band's own y, well above either tier's own
    # channel, so it crosses no other Metal2 in either tier -- see the
    # module docstring), then the shared vertical run. ---
    v1x, v1y = (mp.tier1.tap_band[0] + mp.tier1.tap_band[2]) / 2.0, (
        mp.tier1.tap_band[1] + mp.tier1.tap_band[3]
    ) / 2.0
    v2x, v2y = (mp.tier2.tap_band[0] + mp.tier2.tap_band[2]) / 2.0, (
        mp.tier2.tap_band[1] + mp.tier2.tap_band[3]
    ) / 2.0
    prim.via1_stack(canvas, v1x, v1y)
    prim.via1_stack(canvas, v2x, v2y)
    prim.m2_route(
        canvas,
        [(v1x, v1y), (mp.link_vdd_x, v1y), (mp.link_vdd_x, v2y), (v2x, v2y)],
    )

    # --- the shared outer GND_VCO guard ring, around both tiers + the mid tap ---
    prim.guard_ring(canvas, "p", *mp.outer, RING_WIDTH_UM, GND_NET)

    # --- tie the mid tap's own Metal1 pad to the outer ring's left band.
    # DF.13_MV/DF.14_MV only needs the mid tap to be geometrically close (the
    # p-substrate itself carries GND_VCO with no metal at all), but this repo
    # proves connectivity rather than assuming it (see block.py's own
    # connectivity_report()) -- so the mid tap is also explicitly one metal
    # net with the rest of this block's own GND_VCO, not a second island that
    # happens to share a net name. ---
    prim.h_wire(canvas, mp.outer[0] + RING_WIDTH_UM, mp.mid_gnd_tap[0], (mp.mid_gnd_tap[1] + mp.mid_gnd_tap[3]) / 2.0)

    # --- block boundary pins ---
    def _leftmost(b: _Builder, net: str) -> tuple[float, float]:
        for row in ("nfet", "pfet"):
            xs = b.net_x.get((net, row))
            if xs:
                return (min(xs), b.plan.track_y(net, row))
        raise KeyError(net)

    for net in dev.MIRROR_IN_NETS:
        b = b1 if _IN_NET_TIER[net] == 1 else b2
        x, y = _leftmost(b, net)
        canvas.pin(net, x - pad - 0.6, y - pad, x - pad, y + pad, layer="metal2")
        prim.m2_wire(canvas, x - pad - 0.6, x, y)
    for net in dev.MIRROR_OUT_NETS:
        b = b1 if _OUT_NET_TIER[net] == 1 else b2
        y = b.plan.track_hi[net]
        x = b.track_x1[net] + pad
        canvas.pin(net, x, y - pad, x + 0.6, y + pad, layer="metal2")
        prim.m2_wire(canvas, x - pad, x + 0.6, y)

    net_x = {f"t1:{k[0]}:{k[1]}": v for k, v in b1.net_x.items()}
    net_x.update({f"t2:{k[0]}:{k[1]}": v for k, v in b2.net_x.items()})

    if outdir is not None:
        outdir = Path(outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        canvas.write_gds(outdir / f"{TOP_CELL}.gds")

    return MirrorResult(canvas=canvas, plan=mp, footprint=mp.outer, net_x=net_x)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--outdir",
        default=str(Path(__file__).resolve().parents[2] / "evidence" / "vco-layout" / "work"),
    )
    args = parser.parse_args()
    result = build(Path(args.outdir))
    x0, y0, x1, y1 = result.footprint
    print(f"wrote {args.outdir}/{TOP_CELL}.gds")
    print(f"footprint: {x1 - x0:.3f} x {y1 - y0:.3f} um  ({(x1 - x0) * (y1 - y0):.1f} um^2)")
    for c in dev.MIRROR_CASCADES:
        centre = array_width_um(c) / 2.0
        print(
            f"cascade {c.name}: width {array_width_um(c):.3f} um, centre {centre:.3f}, "
            f"A centroid {leg_centroid_um(c, 'A'):.3f}, S centroid {leg_centroid_um(c, 'S'):.3f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
