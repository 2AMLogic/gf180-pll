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

Scope note (issue #293): this module only carries the devices this pass's
layout actually draws -- the 5-stage current-starved ring
(``vco_stage.sch`` x5) plus its own guard ring and the carried-forward
22 pF decap. The bias generator (``vco_bias.sch``), the 3-cascade
band-select mirror, and the 3-stage output buffer are explicitly deferred
to follow-up issues (see ``ring.py``'s module docstring) -- their device
tables are not duplicated here.
"""

from __future__ import annotations

from dataclasses import dataclass


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
