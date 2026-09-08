"""Pure-Python device data for the VCO block -- no ``klayout`` import.

Every number here is read directly off ``design/netlist/vco.spice`` (the
frozen export of ``vco.sch`` / ``vco_stage.sch`` / ``vco_bias.sch``), not
re-derived: this module is the single place the layout generator (and its
tests) get "what has to be built" from, so a schematic change shows up here
as an explicit diff rather than a silent re-guess. Keeping it import-light
(stdlib ``dataclasses`` only) means ``layout/tests/test_vco_layout.py`` can
check the layout's own claims about what it built against these numbers
without needing a KLayout-capable Python (same convention as
``floorplan/skeleton.py`` / ``layout/tests/test_floorplan_skeleton.py``).

Scope note (issue #293, cumulative): the tables here grow one increment at a
time as ``#293``'s own acceptance-criteria checklist is worked through.

* PR #305 added ``STAGE_FETS`` (the 5-stage current-starved ring) plus the
  carried-forward 22 pF decap constants.
* PR #313 added ``BUFFER_STAGES`` (``vco.sch``'s 3-stage tapered output
  buffer) and ``MIRROR_*`` (``vco_bias.sch``'s 3-cascade band-select mirror,
  its band-code inverters, and its switch muxes).
* This increment adds ``PolyResistor``/``BIAS_RESISTORS`` (``vco_bias.sch``'s
  ``RCG``/``ROFF``/``RDEG``, the three ``ppolyf_u_3k`` poly resistors that
  were the named reason the V-to-I core stayed undrawn -- see
  ``primitives.poly_resistor()``'s own module-level constant block for the
  PDK-generator citation).
* Still absent, deliberately: the V-to-I core's *transistors*
  (``MP1``/``MP2``/``MN1``/``MN2``/``MSU1``-``MSU3``/``MPR``/``MD1``/
  ``MD2``/``MOFF``/``MVI``/``MSUM``) and the inter-sub-block wiring that
  merges ring + bias generator + mirror + buffer under one shared guard
  ring -- see ``bias_resistors.py``'s module docstring for why proving the
  new poly-resistor primitive stayed a standalone slice rather than being
  folded into a full V-to-I core assembly in the same increment.
"""

from __future__ import annotations

from dataclasses import dataclass

LAYOUT_GRID_UM = 0.005
"""Manufacturing grid every drawn vertex must land on.

``$PDK_ROOT/libs.tech/klayout/drc/rule_decks/geom.drc``'s OFFGRID section
runs ``<layer>.ongrid(0.005)`` on every drawn layer when ``run_drc.py`` is
invoked without ``--no_offgrid`` -- which is how this repo runs it (see
``layout/run_pv.py drc --offgrid``). A generator that computes a midpoint or
divides a width by a finger count will land off this grid routinely, so
``primitives.Canvas`` snaps every coordinate to it and ``snap_um()`` below
lets the pure-Python placement math agree with what is actually drawn.
"""


def snap_um(v: float) -> float:
    """Round ``v`` to the nearest manufacturing-grid point."""
    return round(round(v / LAYOUT_GRID_UM) * LAYOUT_GRID_UM, 6)


@dataclass(frozen=True)
class Fet:
    """One ``nfet_03v3`` / ``pfet_03v3`` instance, sized in microns."""

    name: str
    kind: str  # "nfet" or "pfet"
    w_um: float
    l_um: float
    gate_net: str
    top_net: str  # the "upper" S/D terminal in the stage's vertical stack
    bottom_net: str  # the "lower" S/D terminal
    nf: int = 1  # the frozen netlist's own ``nf=`` parameter
    layout_nf: int | None = None  # fingers actually drawn; ``None`` => ``nf``

    @property
    def fingers(self) -> int:
        return self.nf if self.layout_nf is None else self.layout_nf

    @property
    def finger_w_um(self) -> float:
        """Per-finger drawn width, snapped to the manufacturing grid.

        Three of ``vco_bias.sch``'s band-mirror legs have a schematic ``W``
        that is not an exact multiple of ``LAYOUT_GRID_UM`` once divided by
        the finger count (``17.225/2``, ``8.6125/2``, ``78.87/8``), so the
        drawn per-finger width is the nearest grid point and the drawn leg
        width differs from the schematic by at most half a grid step per
        finger. ``w_deviation_frac`` quantifies that; the tests bound it.
        """
        return snap_um(self.w_um / self.fingers)

    @property
    def drawn_w_um(self) -> float:
        """Total width actually drawn: ``fingers * finger_w_um``."""
        return round(self.fingers * self.finger_w_um, 6)

    @property
    def w_deviation_frac(self) -> float:
        return abs(self.drawn_w_um - self.w_um) / self.w_um


