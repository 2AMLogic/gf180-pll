"""Transistor parameter tables for ``lock_detector``, read off the schematics.

Every ``Fet`` below is transcribed directly from the committed netlist export
(``design/netlist/lock_detector.spice``, itself generated from
``design/lock_detector.sch`` + the leaf-cell schematics it instantiates --
``xor2_3v3.sch``, ``delaywin_3v3.sch``, ``nand2_3v3.sch``, ``inv_3v3.sch``,
``schmitt_3v3.sch``), never re-derived or approximated. SPICE device lines in
this PDK are ``X<name> D G S B model L=.. W=.. ...`` (gf180mcu's own
``nfet_03v3``/``pfet_03v3`` subckt pin order) -- the ``d``/``g``/``s``/``b``
fields on each ``Fet`` below are transcribed in that same D/G/S/B order so a
reviewer can diff this file against the ``.spice`` export line by line.

All devices are ``nfet_03v3``/``pfet_03v3`` -- the gf180mcu 3.3 V thick-oxide
flavour DR-002 Decision 3 mandates for this whole design (no dualgate/5V
marker layers are ever drawn by this package's primitives, see
``primitives.py``).
"""

from __future__ import annotations

from dataclasses import dataclass

#: Fixed contact size, CO.1 (min/max 0.22 um -- gf180mcu contacts are not
#: resizable, so this is a hard constant, not a derived margin).
DRC_CONTACT_SIZE_UM = 0.22


@dataclass(frozen=True)
class Fet:
    name: str
    kind: str  # "nfet" | "pfet"
    w_um: float
    l_um: float
    d: str
    g: str
    s: str
    b: str


# --- inv_3v3.sch: XMP Y A VDD VDD pfet_03v3 L=0.28u W=2.5u; XMN Y A VSS VSS nfet_03v3 L=0.28u W=1u ---
def inv_fets(prefix: str, a: str, y: str, vdd: str, vss: str) -> tuple[Fet, Fet]:
    mp = Fet(f"{prefix}MP", "pfet", 2.5, 0.28, d=y, g=a, s=vdd, b=vdd)
    mn = Fet(f"{prefix}MN", "nfet", 1.0, 0.28, d=y, g=a, s=vss, b=vss)
    return mp, mn


# --- nand2_3v3.sch ---
# XMPA Y A VDD VDD pfet_03v3 L=0.28u W=2.5u
# XMPB Y B VDD VDD pfet_03v3 L=0.28u W=2.5u
# XMNA Y A NMID VSS nfet_03v3 L=0.28u W=2u
# XMNB NMID B VSS VSS nfet_03v3 L=0.28u W=2u
def nand2_fets(prefix: str, a: str, b: str, y: str, vdd: str, vss: str) -> tuple[Fet, Fet, Fet, Fet]:
    nmid = f"{prefix}NMID"
    mpa = Fet(f"{prefix}MPA", "pfet", 2.5, 0.28, d=y, g=a, s=vdd, b=vdd)
    mpb = Fet(f"{prefix}MPB", "pfet", 2.5, 0.28, d=y, g=b, s=vdd, b=vdd)
    mna = Fet(f"{prefix}MNA", "nfet", 2.0, 0.28, d=y, g=a, s=nmid, b=vss)
    mnb = Fet(f"{prefix}MNB", "nfet", 2.0, 0.28, d=nmid, g=b, s=vss, b=vss)
    return mpa, mpb, mna, mnb


# --- schmitt_3v3.sch (classic 6T inverting CMOS Schmitt trigger) ---
# XMP1 P1 A VDD VDD pfet_03v3 L=0.28u W=2.5u
# XMP2 Y  A P1  VDD pfet_03v3 L=0.28u W=2.5u
# XMP3 VSS Y P1 VDD pfet_03v3 L=0.28u W=1.2u
# XMN1 N1 A VSS VSS nfet_03v3 L=0.28u W=1u
# XMN2 Y  A N1  VSS nfet_03v3 L=0.28u W=1u
# XMN3 VDD Y N1 VSS nfet_03v3 L=0.28u W=0.5u
def schmitt_fets(prefix: str, a: str, y: str, vdd: str, vss: str) -> tuple[Fet, ...]:
    p1 = f"{prefix}P1"
    n1 = f"{prefix}N1"
    mp1 = Fet(f"{prefix}MP1", "pfet", 2.5, 0.28, d=p1, g=a, s=vdd, b=vdd)
    mp2 = Fet(f"{prefix}MP2", "pfet", 2.5, 0.28, d=y, g=a, s=p1, b=vdd)
    mp3 = Fet(f"{prefix}MP3", "pfet", 1.2, 0.28, d=vss, g=y, s=p1, b=vdd)
    mn1 = Fet(f"{prefix}MN1", "nfet", 1.0, 0.28, d=n1, g=a, s=vss, b=vss)
    mn2 = Fet(f"{prefix}MN2", "nfet", 1.0, 0.28, d=y, g=a, s=n1, b=vss)
    mn3 = Fet(f"{prefix}MN3", "nfet", 0.5, 0.28, d=vdd, g=y, s=n1, b=vss)
    return mp1, mp2, mp3, mn1, mn2, mn3


# --- delaywin_3v3.sch's MOS-cap load: nfet_03v3, D=S=B=VSS, G=the delayed node ---
def moscap_fet(name: str, w_um: float, l_um: float, node: str, vss: str) -> Fet:
    return Fet(name, "nfet", w_um, l_um, d=vss, g=node, s=vss, b=vss)


