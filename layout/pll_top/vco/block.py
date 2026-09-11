"""The whole VCO block: five sub-blocks wired together under one guard ring.

WHAT THIS MODULE IS
--------------------
Issue #293's final increment. Four earlier increments each drew one piece of
``vco.sch``/``vco_bias.sch`` as its own standalone, DRC-clean block:

======================  ==========================  =========================
Sub-block               Generator                   Landed in
======================  ==========================  =========================
5-stage ring            ``ring.py``                 PR #305
band-select mirror      ``mirror.py``               PR #313
3-stage output buffer   ``buffer.py``               PR #313
``RCG``/``ROFF``/       ``bias_resistors.py``       PR #314
``RDEG``
V-to-I core             ``vtoi_core.py``            PR #316
======================  ==========================  =========================

Each of those five carries its own dedicated guard ring and proves clean on
its own -- but five separately-clean blocks are not one clean block, and none
of the *inter*-sub-block nets (``NC``/``NOFF``/``NVI`` from the resistors to
the V-to-I core, ``VBP0`` from the core to the mirror, ``VBP``/``VBN`` from
the mirror to the ring, ``Y5`` from the ring to the buffer, and the
``VDD_VCO``/``GND_VCO`` distribution that has to reach all five) existed as
drawn geometry anywhere. This module draws them, wraps the result in the
block-level ``GND_VCO`` substrate ring PLL-FLOORPLAN.md section 1 asks for,
carries the 22 pF decap forward against *this* block's own ``VDD_VCO``
pin/ring-tap junction, and is DRC-clean as one layout.

FLAT, NOT HIERARCHICAL
-----------------------
``primitives.Canvas.at()`` translates a sub-block generator's own local
coordinates into this block's frame, so every sub-block is drawn into one
flat top cell instead of being instanced. That is a deliberate trade (see
``Canvas.at()``'s own docstring): this block's routing has to *merge* with
sub-block shapes -- a via1 landing inside a sub-block's own Metal1 rail, a
Metal2 track extended past a sub-block's boundary -- and shapes that must
merge into one polygon for DRC have to live in one cell. Every sub-block
generator is unchanged when built standalone (offset ``(0, 0)``), which is
what keeps the five standalone DRC proofs on ``main`` still valid.

ROUTING DISCIPLINE (why this is checkable by hand)
---------------------------------------------------
Two of the five sub-blocks (``mirror.py``, ``vtoi_core.py``) already use
Metal2, as horizontal per-net tracks on a ``TRACK_PITCH_UM`` = 0.8 um pitch
inside their own device channel; the other three use Metal1 only. So:

* **Every top-level signal route is Metal2.** Metal2 has no spacing
  relationship with Metal1, comp, poly or implant in this deck, so a route
  may cross any sub-block's guard ring, rails, devices and taps freely. The
  only geometry a top-level route can collide with is *other Metal2*.
* **A route into a mesh-block pin is that pin's own track, extended.** Both
  mesh blocks pin a net by stubbing its track past the device row; extending
  that same track further (in the same direction, at the same y) adds no new
  neighbour relationship -- the extension's nearest other-net Metal2 is still
  the adjacent track, 0.8 - 0.44 = 0.36 um away, above ``M2.2a``'s 0.28 um.
* **Every other route runs in an inter-row channel or a side column**, whose
  widths are the ``*_GAP_UM``/``*_X`` constants below. ``_Router.reserve()``
  records every segment and raises if two different nets' Metal2 come within
  ``M2.2a`` -- the same "a spacing bug is cheaper as a Python exception than
  as a DRC marker" check ``mirror.py``'s ``Plan.reserve()`` makes on Metal1.

THE ONE NET THAT IS NOT METAL2: ``VDD_VCO``
---------------------------------------------
The supply trunk cannot be Metal2 without crossing every Metal2 signal that
escapes to the same side, and it cannot be a plain Metal1 run into a
sub-block either -- a Metal1 wire entering any of these blocks crosses that
block's own Metal1-covered ``GND_VCO`` guard ring band, i.e. shorts to
ground. So ``VDD_VCO`` is a **Metal1 vertical trunk** in the right-hand
channel (signals cross over it on Metal2, no rule between the layers), and
each sub-block is fed by a short Metal2 hop from the trunk to a via1 landing
on that block's own n-well tap band -- hopping over its guard ring on the
layer that is allowed to. ``GND_VCO`` needs no trunk at all: it is the
substrate, and the block-level ring is tied to each sub-block's own ring by a
Metal1 strap in the left-hand channel.

THE BLOCK'S GUARD RING IS TWO-SIDED (issue #324)
--------------------------------------------------
PLL-FLOORPLAN.md section 1 asks for the VCO's ring to be "a real two-sided
ring, not a substrate-only one" -- ``GND_VCO`` on the substrate side and a
``VDD_VCO``-tied n-well tap ring on the well side. Both bands are now drawn,
concentric: the ``GND_VCO`` p+ substrate ring immediately around the block's
content (step 8 below), and a ``VDD_VCO`` n-well tap ring outside it
(step 8b) -- ``NWELL_RING_*`` for the geometry and the rules each number
comes from. ``placement().outer`` is the substrate ring, ``nwell_ring`` the
n-well band's outer edge, and ``footprint_um()`` is the latter, i.e. the
block's real outermost geometry.

The n-well band goes *outside* on purpose. In a p-substrate flow with no
deep n-well, the p+ ring is what the devices' own sources already tie into,
so it belongs closest to them; the reverse-biased well/substrate junction
belongs outside it, collecting what gets past. Putting it inside would also
mean threading a well band between the substrate ring and five sub-block
rings already strapped to that ring in Metal1.

Every n-well *inside* the block remains ``VDD_VCO``-tied by its own
sub-block's tap band (12.1 um worst case, well inside section 1's own 15 um
bound), which is the well-tie and tap-pitch half of the same requirement.
The ring band is reached the same way every sub-block's tap band is -- one
Metal2 hop from the Metal1 supply trunk, hopping over the substrate ring on
the layer that is allowed to. One hop is enough for the whole ring because
``primitives.guard_ring()`` draws all four bands as one continuous Metal1
shape; ``connectivity_report()`` probes the band *opposite* the feed, so
"the ring is continuous" is proved rather than assumed.

DEVIATION FROM THE ROM FLOORPLAN, STATED PLAINLY
--------------------------------------------------
``footprint_um()`` reports the assembled block at 172.52 x 183.48 um
(31,654 um^2 = 0.0317 mm^2) against PLL-FLOORPLAN.md section 5's
0.011-0.017 mm^2 ROM row for the whole VCO -- still a **1.9-2.9x overrun**.
That record's section 5 names this case in advance and prescribes the
response ("the next floorplan revision should state the overrun explicitly
rather than silently rounding the total down"), so it is stated here, in
``layout/floorplan/skeleton.py``'s docstring, and in
``layout/evidence/vco-layout/PROOF-fold.md`` / ``PROOF-2d-fold.md`` with the
re-run budget arithmetic (``PROOF-block.md`` carries the pre-fold version of
the same accounting, plus a correction note on one arithmetic slip in it).

The cause is the one already recorded per sub-block: every device is drawn
as its own diffusion island wired by metal (``primitives.py``'s module
docstring). Issue #293's own increment took the easy part back -- packing
the resistor trio into the V-to-I core row's own leftover width rather than
beside it, and trimming the boundary-pin channels, worth ~11 % -- and left
the real lever, folding the single-row sub-blocks into multiple rows,
explicitly to a follow-up. Issue #324 pulled that lever on the widest one:
``mirror.py``'s band-select mirror is now two stacked banks rather than one
NMOS/PMOS row pair (269.9 x 37.1 um -> 152.6 x 53.0 um), which took the
assembled block from 294.78 x 148.18 um to 176.98 x 164.08 um before the
n-well ring's own +6.2 um per axis. Height is the currency width was bought
with, and it is affordable: the floorplan skeleton's height is set by the
loop filter's 195 um, not by this block.

Issue #336 then folded cascades A and C of the mirror's own arrays from flat
rows into 2-D common-centroid grids (A: 1x4 -> 2x2; C: 1x9 -> 3x3), which is
the lever #324 could not reach -- cascade C alone (115.18 um) was already
alone in its bank's PMOS row, so no further *row* split could shrink it.
That narrows the mirror from 152.6 to 115.9 um wide, but grows it from 53.0
to 66.2 um tall, and the mirror's new height has no other sub-block in its
own row to absorb it into -- so the assembled block's own width drops
(183.18 -> 172.52 um) while its height grows by essentially the same amount
the mirror did (170.28 -> 183.48 um), leaving the block's own area roughly
unchanged (31,192 -> 31,654 um^2, +1.5 %). **Recorded as what it is: #336 is
a real, DRC-clean width reduction that retires cascade C as the mirror's own
width bottleneck, but it is not, on its own, an area win for the assembled
block** -- see ``PROOF-2d-fold.md``.

**The V-to-I core is now the practical width floor.** The ring, the buffer
and the resistor trio are all narrower than the mirror even after #336; the
V-to-I core (121.18 um) plus the bias-resistor row it sits beside (combined
140.7 um) now exceeds the mirror's own 115.9 um, so the mirror is very
likely no longer the block's own width bottleneck.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import bias_resistors
from . import buffer as out_buffer
from . import devices as dev
from . import mirror
from . import primitives as prim
from . import ring
from . import vtoi_core

TOP_CELL = "vco_block"

VDD_NET = "VDD_VCO"
GND_NET = "GND_VCO"

# --- inter-row channels (um) ------------------------------------------------
ROW_GAP_BIAS_TO_MIRROR_UM = 8.0
ROW_GAP_MIRROR_TO_RING_UM = 6.0  # carries the VBP and VBN lanes
ROW_GAP_RING_TO_BUFFER_UM = 6.0  # carries the Y5 lane

# The resistor trio is only 13 x 40 um and the V-to-I core's own row is 51 um
# tall and stops at x = 117 while the band mirror below sets the block's full
# ~266 um width -- so the resistors go in *that row's own leftover space*,
# right of the core, rather than beside it on the left where they would widen
# the whole block by their own footprint plus a channel. Cost of doing so: the
# ``VBP0`` route can no longer leave the core on the right (its horizontal run
# would cross the two resistor riser columns), so it leaves on the left
# instead -- see ``VBP0_COL_OFFSET_UM``.
RES_CHANNEL_UM = 6.5  # V-to-I core right edge -> resistor block left edge
RES_COL_NVI_OFFSET_UM = 2.0  # ... and the two riser columns inside it. NVI is
RES_COL_NOFF_OFFSET_UM = 4.0  # the *inner* column even though its track is the
# outer one: that ordering is what keeps the two crossing-free (NOFF's own
# horizontal run then passes the NVI column at a y the NVI riser has not
# started at yet). ``_Router.reserve()`` proves it rather than trusting this.

BUFFER_DX_UM = 57.0  # puts the buffer's own Y5 input pin almost directly over
# the ring's stage-5 output pad, so the Y5 hop is a short vertical rather than
# a run across the block -- PLL-FLOORPLAN.md section 1's "farthest from the
# ring's own starved internal nodes" applies to the buffer's *last* stage,
# which buffer.py already places at its far right.

# --- right-hand channel: one Metal1 supply trunk + two Metal2 columns -------
VDD_TRUNK_CLEARANCE_UM = 1.5  # widest sub-block's right edge -> trunk centre
VDD_TRUNK_WIDTH_UM = 1.0
COL_PITCH_UM = 2.0  # Metal2 column pitch in the right-hand channel
CLK_PIN_OFFSET_UM = 3.0  # last Metal2 column -> the CLK output pin

# --- left-hand channel ------------------------------------------------------
# Two columns only, and their order matters: the ``VBP0`` riser (which spans
# the whole bias-row-to-mirror-row height) sits *outside* the input-pin
# column, so the four input routes -- which all run rightward from their pin
# to their own sub-block's track -- never cross it.
VBP0_COL_OFFSET_UM = 7.0  # leftmost sub-block edge -> the VBP0 riser column
LEFT_PIN_CHANNEL_UM = 3.0  # leftmost sub-block edge -> the input-pin column
PIN_STUB_UM = 0.6  # drawn length of a boundary pin's own landing pad

# --- block-level guard ring -------------------------------------------------
SHARED_MARGIN_UM = 3.0  # content bbox -> guard ring inner edge
SHARED_RING_WIDTH_UM = 1.2
STRAP_WIDTH_UM = 1.2  # Metal1 tie, block ring <-> a sub-block's own ring

# --- block-level n-well tap ring (issue #324) -------------------------------
# The second, concentric half of PLL-FLOORPLAN.md section 1's "real two-sided
# ring": a VDD_VCO-tied n-well band outside the GND_VCO substrate ring. Outside
# rather than inside on purpose -- in a p-substrate flow with no deep n-well,
# the p+ ring belongs closest to the noisy devices (it is the low-impedance
# substrate tie those devices' own sources already run to) and the n-well band
# belongs outside it, where the reverse-biased well/substrate junction collects
# what gets past the p+ ring. Putting it inside would also mean threading it
# between the block ring and five sub-block rings that are already strapped to
# that ring in Metal1.
NWELL_RING_GAP_UM = 1.5
"""GND_VCO ring's outer edge -> the n-well's inner edge.

