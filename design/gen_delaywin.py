#!/usr/bin/env python3
"""Emit design/delaywin_3v3.sch -- the trimmed lock-detector window delay cell.

The cell is a regular 4 x (stage) x 4 x (trim segment) array; writing the
xschem source by hand would be 80+ near-identical device placements with
hand-maintained label coordinates, so it is generated from the one table of
sizes below instead. Re-run after changing a size:

    python3 design/gen_delaywin.py && ./design/netlist.sh --top lock_detector

The generated file is committed (it is the schematic; xschem opens and edits
it like any other), and this generator is committed beside it so the sizing
table stays reviewable as a table rather than as 80 scattered W= attributes.
"""

from __future__ import annotations

import os

# --- the sizing table (sim/lock-window-trim/records/ is the evidence) --------
#: Always-on MOS-capacitor load on every stage, in um (L = CAP_L_UM). Sized so
#: the trim rule's reference-condition target lands near the MIDDLE of the code
#: range at the middle of the process distribution -- i.e. so a slow part still
#: has codes below it and a fast part still has codes above it. This is a
#: centring number, not a delay number: the delay is set by the code.
W_BASE_UM = 6.2
#: Unit trim segment: MOS-cap width, in um. Segment j carries WEIGHTS[j] x this.
W_UNIT_CAP_UM = 0.5
#: Unit trim segment: pass-gate / kill-device width, in um. Scaled by the same
#: weight as the segment's own capacitor so the switch's own parasitic scales
#: with what it switches -- which is what keeps the code-to-delay map linear,
#: and therefore monotonic, in the trim code (see design/README.md).
#:
#: This is why the LSB is halved in LENGTH rather than in width: gf180mcu's
#: 3.3 V devices have a 0.22 um minimum width, so a half-width unit segment
#: (0.25 um cap) could not have a half-width switch (0.11 um) to go with it,
#: and an unweighted switch is exactly what breaks monotonicity. Halving
#: CAP_L_SEG_UM instead halves the unit capacitance with every device in the
#: array still at or above the minimum width.
W_UNIT_SW_UM = 0.22
#: Binary weights, LSB first: segment j is switched by trim bit Tj. Four bits,
#: not three: the 3-bit array measured (sim/lock-window-trim, 936 points,
#: record 20260917-180533-92bd3ee) a 4.9-6.8 % step, which leaves the
#: continuous-population spread at 1.631x against DR-013 Decision 4's 1.65x
#: -- 1.2 % of margin, less than the +1.4...7.0 % by which DR-013 measured the
#: observable window to run wider than this bare chain (delta). Halving the
#: step buys that margin back; the cost is one more static configuration pin.
WEIGHTS = (1, 2, 4, 8)
#: MOS-cap length, in um: the always-on base load.
CAP_L_UM = 2.0
#: MOS-cap length, in um: one trim segment. Half the base's, so the unit
#: segment is half the capacitance a full-length one of the same width would
#: be -- see W_UNIT_SW_UM above for why the halving is in L and not in W.
CAP_L_SEG_UM = 1.0
SW_L_UM = 0.28
KILL_L_UM = 0.5

STAGE_PITCH = 600
SEG_PITCH = 400
SEG_Y0 = 600