# --- delaywin_3v3.sch's DR-014 trim network (issue #411) -------------------
# Every constant below is the *same number* ``design/gen_delaywin.py``'s own
# sizing table carries, transcribed here in the same D/G/S/B order as the
# rest of this file so a reviewer can diff both against
# ``design/netlist/lock_detector.spice``'s own ``delaywin_3v3`` subckt line
# by line. Two tables, one source of truth: that generator writes the
# schematic, the schematic is netlisted to the committed ``.spice``, and
# ``layout/tests/test_lock_detector_devices.py`` asserts this file agrees
# with that committed export device for device -- so a sizing change made in
# only one of the two places fails the test run rather than silently
# producing a layout that no longer matches its own schematic.
#
# XMB<i>   VSS  D<i>  VSS   VSS nfet_03v3 L=2u    W=6.2u          (always-on base load)
# XMSN<i><j> D<i>  T<j>  S<i><j> VSS nfet_03v3 L=0.28u W=weight*0.22u  (pass gate, N half)
# XMSP<i><j> S<i><j> T<j>B D<i>  VDD pfet_03v3 L=0.28u W=weight*0.22u  (pass gate, P half)
# XMK<i><j>  S<i><j> T<j>B VSS   VSS nfet_03v3 L=0.5u  W=weight*0.22u  (kill device)
# XMC<i><j>  VSS  S<i><j> VSS   VSS nfet_03v3 L=1u    W=weight*0.5u   (segment MOS cap)

#: Binary weights, LSB first: segment ``j`` is switched by trim bit ``Tj``
#: (``design/gen_delaywin.py``'s ``WEIGHTS``).
TRIM_WEIGHTS: tuple[int, ...] = (1, 2, 4, 8)
#: Unit trim segment: pass-gate / kill-device width, in um -- gf180mcu's 3.3 V
#: minimum width, which is why the LSB is halved in *length* rather than in
#: width (``gen_delaywin.py``'s ``W_UNIT_SW_UM``).
TRIM_W_UNIT_SW_UM = 0.22
#: Unit trim segment: MOS-cap width, in um (``W_UNIT_CAP_UM``).
TRIM_W_UNIT_CAP_UM = 0.5
#: Pass-gate length, in um (``SW_L_UM``).
TRIM_SW_L_UM = 0.28
#: Kill-device length, in um (``KILL_L_UM``).
TRIM_KILL_L_UM = 0.5
#: Segment MOS-cap length, in um -- half the always-on load's, so the unit
#: segment is half the capacitance (``CAP_L_SEG_UM``).
TRIM_CAP_L_UM = 1.0
#: Always-on per-stage MOS-cap load, in um (``W_BASE_UM`` / ``CAP_L_UM``).
BASE_CAP_W_UM = 6.2
BASE_CAP_L_UM = 2.0


def base_cap_fet(name: str, node: str, vss: str) -> Fet:
    """``XMB<i>``: the always-on per-stage MOS-cap load, D=S=B=VSS, G=``node``."""
    return moscap_fet(name, BASE_CAP_W_UM, BASE_CAP_L_UM, node, vss)


def trim_segment_fets(
    prefix: str,
    stage: int,
    j: int,
    node: str,
    seg: str,
    t: str,
    tb: str,
    vdd: str,
    vss: str,
) -> tuple[Fet, Fet, Fet, Fet]:
    """``(MSN, MSP, MK, MC)`` for one binary-weighted trim segment.

    ``stage`` is the 1-based delay-stage index and ``j`` the 0-based segment
    index, matching the schematic's own ``XMSN<stage><j>`` naming.  ``node``
    is the stage's own delayed output (``D1``-``D3``/``Y``), ``seg`` the
    segment's switched node (``S<stage><j>``), ``t``/``tb`` the trim bit and
    its complement.  Every device in the segment carries the *same* weight
    (``TRIM_WEIGHTS[j]``) so the switch's own parasitic scales with what it
    switches -- which is what keeps the code-to-delay map monotonic (DR-014;
    an unweighted switch makes code 3 slower than code 4, measured).
    """
    weight = TRIM_WEIGHTS[j]
    w_sw = weight * TRIM_W_UNIT_SW_UM
    w_cap = weight * TRIM_W_UNIT_CAP_UM
    msn = Fet(f"{prefix}MSN{stage}{j}", "nfet", w_sw, TRIM_SW_L_UM, d=node, g=t, s=seg, b=vss)
    msp = Fet(f"{prefix}MSP{stage}{j}", "pfet", w_sw, TRIM_SW_L_UM, d=seg, g=tb, s=node, b=vdd)
    mk = Fet(f"{prefix}MK{stage}{j}", "nfet", w_sw, TRIM_KILL_L_UM, d=seg, g=tb, s=vss, b=vss)
    mc = Fet(f"{prefix}MC{stage}{j}", "nfet", w_cap, TRIM_CAP_L_UM, d=vss, g=seg, s=vss, b=vss)
    return msn, msp, mk, mc


# --- lock_detector.sch's own standalone devices ---
# XMDNW VWIN WIDE VSS VSS nfet_03v3 L=0.5u W=2u   (gated pull-down)
# XMUPW VWIN VSS VDD VDD pfet_03v3 L=20u W=0.22u  (always-on weak pull-up, gate tied to VSS)
# XMCW  VSS VWIN VSS VSS nfet_03v3 L=6u W=30u     (integrating MOS cap)
def mdnw_fet(vwin: str, wide: str, vss: str) -> Fet:
    return Fet("MDNW", "nfet", 2.0, 0.5, d=vwin, g=wide, s=vss, b=vss)


def mupw_fet(vwin: str, vdd: str, vss: str) -> Fet:
    return Fet("MUPW", "pfet", 0.22, 20.0, d=vwin, g=vss, s=vdd, b=vdd)


def mcw_fet(vwin: str, vss: str) -> Fet:
    return Fet("MCW", "nfet", 30.0, 6.0, d=vss, g=vwin, s=vss, b=vss)