``DF.16_LV``'s own minimum (n-well to comp outside it) is 0.43 um. 1.5 um is
used so the p-ring's *pplus* (0.3 um past its comp) also clears the n-well by
1.2 um -- the same clearance ``mirror.py``'s single-row layout already kept
between its own p-ring and n-well and DRC-proved clean.
"""

NWELL_RING_TAP_INSET_UM = 0.5  # n-well edge -> its own ncomp (DF.4d_LV = 0.12 min)
NWELL_RING_TAP_WIDTH_UM = 0.6  # ncomp band thickness (NP.1's min is 0.4)
NWELL_RING_WIDTH_UM = 2 * NWELL_RING_TAP_INSET_UM + NWELL_RING_TAP_WIDTH_UM
"""Drawn n-well band width, 1.6 um -- comfortably above ``NW.1a_LV``'s 0.86."""

M2_HALF_UM = prim.METAL2_WIRE_WIDTH_UM / 2.0


# ---------------------------------------------------------------------------
# Reference LVS netlist (issue #367)
# ---------------------------------------------------------------------------
#
# A flat, flattened re-expression of design/netlist/vco.spice's own three
# subckts (vco / vco_bias / vco_stage), following divider_chain.py's own
# "REFERENCE NETLIST" discipline: every device's W/L and connection traces
# directly to devices.py's tables (which are themselves read off that
# generated file's own .subckt bodies -- see devices.py's module docstring),
# not re-derived independently. This is *not* that generated file's own
# literal hierarchical text: the five ring stages, three mirror cascades,
# three-stage buffer, three bias resistors and twelve-transistor V-to-I core
# are all inlined into one flat .subckt with every sub-block-internal net
# (only the ring's own per-stage NH/NT nodes -- every other net devices.py
# names is already a block-boundary or inter-sub-block name reused verbatim
# across every table in that module) uniquely prefixed per instance -- the
# same reason a first attempt at divider_chain's own reference using the
# generated hierarchical file directly failed LVS outright (gf180mcu's LVS
# deck matches sub-circuits by name; a flattened GDS has none to match once
# named instances become geometry).

