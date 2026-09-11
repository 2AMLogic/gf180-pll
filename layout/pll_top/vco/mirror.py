"""``vco_bias.sch``'s 3-cascade band-select mirror, laid out common-centroid.

WHY THIS BLOCK IS DRAWN SEPARATELY FROM THE REST OF ``vco_bias.sch``
--------------------------------------------------------------------
``vco_bias.sch`` contains two structurally different things: a V-to-I core
(``MP1``/``MP2``/``MN1``/``MN2``/``MSU*``/``MPR``/``MD1``/``MD2``/``MOFF``/
``MVI``/``MSUM``, plus **three ``ppolyf_u_3k`` poly resistors**
``RCG``/``ROFF``/``RDEG``) that turns ``VCTRL`` into the summing-node current
``VBP0``, and the band-select mirror that scales ``VBP0`` by the 3-bit band
code. This module draws the second. The first needs a poly-resistor generator
``primitives.py`` does not have (a different device class with its own
``PRES``/``sab`` rule set), which is its own increment of issue #293 — not
something to fake with a transistor.

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
visual inspection — a matching mistake here passes DRC clean and only
surfaces much later at extraction.

The patterns come from ``devices.py``. Each is a **grid** of rows
(bottom-to-top), each row itself left-to-right; a 1-row grid is a flat
array, exactly what every cascade drew before issue #336. Every grid is
symmetric under 180-degree rotation about its own centre, which is what
makes both legs' centroids coincide with the array centre in *x and y* even
though the two legs have different finger widths — see
``check_common_centroid()`` for the arithmetic:

===========  =============================  =====================
Cascade      Pattern (bottom → top row)      Netlist ``nf``
===========  =============================  =====================
A (pfet)     ``A S`` / ``S A`` (2x2)         2 / 2, folded (#336)
B (nfet)     ``A S S A`` (1x4)               1 / 1, **folded to 2**
C (pfet)     ``S S S`` / ``S A S`` / ``S S S`` (3x3)  1 / 8, folded (#336)
===========  =============================  =====================

Cascade B is the one place the drawn finger count deviates from the frozen
netlist's ``nf``: two single-finger devices cannot be interdigitated at all
(a one-finger leg's centroid *is* that finger's centre, which can never
coincide with a different one-finger leg's centre), so each leg is folded
into two fingers of exactly half its schematic ``W``. Total ``W``, ``L`` and
device count are preserved exactly; only ``nf`` differs. See
``devices.CASCADE_B``'s comment — this is recorded, not silent, because it is
a real layout-vs-schematic parameter difference the future LVS increment has
to reconcile.

WHY THE DEVICES ARE FOLDED INTO TWO BANKS, NOT ONE ROW
-------------------------------------------------------
Every device here is its own diffusion island wired by metal
(``primitives.py``'s convention), so a single PMOS row holding all eleven
pfets is 248 um wide -- wide enough that it, alone, set the *assembled*
VCO block's width (294.78 um) and its 2.6-4.0x overrun against
``PLL-FLOORPLAN.md`` section 5's ROM area row. Issue #324 folds it.

The fold is a **bank**, not a coordinate shift: a bank is one complete
NMOS-row / Metal2-channel / PMOS-row stack, exactly the structure this
module has always drawn, and ``BANKS`` below stacks two of them
vertically. Each bank carries its own n-well + ``VDD_VCO`` tap band above
its PMOS row; each bank above the first also carries its own ``GND_VCO``
substrate tap strip below its NMOS row (``sub_tap``), butted into the
block's own guard ring on the left so the strip is one continuous pcomp
shape with it rather than a separate island relying on substrate
conduction.

The split is by *cascade section*, chosen so that only two nets cross a
bank boundary at all:

===========  =====================================  ====================
Bank         PMOS row                               NMOS row
===========  =====================================  ====================
lower        band-code inverters, cascade A, its     ``MIN0``/``MDA``/
             mux, ``MDB``, cascade C's mux           cascade B/its mux/
                                                     ``MIN1``/``MIN2``
upper        cascade C, ``MDP``                      ``MDN``/``MMN``
===========  =====================================  ====================

``VBP2`` and ``GC`` are the only two nets escaped from both banks; every
other net is local to one. That matters because the mesh (see the next
section) is per bank -- each bank's channel carries only the tracks its
own two rows need -- and a net that spans banks costs one extra Metal1
link column in the right-hand strip, which is where the two tracks of a
both-rows net were already being joined before this fold.

ROUTING: WHY THIS BLOCK USES METAL2 AND ``ring.py`` DID NOT
-----------------------------------------------------------
An interdigitated array has to get four nets across the same span: the
shared source bus, the shared drain bus, and *two* gate buses (one per leg).
``primitives.mosfet()``'s S/D pads sit at the top and bottom of each finger,
so the source and drain buses consume both of those tracks, and the two gate
buses have to cross the array in the corridor between them. Widening the S/D
comp overhang (``primitives.mosfet(sd_overhang=...)``, added for exactly this)
opens that corridor — but the array's own drain/gate nets still have to reach
devices in the *other* transistor row, and every such net would then have to
cross every other one. That is not planar in a single metal. So this block
routes all 14 inter-device nets as Metal2 tracks in the channel between the
NMOS and PMOS rows, with Metal1 only for the short vertical escapes from each
device pad up/down to its track. ``ring.py``'s ring is a chain, not a mesh,
so it needed none of this.

Every Metal1 escape column is registered with ``_Plan.reserve()``, which
fails the build if two different nets' columns come within ``M1.2a``'s
0.23 µm — a spacing bug in a generated 200 µm-wide block is much cheaper to
catch as a Python exception than as one of several thousand DRC markers.
That check is *block-wide*, not per bank, so it also covers the one new class
of neighbour the fold introduces: a link column that now spans several banks'
worth of y.

TWO-DIMENSIONAL ARRAYS: FOLDING A CASCADE'S OWN ROW, NOT JUST THE BANK
------------------------------------------------------------------------
Issue #336 folds cascades A and C a second time, *inside* their own item:
each becomes an R x C grid of fingers (A: 2x2; C: 3x3) rather than one row,
which is the width lever a bank fold cannot reach once a cascade is already
alone in its own bank row (cascade C, 115.18 µm, was — see ``PROOF-fold.md``
and issue #336). ``col_widths_um()``/``col_box_x0_um()`` give every row the
same column layout (each column as wide as the widest finger *any* row
places there), so a finger's own centre always coincides with its column's
centre regardless of which leg occupies it — the fact
``check_common_centroid()`` needs for the x centroid, generalising the
single-row case's uniform finger pitch.

A single row's four nets (shared source bus, shared drain bus, two gate
buses) already use both the top/bottom S/D pad tracks and the corridor
between them (see ROUTING, above). An R-row grid has to answer the same
"how do N nets cross the same span without touching" question *again*, in
the other axis, to tie each row's own S/D and gate buses into one node per
net — and the module docstring's own channel is not available for it: that
Metal2 channel is per bank and sits *outside* the array (between the PMOS
and NMOS rows), where a multi-row PMOS (or NMOS) array's own internal rows
never reach.

``draw_cc_array()`` answers it with a *second*, purely local Metal2 hop,
confined to the array's own footprint and never touching the bank's own
channel tracks:

* **Gate buses** stay Metal1. Every row's own gate bus (per leg) already
  terminates at the same x — ``ARRAY_LEFT_ESCAPE_UM``/``ARRAY_RIGHT_ESCAPE_UM``
  past the array, outside every row's finger footprint, a lane nothing else
  ever draws into — so one Metal1 vertical spanning every row that owns that
  leg T-joins them into one node with no via at all, and the array's one
  escape point moves from that vertical instead of from a single row's bus.
* **S/D buses** cannot reuse that lane: unlike the gate buses, a row's S/D
  bus spans the row's own full width, so two rows' S/D pads only line up
  *inside* the array, in an inter-column gap (``col_box_x0_um()`` guarantees
  those gaps are finger-free in every row by construction). Tying them there
  needs a via1 up to Metal2, a short Metal2 vertical spanning the rows that
  need joining, and a via1 back down at each row — a self-contained hop that
  never leaves the array's own x-span, so it cannot collide with the bank's
  own channel tracks, which live in a completely different y band (between
  the rows, not inside one array's own footprint).

Every riser is registered with ``Plan.reserve(..., layer="metal2")`` — the
same spacing proof the module's Metal1 escape columns get, generalised to a
second layer that is never compared against the first (Metal1 and Metal2
shapes have no DRC spacing relationship absent a via1 joining them). DRC
alone cannot see whether a riser's via1 actually lands on its row's own pad
rather than stopping short of it — a Metal2 wire 0.01 µm short of its via1
is DRC-clean and completely disconnected — so ``connectivity_report()``
(below ``build()``) probes every row's own tie, not just the array's two end
rows, which is the property a weaker end-only probe set would silently miss
if an *interior* row's via broke.

WHY THE TWO BANKS' TRACK GROUPS CANNOT INTERACT
------------------------------------------------
The lo/hi split above is what keeps an NMOS escape column and a PMOS escape
column from ever overlapping in y *within* one bank. Across banks the same
guarantee comes for free from the geometry: bank ``k``'s NMOS row sits
physically **above** bank ``k-1``'s PMOS row (with that bank's n-well, its tap
band and the next bank's own substrate tap strip in between), so bank ``k``'s
upward escapes start above where bank ``k-1``'s downward escapes end.
``layout/tests/test_vco_layout.py`` asserts the ``max(lo) < min(hi)``
invariant bank by bank rather than globally -- globally it is false by
construction once the rows are folded, and asserting it globally would be
asserting the single-row layout.

Standalone-DRC scope: like ``ring.py``'s and ``buffer.py``'s blocks, this one
draws its own dedicated guard ring (outer substrate ``p`` ring tied
``GND_VCO``; an n-well tap band tied ``VDD_VCO``) so it is provable on its
own. ``VBP0``/``B0``/``B1``/``B2`` are input pins and ``VBP``/``VBN`` output
pins at the block boundary — ``VBP``/``VBN`` are exactly the nets
``ring.py``'s block already exposes as Metal1 pins, which is what let
``block.py``'s integration increment route to them rather than re-derive
them. ``block.py`` reaches every one of these pins by *extending that pin's
own Metal2 track* in its own direction, so nothing it adds changes this
block's internal spacing relationships -- see that module's docstring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import devices as dev
from . import primitives as prim
from ._escape_builder import EscapeBuilderMixin

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
CC_ROW_GAP_UM = 0.4
"""Comp-to-comp gap between two stacked rows of a 2-D common-centroid array
(issue #336's fold of cascade C -- see ``draw_cc_array()``).

The binding rule is ``DF.3a_LV``'s 0.28 um comp-to-comp minimum: the two rows
are the same fet kind, so their pplus/nplus implants may legally touch or
overlap (no ``PP.2``/``NP.2`` cross-polarity spacing applies between same-type
implants), and the two rows' facing Metal1 pads are two *different* nets
(one row's ``top_net``, the next row's ``bottom_net``) needing ``M1.2a``'s
0.23 um clear once each pad's own margin overshoot past its comp edge
(``METAL1_PAD_MARGIN_UM`` net of ``CONTACT_ROW_MARGIN_UM``, 0.02 um) is
subtracted -- 0.27 um. 0.4 um clears both with real margin (43% over the
tighter, DF.3a_LV, bound) while staying deliberately tight: unlike this
module's other gaps, every um here is spent twice (once per row boundary a
2-D array needs), directly against issue #336's own area-saving goal, and
this module's ``M1.2a``-adjacent margins have never sat exactly on the DRC
boundary but have also never needed to spend far past it -- see
``SD_OVERHANG_UM``'s own comment for that convention.
"""
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

# --- inter-bank geometry (um), see the module docstring's fold section ------
SUB_TAP_WIDTH_UM = 0.6
"""``GND_VCO`` substrate tap strip drawn under every bank above the first.

