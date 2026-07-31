v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
T {cp_dumpbuf - dump-node tracking buffer: complementary pair of unity-gain 5T OTAs} 100 -60 0 0 0.3 0.3 {layer=8}
T {* Holds the charge pump's shared dump node VDUMP at the control-node voltage
* VREF, so that a steering switch closing sees NO step between the tail it was
* holding and the node it is being connected to.
*
* WHY THIS EXISTS.  The charge pump's dominant error is not current mismatch
* (worst systematic DC mismatch is about 5 %).  It is the tail-node charge
* exchange: when a steering switch closes, the tail node it was parked on is
* dragged from the dump-node voltage to the control-node voltage, and that
* charge -- (C_tail)*(Vctrl - Vdump) -- comes out of the control node once per
* reference cycle.  Both polarities' tails move in the SAME direction, so the
* two errors add rather than cancel, and the residue appears as an effective
* UP/DN pulse-width skew proportional to (Vdump - Vctrl): about -14.4 ns per
* volt of (Vctrl - Vdump) at the nominal trim code.  The diode clamp this cell
* replaces parked VDUMP at a FIXED 1.487 V, so the error nulled only at one
* control voltage and reached -19.4 ns at the top of the 0.9-2.4 V window
* (sim/cp-compliance record 20260731-122451-63e4b47).  Re-centring that clamp
* cannot fix it: the null was already near mid-window, so the best a re-centre
* buys is about 20 % on the worst case, and it makes the low end worse.  Making
* the dump node TRACK Vctrl removes the term instead of re-balancing it, and
* is the textbook answer.  DR-005 settles that this bias helper is compatible
* with DR-001 Decision 1's no-opamp-in-the-loop-path constraint.
*
* TOPOLOGY, and why two amplifiers rather than one.  A single differential pair
* cannot cover the whole 0.9-2.4 V window on a 2.97 V worst-case rail: an
* NMOS-input pair runs out of tail headroom at the bottom (Vin - Vgs must stay
* above the tail device's Vdsat) and a PMOS-input pair runs out at the top.
* So this cell is TWO five-transistor OTAs, each in unity-gain feedback on the
* same node, with their outputs tied together:
*
*   MTN/MN1/MN2/MN3/MN4  NMOS input pair, PMOS mirror load  -- covers the top
*   MTP/MP1/MP2/MP3/MP4  PMOS input pair, NMOS mirror load  -- covers the bottom
*
* MN1/MP1 sense VREF, MN2/MP2 sense VDUMP, and the drain of MN2/MP2 IS VDUMP,
* which is what closes each unity-gain loop.  Where the two overlap they simply
* work in parallel (the node sees the sum of the two transconductances); at
* either extreme the out-of-range amplifier's tail collapses, its mirror diode
* pulls the mirror node to its own rail and its output device turns off, so it
* goes high-impedance rather than fighting.  Neither internal drain node is
* ever floating -- each is diode-clamped to a rail through its own mirror
* diode -- so the DC operating point is well defined at every corner.
*
* SIZING.
* - Tails MTN (16u/1u off VBN) and MTP (48u/1u off VBP) mirror 4 unit currents
*   each, about 8 uA, from the same 4x-scaled bias diodes the legs use.  That
*   is not chosen for speed alone: the output drive of a 5T OTA is its tail
*   current, and the buffer must be able to HOLD the dump node while one
*   polarity is asserted on its own and the other is dumping its full Icp into
*   VDUMP.  Sized to exceed the largest trim code's Icp (7.2 uA), so a
*   persistently one-sided PFD state -- which is exactly what acquisition looks
*   like -- cannot collapse the node.  A 2-unit (4 uA) version was built and
*   measured first: it nulls the skew just as well in the locked case but lets
*   the node sag under a one-sided load and settles too slowly afterwards.
* - Input pairs are WIDE (16u/1u N, 48u/1u P) and run in weak/moderate
*   inversion.  High gm does two things at once here: it keeps the residual
*   input offset -- which is exactly the residual Vdump-Vctrl error, and hence
*   the residual skew -- in the millivolt range against the mirror's
*   channel-length-modulation error, and it lowers Vgs, which is what buys each
*   pair its share of the input range.  L = 1u everywhere for matching and
*   output resistance, as in the mirror legs.
* - Mirror loads are 1:1 (MN3:MN4, MP3:MP4).  A ratioed load would buy output
*   drive at the price of a systematic input offset, and the input offset is
*   the error this cell exists to remove.
* - MP1/MP2 have their bulk tied to their common source PSRC rather than to
*   VDD: removing the body effect on the input pair recovers input range at the
*   top of the window.  MN1/MN2 cannot do the same -- there is no isolated
*   p-well for nfet_03v3 -- which is part of why the PMOS-input amplifier is
*   the one carrying the bottom of the range.
*
* WHAT IT COSTS, honestly.
* - About 16 uA of static current (two 8 uA tails), roughly 3x the nominal Icp,
*   or ~53 uW.  Negligible against the block budget, but it is not free.
* - Two gates (MN1, MP1) now sit on the control node: about 64 um^2 of gate
*   area, ~0.3 pF, against a loop-filter C1 in the hundred-pF range.  That is a
*   0.2 % perturbation of the filter, but it is also a charge path: while the
*   amplifier's own source nodes are slewing, their Cgs pulls current from the
*   control node.  It is an OFFSET, not a gain term -- the excursion does not
*   grow with pulse width -- and it is inside the measured charge in both
*   sim/cp-compliance and sim/pfd-deadzone rather than argued away.} 1900 -300 0 0 0.25 0.25 {layer=8}
C {symbols/nfet_03v3.sym} 300 -300 0 0 {name=MTN
L=1u
W=16u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {devices/lab_pin.sym} 320 -330 0 0 {name=l_MTN_D lab=NSRC}
C {devices/lab_pin.sym} 280 -300 0 0 {name=l_MTN_G lab=VBN}
C {devices/lab_pin.sym} 320 -270 0 0 {name=l_MTN_S lab=VSS}
C {devices/lab_pin.sym} 320 -300 0 0 {name=l_MTN_B lab=VSS}
T {MTN} 260 -355 0 0 0.25 0.25 {layer=15}
C {symbols/nfet_03v3.sym} 560 -300 0 0 {name=MN1
L=1u
W=16u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {devices/lab_pin.sym} 580 -330 0 0 {name=l_MN1_D lab=NDA}
C {devices/lab_pin.sym} 540 -300 0 0 {name=l_MN1_G lab=VREF}
C {devices/lab_pin.sym} 580 -270 0 0 {name=l_MN1_S lab=NSRC}
C {devices/lab_pin.sym} 580 -300 0 0 {name=l_MN1_B lab=VSS}
T {MN1} 520 -355 0 0 0.25 0.25 {layer=15}
C {symbols/nfet_03v3.sym} 820 -300 0 0 {name=MN2
L=1u
W=16u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {devices/lab_pin.sym} 840 -330 0 0 {name=l_MN2_D lab=VDUMP}
C {devices/lab_pin.sym} 800 -300 0 0 {name=l_MN2_G lab=VDUMP}
C {devices/lab_pin.sym} 840 -270 0 0 {name=l_MN2_S lab=NSRC}
C {devices/lab_pin.sym} 840 -300 0 0 {name=l_MN2_B lab=VSS}
T {MN2} 780 -355 0 0 0.25 0.25 {layer=15}
C {symbols/pfet_03v3.sym} 1080 -300 0 0 {name=MN3
L=1u
W=24u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {devices/lab_pin.sym} 1100 -270 0 0 {name=l_MN3_D lab=NDA}
C {devices/lab_pin.sym} 1060 -300 0 0 {name=l_MN3_G lab=NDA}
C {devices/lab_pin.sym} 1100 -330 0 0 {name=l_MN3_S lab=VDD}
C {devices/lab_pin.sym} 1100 -300 0 0 {name=l_MN3_B lab=VDD}
T {MN3} 1040 -355 0 0 0.25 0.25 {layer=15}
C {symbols/pfet_03v3.sym} 1340 -300 0 0 {name=MN4
L=1u
W=24u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {devices/lab_pin.sym} 1360 -270 0 0 {name=l_MN4_D lab=VDUMP}
C {devices/lab_pin.sym} 1320 -300 0 0 {name=l_MN4_G lab=NDA}
C {devices/lab_pin.sym} 1360 -330 0 0 {name=l_MN4_S lab=VDD}
C {devices/lab_pin.sym} 1360 -300 0 0 {name=l_MN4_B lab=VDD}
T {MN4} 1300 -355 0 0 0.25 0.25 {layer=15}
C {symbols/pfet_03v3.sym} 300 -520 0 0 {name=MTP
L=1u
W=48u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {devices/lab_pin.sym} 320 -490 0 0 {name=l_MTP_D lab=PSRC}
C {devices/lab_pin.sym} 280 -520 0 0 {name=l_MTP_G lab=VBP}
C {devices/lab_pin.sym} 320 -550 0 0 {name=l_MTP_S lab=VDD}
C {devices/lab_pin.sym} 320 -520 0 0 {name=l_MTP_B lab=VDD}
T {MTP} 260 -575 0 0 0.25 0.25 {layer=15}
C {symbols/pfet_03v3.sym} 560 -520 0 0 {name=MP1
L=1u
W=48u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {devices/lab_pin.sym} 580 -490 0 0 {name=l_MP1_D lab=PDA}
C {devices/lab_pin.sym} 540 -520 0 0 {name=l_MP1_G lab=VREF}
C {devices/lab_pin.sym} 580 -550 0 0 {name=l_MP1_S lab=PSRC}
C {devices/lab_pin.sym} 580 -520 0 0 {name=l_MP1_B lab=PSRC}
T {MP1} 520 -575 0 0 0.25 0.25 {layer=15}
C {symbols/pfet_03v3.sym} 820 -520 0 0 {name=MP2
L=1u
W=48u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {devices/lab_pin.sym} 840 -490 0 0 {name=l_MP2_D lab=VDUMP}
C {devices/lab_pin.sym} 800 -520 0 0 {name=l_MP2_G lab=VDUMP}
C {devices/lab_pin.sym} 840 -550 0 0 {name=l_MP2_S lab=PSRC}
C {devices/lab_pin.sym} 840 -520 0 0 {name=l_MP2_B lab=PSRC}
T {MP2} 780 -575 0 0 0.25 0.25 {layer=15}
C {symbols/nfet_03v3.sym} 1080 -520 0 0 {name=MP3
L=1u
W=16u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {devices/lab_pin.sym} 1100 -550 0 0 {name=l_MP3_D lab=PDA}
C {devices/lab_pin.sym} 1060 -520 0 0 {name=l_MP3_G lab=PDA}
C {devices/lab_pin.sym} 1100 -490 0 0 {name=l_MP3_S lab=VSS}
C {devices/lab_pin.sym} 1100 -520 0 0 {name=l_MP3_B lab=VSS}
T {MP3} 1040 -575 0 0 0.25 0.25 {layer=15}
C {symbols/nfet_03v3.sym} 1340 -520 0 0 {name=MP4
L=1u
W=16u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {devices/lab_pin.sym} 1360 -550 0 0 {name=l_MP4_D lab=VDUMP}
C {devices/lab_pin.sym} 1320 -520 0 0 {name=l_MP4_G lab=PDA}
C {devices/lab_pin.sym} 1360 -490 0 0 {name=l_MP4_S lab=VSS}
C {devices/lab_pin.sym} 1360 -520 0 0 {name=l_MP4_B lab=VSS}
T {MP4} 1300 -575 0 0 0.25 0.25 {layer=15}
C {devices/ipin.sym} 100 -100 0 0 {name=P0 lab=VREF}
C {devices/ipin.sym} 100 -120 0 0 {name=P1 lab=VBN}
C {devices/ipin.sym} 100 -140 0 0 {name=P2 lab=VBP}
C {devices/iopin.sym} 100 -160 0 0 {name=P3 lab=VDUMP}
C {devices/iopin.sym} 100 -180 0 0 {name=P4 lab=VDD}
C {devices/iopin.sym} 100 -200 0 0 {name=P5 lab=VSS}