# vco_stage.sch, .subckt vco_stage A Y VDD VSS VBP VBN -- one current-starved
# inverter delay cell. Netlist order below matches design/netlist/vco.spice's
# XMPH/XMP/XMN/XMNT device lines exactly (W/L only; nf=1 for all four).
#
# Vertical stack per stage, VDD (top) to VSS (bottom) -- see ring.py for why
# this is drawn as a literal top-to-bottom chain:
#   VDD -- MPH(head, pfet) -- NH -- MP(switch, pfet) -- Y
#                                                          |
#   VSS -- MNT(tail, nfet) -- NT -- MN(switch, nfet) ---- Y
STAGE_FETS = (
    Fet("MPH", "pfet", w_um=10.0, l_um=0.5, gate_net="VBP", top_net="VDD", bottom_net="NH"),
    Fet("MP", "pfet", w_um=5.0, l_um=0.28, gate_net="A", top_net="NH", bottom_net="Y"),
    Fet("MN", "nfet", w_um=2.0, l_um=0.28, gate_net="A", top_net="Y", bottom_net="NT"),
    Fet("MNT", "nfet", w_um=4.0, l_um=0.5, gate_net="VBN", top_net="NT", bottom_net="VSS"),
)

STAGE_COUNT = 5  # DR-003 Decision 2: fixed at 5, no fallback to 3 or 7.

# vco.sch's committed 22 pF decap: 2x cap_nmos_03v3, 50x50 um (unchanged from
# layout/floorplan/skeleton.py's VCO_DECAP_0/1 -- carried forward, not redrawn).
DECAP_COUNT = 2
DECAP_SIZE_UM = 50.0

# --- Design-rule constants (gf180mcuD, nfet_03v3/pfet_03v3 = the "_LV"
# rule class -- see layout/pll_top/vco/primitives.py's module docstring for
# the rule-file citations). Every constant below is the PDK's own minimum;
# the generator in primitives.py adds margin on top of these, not exactly
# these values, so a rounding slip does not sit exactly on the DRC boundary.
DRC_COMP_MIN_SPACE_UM = 0.28  # DF.3a_LV
DRC_COMP_EXTEND_GATE_UM = 0.24  # DF.6_LV
DRC_POLY_GATE_LEN_MIN_UM = 0.28  # PL.2_LV
DRC_POLY_ENDCAP_UM = 0.22  # PL.4_LV
DRC_POLY_FIELD_TO_COMP_UM = 0.1  # PL.5a/b_LV
DRC_CONTACT_SIZE_UM = 0.22  # CO.1
DRC_CONTACT_SPACE_UM = 0.25  # CO.2a
DRC_CONTACT_POLY_ENCLOSE_UM = 0.07  # CO.3
DRC_CONTACT_COMP_ENCLOSE_UM = 0.07  # CO.4
DRC_CONTACT_TO_GATE_POLY_UM = 0.15  # CO.7
DRC_POLY_CONTACT_TO_COMP_UM = 0.17  # CO.8
DRC_NPLUS_MIN_WIDTH_UM = 0.4  # NP.1 / PP.1
DRC_IMPLANT_GATE_ENCLOSE_UM = 0.23  # NP.5a / PP.5a
DRC_IMPLANT_COMP_EXTEND_UM = 0.16  # NP.5b / PP.5b (comp inside/outside its own well)
DRC_NWELL_PCOMP_ENCLOSE_UM = 0.43  # DF.4c_LV
DRC_NWELL_NCOMP_ENCLOSE_UM = 0.12  # DF.4d_LV (n-well tap)
DRC_NWELL_TO_NCOMP_OUT_UM = 0.43  # DF.16_LV (nwell edge to NMOS comp outside it)
DRC_NWELL_MIN_WIDTH_UM = 0.86  # NW.1a_LV
DRC_TAP_PITCH_MAX_UM = 15.0  # DF.13_MV/DF.14_MV -- PLL-FLOORPLAN.md's own bound
DRC_METAL1_MIN_WIDTH_UM = 0.23  # M1.1
DRC_METAL1_MIN_SPACE_UM = 0.23  # M1.2a
DRC_METAL1_MIN_AREA_UM2 = 0.1444  # M1.3
DRC_METAL2_MIN_WIDTH_UM = 0.28  # M2.1
DRC_METAL2_MIN_SPACE_UM = 0.28  # M2.2a
DRC_METAL2_MIN_AREA_UM2 = 0.1444  # M2.3
DRC_VIA1_SIZE_UM = 0.26  # V1.1 (min *and* max -- via1 is exactly 0.26 um square)
DRC_VIA1_MIN_SPACE_UM = 0.26  # V1.2a
DRC_VIA1_EOL_METAL_WIDTH_UM = 0.34  # V1.3c / V1.4b apply only to metal < 0.34 um wide