RESISTOR_LVS_MODEL = "ppolyf_u"
"""The poly-resistor device class gf180mcu's own signoff LVS deck actually
extracts **from the geometry ``primitives.poly_resistor()`` draws** -- not
``ppolyf_u_3k``, which is the class ``design/netlist/vco.spice`` names on
``XRCG``/``XROFF``/``XRDEG`` (``devices.BIAS_RESISTORS``), and not
``ppolyf_u_1k``, which this constant wrongly named until issue #378.

Read off the deck's own extracted netlist, not inferred (issue #378, see
``layout/evidence/vco-layout/PROOF-378-resistor-class-fix.md``). The run's
own ``vco_block.cir`` states the three resistors as::

    R$77 GND_VCO NC   GND_VCO  1960 ppolyf_u L=5.6U W=1U
    R$78 GND_VCO NOFF GND_VCO 11550 ppolyf_u L=33U  W=1U
    R$79 GND_VCO NVI  GND_VCO 11550 ppolyf_u L=33U  W=1U

-- device class ``ppolyf_u``, at 350 ohm/sq (1960 / 5.6 == 11550 / 33 ==
350), the *unmarked* p+ poly resistor.

**Why not the high-sheet class.** ``rule_decks/res_derivations.lvs`` derives
every high-sheet variant (``PPOLYF_U_1K``/``_2K``/``_3K``, whichever
``$poly_res`` selects) as ``poly2.and(sab).and(res_mk).and(resistor)`` --
``resistor`` being GDS layer ``(62, 0)``. ``primitives.poly_resistor()``
draws ``res_mk``/``poly2``/``sab``/``pplus``/contacts and no ``(62, 0)`` at
all, so the layout falls into that same file's *unmarked* branch,
``ppolyf_u_layer = pplus.and(poly2).and(sab).and(res_mk)
.not_interacting(resistor)...`` -- extracted by ``res_extraction.lvs``'s own
un-gated ``extract_devices(resistor_with_bulk('ppolyf_u', 350, BResistor))``.
The deck's ``poly_res`` switch (hardcoded ``"1k"`` by the PDK's own
``run_lvs.py``, with no CLI override) only chooses *which* high-sheet class
the marked branch produces; with no ``(62, 0)`` drawn, it never applies to
this layout. The deck's log line ``Extracting PPOLYF_U_1K device`` -- which
issue #367's own reading of this took as evidence for ``ppolyf_u_1k`` -- is
printed for **every** class the deck attempts (``Extracting PPOLYF_U
device`` appears six lines above it in the same log) and says nothing about
which class any geometry actually produced.

Naming a class the deck does not extract is not a cosmetic mislabel: it
cost the assembled ``vco_block`` LVS run its match. The comparer paired the
three resistors only ``MatchWithWarning`` across the two class names, which
left every net adjacent to them (``NC``/``NOFF``/``NVI`` and, through their
shared bottom terminal, ``GND_VCO``) topologically unconfirmed -- the exact
four ``Mismatch`` nets issue #378 was filed for.

**Still a disclosed deviation, and a larger one than before**: the layout
draws a 350 ohm/sq unmarked resistor where ``design/netlist/vco.spice``
specifies ``ppolyf_u_3k`` (3000 ohm/sq) -- ~8.6x the sheet resistance, a
design-level discrepancy in the bias network, tracked separately as issue
#381 rather than papered over here. ``PROOF-lvs.md`` and
``PROOF-378-resistor-class-fix.md`` record it explicitly rather than
silently renaming the schematic's own class or dropping the devices.
"""

DECAP_LVS_MODEL = "cap_nmos_03v3"
"""The device class ``design/netlist/vco.spice``'s ``XCDEC1``/``XCDEC2``
name -- deliberately **not** emitted by :func:`reference_netlist` at all.

``ring.py``'s own module docstring (carried into this module's
``decap_boxes_um()``) already states the carried-forward 22 pF decap pair is
drawn as two boundary-layer marker rectangles (GDS layer (0, 0); no DRC rule
in this deck references it -- see ``primitives.LAYER``'s docstring), not real
``cap_nmos_03v3`` device geometry (comp/poly2/``mos_cap_mk``): "AC's own
wording is 'carried forward **unchanged**', not 're-drawn as a real MOS-cap
device' -- turning it into real device geometry is follow-up-issue scope".
With no matching layout geometry for the deck to extract, including
``XCDEC1``/``XCDEC2`` in this reference would not "confirm ``cap_nmos_03v3``
recognition" -- it would just fail LVS with two permanently-unmatched
schematic-side devices for a device family this increment never draws.
Disclosed here and in ``PROOF-lvs.md`` rather than silently omitted with no
comment.
"""


def _fet_line(instance: str, f: dev.Fet, net_map: dict[str, str] | None = None) -> str:
    """One ``M_<instance>`` MOSFET4 line: ``D=top_net G=gate_net S=bottom_net``.

    ``net_map`` renames any of ``f``'s three nets found as a key (the ring's
    own per-stage translation -- see :func:`reference_netlist`); every other
    net passes through verbatim, which is correct for every non-ring device
    table in ``devices.py`` since those already use global, block-boundary or
    inter-sub-block net names directly (no per-instance-local nodes to
    rename).

    ``W`` is ``f.drawn_w_um`` -- the *drawn* width (fingers times the
    grid-snapped per-finger width: ``devices.Fet.finger_w_um``), not the
    schematic's own literal ``w_um`` -- so this reference always states what
    the layout actually manufactures, the same "layout is what gets
    verified" reasoning ``devices.Fet.w_deviation_frac`` (tested already on
    ``main``) exists for. For most devices the two are identical; three
    (``MA1``, ``MB1``, ``MC1``) differ by up to ~0.03 % because 17.225/2,
    8.6125/2 and 78.87/8 are not exact multiples of the 5 nm manufacturing
    grid (``devices.LAYOUT_GRID_UM``) -- an existing, already-tested property
    of the DRC-clean geometry on ``main``, not something this issue
    introduces. ``PROOF-lvs.md`` states the three deviations plainly rather
    than rounding them away. ``devices.CASCADE_B``'s own ``nf`` 1 -> 2
    finger fold needs no special case here at all: both its legs' ``fingers``
    (``layout_nf``) and thus ``drawn_w_um`` already account for it, and
    gf180mcu's own ``netlist.simplify`` (the LVS deck's default, un-flagged
    behaviour -- see ``PROOF-lvs.md``) combines the two separately-drawn,
    identically-connected fingers ``mirror.py`` draws for each leg back into
    one device with the summed ``W`` before comparison, so one reference line
    per logical device -- not one per drawn finger -- is what actually
    matches the deck's own extracted netlist.
    """

    def n(net: str) -> str:
        return net_map[net] if net_map and net in net_map else net

    model = f"{f.kind}_03v3"
    bulk = VDD_NET if f.kind == "pfet" else GND_NET
    return (
        f"M_{instance} {n(f.top_net)} {n(f.gate_net)} {n(f.bottom_net)} {bulk} "
        f"{model} W={f.drawn_w_um}u L={f.l_um}u"
    )


