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