# ---------------------------------------------------------------------------
# vco.sch top level: the 3-stage tapered output buffer (Y5 -> NB1 -> NB2 ->
# CLK). Read off design/netlist/vco.spice's XMBP1/XMBN1 .. XMBP3/XMBN3 lines;
# every device is nf=1, L=0.28 um. PLL-FLOORPLAN.md section 1 requires the
# largest/fastest stage to sit closest to the CLK pin and farthest from the
# ring's starved internal nodes, which is why BUFFER_STAGES is ordered
# smallest-first and buffer.py places it left-to-right in that order with CLK
# on the right edge.
#
# vco.sch's own supply nets for these devices are VDD_VCO/GND_VCO directly
# (they are top-level `vco` devices, not inside a subcircuit), so the net
# names here are the block-boundary names verbatim.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InverterStage:
    """One CMOS inverter: a pfet over an nfet sharing gate and drain nets."""

    index: int
    pfet: Fet
    nfet: Fet

    @property
    def in_net(self) -> str:
        return self.pfet.gate_net

    @property
    def out_net(self) -> str:
        return self.pfet.bottom_net

    @property
    def max_w_um(self) -> float:
        return max(self.pfet.w_um, self.nfet.w_um)


BUFFER_STAGES = (
    InverterStage(
        index=1,
        pfet=Fet("MBP1", "pfet", 1.25, 0.28, "Y5", "VDD_VCO", "NB1"),
        nfet=Fet("MBN1", "nfet", 0.5, 0.28, "Y5", "NB1", "GND_VCO"),
    ),
    InverterStage(
        index=2,
        pfet=Fet("MBP2", "pfet", 3.75, 0.28, "NB1", "VDD_VCO", "NB2"),
        nfet=Fet("MBN2", "nfet", 1.5, 0.28, "NB1", "NB2", "GND_VCO"),
    ),
    InverterStage(
        index=3,
        pfet=Fet("MBP3", "pfet", 11.25, 0.28, "NB2", "VDD_VCO", "CLK"),
        nfet=Fet("MBN3", "nfet", 4.5, 0.28, "NB2", "CLK", "GND_VCO"),
    ),
)

BUFFER_IN_NET = "Y5"  # the ring's own pre-buffer output pin (ring.py: "Y5_CLK_IN")
BUFFER_OUT_NET = "CLK"