def _resistor_line(r: dev.PolyResistor) -> str:
    """One ``R_<name>`` 3-terminal (A/B/bulk) poly-resistor line.

    Node order and the ``W=``/``L=`` parameter names match what gf180mcu's
    own ``SubcircuitModelsReader`` (``rule_decks/custom_classes.lvs``) reads
    for a resistor element -- *not* ``design/netlist/vco.spice``'s own
    ``r_width=``/``r_length=`` spelling, which that reader does not
    recognise (it looks up ``params['W']``/``params['L']`` specifically, so
    a reference line using the schematic's own parameter names would extract
    as a 0x0 resistor). Model is :data:`RESISTOR_LVS_MODEL`, not the
    schematic's own ``ppolyf_u_3k`` -- see that constant's docstring.
    """
    return f"R_{r.name} {r.top_net} {r.bottom_net} {r.bottom_net} {RESISTOR_LVS_MODEL} W={r.w_um}u L={r.l_um}u"


def reference_netlist() -> str:
    """Flattened LVS reference for :data:`TOP_CELL` (``vco_block``).

    See the module-level "Reference LVS netlist" section above for the
    flattening/labelling discipline, and :data:`RESISTOR_LVS_MODEL` /
    :data:`DECAP_LVS_MODEL` for the two disclosed, deliberate departures from
    ``design/netlist/vco.spice``'s own device classes.
    """
    lines: list[str] = [
        f"* Reference LVS netlist for {TOP_CELL} (issue #367).",
        "*",
        "* Flattened re-expression of design/netlist/vco.spice's vco/vco_bias/",
        "* vco_stage subckts -- every device W/L traces to devices.py's own",
        "* tables (themselves read off that generated file). See block.py's",
        "* module-level docstring section and layout/evidence/vco-layout/",
        "* lvs-clean/PROOF-lvs.md for the two disclosed device-class",
        "* deviations (poly resistors, and the excluded MOS decap pair).",
        "*",
        "* Run LVS with --lvs-sub=GND_VCO (this block's own substrate net --",
        "* NOT layout/run_pv.py's own VSS default; see layout/README.md's",
        '* "substrate-net gotcha").',
        "",
        f".subckt {TOP_CELL} VCTRL B0 B1 B2 CLK VDD_VCO GND_VCO",
    ]

    # --- ring: 5x vco_stage.sch, chained Y_i -> A_(i+1), wraparound Y5 -> A1.
    # NH/NT are the only per-instance-local nets in the whole reference. ---
    for i in range(dev.STAGE_COUNT):
        stage_num = i + 1
        a_net = "Y5" if i == 0 else f"Y{i}"
        y_net = f"Y{stage_num}"
        net_map = {
            "A": a_net,
            "Y": y_net,
            "VDD": VDD_NET,
            "VSS": GND_NET,
            "VBP": "VBP",
            "VBN": "VBN",
            "NH": f"S{stage_num}_NH",
            "NT": f"S{stage_num}_NT",
        }
        for f in dev.STAGE_FETS:
            lines.append(_fet_line(f"S{stage_num}_{f.name}", f, net_map))

    # --- 3-stage output buffer (Y5 -> NB1 -> NB2 -> CLK); already global net
    # names, per devices.py's own module-level comment on BUFFER_STAGES. ---
    for st in dev.BUFFER_STAGES:
        lines.append(_fet_line(st.pfet.name, st.pfet))
        lines.append(_fet_line(st.nfet.name, st.nfet))

    # --- 3-cascade band-select mirror: cascades, switch muxes, output-mirror
    # loads, band-code inverters -- all already global net names. ---
    for cascade in dev.MIRROR_CASCADES:
        lines.append(_fet_line(cascade.always_on.name, cascade.always_on))
        lines.append(_fet_line(cascade.switched.name, cascade.switched))
    for mux in dev.MIRROR_MUXES:
        lines.append(_fet_line(mux.on.name, mux.on))
        lines.append(_fet_line(mux.off.name, mux.off))
    for f in dev.MIRROR_LOADS:
        lines.append(_fet_line(f.name, f))
    for inv in dev.MIRROR_INVERTERS:
        lines.append(_fet_line(inv.pfet.name, inv.pfet))
        lines.append(_fet_line(inv.nfet.name, inv.nfet))

    # --- RCG/ROFF/RDEG poly resistors -- see RESISTOR_LVS_MODEL. ---
    for r in dev.BIAS_RESISTORS:
        lines.append(_resistor_line(r))

    # --- V-to-I core (constant-gm reference, startup kick, 2*Vgs stack,
    # offset/degenerated V-to-I branches, summing device) -- already global
    # net names. ---
    for f in dev.VTOI_ALL_FETS:
        lines.append(_fet_line(f.name, f))

    # NOTE: design/netlist/vco.spice's XCDEC1/XCDEC2 (cap_nmos_03v3, 22 pF
    # total) are deliberately NOT emitted -- see DECAP_LVS_MODEL's docstring.

    lines.append(".ends")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Placement -- pure Python (no KLayout import), same convention as every other
# module in this package: footprint_um() and layout/tests/ derive the block's
# extents from the same arithmetic build() draws from.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Placement:
    """Where each sub-block generator's own local origin lands in this block."""

    dx_res: float
    dy_res: float
    dx_vtoi: float
    dy_vtoi: float
    dx_mirror: float
    dy_mirror: float
    dx_ring: float
    dy_ring: float
    dx_buffer: float
    dy_buffer: float
    # derived channel geometry, absolute coordinates
    vdd_trunk_x: float
    col_vbp_x: float
    col_vbn_x: float
    col_vbp0_x: float
    clk_pin_x: float
    left_pin_x: float
    res_col_noff_x: float
    res_col_nvi_x: float
    content: tuple  # (x0, y0, x1, y1) of everything the guard ring encloses
    outer: tuple  # (x0, y0, x1, y1) of the block-level GND_VCO substrate ring
    nwell_tap: tuple  # (x0, y0, x1, y1), outer edge of the VDD_VCO ncomp ring
    nwell_ring: tuple  # (x0, y0, x1, y1), outer edge of that ring's own n-well
    boundary: tuple  # the block's own footprint -- == nwell_ring, the
    # outermost geometry this block draws

    def boxes(self) -> dict:
        """Each sub-block's own guard-ring box, translated into block coords."""
        return {
            "bias_resistors": _shift(bias_resistors.footprint_um(), self.dx_res, self.dy_res),
            "vtoi_core": _shift(vtoi_core.footprint_um(), self.dx_vtoi, self.dy_vtoi),
            "mirror": _shift(mirror.footprint_um(), self.dx_mirror, self.dy_mirror),
            "ring": _shift(ring.footprint_um(with_decap=False), self.dx_ring, self.dy_ring),
            "buffer": _shift(out_buffer.footprint_um(), self.dx_buffer, self.dy_buffer),
        }


def _shift(box: tuple, dx: float, dy: float) -> tuple:
    return (box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy)