HEADER = """gf180-pll :: delaywin_3v3 -- the lock detector's phase-error WINDOW, trimmed.

Four 1x inverters (even count, so the block is non-inverting), each loaded by
nfet_03v3 MOS capacitors (drain = source = bulk = VSS, gate on the delayed
node). The resulting propagation delay t_win is the half-width of the lock
window: lock_detector only reacts to a phase-error pulse that is still high
t_win later, so any |phase error| < t_win is inside the window.

Each stage's load is one ALWAYS-ON capacitor plus FOUR SWITCHED SEGMENTS,
binary-weighted 1:2:4:8 and selected by the static trim code T3:T2:T1:T0 -- a
fixed, test-set process trim (DR-014), not a self-calibration loop. Raising
the code adds capacitance and widens the window; the code-to-delay map is
monotonic at every PVT corner because each segment's pass gate and kill
device are scaled by the SAME weight as the segment capacitor they switch, so
the switch's own parasitic scales with the segment rather than adding a
fixed, weight-independent step (an unweighted switch makes code 3 slower than
code 4 -- measured, not assumed).

The unit segment is HALF the length of the always-on load (1 um against
2 um), not half its width: the PDK's 3.3 V devices stop at a 0.22 um width,
which is already the LSB switch's width, so a half-width LSB could not carry
a switch scaled to it. Halving in L keeps every device in the array legal and
keeps the switch-to-capacitor ratio identical across all four segments.

Segment j is connected to the delayed node by a full transmission gate (Tj
high) and clamped to VSS by a kill device (Tj low), so a deselected segment
is a defined LOW node rather than a floating one.

The load is a MOS capacitor built from the SAME nfet_03v3 primitive as the
logic, not a MIM or poly device -- deliberately, so the window's PVT spread
rides entirely on the MOS corner axis that the default grid already sweeps,
with no independent passive corner axis to leave silently at typical
(sim/README.md "Default corner matrix"). t_win therefore tracks gate delay
over PVT rather than moving against it.

This file is GENERATED by design/gen_delaywin.py -- edit the sizing table
there, not the 80 device placements here."""