# ---------------------------------------------------------------------------
# vco_bias.sch: the 3-cascade band-select mirror.
#
# Read off design/netlist/vco.spice's `.subckt vco_bias` device lines. The
# subcircuit's own supply pins are VDD/VSS; vco.sch binds them to
# VDD_VCO/GND_VCO (`XBIAS VCTRL B0 B1 B2 VBP VBN VDD_VCO GND_VCO vco_bias`),
# so the block-boundary names are used directly here -- same convention as
# BUFFER_STAGES above and as ring.py's own pin names.
#
# Signal chain, as instantiated: VBP0 (the V-to-I core's summing node, an
# input pin of *this* sub-block until that core is drawn) -> cascade A ->
# VBN1 -> cascade B -> VBP2 -> cascade C -> VBN -> the VBN/VBP output pair
# the ring's own VBP/VBN pins consume.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CascadePair:
    """One band-select cascade: an always-on leg + its band-switched leg.

    PLL-FLOORPLAN.md section 1: "The three cascades ... are each a
    common-centroid pair (always-on leg interdigitated with its switched
    leg), not three separate blobs". ``pattern`` is the left-to-right drawn
    finger order ("A" = a finger of ``always_on``, "S" = a finger of
    ``switched``) and MUST be a palindrome -- that is what makes both legs'
    finger centroids coincide with the array's own centre regardless of the
    two legs' different finger widths (see ``mirror.py``).
    """

    name: str
    always_on: Fet
    switched: Fet
    pattern: tuple[str, ...]

    @property
    def kind(self) -> str:
        return self.always_on.kind

    def finger_widths(self) -> tuple[float, ...]:
        a, s = self.always_on.finger_w_um, self.switched.finger_w_um
        return tuple(a if tag == "A" else s for tag in self.pattern)


# Cascade A: pfet 26.5 / 17.225 um (PLL-FLOORPLAN.md section 1). Both legs are
# nf=2 in the frozen netlist, so ABBA interdigitation uses the schematic's own
# finger count with no layout-side folding.
CASCADE_A = CascadePair(
    name="A",
    always_on=Fet("MA0", "pfet", 26.5, 1.0, "VBP0", "VDD_VCO", "VBN1", nf=2),
    switched=Fet("MA1", "pfet", 17.225, 1.0, "GA", "VDD_VCO", "VBN1", nf=2),
    pattern=("A", "S", "S", "A"),
)

# Cascade B: nfet 5 / 8.6125 um. Both legs are nf=1 in the frozen netlist, and
# two single-finger devices cannot be interdigitated at all -- a one-finger
# leg's centroid is its own centre, which can never coincide with a different
# one-finger leg's centre. This is the only cascade where the drawn finger
# count deviates from the netlist's `nf`: each leg is folded 1 -> 2 fingers of
# exactly half the schematic W (2.5 um and 4.30625 um), so total W, L and
# device count are preserved exactly and ABBA becomes possible. Recorded here
# rather than silently in the generator because it is a real (if small)
# layout-vs-netlist parameter deviation for the future LVS increment.
CASCADE_B = CascadePair(
    name="B",
    always_on=Fet("MB0", "nfet", 5.0, 1.0, "VBN1", "VBP2", "GND_VCO", nf=1, layout_nf=2),
    switched=Fet("MB1", "nfet", 8.6125, 1.0, "GB", "VBP2", "GND_VCO", nf=1, layout_nf=2),
    pattern=("A", "S", "S", "A"),
)

# Cascade C: pfet 12.3 / 78.87 um -- the 6.4:1 ratio DR-003 calls out as the
# whole point of cascading. MC1 is nf=8 and MC0 is nf=1 in the netlist, which
# already admits a palindromic pattern with no folding: the single MC0 finger
# sits at the array's centre (its centroid *is* the centre) with MC1's eight
# fingers split 4/4 symmetrically around it.
CASCADE_C = CascadePair(
    name="C",
    always_on=Fet("MC0", "pfet", 12.3, 1.0, "VBP2", "VDD_VCO", "VBN", nf=1),
    switched=Fet("MC1", "pfet", 78.87, 1.0, "GC", "VDD_VCO", "VBN", nf=8),
    pattern=("S", "S", "S", "S", "A", "S", "S", "S", "S"),
)

MIRROR_CASCADES = (CASCADE_A, CASCADE_B, CASCADE_C)


@dataclass(frozen=True)
class SwitchMux:
    """A cascade's 2-transistor band mux driving its switched leg's gate.

    ``on`` conducts when the band bit selects the leg (gate = the *inverted*
    band bit for a pfet mux, the true bit for an nfet mux) and pulls the
    switched leg's gate to the cascade's own bias node; ``off`` parks it at
    the rail that turns the leg fully off.
    """

    cascade: str
    out_net: str  # the switched leg's gate net (GA / GB / GC)
    on: Fet
    off: Fet