def placement() -> Placement:
    vt = vtoi_core.footprint_um()
    mi = mirror.footprint_um()
    rg = ring.footprint_um(with_decap=False)
    bf = out_buffer.footprint_um()
    rs = bias_resistors.footprint_um()

    snap = dev.snap_um

    # --- bias row: the V-to-I core sets the origin; the resistor block sits
    # one channel to its right, in that row's own leftover width, at the y
    # offset that lands RCG's own signal pad exactly on the core's NC Metal2
    # track (see bias_resistors.top_pad_center_um() for why that is worth
    # arranging). ---
    dx_vtoi = dy_vtoi = 0.0
    dx_res = snap(vt[2] + RES_CHANNEL_UM - rs[0])
    dy_res = snap(
        vtoi_core.plan().track_lo["NC"] - bias_resistors.top_pad_center_um(dev.BIAS_R_RCG)[1]
    )

    # --- rows stack bottom to top in signal order: bias -> mirror -> ring ->
    # buffer, each left-aligned on the V-to-I core's own x origin. ---
    dx_mirror = dx_ring = 0.0
    dy_mirror = snap(vt[3] + ROW_GAP_BIAS_TO_MIRROR_UM - mi[1])
    dy_ring = snap(dy_mirror + mi[3] + ROW_GAP_MIRROR_TO_RING_UM - rg[1])
    dx_buffer = BUFFER_DX_UM
    dy_buffer = snap(dy_ring + rg[3] + ROW_GAP_RING_TO_BUFFER_UM - bf[1])

    rows = (
        _shift(rs, dx_res, dy_res),
        _shift(vt, dx_vtoi, dy_vtoi),
        _shift(mi, dx_mirror, dy_mirror),
        _shift(rg, dx_ring, dy_ring),
        _shift(bf, dx_buffer, dy_buffer),
    )
    blocks_x1 = max(b[2] for b in rows)
    blocks_x0 = min(b[0] for b in rows)

    vdd_trunk_x = snap(blocks_x1 + VDD_TRUNK_CLEARANCE_UM)
    col_vbp_x = snap(vdd_trunk_x + COL_PITCH_UM)
    col_vbn_x = snap(vdd_trunk_x + 2 * COL_PITCH_UM)
    clk_pin_x = snap(col_vbn_x + CLK_PIN_OFFSET_UM)
    col_vbp0_x = snap(blocks_x0 - VBP0_COL_OFFSET_UM)
    left_pin_x = snap(blocks_x0 - LEFT_PIN_CHANNEL_UM)

    res_col_nvi_x = snap(vt[2] + RES_COL_NVI_OFFSET_UM)
    res_col_noff_x = snap(vt[2] + RES_COL_NOFF_OFFSET_UM)

    content = (
        col_vbp0_x - M2_HALF_UM,
        min(b[1] for b in rows),
        clk_pin_x + M2_HALF_UM,
        max(b[3] for b in rows),
    )
    m = SHARED_MARGIN_UM + SHARED_RING_WIDTH_UM
    outer = (content[0] - m, content[1] - m, content[2] + m, content[3] + m)

    def _grow(box: tuple, d: float) -> tuple:
        return (box[0] - d, box[1] - d, box[2] + d, box[3] + d)

    nwell_ring = _grow(outer, NWELL_RING_GAP_UM + NWELL_RING_WIDTH_UM)
    nwell_tap = _grow(outer, NWELL_RING_GAP_UM + NWELL_RING_WIDTH_UM - NWELL_RING_TAP_INSET_UM)

    return Placement(
        dx_res=dx_res,
        dy_res=dy_res,
        dx_vtoi=dx_vtoi,
        dy_vtoi=dy_vtoi,
        dx_mirror=dx_mirror,
        dy_mirror=dy_mirror,
        dx_ring=dx_ring,
        dy_ring=dy_ring,
        dx_buffer=dx_buffer,
        dy_buffer=dy_buffer,
        vdd_trunk_x=vdd_trunk_x,
        col_vbp_x=col_vbp_x,
        col_vbn_x=col_vbn_x,
        col_vbp0_x=col_vbp0_x,
        clk_pin_x=clk_pin_x,
        left_pin_x=left_pin_x,
        res_col_noff_x=res_col_noff_x,
        res_col_nvi_x=res_col_nvi_x,
        content=content,
        outer=outer,
        nwell_tap=nwell_tap,
        nwell_ring=nwell_ring,
        boundary=nwell_ring,
    )


def footprint_um() -> tuple:
    """Pure-Python (no KLayout) footprint: the block's outermost guard band.

    That is the ``VDD_VCO`` n-well ring's own outer edge (issue #324), not the
    ``GND_VCO`` substrate ring's -- the substrate ring is now the *inner* of
    two concentric bands. ``placement().outer`` is still the substrate ring, so
    every check that is really about "inside the block's guard ring" (sub-block
    containment, the decap placement) keeps using it.
    """
    return placement().boundary


def decap_boxes_um() -> tuple:
    """The two carried-forward 22 pF decap footprints, absolute coordinates.

    Placed in the open area to the right of the V-to-I core, immediately left
    of this block's own ``VDD_VCO`` pin -- i.e. against the pin/ring-tap
    junction where the supply trunk meets the core's n-well tap band, which is
    what issue #293's acceptance criterion asks for. Carried forward as the
    same layer-(0, 0) boundary markers ``ring.py`` and
    ``layout/floorplan/skeleton.py`` have always used (no DRC rule in this
    deck references that layer); ``ring.build(draw_decap=False)`` suppresses
    the ring block's own copy so this is one marker pair for one physical
    pair of caps, not two.
    """
    p = placement()
    size = dev.DECAP_SIZE_UM
    gap = 2.0
    x1 = p.vdd_trunk_x - 5.0
    y0 = _shift(vtoi_core.footprint_um(), p.dx_vtoi, p.dy_vtoi)[3] - size
    first_x0 = x1 - 2 * size - gap
    return (
        (first_x0, y0, first_x0 + size, y0 + size),
        (first_x0 + size + gap, y0, x1, y0 + size),
    )


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


@dataclass
class VcoBlockResult:
    canvas: prim.Canvas
    placement: Placement
    footprint: tuple = (0.0, 0.0, 0.0, 0.0)
    sub_pins: dict = field(default_factory=dict)
    nets: dict = field(default_factory=dict)


def _center(box: tuple) -> tuple[float, float]:
    return ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)


class _Router:
    """Draws top-level Metal2 routes and proves they never crowd each other.

    Same intent as ``mirror.Plan.reserve()``: a spacing bug in a generated
    300 um-wide block is much cheaper to find as a Python exception naming the
    two nets than as one of several thousand DRC markers. Every rectangle this
    class draws is recorded; a new rectangle that comes within ``M2.2a``'s
    0.28 um of a *different* net's recorded rectangle raises.
    """

    def __init__(self, canvas: prim.Canvas) -> None:
        self.canvas = canvas
        self._boxes: list[tuple[str, float, float, float, float]] = []

    def _reserve(self, net: str, box: tuple) -> None:
        s = dev.DRC_METAL2_MIN_SPACE_UM
        x0, y0, x1, y1 = box
        for other, ox0, oy0, ox1, oy1 in self._boxes:
            if other == net:
                continue
            if x0 - s < ox1 and ox0 < x1 + s and y0 - s < oy1 and oy0 < y1 + s:
                raise ValueError(
                    f"top-level Metal2 for {net!r} and {other!r} are closer than M2.2a's "
                    f"{s} um: ({x0:.3f},{y0:.3f})-({x1:.3f},{y1:.3f}) vs "
                    f"({ox0:.3f},{oy0:.3f})-({ox1:.3f},{oy1:.3f})"
                )
        self._boxes.append((net, x0, y0, x1, y1))

    def route(self, net: str, points: list[tuple[float, float]]) -> None:
        half = M2_HALF_UM
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            if abs(y1 - y0) < 1e-9:
                box = (min(x0, x1) - half, y0 - half, max(x0, x1) + half, y0 + half)
            elif abs(x1 - x0) < 1e-9:
                box = (x0 - half, min(y0, y1) - half, x0 + half, max(y0, y1) + half)
            else:
                raise ValueError(f"non-Manhattan segment for {net!r}")
            self._reserve(net, box)
        prim.m2_route(self.canvas, points)

    def via(self, net: str, x: float, y: float) -> None:
        pad = prim.via1_stack(self.canvas, x, y)
        self._reserve(net, pad)