def emit() -> str:
    out = [
        "v {xschem version=3.4.7 file_version=1.2}",
        "G {}",
        "K {}",
        "V {}",
        "S {}",
        "E {}",
        "T {%s} -700 -900 0 0 0.4 0.4 {}" % HEADER,
        "C {ipin.sym} -700 0 0 0 {name=p1 lab=A}",
        "C {opin.sym} %d 0 0 0 {name=p2 lab=Y}" % (4 * STAGE_PITCH + 100),
        "C {iopin.sym} -700 200 0 0 {name=p3 lab=VDD}",
        "C {iopin.sym} -700 300 0 0 {name=p4 lab=VSS}",
    ]
    for j in range(len(WEIGHTS)):
        out.append("C {ipin.sym} -700 %d 0 0 {name=p%d lab=T%d}" % (SEG_Y0 + j * SEG_PITCH, 5 + j, j))

    # Trim-bit complement inverters, shared by all four stages.
    for j in range(len(WEIGHTS)):
        y = SEG_Y0 + j * SEG_PITCH
        out += [
            "C {inv_3v3.sym} -400 %d 0 0 {name=XIT%d}" % (y, j),
            "C {lab_pin.sym} -440 %d 0 0 {name=lt%da lab=T%d}" % (y, j, j),
            "C {lab_pin.sym} -360 %d 0 0 {name=lt%db lab=T%dB}" % (y, j, j),
            "C {lab_pin.sym} -400 %d 0 0 {name=lt%dc lab=VDD}" % (y - 40, j),
            "C {lab_pin.sym} -400 %d 0 0 {name=lt%dd lab=VSS}" % (y + 40, j),
        ]

    nodes = ["A", "D1", "D2", "D3", "Y"]
    for i in range(4):
        x = i * STAGE_PITCH
        src, dst = nodes[i], nodes[i + 1]
        tag = chr(ord("a") + i)
        # --- the delay stage itself ---
        out += [
            "C {inv_3v3.sym} %d 0 0 0 {name=XI%d}" % (x, i + 1),
            "C {lab_pin.sym} %d 0 0 0 {name=l%s1 lab=%s}" % (x - 40, tag, src),
            "C {lab_pin.sym} %d 0 0 0 {name=l%s2 lab=%s}" % (x + 40, tag, dst),
            "C {lab_pin.sym} %d -40 0 0 {name=l%s3 lab=VDD}" % (x, tag),
            "C {lab_pin.sym} %d 40 0 0 {name=l%s4 lab=VSS}" % (x, tag),
            # --- always-on base MOS cap: D=S=B=VSS, G=stage output ---
            "C {nfet_03v3.sym} %d 300 0 0 {name=MB%d model=nfet_03v3 W=%gu L=%gu nf=1 m=1}"
            % (x, i + 1, W_BASE_UM, CAP_L_UM),
            "C {lab_pin.sym} %d 300 0 0 {name=l%sb1 lab=%s}" % (x - 20, tag, dst),
            "C {lab_pin.sym} %d 270 0 0 {name=l%sb2 lab=VSS}" % (x + 20, tag),
            "C {lab_pin.sym} %d 330 0 0 {name=l%sb3 lab=VSS}" % (x + 20, tag),
            "C {lab_pin.sym} %d 300 0 0 {name=l%sb4 lab=VSS}" % (x + 20, tag),
        ]
        # --- the switched trim segments ---
        for j, weight in enumerate(WEIGHTS):
            y = SEG_Y0 + j * SEG_PITCH
            seg = "S%d%d" % (i + 1, j)
            n = "%s%d" % (tag, j)
            wsw = weight * W_UNIT_SW_UM
            wcap = weight * W_UNIT_CAP_UM
            out += [
                # pass gate, NMOS half: D=stage node, G=Tj, S=SEG, B=VSS
                "C {nfet_03v3.sym} %d %d 0 0 {name=MSN%d%d model=nfet_03v3 W=%gu L=%gu nf=1 m=1}"
                % (x, y, i + 1, j, wsw, SW_L_UM),
                "C {lab_pin.sym} %d %d 0 0 {name=l%sn1 lab=T%d}" % (x - 20, y, n, j),
                "C {lab_pin.sym} %d %d 0 0 {name=l%sn2 lab=%s}" % (x + 20, y - 30, n, dst),
                "C {lab_pin.sym} %d %d 0 0 {name=l%sn3 lab=%s}" % (x + 20, y + 30, n, seg),
                "C {lab_pin.sym} %d %d 0 0 {name=l%sn4 lab=VSS}" % (x + 20, y, n),
                # pass gate, PMOS half: D=SEG, G=TjB, S=stage node, B=VDD
                "C {pfet_03v3.sym} %d %d 0 0 {name=MSP%d%d model=pfet_03v3 W=%gu L=%gu nf=1 m=1}"
                % (x + 130, y, i + 1, j, wsw, SW_L_UM),
                "C {lab_pin.sym} %d %d 0 0 {name=l%sp1 lab=T%dB}" % (x + 110, y, n, j),
                "C {lab_pin.sym} %d %d 0 0 {name=l%sp2 lab=%s}" % (x + 150, y + 30, n, seg),
                "C {lab_pin.sym} %d %d 0 0 {name=l%sp3 lab=%s}" % (x + 150, y - 30, n, dst),
                "C {lab_pin.sym} %d %d 0 0 {name=l%sp4 lab=VDD}" % (x + 150, y, n),
                # kill device: D=SEG, G=TjB, S=B=VSS
                "C {nfet_03v3.sym} %d %d 0 0 {name=MK%d%d model=nfet_03v3 W=%gu L=%gu nf=1 m=1}"
                % (x + 260, y, i + 1, j, wsw, KILL_L_UM),
                "C {lab_pin.sym} %d %d 0 0 {name=l%sk1 lab=T%dB}" % (x + 240, y, n, j),
                "C {lab_pin.sym} %d %d 0 0 {name=l%sk2 lab=%s}" % (x + 280, y - 30, n, seg),
                "C {lab_pin.sym} %d %d 0 0 {name=l%sk3 lab=VSS}" % (x + 280, y + 30, n),
                "C {lab_pin.sym} %d %d 0 0 {name=l%sk4 lab=VSS}" % (x + 280, y, n),
                # segment MOS cap: D=S=B=VSS, G=SEG
                "C {nfet_03v3.sym} %d %d 0 0 {name=MC%d%d model=nfet_03v3 W=%gu L=%gu nf=1 m=1}"
                % (x + 390, y, i + 1, j, wcap, CAP_L_SEG_UM),
                "C {lab_pin.sym} %d %d 0 0 {name=l%sc1 lab=%s}" % (x + 370, y, n, seg),
                "C {lab_pin.sym} %d %d 0 0 {name=l%sc2 lab=VSS}" % (x + 410, y - 30, n),
                "C {lab_pin.sym} %d %d 0 0 {name=l%sc3 lab=VSS}" % (x + 410, y + 30, n),
                "C {lab_pin.sym} %d %d 0 0 {name=l%sc4 lab=VSS}" % (x + 410, y, n),
            ]
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "delaywin_3v3.sch")
    with open(path, "w") as fh:
        fh.write(emit())
    print("wrote %s" % path)