Bank 0's NMOS sources tie into the block's own outer guard ring, whose
bottom band is directly below them; a higher bank has no such band within
reach, so it gets its own strip. The strip is butted into the ring's left
band (see ``plan()``), i.e. it is drawn as one continuous pcomp shape with
the ring rather than as an island tied only through the substrate -- which
also means the metal-connectivity extraction sees one ``GND_VCO`` net, not
two.
"""

BANK_NWELL_TO_TAP_UM = 1.5
"""Bank ``k-1``'s n-well top edge -> bank ``k``'s substrate tap comp.

``DF.16_LV``'s own minimum is 0.43 um; 1.5 um also keeps the tap's own
pplus (``primitives.IMPLANT_MARGIN_UM`` = 0.3 um beyond its comp) 1.2 um
clear of the n-well, matching the clearance this block's outer p-ring
already keeps from the same n-well in the single-row layout that DRC-proved
clean.
"""

BANK_TAP_TO_NMOS_UM = 1.0
"""Substrate tap comp -> the NMOS row's own comp, inside one bank.

``DF.3a_LV``'s comp-to-comp minimum is 0.28 um. 1.0 um is used instead so
the two islands' *implants* also clear each other by 0.4 um (each extends
``IMPLANT_MARGIN_UM`` = 0.3 um past its comp), i.e. ``PP.2``/``NP.2``'s own
0.4 um same-layer spacing is met with no reliance on nplus and pplus being
different layers.
"""
OUTER_MARGIN_LEFT_UM = 3.0
OUTER_MARGIN_RIGHT_UM = 3.0
OUTER_MARGIN_BELOW_UM = 2.5
OUTER_MARGIN_ABOVE_UM = 2.5

# Inter-device net order, used for track assignment. Ordering is arbitrary for
# DRC (two tracks never touch) and chosen here to read in signal order: band
# code first, then the cascade chain.
#
# THE CHANNEL IS SPLIT INTO TWO TRACK GROUPS, AND THAT IS LOad-BEARING.
# A Metal1 escape column from the NMOS row runs *upward* from a device pad to
# its track; one from the PMOS row runs *downward*. If both groups' tracks
# were interleaved, an NMOS column reaching a high track and a PMOS column
# reaching a low track would overlap in y -- and if their x happened to
# coincide (which it did, on the first build of this generator: MDN's drain
# pad landed on MSWA0's gate tab), that is a hard M1.2a short between two
# different nets. So every net that needs escapes in *both* rows gets two
# tracks: a "lo" one in the lower group, reachable only from the NMOS row,
# and a "hi" one in the upper group, reachable only from the PMOS row. By
# construction every NMOS column ends below every PMOS column starts, so the
# two rows' columns can never interact whatever their x.
#
# The two tracks of such a net are tied together by one Metal1 "link" column
# in a dedicated strip to the right of both rows (``LINK_MARGIN_UM`` past the
# rows' right edge), where no device escape exists -- the one place a
# lo-to-hi column is safe.
NET_ORDER = (
    "B0",
    "B0B",
    "B1",
    "B1B",
    "B2",
    "B2B",
    "VBP0",
    "GA",
    "VBN1",
    "GB",
    "VBP2",
    "GC",
    "VBN",
    "VBP",
)


@dataclass(frozen=True)
class Bank:
    """One NMOS-row / Metal2-channel / PMOS-row stack, left to right.

    Names index ``devices.py``'s own tables (``CASCADES`` for the three
    common-centroid arrays, ``DEVICES`` for everything else).
    """

    name: str
    pmos: tuple[str, ...]
    nmos: tuple[str, ...]


# The fold (issue #324). Split by cascade section, which is what keeps the
# cross-bank net count at two (``VBP2`` and ``GC``) -- see the module
# docstring. Cascade C is 115.18 um wide on its own and is the reason the
# upper bank holds only it and the output mirror's ``MDP``: it, not the
# device count, is what sets each bank's width.
BANKS = (
    Bank(
        name="lower",
        pmos=("MIP0", "A", "MSWA0", "MSWA1", "MIP1", "MDB", "MIP2", "MSWC0", "MSWC1"),
        nmos=("MIN0", "MDA", "B", "MSWB0", "MSWB1", "MIN1", "MIN2"),
    ),
    Bank(
        name="upper",
        pmos=("C", "MDP"),
        nmos=("MDN", "MMN"),
    ),
)

# Every device, in bank-then-row order -- the flat view the pre-fold layout
# drew as one row each, kept so a reader can check no device was dropped.
PMOS_ROW = tuple(name for b in BANKS for name in b.pmos)
NMOS_ROW = tuple(name for b in BANKS for name in b.nmos)


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


def col_widths_um(cascade: dev.CascadePair) -> tuple[float, ...]:
    """Per-column width: the widest finger *any row* of the grid places there.

    Not the array's global widest finger -- a column pays uniform-pitch slack
    only against the fingers that actually land in it. Cascade C's outer
    columns hold only ``MC1`` fingers (9.85 um) in every row, so only its
    centre column (which also holds ``MC0``'s single 12.3 um finger) pays the
    slack; see ``mirror.py``'s module docstring. For a single-row cascade (A,
    B) every column has exactly one occupant, so this is exactly that
    finger's own width -- no behaviour change from the pre-#336 flat layout.
    """
    grid = cascade.finger_widths()
    cols = len(grid[0])
    return tuple(max(row[c] for row in grid) for c in range(cols))


def col_box_x0_um(cascade: dev.CascadePair, x0: float = 0.0) -> tuple[float, ...]:
    """Left edge of each column's own *box* (``col_widths_um()`` wide), from ``x0``.

    Not any particular row's own (possibly slack-centred) finger edge -- see
    ``finger_x0_um()``, which centres a narrower occupant inside this same
    box. Column boxes are identical for every row by construction, which is
    what ``draw_cc_array()``'s S/D risers rely on: the inter-column *gap*
    ``col_box_x0_um()[c] + col_widths_um()[c]`` to ``col_box_x0_um()[c+1]``
    is empty of any finger in every row, regardless of which row's occupant
    is narrower than its column.
    """
    colw = col_widths_um(cascade)
    xs = []
    x = x0
    for w in colw:
        xs.append(x)
        x += w + CC_FINGER_GAP_UM
    return tuple(xs)


def finger_x0_um(cascade: dev.CascadePair, x0: float = 0.0) -> tuple[tuple[float, ...], ...]:
    """Left comp edge of each drawn finger, as an (row, col) grid from ``x0``.

    Every finger is centred in its own column's box, which is why a finger's
    own centre coincides with its column's centre regardless of which leg (and
    so which width) occupies it -- the arithmetic fact
    ``check_common_centroid()`` relies on for the x centroid.
    """
    colw = col_widths_um(cascade)
    col_x0 = col_box_x0_um(cascade, x0)
    widths = cascade.finger_widths()
    return tuple(
        tuple(col_x0[c] + (colw[c] - widths[r][c]) / 2.0 for c in range(len(colw)))
        for r in range(len(cascade.pattern))
    )


def array_width_um(cascade: dev.CascadePair) -> float:
    colw = col_widths_um(cascade)
    return sum(colw) + (len(colw) - 1) * CC_FINGER_GAP_UM


def array_height_um(cascade: dev.CascadePair) -> float:
    """Total drawn height of the array, rows plus their inter-row gaps.

    Every row is the same device -- ``check_common_centroid()`` requires
    ``always_on.l_um == switched.l_um`` precisely so one ``device_height_um()``
    covers every row -- so a single-row cascade's height is exactly
    ``device_height_um(l_um)``, unchanged from the pre-#336 layout.
    """
    rows = len(cascade.pattern)
    row_h = device_height_um(cascade.always_on.l_um)
    return rows * row_h + (rows - 1) * CC_ROW_GAP_UM


def row_y0_um(cascade: dev.CascadePair, y0: float = 0.0) -> tuple[float, ...]:
    """Bottom-edge y of each row, row 0 = bottom-most, from ``y0``."""
    row_h = device_height_um(cascade.always_on.l_um)
    return tuple(y0 + r * (row_h + CC_ROW_GAP_UM) for r in range(len(cascade.pattern)))


def leg_centroid_um(
    cascade: dev.CascadePair, leg: str, x0: float = 0.0, y0: float = 0.0
) -> tuple[float, float]:
    """(x, y) centroid (area-weighted finger centre) of one leg's fingers.

    Area-weighted and plain-mean coincide here because every finger of a
    given leg has the same width -- the weighting is written out anyway so
    the function stays correct if a leg ever gets unequal fingers.
    """
    xs = finger_x0_um(cascade, x0)
    ys = row_y0_um(cascade, y0)
    widths = cascade.finger_widths()
    row_h = device_height_um(cascade.always_on.l_um)
    sx = sy = total_w = 0.0
    for r, row in enumerate(cascade.pattern):
        for c, tag in enumerate(row):
            if tag != leg:
                continue
            w = widths[r][c]
            sx += (xs[r][c] + w / 2.0) * w
            sy += (ys[r] + row_h / 2.0) * w
            total_w += w
    return (sx / total_w, sy / total_w)


def check_common_centroid(cascade: dev.CascadePair, tol_um: float = 1e-9) -> None:
    """Raise unless both legs' centroids coincide with the array's centre.

    This is the acceptance criterion "band-select mirror cascades laid out
    common-centroid (always-on leg interdigitated with switched leg per
    cascade), not row-placed" reduced to something a build can fail on --
    generalised (issue #336) to a 2-D R x C grid, both x *and* y. A 1-row
    grid (cascades A, B) is the special case this generalises from, and every
    check below reduces to exactly what it checked before #336 when
    ``len(cascade.pattern) == 1``.
    """
    grid = cascade.pattern
    if not grid or any(len(row) == 0 for row in grid):
        raise ValueError(f"cascade {cascade.name}: empty pattern grid")
    cols = len(grid[0])
    if any(len(row) != cols for row in grid):
        raise ValueError(f"cascade {cascade.name}: pattern rows have different column counts")
    if cascade.always_on.l_um != cascade.switched.l_um:
        raise ValueError(f"cascade {cascade.name}: legs have different L; row height is undefined")

    # The grid must be symmetric under 180-degree rotation about its own
    # centre: pattern[r][c] == pattern[R-1-r][C-1-c] for every cell. For a
    # 1-row grid this is exactly the old flat-palindrome check
    # (pattern[0][c] == pattern[0][C-1-c]); a 1-column-pair grid like cascade
    # A's proposed 2x2 fold ("A S" over "S A") satisfies this rotation
    # symmetry despite *neither individual row* being a palindrome, which is
    # why rotation symmetry -- not "every row and the row order are each
    # separately a palindrome" -- is the right general condition here.
    #
    # It is also what makes both legs' centroids coincide with the array
    # centre in x *and* y: a column's occupant multiset (over every row) is
    # provably identical to its mirror column's occupant multiset under this
    # symmetry (substitute the relation with r' = R-1-r), so column c and
    # column C-1-c always get the same width (see col_widths_um()) and every
    # leg's per-column and per-row weight distribution is symmetric about the
    # centre regardless of how the legs are actually arranged inside that
    # symmetry.
    rows_n = len(grid)
    for r in range(rows_n):
        for c in range(cols):
            if grid[r][c] != grid[rows_n - 1 - r][cols - 1 - c]:
                raise ValueError(
                    f"cascade {cascade.name}: pattern {grid} is not symmetric under "
                    f"180-degree rotation -- cell ({r},{c})={grid[r][c]!r} != "
                    f"cell ({rows_n - 1 - r},{cols - 1 - c})={grid[rows_n - 1 - r][cols - 1 - c]!r}"
                )

    flat = [tag for row in grid for tag in row]
    if flat.count("A") != cascade.always_on.fingers:
        raise ValueError(f"cascade {cascade.name}: pattern has the wrong always-on finger count")
    if flat.count("S") != cascade.switched.fingers:
        raise ValueError(f"cascade {cascade.name}: pattern has the wrong switched finger count")

    centre_x = array_width_um(cascade) / 2.0
    centre_y = array_height_um(cascade) / 2.0
    for leg in ("A", "S"):
        cx, cy = leg_centroid_um(cascade, leg)
        if abs(cx - centre_x) > tol_um or abs(cy - centre_y) > tol_um:
            raise ValueError(
                f"cascade {cascade.name}: leg {leg} centroid ({cx:.6f}, {cy:.6f}) um != "
                f"array centre ({centre_x:.6f}, {centre_y:.6f}) um"
            )

    # Interdigitation, not two blobs: a "row-placed" pair is exactly two
    # maximal runs (all of one leg, then all of the other) in the row-major
    # flattening. Any genuinely interleaved pattern -- ABBA, SSSSASSSS, or
    # cascade C's SSS/SAS/SSS grid flattened to SSSSASSSS -- has three or
    # more.
    runs = 1 + sum(1 for a, b in zip(flat, flat[1:]) if a != b)
    if runs < 3:
        raise ValueError(f"cascade {cascade.name}: pattern {grid} is row-placed ({runs} runs), not interdigitated")


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
class BankPlan:
    """One bank's own geometry: two device rows and the channel between them."""

    index: int = 0
    name: str = ""
    pmos: list[Item] = field(default_factory=list)
    nmos: list[Item] = field(default_factory=list)
    net_rows: dict[str, set] = field(default_factory=dict)
    track_lo: dict[str, float] = field(default_factory=dict)
    track_hi: dict[str, float] = field(default_factory=dict)
    channel: tuple[float, float] = (0.0, 0.0)
    nmos_bottom: float = 0.0
    nmos_top: float = 0.0
    pmos_bottom: float = 0.0
    pmos_top: float = 0.0
    nwell: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    tap_band: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    sub_tap: tuple[float, float, float, float] | None = None
    """``GND_VCO`` substrate tap strip below this bank's NMOS row.

    ``None`` for bank 0 only: the block's own outer guard ring's bottom band
    already sits directly below that bank's NMOS row and serves the same
    purpose.
    """

    def track_y(self, net: str, row: str) -> float:
        """The Metal2 track ``row``'s Metal1 escape columns may land ``net`` on."""
        return self.track_lo[net] if row == "nfet" else self.track_hi[net]

    def items(self) -> list[Item]:
        return self.pmos + self.nmos

    def row_x1(self) -> float:
        return max(it.x0 + it.width for it in self.items())

    def gnd_stub_y(self, outer: tuple) -> float:
        """Where an NMOS source stub in this bank lands on ``GND_VCO`` metal."""
        if self.sub_tap is None:
            return outer[1] + RING_WIDTH_UM + prim.METAL1_PAD_MARGIN_UM
        return self.sub_tap[3] + prim.METAL1_PAD_MARGIN_UM


@dataclass
class Plan:
    banks: list[BankPlan] = field(default_factory=list)
    net_rows: dict[str, set] = field(default_factory=dict)
    net_groups: dict[str, set] = field(default_factory=dict)
    link_x: dict[str, float] = field(default_factory=dict)
    outer: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    _columns: list = field(default_factory=list)

    # Flat views, so a caller that only wants "every drawn device" does not
    # have to know the fold exists.
    @property
    def pmos(self) -> list[Item]:
        return [it for b in self.banks for it in b.pmos]

    @property
    def nmos(self) -> list[Item]:
        return [it for b in self.banks for it in b.nmos]

    # -- escape-column bookkeeping (see the module docstring) --
    def reserve(
        self, net: str, x0: float, y0: float, x1: float, y1: float, *, layer: str = "metal1"
    ) -> None:
        """Prove ``net``'s column clears every other net's column on ``layer``.

        Metal1 by default (every device escape and gate/S-D bus tie); the
        2-D common-centroid array's inter-row S/D risers (issue #336) reserve
        on ``"metal2"`` instead, at ``M2.2a``'s wider minimum -- the two
        layers are never compared against each other, matching the physical
        reality that Metal1 and Metal2 shapes do not interact absent a via1.
        """
        s = dev.DRC_METAL1_MIN_SPACE_UM if layer == "metal1" else dev.DRC_METAL2_MIN_SPACE_UM
        for other_layer, other_net, ox0, oy0, ox1, oy1 in self._columns:
            if other_layer != layer or other_net == net:
                continue
            if x0 - s < ox1 and ox0 < x1 + s and y0 - s < oy1 and oy0 < y1 + s:
                raise ValueError(
                    f"{layer} escape columns for {net!r} and {other_net!r} are closer than "
                    f"{s} um: ({x0:.3f},{y0:.3f})-({x1:.3f},{y1:.3f}) vs "
                    f"({ox0:.3f},{oy0:.3f})-({ox1:.3f},{oy1:.3f})"
                )
        self._columns.append((layer, net, x0, y0, x1, y1))


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


def item_height_um(item: Item) -> float:
    """How tall a plan ``Item`` draws: one row for a plain fet, R rows (plus
    their inter-row gaps) for a common-centroid array -- see
    ``array_height_um()``."""
    return device_height_um(item.fet.l_um) if item.kind == "fet" else array_height_um(item.cascade)


def _row_height_um(items: list[Item]) -> float:
    return max(item_height_um(it) for it in items)


def plan() -> Plan:
    for cascade in dev.MIRROR_CASCADES:
        check_common_centroid(cascade)

    p = Plan()
    m = prim.NWELL_MARGIN_UM

    y_floor = 0.0  # bank 0's NMOS row bottom; every later bank stacks above
    for index, bank in enumerate(BANKS):
        bp = BankPlan(index=index, name=bank.name)
        bp.pmos = _row_items(bank.pmos)
        bp.nmos = _row_items(bank.nmos)
        bp.net_rows = _net_rows(bp.pmos, bp.nmos)

        missing = set(bp.net_rows) - set(NET_ORDER)
        if missing:
            raise ValueError(f"nets with no track assignment: {sorted(missing)}")

        if index == 0:
            bp.nmos_bottom = 0.0
        else:
            prev = p.banks[-1]
            tap_y0 = dev.snap_um(prev.nwell[3] + BANK_NWELL_TO_TAP_UM)
            # x0 is patched below, once the outer ring's own box is known --
            # the strip is butted into that ring's left band on purpose.
            bp.sub_tap = (0.0, tap_y0, bp.row_x1(), tap_y0 + SUB_TAP_WIDTH_UM)
            bp.nmos_bottom = dev.snap_um(bp.sub_tap[3] + BANK_TAP_TO_NMOS_UM)
        bp.nmos_top = bp.nmos_bottom + _row_height_um(bp.nmos)

        # --- lower track group (NMOS-row escapes), then upper (PMOS-row) ---
        lo_nets = [n for n in NET_ORDER if "nfet" in bp.net_rows.get(n, ())]
        hi_nets = [n for n in NET_ORDER if "pfet" in bp.net_rows.get(n, ())]
        ch_y0 = bp.nmos_top + CHANNEL_MARGIN_UM
        for i, net in enumerate(lo_nets):
            bp.track_lo[net] = ch_y0 + TRACK_PITCH_UM / 2.0 + i * TRACK_PITCH_UM
        base_hi = ch_y0 + len(lo_nets) * TRACK_PITCH_UM
        for j, net in enumerate(hi_nets):
            bp.track_hi[net] = base_hi + TRACK_PITCH_UM / 2.0 + j * TRACK_PITCH_UM
        ch_y1 = base_hi + len(hi_nets) * TRACK_PITCH_UM
        bp.channel = (ch_y0, ch_y1)
        # A net escaped from only one row of this bank still needs a value for
        # the other, so escape() can be row-agnostic; with no column ever
        # reaching it, aliasing is harmless.
        for net in bp.net_rows:
            if net not in bp.track_lo:
                bp.track_lo[net] = bp.track_hi[net]
            elif net not in bp.track_hi:
                bp.track_hi[net] = bp.track_lo[net]

        bp.pmos_bottom = ch_y1 + CHANNEL_MARGIN_UM
        bp.pmos_top = bp.pmos_bottom + _row_height_um(bp.pmos)

        pmos_x0 = bp.pmos[0].x0
        pmos_x1 = bp.pmos[-1].x0 + bp.pmos[-1].width
        bp.tap_band = (
            pmos_x0,
            bp.pmos_top + TAP_GAP_UM,
            pmos_x1,
            bp.pmos_top + TAP_GAP_UM + TAP_BAND_WIDTH_UM,
        )
        bp.nwell = (pmos_x0 - m, bp.pmos_bottom - m, pmos_x1 + m, bp.tap_band[3] + m)

        p.banks.append(bp)
        y_floor = bp.nwell[3]

    # --- block-wide net bookkeeping -----------------------------------------
    for bp in p.banks:
        for net, rows in bp.net_rows.items():
            p.net_rows.setdefault(net, set()).update(rows)
            for row in rows:
                p.net_groups.setdefault(net, set()).add((bp.index, row))

    # --- link columns, right of every bank's rows ---------------------------
    # A net escaped from more than one (bank, row) group needs exactly one
    # Metal1 column joining all of its tracks. Pre-fold that meant "a net in
    # both rows"; folded, it also means "a net in more than one bank".
    rows_right = (
        max(bp.row_x1() for bp in p.banks)
        + ARRAY_RIGHT_ESCAPE_UM
        + max(JOG_ESCAPE_UM, ARRAY_RIGHT_ESCAPE_UM)
        + ESCAPE_WIRE_W_UM / 2.0
    )
    link_nets = [n for n in NET_ORDER if len(p.net_groups.get(n, ())) > 1]
    for k, net in enumerate(link_nets):
        p.link_x[net] = rows_right + LINK_MARGIN_UM + k * LINK_PITCH_UM

    # Leftmost Metal1 anywhere: a gate contact tab's own pad, or (for a row
    # that starts with an array) that array's always-on gate escape column.
    tab_dx = prim.POLY_ENDCAP_UM - prim.GATE_TAB_OVERLAP_UM + prim.GATE_TAB_W_UM + prim.METAL1_PAD_MARGIN_UM
    left_metal = -tab_dx
    for bp in p.banks:
        for items in (bp.pmos, bp.nmos):
            if items and items[0].kind == "cc":
                left_metal = min(
                    left_metal, items[0].x0 - ARRAY_LEFT_ESCAPE_UM - ESCAPE_WIRE_W_UM / 2.0
                )
    right_metal = max([rows_right] + [x + ESCAPE_WIRE_W_UM / 2.0 for x in p.link_x.values()])
    gnd_pad_y0 = prim.CONTACT_ROW_MARGIN_UM - prim.METAL1_PAD_MARGIN_UM

    p.outer = (
        min(min(bp.nwell[0] for bp in p.banks), left_metal) - OUTER_MARGIN_LEFT_UM,
        gnd_pad_y0 - OUTER_MARGIN_BELOW_UM - RING_WIDTH_UM,
        max(max(bp.nwell[2] for bp in p.banks), right_metal) + OUTER_MARGIN_RIGHT_UM,
        y_floor + OUTER_MARGIN_ABOVE_UM,
    )

    # Butt every substrate tap strip into the outer ring's left band, so the
    # two are one continuous pcomp shape (and one extracted GND_VCO net)
    # rather than an island relying on substrate conduction alone.
    for bp in p.banks:
        if bp.sub_tap is not None:
            bp.sub_tap = (p.outer[0] + RING_WIDTH_UM, bp.sub_tap[1], bp.sub_tap[2], bp.sub_tap[3])
    return p


def footprint_um() -> tuple:
    return plan().outer


def max_pmos_tap_distance_um() -> float:
    """Worst-case pfet-to-nearest-n-well-tap distance (DF.13_MV/DF.14_MV).

    Each bank carries its own tap band along the full length of its PMOS
    row's top edge, so the worst case is a device's own bottom (drain) edge,
    taken over every bank.
    """
    p = plan()
    return max((bp.pmos_top - bp.pmos_bottom) + TAP_GAP_UM for bp in p.banks)


def max_nmos_tap_distance_um() -> float:
    """Worst-case nfet-to-nearest-substrate-tap, over every bank.

    Bank 0 ties to the outer p-ring's bottom band; every bank above it ties
    to its own ``sub_tap`` strip, which sits directly below its NMOS row --
    so folding the rows does not lengthen this distance, it shortens it.
    """
    p = plan()
    worst = 0.0
    for bp in p.banks:
        near = p.outer[1] + RING_WIDTH_UM if bp.sub_tap is None else bp.sub_tap[3]
        worst = max(worst, bp.nmos_top - near)
    return worst


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------


@dataclass
class MirrorResult:
    canvas: prim.Canvas
    plan: Plan
    footprint: tuple = (0.0, 0.0, 0.0, 0.0)
    net_x: dict = field(default_factory=dict)


class _Builder(EscapeBuilderMixin):
    def __init__(self, canvas: prim.Canvas | None = None) -> None:
        self.plan = plan()
        self.canvas = prim.Canvas(TOP_CELL) if canvas is None else canvas
        self.net_x: dict[tuple[str, int, str], list[float]] = {}
        self.escape_wire_w_um = ESCAPE_WIRE_W_UM

    # -- escape()/jog_escape()/rail_stub()/_y_bottom() are inherited from
    # EscapeBuilderMixin (factored out to _escape_builder.py; identical to
    # what this class used to define directly) -- each call below passes the
    # ``BankPlan`` selecting which bank's own channel/rows a column reaches.

    # -- devices -------------------------------------------------------------
    def draw_fet(self, item: Item, row: str, bank: BankPlan) -> None:
        fet = item.fet
        ports = prim.mosfet(
            self.canvas,
            fet,
            item.x0,
            self._y_bottom(row, device_height_um(fet.l_um), bank),
            sd_overhang=SD_OVERHANG_UM,
        )
        x_pad_c = (ports.bottom_pad[0] + ports.bottom_pad[2]) / 2.0
        x_jog = item.x0 + item.width + JOG_ESCAPE_UM

        if row == "pfet":
            # source (top): to the n-well tap band if it is VDD, else jog out
            if fet.top_net == VDD_NET:
                self.rail_stub(VDD_NET, x_pad_c, ports.top_pad[3], bank.tap_band[1])
            else:
                self.jog_escape(fet.top_net, ports.top_pad, x_jog, row, bank)
            self.escape(fet.bottom_net, x_pad_c, ports.bottom_pad[1], row, bank)
            self.escape(fet.gate_net, ports.gate_tab_x_center, ports.gate_pad[1], row, bank)
        else:
            if fet.bottom_net == GND_NET:
                self.rail_stub(
                    GND_NET, x_pad_c, ports.bottom_pad[1], bank.gnd_stub_y(self.plan.outer)
                )
            else:
                self.jog_escape(fet.bottom_net, ports.bottom_pad, x_jog, row, bank)
            self.escape(fet.top_net, x_pad_c, ports.top_pad[3], row, bank)
            self.escape(fet.gate_net, ports.gate_tab_x_center, ports.gate_pad[3], row, bank)

    def draw_cc_array(self, item: Item, row: str, bank: BankPlan) -> None:
        """One cascade, interdigitated per ``devices.CascadePair.pattern``.

        Handles both a 1-row array (cascades A, B -- byte-for-byte what this
        method drew before issue #336, see the R == 1 branches below) and an
        R-row grid (cascade C's 3x3 fold). A grid needs each row's own S/D
        buses and gate buses tied to the *other* rows' -- see the module
        docstring's "TWO-DIMENSIONAL ARRAYS" section for why that is a Metal2
        hop for the S/D buses but plain Metal1 for the gate buses.
        """
        cascade = item.cascade
        legs = {"A": cascade.always_on, "S": cascade.switched}
        l_um = cascade.always_on.l_um
        grid = cascade.pattern
        rows = len(grid)
        row_h = device_height_um(l_um)
        y_item_bottom = self._y_bottom(row, item_height_um(item), bank)
        row_y0 = [dev.snap_um(y_item_bottom + r * (row_h + CC_ROW_GAP_UM)) for r in range(rows)]

        # --- draw every row's fingers ---
        rows_ports: list[list[tuple[str, prim.MosfetPorts]]] = []
        for r, tags in enumerate(grid):
            xs = item.finger_x0[r]
            widths = cascade.finger_widths()[r]
            rows_ports.append(
                [
                    (
                        tag,
                        prim.mosfet(
                            self.canvas, legs[tag], x0, row_y0[r], w_um=w, sd_overhang=SD_OVERHANG_UM
                        ),
                    )
                    for x0, w, tag in zip(xs, widths, tags)
                ]
            )

        # --- per-row shared source and drain buses: one Metal1 rectangle
        # each, drawn at exactly the pads' own y so the merged polygon has no
        # notch (the same rule ring.py's rails follow). For R == 1 this is
        # exactly the pre-#336 single bus pair. ---
        row_bus_lo: list[tuple[float, float, float, float]] = []
        row_bus_hi: list[tuple[float, float, float, float]] = []
        for ports in rows_ports:
            pads_lo = [p.bottom_pad for _, p in ports]
            pads_hi = [p.top_pad for _, p in ports]
            bus_x0 = min(p[0] for p in pads_lo)
            bus_x1 = max(p[2] for p in pads_lo)
            b_lo = (bus_x0, pads_lo[0][1], bus_x1, pads_lo[0][3])
            b_hi = (bus_x0, pads_hi[0][1], bus_x1, pads_hi[0][3])
            self.canvas.rect("metal1", *b_lo)
            self.canvas.rect("metal1", *b_hi)
            row_bus_lo.append(b_lo)
            row_bus_hi.append(b_hi)

        # --- two gate buses per row, one per leg that row actually has a
        # finger of (cascade C's centre leg, "A", exists in only one row) ---
        left_x = item.x0 - ARRAY_LEFT_ESCAPE_UM
        right_x = item.x0 + item.width + ARRAY_RIGHT_ESCAPE_UM
        bus_end = {"A": left_x, "S": right_x}
        row_gate_y: list[dict[str, float]] = [dict() for _ in range(rows)]
        for r, ports in enumerate(rows_ports):
            y_lo, y_hi = gate_bus_y_um(l_um, row_y0[r])
            by = {"A": y_lo, "S": y_hi}
            for leg in ("A", "S"):
                tabs = [p.gate_tab_x_center for tag, p in ports if tag == leg]
                if not tabs:
                    continue
                y = by[leg]
                row_gate_y[r][leg] = y
                prim.h_wire(
                    self.canvas,
                    min(tabs + [bus_end[leg]]) - prim.METAL1_WIRE_WIDTH_UM / 2.0,
                    max(tabs + [bus_end[leg]]) + prim.METAL1_WIRE_WIDTH_UM / 2.0,
                    y,
                )
                for tag, p in ports:
                    if tag != leg:
                        continue
                    if y < p.gate_pad[1]:
                        prim.v_wire(self.canvas, p.gate_tab_x_center, y, p.gate_pad[1])
                    else:
                        prim.v_wire(self.canvas, p.gate_tab_x_center, p.gate_pad[3], y)

        # --- tie each leg's per-row gate buses together and escape the tied
        # node once. Every row's own gate bus already terminates exactly at
        # ``bus_end[leg]`` -- outside the array's finger footprint, in a lane
        # nothing else ever draws into -- so a single Metal1 vertical there,
        # spanning every row that owns this leg, T-joins into one continuous
        # net with no via1 needed. A leg confined to one row (cascade C's "A")
        # makes this a no-op and reduces to the pre-#336 single escape. ---
        for leg in ("A", "S"):
            rows_with_leg = [r for r in range(rows) if leg in row_gate_y[r]]
            if not rows_with_leg:
                continue
            x = bus_end[leg]
            ys = [row_gate_y[r][leg] for r in rows_with_leg]
            if len(ys) > 1:
                y0, y1 = min(ys), max(ys)
                half = ESCAPE_WIRE_W_UM / 2.0
                self.plan.reserve(legs[leg].gate_net, x - half, y0, x + half, y1)
                prim.v_wire(self.canvas, x, y0, y1, width=ESCAPE_WIRE_W_UM)
            self.escape(legs[leg].gate_net, x, ys[0], row, bank)

        # --- source / drain: two points inside the array's own inter-column
        # gaps, chosen so a row's own bus never has to widen to reach them
        # (see col_box_x0_um()). A >=3-column array (cascade C) has at least
        # two distinct gaps and uses one each -- the same two points (1/3
        # into the gap after column 0, and after column 1) the pre-#336
        # single-row array used for its own escape points. A 2-column array
        # (cascade A's 2x2 fold) has only one gap, so both points share it,
        # at 1/3 and 2/3 in. Each row's own bus pad is tied into the other
        # rows' via a Metal2 hop -- the gate buses' own escape lane cannot
        # carry it too, because the S/D buses (unlike the gate buses) do not
        # confine themselves to a lane outside the finger footprint; see the
        # module docstring. ---
        cols = len(grid[0])
        if cols < 2:
            raise ValueError(f"cascade {cascade.name}: need at least 2 columns for S/D risers")
        colw = col_widths_um(cascade)
        col_x0 = col_box_x0_um(cascade, item.x0)
        gap = CC_FINGER_GAP_UM
        if cols >= 3:
            gap0_x = dev.snap_um(col_x0[0] + colw[0] + gap / 3.0)
            gap1_x = dev.snap_um(col_x0[1] + colw[1] + gap / 3.0)
        else:
            gap0_x = dev.snap_um(col_x0[0] + colw[0] + gap / 3.0)
            gap1_x = dev.snap_um(col_x0[0] + colw[0] + 2.0 * gap / 3.0)

        def _tie_rows(net: str, pads: list[tuple[float, float, float, float]], gap_x: float) -> None:
            """Metal2 hop tying every row's own ``net`` pad into one node.

            A no-op for a 1-row array: ``pads`` has one entry, and the
            caller's own escape()/rail_stub() call (below) connects it exactly
            as the pre-#336 single-row array did.
            """
            for p in pads:
                if not p[0] <= gap_x <= p[2]:
                    raise ValueError(
                        f"cascade {cascade.name}: riser x {gap_x} falls outside a row's own "
                        f"{net!r} bus {p} -- an outer column has uniform-pitch slack this "
                        f"generator does not yet widen the bus to cover"
                    )
            if len(pads) < 2:
                return
            ys = [(p[1] + p[3]) / 2.0 for p in pads]
            for y in ys:
                prim.via1_stack(self.canvas, gap_x, y)
            y0, y1 = min(ys), max(ys)
            half = prim.METAL2_WIRE_WIDTH_UM / 2.0
            self.plan.reserve(net, gap_x - half, y0, gap_x + half, y1, layer="metal2")
            prim.m2_route(self.canvas, [(gap_x, y0), (gap_x, y1)])

        if row == "pfet":
            escape_net, escape_pads, escape_gap = cascade.always_on.bottom_net, row_bus_lo, gap0_x
            rail_pads, rail_gap = row_bus_hi, gap1_x
            escape_edge_y = escape_pads[0][1]  # bottom-most row's own bottom edge
            rail_edge_y = rail_pads[-1][3]  # top-most row's own top edge
        else:
            escape_net, escape_pads, escape_gap = cascade.always_on.top_net, row_bus_hi, gap0_x
            rail_pads, rail_gap = row_bus_lo, gap1_x
            escape_edge_y = escape_pads[-1][3]  # top-most row's own top edge
            rail_edge_y = rail_pads[0][1]  # bottom-most row's own bottom edge
        rail_net = VDD_NET if row == "pfet" else GND_NET
        rail_dest_y = bank.tap_band[1] if row == "pfet" else bank.gnd_stub_y(self.plan.outer)

        _tie_rows(escape_net, escape_pads, escape_gap)
        _tie_rows(rail_net, rail_pads, rail_gap)
        self.escape(escape_net, escape_gap, escape_edge_y, row, bank)
        self.rail_stub(rail_net, rail_gap, rail_edge_y, rail_dest_y)

    # -- assembly ------------------------------------------------------------
    def build(self) -> MirrorResult:
        p = self.plan
        for bank in p.banks:
            for item in bank.pmos:
                (self.draw_cc_array if item.kind == "cc" else self.draw_fet)(item, "pfet", bank)
            for item in bank.nmos:
                (self.draw_cc_array if item.kind == "cc" else self.draw_fet)(item, "nfet", bank)

        # --- Metal2 tracks, one per (net, bank, row) group, each stretched to
        # the net's own link column so all its groups end up on one net ---
        pad = ESCAPE_WIRE_W_UM / 2.0
        track_x1: dict[str, float] = {}
        for net in NET_ORDER:
            for bank in p.banks:
                for row in ("nfet", "pfet"):
                    xs = self.net_x.get((net, bank.index, row))
                    if not xs:
                        continue
                    x_link = p.link_x.get(net)
                    x1 = max(xs + ([x_link] if x_link is not None else []))
                    prim.m2_wire(self.canvas, min(xs) - pad, x1 + pad, bank.track_y(net, row))
                    track_x1[net] = max(track_x1.get(net, x1), x1)

        # --- link columns: one Metal1 run joining every track a net owns,
        # in the strip right of every bank's rows (see NET_ORDER's comment).
        # Pre-fold this joined a net's lo and hi track; folded, the same
        # column also joins the banks, which is why it is drawn from the
        # net's lowest track to its highest with a via1 on each. ---
        for net, x in p.link_x.items():
            ys = sorted(
                {
                    bank.track_y(net, row)
                    for bank in p.banks
                    for row in ("nfet", "pfet")
                    if (net, bank.index, row) in self.net_x
                }
            )
            self.plan.reserve(net, x - pad, ys[0], x + pad, ys[-1])
            prim.v_wire(self.canvas, x, ys[0], ys[-1], width=ESCAPE_WIRE_W_UM)
            for y in ys:
                prim.via1_stack(self.canvas, x, y)

        # --- block boundary pins ---
        def _group(net: str, banks: list, rows: tuple) -> tuple[float, float, float]:
            """(min x, max x, track y) of the first drawn group of ``net``."""
            for bank in banks:
                for row in rows:
                    xs = self.net_x.get((net, bank.index, row))
                    if xs:
                        return (min(xs), max(xs), bank.track_y(net, row))
            raise KeyError(net)

        for net in dev.MIRROR_IN_NETS:
            x, _, y = _group(net, p.banks, ("nfet", "pfet"))
            self.canvas.pin(net, x - pad - 0.6, y - pad, x - pad, y + pad, layer="metal2_label")
            prim.m2_wire(self.canvas, x - pad - 0.6, x, y)
        for net in dev.MIRROR_OUT_NETS:
            # Output pins leave on the right, so they take the *last* bank's
            # PMOS-side track -- the topmost, rightmost one this net owns.
            _, _, y = _group(net, list(reversed(p.banks)), ("pfet", "nfet"))
            x = track_x1[net] + pad
            self.canvas.pin(net, x, y - pad, x + 0.6, y + pad, layer="metal2_label")
            prim.m2_wire(self.canvas, x - pad, x + 0.6, y)

        # --- per-bank n-well + VDD_VCO tap band, per-bank GND_VCO substrate
        # tap strip, and the one outer GND_VCO guard ring around all of it ---
        for bank in p.banks:
            self.canvas.rect("nwell", *bank.nwell)
            prim.tap_strip(self.canvas, "n", *bank.tap_band, VDD_NET)
            if bank.sub_tap is not None:
                prim.tap_strip(self.canvas, "p", *bank.sub_tap, GND_NET)
        prim.guard_ring(self.canvas, "p", *p.outer, RING_WIDTH_UM, GND_NET)

        return MirrorResult(canvas=self.canvas, plan=p, footprint=p.outer, net_x=self.net_x)


def build(outdir: Path | None = None, canvas: prim.Canvas | None = None) -> MirrorResult:
    """``canvas`` draws into a caller-supplied canvas -- see ``ring.build()``."""
    result = _Builder(canvas).build()
    if outdir is not None:
        outdir = Path(outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        result.canvas.write_gds(outdir / f"{TOP_CELL}.gds")
    return result


def _bus_pad_centre_y_um(row_y0: float, row_h: float, edge: str) -> float:
    """Centre y of a drawn row's own S/D pad -- see ``primitives.mosfet()``'s
    ``_terminal_pad()``. ``edge`` is ``"bottom"`` or ``"top"``."""
    half_contact = prim.CONTACT_SIZE_UM / 2.0
    if edge == "bottom":
        return row_y0 + prim.CONTACT_ROW_MARGIN_UM + half_contact
    return row_y0 + row_h - prim.CONTACT_ROW_MARGIN_UM - half_contact


def _cc_riser_probes(item: Item, bank: BankPlan, row: str) -> list[tuple[str, str, float, float]]:
    """(net, layer, x, y) Metal1 probe pairs for one multi-row array's own
    internal ties -- the risers ``draw_cc_array()`` draws to make an R-row
    array's per-row S/D and gate buses one electrical node each, which DRC
    cannot see (a Metal2 hop that stops short of its via1 is DRC-clean and
    completely broken). Empty for an R == 1 array: its single row needs no
    internal tie, and its one escape/rail_stub column is already exactly
    what the pre-#336 single-row array drew, which DRC + ``Plan.reserve()``
    already cover.
    """
    cascade = item.cascade
    grid = cascade.pattern
    rows = len(grid)
    if rows < 2:
        return []
    row_h = device_height_um(cascade.always_on.l_um)
    y_item_bottom = bank.pmos_top - item_height_um(item) if row == "pfet" else bank.nmos_bottom
    row_y0 = [dev.snap_um(y_item_bottom + r * (row_h + CC_ROW_GAP_UM)) for r in range(rows)]

    cols = len(grid[0])
    colw = col_widths_um(cascade)
    col_x0 = col_box_x0_um(cascade, item.x0)
    gap = CC_FINGER_GAP_UM
    if cols >= 3:
        gap0_x = dev.snap_um(col_x0[0] + colw[0] + gap / 3.0)
        gap1_x = dev.snap_um(col_x0[1] + colw[1] + gap / 3.0)
    else:
        gap0_x = dev.snap_um(col_x0[0] + colw[0] + gap / 3.0)
        gap1_x = dev.snap_um(col_x0[0] + colw[0] + 2.0 * gap / 3.0)

    if row == "pfet":
        escape_net, escape_gap, escape_edge = cascade.always_on.bottom_net, gap0_x, "bottom"
        rail_net, rail_gap, rail_edge = VDD_NET, gap1_x, "top"
    else:
        escape_net, escape_gap, escape_edge = cascade.always_on.top_net, gap0_x, "top"
        rail_net, rail_gap, rail_edge = GND_NET, gap1_x, "bottom"

    # Every row, not just the two ends: a via lost on an *interior* row would
    # still leave the end-to-end riser intact (the metal2 spine between the
    # two end rows never touched that via), isolating only that row's own
    # bus -- a real, DRC-invisible fault a first-and-last-row-only probe set
    # would silently miss.
    probes = []
    for net, gap_x, edge in ((escape_net, escape_gap, escape_edge), (rail_net, rail_gap, rail_edge)):
        for r in range(rows):
            y = _bus_pad_centre_y_um(row_y0[r], row_h, edge)
            probes.append((net, "metal1", gap_x, y))

    left_x = item.x0 - ARRAY_LEFT_ESCAPE_UM
    right_x = item.x0 + item.width + ARRAY_RIGHT_ESCAPE_UM
    bus_end = {"A": left_x, "S": right_x}
    for leg in ("A", "S"):
        rows_with_leg = [r for r in range(rows) if any(tag == leg for tag in grid[r])]
        if len(rows_with_leg) < 2:
            continue
        net = cascade.always_on.gate_net if leg == "A" else cascade.switched.gate_net
        for r in rows_with_leg:
            y_lo, y_hi = gate_bus_y_um(cascade.always_on.l_um, row_y0[r])
            y = y_lo if leg == "A" else y_hi
            probes.append((net, "metal1", bus_end[leg], y))
    return probes


def connectivity_report(result: MirrorResult) -> list[tuple[str, bool, str]]:
    """Extract metal connectivity and check every 2-D array's own internal
    row-to-row tie actually joins into one net.

    Every other net this block routes is a single Metal1 escape column DRC
    and ``Plan.reserve()`` already prove correct by construction (one column,
    one via1, checked for spacing at build time); the property neither of
    those checks can see is whether a *new* piece of geometry -- the Metal2
    riser an R-row common-centroid array (issue #336) needs to tie its own
    rows together -- actually reaches every via1 it claims to. Same
    machinery ``block.connectivity_report()`` uses (KLayout's own
    ``LayoutToNetlist``, restricted to metal1/via1/metal2), scoped here to
    just the nets this block's own 2-D arrays introduce a new tie for.
    """
    import klayout.db as db  # noqa: PLC0415

    layout = result.canvas.layout
    cell = result.canvas.top
    l2n = db.LayoutToNetlist(db.RecursiveShapeIterator(layout, cell, []))
    layers = {}
    for name in ("metal1", "via1", "metal2"):
        layers[name] = l2n.make_polygon_layer(layout.layer(*prim.LAYER[name]), name)
    l2n.connect(layers["metal1"])
    l2n.connect(layers["via1"])
    l2n.connect(layers["metal2"])
    l2n.connect(layers["metal1"], layers["via1"])
    l2n.connect(layers["via1"], layers["metal2"])
    l2n.extract_netlist()

    # Keyed by (net, item.name) rather than net alone: VDD_VCO/GND_VCO are
    # each other bank's own *separate* rail island pre-assembly (only
    # block.py's own supply trunk joins the banks' tap bands into one net --
    # see mirror.py's module docstring), so aggregating by net name alone
    # would compare two cascades' unrelated rail islands against each other
    # and report a false failure.
    probes_by_key: dict[tuple[str, str], list[tuple[str, float, float]]] = {}
    for bank in result.plan.banks:
        for items, row in ((bank.pmos, "pfet"), (bank.nmos, "nfet")):
            for item in items:
                if item.kind != "cc":
                    continue
                for net, layer, x, y in _cc_riser_probes(item, bank, row):
                    probes_by_key.setdefault((net, item.name), []).append((layer, x, y))

    out: list[tuple[str, bool, str]] = []
    for (net, item_name), probes in probes_by_key.items():
        label = f"{net} ({item_name})"
        found = [l2n.probe_net(layers[layer], db.DPoint(x, y)) for layer, x, y in probes]
        missing = [p for p, n in zip(probes, found) if n is None]
        if missing:
            out.append((label, False, f"2-D array internal tie: no metal found at {missing}"))
            continue
        ids = {n.cluster_id for n in found}
        ok = len(ids) == 1
        out.append(
            (
                label,
                ok,
                f"2-D array internal tie: {len(probes)} probe(s) -> "
                + ("one net" if ok else f"{len(ids)} separate nets {sorted(ids)}"),
            )
        )
    return out


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
    for bank in result.plan.banks:
        print(
            f"bank {bank.index} ({bank.name}): pmos row {bank.pmos[-1].x0 + bank.pmos[-1].width:.3f} um wide, "
            f"nmos row {bank.nmos[-1].x0 + bank.nmos[-1].width:.3f} um, "
            f"channel {bank.channel[1] - bank.channel[0]:.3f} um "
            f"({len(bank.track_lo)} lo / {len(bank.track_hi)} hi tracks), "
            f"y {bank.nmos_bottom:.3f}..{bank.nwell[3]:.3f}"
        )
    print(f"link columns: {len(result.plan.link_x)} ({', '.join(sorted(result.plan.link_x))})")
    for c in dev.MIRROR_CASCADES:
        cw, ch = array_width_um(c), array_height_um(c)
        ax, ay = leg_centroid_um(c, "A")
        sx, sy = leg_centroid_um(c, "S")
        print(
            f"cascade {c.name}: {len(c.pattern)} row(s), {cw:.3f} x {ch:.3f} um, "
            f"centre ({cw / 2.0:.3f}, {ch / 2.0:.3f}), "
            f"A centroid ({ax:.3f}, {ay:.3f}), S centroid ({sx:.3f}, {sy:.3f})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