def build(outdir: Path | None = None) -> VcoBlockResult:
    p = placement()
    canvas = prim.Canvas(TOP_CELL)

    # --- 1. place the five sub-blocks --------------------------------------
    with canvas.at(p.dx_res, p.dy_res) as res_pins:
        bias_resistors.build(canvas=canvas)
    with canvas.at(p.dx_vtoi, p.dy_vtoi) as vtoi_pins:
        vtoi_res = vtoi_core.build(canvas=canvas)
    with canvas.at(p.dx_mirror, p.dy_mirror) as mirror_pins:
        mirror.build(canvas=canvas)
    with canvas.at(p.dx_ring, p.dy_ring) as ring_pins:
        ring_res = ring.build(canvas=canvas, draw_decap=False)
    with canvas.at(p.dx_buffer, p.dy_buffer) as buffer_pins:
        out_buffer.build(canvas=canvas)

    sub_pins = {
        "bias_resistors": res_pins,
        "vtoi_core": vtoi_pins,
        "mirror": mirror_pins,
        "ring": ring_pins,
        "buffer": buffer_pins,
    }
    r = _Router(canvas)
    boxes = p.boxes()

    def track_in(pins: dict, net: str) -> tuple[float, float]:
        """A mesh block's *input*-side pin: (track left end x, track y)."""
        box = pins[net][0]
        return (box[2], _center(box)[1])

    def track_out(pins: dict, net: str) -> tuple[float, float]:
        """A mesh block's *output*-side pin: (track right end x, track y)."""
        box = pins[net][0]
        return (box[0], _center(box)[1])

    # --- 2. bias generator: RCG/ROFF/RDEG -> the V-to-I core ---------------
    # Each route starts at the core's own track (``track_in()`` returns that
    # track's far end, so the route redraws the whole track and cannot leave a
    # gap) and runs right to the resistor's pad. NC is a straight wire by
    # construction -- placement() picked the resistor block's y offset so
    # RCG's pad lands on that track. NOFF and NVI rise through their own
    # columns; see RES_COL_*_OFFSET_UM for why NVI takes the inner one.
    nc_x, nc_y = track_in(vtoi_pins, "NC")
    nc_pad_x, nc_pad_y = _center(res_pins["NC"][0])
    r.route("NC", [(nc_x, nc_y), (nc_pad_x, nc_y)])
    r.via("NC", nc_pad_x, nc_pad_y)

    noff_x, noff_y = track_in(vtoi_pins, "NOFF")
    noff_pad_x, noff_pad_y = _center(res_pins["NOFF"][0])
    nvi_x, nvi_y = track_in(vtoi_pins, "NVI")
    nvi_pad_x, nvi_pad_y = _center(res_pins["NVI"][0])
    nvi_lane_y = dev.snap_um(nvi_pad_y + 2.1)
    r.route(
        "NOFF",
        [
            (noff_x, noff_y),
            (p.res_col_noff_x, noff_y),
            (p.res_col_noff_x, noff_pad_y),
            (noff_pad_x, noff_pad_y),
        ],
    )
    r.via("NOFF", noff_pad_x, noff_pad_y)
    r.route(
        "NVI",
        [
            (nvi_x, nvi_y),
            (p.res_col_nvi_x, nvi_y),
            (p.res_col_nvi_x, nvi_lane_y),
            (nvi_pad_x, nvi_lane_y),
            (nvi_pad_x, nvi_pad_y),
        ],
    )
    r.via("NVI", nvi_pad_x, nvi_pad_y)

    # --- 3. VBP0: the V-to-I core's summing node -> the mirror's cascade A.
    # Out on the core's *left* (the right is where the resistor risers are),
    # up the left-hand riser column, back in on the mirror's own VBP0 track.
    # The riser cannot run up inside the mirror's own width -- it would cross
    # every one of that block's horizontal Metal2 tracks -- so it takes the
    # channel outside the mirror's left edge. ---
    vbp0_y = _center(vtoi_pins["VBP0"][0])[1]
    vbp0_track_x0 = min(vtoi_res.net_x[("VBP0", 0, "pfet")]) - M2_HALF_UM + p.dx_vtoi
    vbp0_in_x, vbp0_in_y = track_in(mirror_pins, "VBP0")
    r.route(
        "VBP0",
        [
            (vbp0_track_x0, vbp0_y),
            (p.col_vbp0_x, vbp0_y),
            (p.col_vbp0_x, vbp0_in_y),
            (vbp0_in_x, vbp0_in_y),
        ],
    )

    # --- 4. VBP / VBN: the mirror's outputs -> the ring's own bias nets.
    # VBN still lands near the ring's own bottom edge (issue #371 moved its
    # own internal Metal2 trunk there, clear of the block's own guard ring
    # and of the ring's own device geometry -- see ring.py's module
    # docstring), a short straight run up from the mirror-ring gap, same
    # shape this always had. VBP's own trunk moved to the *opposite* end
    # (above the ring's own inner tap ring, issue #371 again -- nothing
    # else on Metal2 in ring.py ever reaches that high), so a straight run
    # up from the gap at the same x would run the entire height of the
    # ring block and cross VBN's own trunk near the bottom on the way --
    # this bypasses that by taking the clear routing channel *outside* the
    # ring's own left edge instead, the same "channel outside the block's
    # own width" escape this function's own VBP0 riser (step 3, above)
    # already uses for an analogous crossing. ---
    ring_ports = ring_res.stage_ports
    rail_x0 = min(q.a_gate_pad_bottom[0] for q in ring_ports) + p.dx_ring
    vbp_rail_y = _center(ring_pins["VBP"][0])[1]
    vbn_rail_y = _center(ring_pins["VBN"][0])[1]
    vbp_land_x = dev.snap_um(rail_x0 + 0.5)
    vbn_land_x = dev.snap_um(p.dx_ring + (dev.STAGE_COUNT - 1) * ring.STAGE_PITCH_UM + 4.0)
    vbp_bypass_x = dev.snap_um(boxes["ring"][0] - 1.0)

    channel_y0 = boxes["mirror"][3]
    lane_vbp_y = dev.snap_um(channel_y0 + ROW_GAP_MIRROR_TO_RING_UM * 0.32)
    lane_vbn_y = dev.snap_um(channel_y0 + ROW_GAP_MIRROR_TO_RING_UM * 0.58)

    vbp_out_x, vbp_out_y = track_out(mirror_pins, "VBP")
    r.route(
        "VBP",
        [
            (vbp_out_x, vbp_out_y),
            (p.col_vbp_x, vbp_out_y),
            (p.col_vbp_x, lane_vbp_y),
            (vbp_bypass_x, lane_vbp_y),
            (vbp_bypass_x, vbp_rail_y),
            (vbp_land_x, vbp_rail_y),
        ],
    )
    r.via("VBP", vbp_land_x, vbp_rail_y)

    vbn_out_x, vbn_out_y = track_out(mirror_pins, "VBN")
    r.route(
        "VBN",
        [
            (vbn_out_x, vbn_out_y),
            (p.col_vbn_x, vbn_out_y),
            (p.col_vbn_x, lane_vbn_y),
            (vbn_land_x, lane_vbn_y),
            (vbn_land_x, vbn_rail_y),
        ],
    )
    r.via("VBN", vbn_land_x, vbn_rail_y)

    # --- 5. Y5: the ring's stage-5 output -> the buffer's input gate ------
    y5_pad = ring_pins["Y5_CLK_IN"][0]
    y5_x, y5_y = _center(y5_pad)
    buf_in_x, buf_in_y = _center(buffer_pins[dev.BUFFER_IN_NET][0])
    lane_y5_y = dev.snap_um(boxes["ring"][3] + ROW_GAP_RING_TO_BUFFER_UM / 2.0)
    r.route(
        "Y5",
        [
            (y5_x, y5_y),
            (y5_x, lane_y5_y),
            (buf_in_x, lane_y5_y),
            (buf_in_x, buf_in_y),
        ],
    )
    r.via("Y5", y5_x, y5_y)
    r.via("Y5", buf_in_x, buf_in_y)

    # --- 6. VDD_VCO: Metal1 trunk + one Metal2 hop per sub-block onto that
    # block's own n-well tap band (see the module docstring for why the
    # supply is the one net that cannot be Metal2 all the way in). ---
    trunk_y0 = min(b[1] for b in boxes.values())
    trunk_y1 = max(b[3] for b in boxes.values())
    prim.v_wire(canvas, p.vdd_trunk_x, trunk_y0, trunk_y1, width=VDD_TRUNK_WIDTH_UM)

    def vdd_feed(pins: dict) -> float:
        """Hop from the trunk onto the topmost ``VDD_VCO`` tap band of a block."""
        band = max(pins[VDD_NET], key=lambda b: b[3])
        y = _center(band)[1]
        x = dev.snap_um(band[2] - 0.5)
        r.route(VDD_NET, [(x, y), (p.vdd_trunk_x, y)])
        r.via(VDD_NET, x, y)
        r.via(VDD_NET, p.vdd_trunk_x, y)
        return y

    vdd_pin_y = vdd_feed(vtoi_pins)
    for pins in (mirror_pins, ring_pins, buffer_pins):
        vdd_feed(pins)

    # ... and the same hop again for the block-level n-well tap ring (step 8b),
    # which is outside the GND_VCO ring and so is likewise only reachable on
    # Metal2. One feed point is enough for the whole ring: ``guard_ring()``
    # draws all four bands as one continuous Metal1 shape.
    nw_ring_x = dev.snap_um(p.nwell_tap[2] - NWELL_RING_TAP_WIDTH_UM / 2.0)
    r.route(VDD_NET, [(p.vdd_trunk_x, vdd_pin_y), (nw_ring_x, vdd_pin_y)])
    r.via(VDD_NET, nw_ring_x, vdd_pin_y)

    # --- 7. block boundary pins -------------------------------------------
    # Inputs stay on their own sub-block's track y and simply run out to the
    # left-hand pin column -- no risers, so nothing in the left channel can
    # cross anything else there.
    for pins, net in (
        (vtoi_pins, dev.VTOI_IN_NET),
        (mirror_pins, "B0"),
        (mirror_pins, "B1"),
        (mirror_pins, "B2"),
    ):
        x_in, y_in = track_in(pins, net)
        r.route(net, [(p.left_pin_x, y_in), (x_in, y_in)])
        canvas.pin(
            net,
            p.left_pin_x,
            y_in - M2_HALF_UM,
            p.left_pin_x + PIN_STUB_UM,
            y_in + M2_HALF_UM,
            layer="metal2_label",
        )

    clk_pad = buffer_pins[dev.BUFFER_OUT_NET][0]
    clk_x, clk_y = _center(clk_pad)
    r.route(dev.BUFFER_OUT_NET, [(clk_x, clk_y), (p.clk_pin_x, clk_y)])
    r.via(dev.BUFFER_OUT_NET, clk_x, clk_y)
    canvas.pin(
        dev.BUFFER_OUT_NET,
        p.clk_pin_x - PIN_STUB_UM,
        clk_y - M2_HALF_UM,
        p.clk_pin_x,
        clk_y + M2_HALF_UM,
        layer="metal2_label",
    )
    canvas.pin(
        VDD_NET,
        p.vdd_trunk_x - VDD_TRUNK_WIDTH_UM / 2.0,
        vdd_pin_y - 0.5,
        p.vdd_trunk_x + VDD_TRUNK_WIDTH_UM / 2.0,
        vdd_pin_y + 0.5,
    )

    # --- 8. block-level GND_VCO guard ring + Metal1 straps to each
    # sub-block's own ring. The bias row is strapped as a chain (block ring ->
    # resistors -> V-to-I core) because the resistor block sits between the
    # two; every other row is strapped straight to the block ring's left
    # band. Straps stay on the left, where the Metal1 supply trunk is not. ---
    prim.guard_ring(canvas, "p", *p.outer, SHARED_RING_WIDTH_UM, GND_NET)
    strap_x0 = p.outer[0] + SHARED_RING_WIDTH_UM

    def strap(x0: float, x1: float, y: float) -> None:
        prim.h_wire(canvas, x0, x1, y, width=STRAP_WIDTH_UM)

    res_box = boxes["bias_resistors"]
    vtoi_box = boxes["vtoi_core"]
    # The resistor block sits inboard of the V-to-I core, so it is strapped to
    # the core's own right band rather than to the block ring directly.
    strap(
        vtoi_box[2] - vtoi_core.RING_WIDTH_UM,
        res_box[0] + bias_resistors.RING_WIDTH_UM,
        dev.snap_um((res_box[1] + res_box[3]) / 2.0 - 4.0),
    )
    for key, ring_w in (
        ("vtoi_core", vtoi_core.RING_WIDTH_UM),
        ("mirror", mirror.RING_WIDTH_UM),
        ("ring", ring.RING_WIDTH_UM),
        ("buffer", out_buffer.RING_WIDTH_UM),
    ):
        box = boxes[key]
        strap(strap_x0, box[0] + ring_w, dev.snap_um((box[1] + box[3]) / 2.0))

    # --- 8b. block-level VDD_VCO n-well tap ring, concentric outside the
    # GND_VCO substrate ring (issue #324). ``guard_ring(kind="n")`` draws only
    # the ncomp/nplus/contact/Metal1 bands, so the n-well those bands sit in is
    # this caller's own responsibility -- drawn with ``rect_frame()`` (issue
    # #339) rather than a single filled ``rect()`` so the well is a real
    # annulus (a filled slab put every device in the block inside the well in
    # PR #333, undetected by DRC or connectivity extraction; see
    # ``rect_frame()``'s own docstring). ---
    nwr, nwt = p.nwell_ring, p.nwell_tap
    prim.rect_frame(canvas, "nwell", *nwr, NWELL_RING_WIDTH_UM)
    prim.guard_ring(canvas, "n", *nwt, NWELL_RING_TAP_WIDTH_UM, VDD_NET)

    # --- 9. carried-forward 22 pF decap, against this block's VDD_VCO pin --
    for i, box in enumerate(decap_boxes_um()):
        canvas.rect("boundary", *box)
        canvas.label("boundary", f"vco.decap{i}", box[0] + 1.0, box[1] + 1.0)

    if outdir is not None:
        outdir = Path(outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        canvas.write_gds(outdir / f"{TOP_CELL}.gds")

    return VcoBlockResult(
        canvas=canvas,
        placement=p,
        footprint=p.boundary,
        sub_pins=sub_pins,
        nets={
            "VBP_land_x": vbp_land_x,
            "VBN_land_x": vbn_land_x,
            "vdd_pin_y": vdd_pin_y,
            "nwell_ring_feed_x": nw_ring_x,
            "lane_vbp_y": lane_vbp_y,
            "lane_vbn_y": lane_vbn_y,
            "lane_y5_y": lane_y5_y,
        },
    )


# ---------------------------------------------------------------------------
# Connectivity proof
# ---------------------------------------------------------------------------
#
# DRC proves this block breaks no rule. It does *not* prove the inter-sub-block
# routes actually connect anything -- a Metal2 wire that stops 0.5 um short of
# its via1, or a via1 that lands beside a rail instead of on it, is perfectly
# DRC-clean and completely broken. Full LVS needs a block-level SPICE netlist
# and a device-recognition pass that is its own increment; what *is* available
# now, and is exactly the property this increment adds, is the metal
# connectivity: extract metal1/via1/metal2 as a connected graph and check that
# each pair of points the router claims to have joined really lands on one net
# (and that two nets which must stay apart did not merge).


CONNECTED_PROBES = (
    # (net, description, [(layer, x, y), ...]) -- every point must be one net
    ("NC", "RCG signal pad <-> V-to-I core's NC track"),
    ("NOFF", "ROFF signal pad <-> V-to-I core's NOFF track"),
    ("NVI", "RDEG signal pad <-> V-to-I core's NVI track"),
    ("VBP0", "V-to-I core summing node <-> band mirror cascade A"),
    ("VBP", "band mirror VBP output <-> ring VBP rail"),
    ("VBN", "band mirror VBN output <-> ring VBN rail"),
    ("Y5", "ring stage-5 output <-> output buffer input gate"),
    ("VDD_VCO", "supply trunk <-> four n-well tap bands + the block n-well ring"),
    ("GND_VCO", "block guard ring <-> every sub-block guard ring + bank tap strips"),
    ("CLK", "output buffer's last stage <-> the block's CLK pin"),
    ("VCTRL", "block VCTRL pin <-> V-to-I core's VCTRL track"),
    ("B0", "block B0 pin <-> band mirror's B0 track"),
    ("B1", "block B1 pin <-> band mirror's B1 track"),
    ("B2", "block B2 pin <-> band mirror's B2 track"),
)

DISTINCT_PROBES = (
    ("VDD_VCO", "GND_VCO"),
    ("VBP", "VBN"),
    ("NOFF", "NVI"),
    ("VBP0", "VBP"),
)


def _probe_points(result: VcoBlockResult) -> dict:
    """Two-or-more (layer, x, y) probe points per net the router claims to join."""
    p = result.placement
    sp = result.sub_pins
    boxes = p.boxes()

    def c(box: tuple) -> tuple[float, float]:
        return _center(box)

    pts: dict[str, list[tuple[str, float, float]]] = {}

    def add(net: str, layer: str, x: float, y: float) -> None:
        pts.setdefault(net, []).append((layer, x, y))

    for net in ("NC", "NOFF", "NVI"):
        add(net, "metal1", *c(sp["bias_resistors"][net][0]))
        add(net, "metal2", *c(sp["vtoi_core"][net][0]))
    add("VBP0", "metal2", *c(sp["vtoi_core"]["VBP0"][0]))
    add("VBP0", "metal2", *c(sp["mirror"]["VBP0"][0]))
    for net in ("VBP", "VBN"):
        add(net, "metal2", *c(sp["mirror"][net][0]))
        add(net, "metal1", *c(sp["ring"][net][0]))
    add("Y5", "metal1", *c(sp["ring"]["Y5_CLK_IN"][0]))
    add("Y5", "metal1", *c(sp["buffer"][dev.BUFFER_IN_NET][0]))
    add("VDD_VCO", "metal1", p.vdd_trunk_x, result.nets["vdd_pin_y"])
    for key in ("vtoi_core", "mirror", "ring", "buffer"):
        band = max(sp[key][VDD_NET], key=lambda b: b[3])
        add("VDD_VCO", "metal1", *c(band))
    # The block-level n-well tap ring, probed on the band *opposite* its single
    # Metal2 feed -- so the probe proves the ring is continuous all the way
    # round, not just that the feed's own via landed.
    add(
        "VDD_VCO",
        "metal1",
        p.nwell_tap[0] + NWELL_RING_TAP_WIDTH_UM / 2.0,
        (p.nwell_tap[1] + p.nwell_tap[3]) / 2.0,
    )
    add("GND_VCO", "metal1", (p.outer[0] + p.outer[2]) / 2.0, p.outer[1] + SHARED_RING_WIDTH_UM / 2.0)
    # Every substrate tap strip the band mirror's row fold added under its
    # upper bank(s) -- butted into that sub-block's own ring, so this proves
    # the butt joint really merged rather than merely abutting on paper.
    mirror_plan = mirror.plan()
    for bank in mirror_plan.banks:
        if bank.sub_tap is None:
            continue
        add(
            "GND_VCO",
            "metal1",
            (bank.sub_tap[0] + bank.sub_tap[2]) / 2.0 + p.dx_mirror,
            (bank.sub_tap[1] + bank.sub_tap[3]) / 2.0 + p.dy_mirror,
        )
    for key, ring_w in (
        ("bias_resistors", bias_resistors.RING_WIDTH_UM),
        ("vtoi_core", vtoi_core.RING_WIDTH_UM),
        ("mirror", mirror.RING_WIDTH_UM),
        ("ring", ring.RING_WIDTH_UM),
        ("buffer", out_buffer.RING_WIDTH_UM),
    ):
        box = boxes[key]
        add("GND_VCO", "metal1", (box[0] + box[2]) / 2.0, box[1] + ring_w / 2.0)
    add("CLK", "metal1", *c(sp["buffer"][dev.BUFFER_OUT_NET][0]))
    add("CLK", "metal2", *c(result.canvas.pins["CLK"][-1]))
    for net, key in (("VCTRL", "vtoi_core"), ("B0", "mirror"), ("B1", "mirror"), ("B2", "mirror")):
        add(net, "metal2", *c(sp[key][net][0]))
        add(net, "metal2", *c(result.canvas.pins[net][-1]))
    return pts


def connectivity_report(result: VcoBlockResult) -> list[tuple[str, bool, str]]:
    """Extract metal connectivity and check every routed net actually joins.

    Uses KLayout's own ``LayoutToNetlist`` connectivity extraction over
    metal1/via1/metal2 -- the same machinery the PDK's LVS deck builds on,
    restricted here to the interconnect layers (no device recognition), which
    is the part this increment is responsible for.
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

    pts = _probe_points(result)
    net_of: dict[str, object] = {}
    out: list[tuple[str, bool, str]] = []
    for net, description in CONNECTED_PROBES:
        probes = pts[net]
        found = []
        for layer, x, y in probes:
            found.append(l2n.probe_net(layers[layer], db.DPoint(x, y)))
        missing = [p for p, n in zip(probes, found) if n is None]
        if missing:
            out.append((net, False, f"{description}: no metal found at {missing}"))
            continue
        ids = {n.cluster_id for n in found}
        ok = len(ids) == 1
        net_of[net] = found[0]
        out.append(
            (
                net,
                ok,
                f"{description}: {len(probes)} probe(s) -> "
                + ("one net" if ok else f"{len(ids)} separate nets {sorted(ids)}"),
            )
        )
    for a, b in DISTINCT_PROBES:
        if a in net_of and b in net_of:
            ok = net_of[a].cluster_id != net_of[b].cluster_id
            out.append((f"{a} != {b}", ok, "distinct nets" if ok else "SHORTED together"))
    return out


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--outdir",
        default=str(Path(__file__).resolve().parents[2] / "evidence" / "vco-layout" / "work"),
    )
    parser.add_argument(
        "--check-connectivity",
        action="store_true",
        help="extract metal connectivity and verify every routed net joins (needs klayout)",
    )
    args = parser.parse_args()
    result = build(Path(args.outdir))
    x0, y0, x1, y1 = result.footprint
    print(f"wrote {args.outdir}/{TOP_CELL}.gds")
    print(f"footprint: {x1 - x0:.3f} x {y1 - y0:.3f} um  ({(x1 - x0) * (y1 - y0):.1f} um^2)")
    pl = result.placement
    for name, box in pl.boxes().items():
        print(f"  {name:<16} {box[0]:9.3f} {box[1]:9.3f} {box[2]:9.3f} {box[3]:9.3f}")
    if args.check_connectivity:
        print()
        failures = 0
        for name, ok, detail in connectivity_report(result):
            print(f"  {'ok  ' if ok else 'FAIL'} {name:<16} {detail}")
            failures += 0 if ok else 1
        print()
        print(f"connectivity: {'PASS' if failures == 0 else f'FAIL ({failures})'}")
        return 0 if failures == 0 else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