MIRROR_MUXES = (
    SwitchMux(
        cascade="A",
        out_net="GA",
        on=Fet("MSWA0", "pfet", 2.0, 0.5, "B0B", "VBP0", "GA"),
        off=Fet("MSWA1", "pfet", 2.0, 0.5, "B0", "VDD_VCO", "GA"),
    ),
    SwitchMux(
        cascade="B",
        out_net="GB",
        on=Fet("MSWB0", "nfet", 2.0, 0.5, "B1", "GB", "VBN1"),
        off=Fet("MSWB1", "nfet", 2.0, 0.5, "B1B", "GB", "GND_VCO"),
    ),
    SwitchMux(
        cascade="C",
        out_net="GC",
        on=Fet("MSWC0", "pfet", 2.0, 0.5, "B2B", "VBP2", "GC"),
        off=Fet("MSWC1", "pfet", 2.0, 0.5, "B2", "VDD_VCO", "GC"),
    ),
)

# Diode-connected loads / the VBN->VBP output mirror (XMDA/XMDB/XMDN/XMMN/XMDP).
MIRROR_LOADS = (
    Fet("MDA", "nfet", 10.0, 1.0, "VBN1", "VBN1", "GND_VCO"),
    Fet("MDB", "pfet", 20.0, 1.0, "VBP2", "VDD_VCO", "VBP2"),
    Fet("MDN", "nfet", 4.0, 0.5, "VBN", "VBN", "GND_VCO"),
    Fet("MMN", "nfet", 4.0, 0.5, "VBN", "VBP", "GND_VCO"),
    Fet("MDP", "pfet", 10.0, 0.5, "VBP", "VDD_VCO", "VBP"),
)

# Band-code inverters (XMIP0/XMIN0 .. XMIP2/XMIN2) -- B<n> -> B<n>B.
MIRROR_INVERTERS = tuple(
    InverterStage(
        index=i,
        pfet=Fet(f"MIP{i}", "pfet", 2.0, 0.28, f"B{i}", "VDD_VCO", f"B{i}B"),
        nfet=Fet(f"MIN{i}", "nfet", 1.0, 0.28, f"B{i}", f"B{i}B", "GND_VCO"),
    )
    for i in range(3)
)

MIRROR_IN_NETS = ("VBP0", "B0", "B1", "B2")
MIRROR_OUT_NETS = ("VBP", "VBN")


# ---------------------------------------------------------------------------
# vco_bias.sch's V-to-I core: the three ppolyf_u_3k poly resistors
# (XRCG/XROFF/XRDEG), read directly off design/netlist/vco.spice's own
# `r_width=`/`r_length=` parameters. All three tie their "P" terminal and
# bulk to VSS (=GND_VCO at the vco.sch block boundary, same binding every
# other bias-generator device in this file already uses); "M" is the
# resistor's own signal-carrying node.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PolyResistor:
    """One ``ppolyf_u_3k`` poly resistor instance, sized in microns.

    ``w_um`` is PRES.1's own "width" (perpendicular to current flow, >= the
    rule's 0.8 um minimum); ``l_um`` is the resistor's length (the
    current-flow axis) -- see ``primitives.poly_resistor()``'s own docstring
    for the drawn geometry these two numbers drive.
    """

    name: str
    w_um: float
    l_um: float
    top_net: str  # the resistor's own signal node ("M" terminal)
    bottom_net: str  # VSS/GND_VCO ("P" terminal, tied with the bulk)


# XRCG NC VSS VSS ppolyf_u_3k r_width=1u r_length=5.6u
BIAS_R_RCG = PolyResistor("RCG", w_um=1.0, l_um=5.6, top_net="NC", bottom_net="GND_VCO")
# XROFF NOFF VSS VSS ppolyf_u_3k r_width=1u r_length=33u
BIAS_R_ROFF = PolyResistor("ROFF", w_um=1.0, l_um=33.0, top_net="NOFF", bottom_net="GND_VCO")
# XRDEG NVI VSS VSS ppolyf_u_3k r_width=1u r_length=33u
BIAS_R_RDEG = PolyResistor("RDEG", w_um=1.0, l_um=33.0, top_net="NVI", bottom_net="GND_VCO")

BIAS_RESISTORS = (BIAS_R_RCG, BIAS_R_ROFF, BIAS_R_RDEG)
