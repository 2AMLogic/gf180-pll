v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
T {gf180-pll :: delaywin_3v3 -- the lock detector's phase-error WINDOW, with a
fixed, test-set TRIM CODE on its delay (DR-014, issue #411).

Four 1x inverters (even count, so the block is non-inverting), each loaded by
nfet_03v3 devices wired as MOS capacitors (drain = source = bulk = VSS, gate on
the delayed node). The resulting propagation delay t_win is the half-width of
the lock window: lock_detector only reacts to a phase-error pulse that is
still high t_win later, so any |phase error| < t_win is inside the window.

WHY THE LOAD IS A MOS CAP AND NOT A MIM OR POLY DEVICE (unchanged from the
untrimmed cell): it is built from the SAME nfet_03v3 primitive as the logic,
deliberately, so the window's PVT spread rides entirely on the MOS corner axis
the default grid already sweeps, with no independent passive corner axis to
leave silently at typical (sim/README.md "Default corner matrix"). t_win
therefore tracks gate delay over PVT rather than moving against it.

THE TRIM (T3 T2 T1 T0), and what it is for.  The untrimmed window's spread over
the mandated PVT grid is ~1.93x (sim/lock-window-sizing/records/
20260915-202802-79c0cee.md), wider than the [1, 2] ns band T1'/T2' require, and
DR-013 Decision 4 sets a <= 1.65x target no re-sizing of the untrimmed chain can
reach -- geometry re-centres the window, it does not narrow it.  DR-014 picks
the mechanism: a fixed trim code, set ONCE AT TEST from a measurement of the
part's own window and held for the life of the part, the same idiom as the Icp
trim-code rule in spec/pll.md.  Trimming per part removes the PROCESS half of
the spread, leaving only the within-bundle voltage and temperature spread
(measured here at 1.456x `ff` .. 1.536x `ss`) plus the trim step's own
quantization.

It is NOT a self-calibration input.  DR-002 Decision 4 puts the lock flag in v1
scope as a PASSIVE MONITOR with no band-search and no calibration hardware, and
that boundary applies to the delay cell the monitor's window is built from
exactly as it applies to the monitor itself.  T3..T0 are static configuration
inputs; nothing on-chip writes them.

HOW A SEGMENT IS SWITCHED.  Each stage carries one always-present base MOS cap
(MB*, W = 5 um) plus four binary-weighted switched segments (MT0*..MT3*,
W = 0.5 / 1 / 2 / 4 um, same device and same L = 2 um).  A segment's BACK PLATE
(its shorted drain/source) is driven by a local inverter from the corresponding
trim bit, so

    Tj = 1  ->  back plate at VSS  ->  the gate inverts the channel over the
                whole 0..VDD swing of the delayed node: segment ENABLED, full
                Cox in circuit;
    Tj = 0  ->  back plate at VDD  ->  the channel cannot be supplied from the
                now reverse-biased drain/source, so the gate sees depletion
                rather than inversion: segment mostly OFF.

The code is therefore ACTIVE HIGH and MONOTONIC: code = 8*T3 + 4*T2 + 2*T1 + T0,
and a larger code means more capacitance, a longer t_win and a wider window.

WHY FOUR BITS AND A 0.5 um LSB, which is this cell's own sizing question (DR-014
Decision 3 leaves it open on purpose) and was answered by measurement, not by
arithmetic.  A disabled segment's residual capacitance is NOT zero -- the gate
still sees a depletion capacitance -- so a switched micron is worth only ~0.71
of an always-on micron, and the usable floor, ceiling and step of the ladder
cannot be read off the drawn widths.  Measured on a 3-bit, 1 um-LSB first cut
(base 5 um, segments 1/2/4 um), a code step was worth 6-8 % of the window: a
+/-3 to 4 % quantization error, which inflates the trimmed population's spread
to ~1.64x and leaves the <= 1.65x target with no usable margin, and which put
the `ff` bundle's best code at the very top of the range with no headroom.
Halving the LSB to 0.5 um and adding the fourth bit takes the step to ~3 % and
the range to ~1.6x, which centres `ss` near code 3 and `ff` near code 11 -- both
inside the code space with several codes of headroom, and a quantization term
small enough that the surviving spread is the worst bundle's own V/T spread plus
about 3 %.  sim/lock-window-trim measures the ladder that this cell actually
has.

One inverter per segment per stage, rather than one per bit shared across the
four stages: a shared back plate would couple each stage's delayed node into its
neighbours' loads through the segment overlap capacitance, feeding the delay
chain forward through a node only as stiff as its driver.  A local driver per
segment keeps every load's back plate a private, hard node, at the cost of
sixteen extra 1x inverters whose inputs are static.} -700 -1500 0 0 0.4 0.4 {}
C {ipin.sym} -700 0 0 0 {name=p1 lab=A}
C {opin.sym} 1700 0 0 0 {name=p2 lab=Y}
C {ipin.sym} -700 100 0 0 {name=p3 lab=T0}
C {ipin.sym} -700 200 0 0 {name=p4 lab=T1}
C {ipin.sym} -700 300 0 0 {name=p5 lab=T2}
C {ipin.sym} -700 400 0 0 {name=p6 lab=T3}
C {iopin.sym} -700 500 0 0 {name=p7 lab=VDD}
C {iopin.sym} -700 600 0 0 {name=p8 lab=VSS}
C {inv_3v3.sym} 0 0 0 0 {name=XI1}
C {lab_pin.sym} -40 0 0 0 {name=la1 lab=A}
C {lab_pin.sym} 40 0 0 0 {name=la2 lab=D1}
C {lab_pin.sym} 0 -40 0 0 {name=la3 lab=VDD}
C {lab_pin.sym} 0 40 0 0 {name=la4 lab=VSS}
C {nfet_03v3.sym} 0 300 0 0 {name=MB1 model=nfet_03v3 W=5u L=2u nf=1 m=1}
C {lab_pin.sym} -20 300 0 0 {name=lab1 lab=D1}
C {lab_pin.sym} 20 270 0 0 {name=lab2 lab=VSS}
C {lab_pin.sym} 20 330 0 0 {name=lab3 lab=VSS}
C {lab_pin.sym} 20 300 0 0 {name=lab4 lab=VSS}
C {inv_3v3.sym} -150 600 0 0 {name=XNB01}
C {lab_pin.sym} -190 600 0 0 {name=lad01 lab=T0}
C {lab_pin.sym} -110 600 0 0 {name=lad02 lab=NB0_1}
C {lab_pin.sym} -150 560 0 0 {name=lad03 lab=VDD}
C {lab_pin.sym} -150 640 0 0 {name=lad04 lab=VSS}
C {nfet_03v3.sym} 0 600 0 0 {name=MT01 model=nfet_03v3 W=0.5u L=2u nf=1 m=1}
C {lab_pin.sym} -20 600 0 0 {name=las01 lab=D1}
C {lab_pin.sym} 20 570 0 0 {name=las02 lab=NB0_1}
C {lab_pin.sym} 20 630 0 0 {name=las03 lab=NB0_1}
C {lab_pin.sym} 20 600 0 0 {name=las04 lab=VSS}
C {inv_3v3.sym} -150 900 0 0 {name=XNB11}
C {lab_pin.sym} -190 900 0 0 {name=lad11 lab=T1}
C {lab_pin.sym} -110 900 0 0 {name=lad12 lab=NB1_1}
C {lab_pin.sym} -150 860 0 0 {name=lad13 lab=VDD}
C {lab_pin.sym} -150 940 0 0 {name=lad14 lab=VSS}
C {nfet_03v3.sym} 0 900 0 0 {name=MT11 model=nfet_03v3 W=1u L=2u nf=1 m=1}
C {lab_pin.sym} -20 900 0 0 {name=las11 lab=D1}
C {lab_pin.sym} 20 870 0 0 {name=las12 lab=NB1_1}
C {lab_pin.sym} 20 930 0 0 {name=las13 lab=NB1_1}
C {lab_pin.sym} 20 900 0 0 {name=las14 lab=VSS}
C {inv_3v3.sym} -150 1200 0 0 {name=XNB21}
C {lab_pin.sym} -190 1200 0 0 {name=lad21 lab=T2}
C {lab_pin.sym} -110 1200 0 0 {name=lad22 lab=NB2_1}
C {lab_pin.sym} -150 1160 0 0 {name=lad23 lab=VDD}
C {lab_pin.sym} -150 1240 0 0 {name=lad24 lab=VSS}
C {nfet_03v3.sym} 0 1200 0 0 {name=MT21 model=nfet_03v3 W=2u L=2u nf=1 m=1}
C {lab_pin.sym} -20 1200 0 0 {name=las21 lab=D1}
C {lab_pin.sym} 20 1170 0 0 {name=las22 lab=NB2_1}
C {lab_pin.sym} 20 1230 0 0 {name=las23 lab=NB2_1}
C {lab_pin.sym} 20 1200 0 0 {name=las24 lab=VSS}
C {inv_3v3.sym} -150 1500 0 0 {name=XNB31}
C {lab_pin.sym} -190 1500 0 0 {name=lad31 lab=T3}
C {lab_pin.sym} -110 1500 0 0 {name=lad32 lab=NB3_1}
C {lab_pin.sym} -150 1460 0 0 {name=lad33 lab=VDD}
C {lab_pin.sym} -150 1540 0 0 {name=lad34 lab=VSS}
C {nfet_03v3.sym} 0 1500 0 0 {name=MT31 model=nfet_03v3 W=4u L=2u nf=1 m=1}
C {lab_pin.sym} -20 1500 0 0 {name=las31 lab=D1}
C {lab_pin.sym} 20 1470 0 0 {name=las32 lab=NB3_1}
C {lab_pin.sym} 20 1530 0 0 {name=las33 lab=NB3_1}
C {lab_pin.sym} 20 1500 0 0 {name=las34 lab=VSS}
C {inv_3v3.sym} 400 0 0 0 {name=XI2}
C {lab_pin.sym} 360 0 0 0 {name=lb1 lab=D1}
C {lab_pin.sym} 440 0 0 0 {name=lb2 lab=D2}
C {lab_pin.sym} 400 -40 0 0 {name=lb3 lab=VDD}
C {lab_pin.sym} 400 40 0 0 {name=lb4 lab=VSS}
C {nfet_03v3.sym} 400 300 0 0 {name=MB2 model=nfet_03v3 W=5u L=2u nf=1 m=1}
C {lab_pin.sym} 380 300 0 0 {name=lbb1 lab=D2}
C {lab_pin.sym} 420 270 0 0 {name=lbb2 lab=VSS}
C {lab_pin.sym} 420 330 0 0 {name=lbb3 lab=VSS}
C {lab_pin.sym} 420 300 0 0 {name=lbb4 lab=VSS}
C {inv_3v3.sym} 250 600 0 0 {name=XNB02}
C {lab_pin.sym} 210 600 0 0 {name=lbd01 lab=T0}
C {lab_pin.sym} 290 600 0 0 {name=lbd02 lab=NB0_2}
C {lab_pin.sym} 250 560 0 0 {name=lbd03 lab=VDD}
C {lab_pin.sym} 250 640 0 0 {name=lbd04 lab=VSS}
C {nfet_03v3.sym} 400 600 0 0 {name=MT02 model=nfet_03v3 W=0.5u L=2u nf=1 m=1}
C {lab_pin.sym} 380 600 0 0 {name=lbs01 lab=D2}
C {lab_pin.sym} 420 570 0 0 {name=lbs02 lab=NB0_2}
C {lab_pin.sym} 420 630 0 0 {name=lbs03 lab=NB0_2}
C {lab_pin.sym} 420 600 0 0 {name=lbs04 lab=VSS}
C {inv_3v3.sym} 250 900 0 0 {name=XNB12}
C {lab_pin.sym} 210 900 0 0 {name=lbd11 lab=T1}
C {lab_pin.sym} 290 900 0 0 {name=lbd12 lab=NB1_2}
C {lab_pin.sym} 250 860 0 0 {name=lbd13 lab=VDD}
C {lab_pin.sym} 250 940 0 0 {name=lbd14 lab=VSS}
C {nfet_03v3.sym} 400 900 0 0 {name=MT12 model=nfet_03v3 W=1u L=2u nf=1 m=1}
C {lab_pin.sym} 380 900 0 0 {name=lbs11 lab=D2}
C {lab_pin.sym} 420 870 0 0 {name=lbs12 lab=NB1_2}
C {lab_pin.sym} 420 930 0 0 {name=lbs13 lab=NB1_2}
C {lab_pin.sym} 420 900 0 0 {name=lbs14 lab=VSS}
C {inv_3v3.sym} 250 1200 0 0 {name=XNB22}
C {lab_pin.sym} 210 1200 0 0 {name=lbd21 lab=T2}
C {lab_pin.sym} 290 1200 0 0 {name=lbd22 lab=NB2_2}
C {lab_pin.sym} 250 1160 0 0 {name=lbd23 lab=VDD}
C {lab_pin.sym} 250 1240 0 0 {name=lbd24 lab=VSS}
C {nfet_03v3.sym} 400 1200 0 0 {name=MT22 model=nfet_03v3 W=2u L=2u nf=1 m=1}
C {lab_pin.sym} 380 1200 0 0 {name=lbs21 lab=D2}
C {lab_pin.sym} 420 1170 0 0 {name=lbs22 lab=NB2_2}
C {lab_pin.sym} 420 1230 0 0 {name=lbs23 lab=NB2_2}
C {lab_pin.sym} 420 1200 0 0 {name=lbs24 lab=VSS}
C {inv_3v3.sym} 250 1500 0 0 {name=XNB32}
C {lab_pin.sym} 210 1500 0 0 {name=lbd31 lab=T3}
C {lab_pin.sym} 290 1500 0 0 {name=lbd32 lab=NB3_2}
C {lab_pin.sym} 250 1460 0 0 {name=lbd33 lab=VDD}
C {lab_pin.sym} 250 1540 0 0 {name=lbd34 lab=VSS}
C {nfet_03v3.sym} 400 1500 0 0 {name=MT32 model=nfet_03v3 W=4u L=2u nf=1 m=1}
C {lab_pin.sym} 380 1500 0 0 {name=lbs31 lab=D2}
C {lab_pin.sym} 420 1470 0 0 {name=lbs32 lab=NB3_2}
C {lab_pin.sym} 420 1530 0 0 {name=lbs33 lab=NB3_2}
C {lab_pin.sym} 420 1500 0 0 {name=lbs34 lab=VSS}
C {inv_3v3.sym} 800 0 0 0 {name=XI3}
C {lab_pin.sym} 760 0 0 0 {name=lc1 lab=D2}
C {lab_pin.sym} 840 0 0 0 {name=lc2 lab=D3}
C {lab_pin.sym} 800 -40 0 0 {name=lc3 lab=VDD}
C {lab_pin.sym} 800 40 0 0 {name=lc4 lab=VSS}
C {nfet_03v3.sym} 800 300 0 0 {name=MB3 model=nfet_03v3 W=5u L=2u nf=1 m=1}
C {lab_pin.sym} 780 300 0 0 {name=lcb1 lab=D3}
C {lab_pin.sym} 820 270 0 0 {name=lcb2 lab=VSS}
C {lab_pin.sym} 820 330 0 0 {name=lcb3 lab=VSS}
C {lab_pin.sym} 820 300 0 0 {name=lcb4 lab=VSS}
C {inv_3v3.sym} 650 600 0 0 {name=XNB03}
C {lab_pin.sym} 610 600 0 0 {name=lcd01 lab=T0}
C {lab_pin.sym} 690 600 0 0 {name=lcd02 lab=NB0_3}
C {lab_pin.sym} 650 560 0 0 {name=lcd03 lab=VDD}
C {lab_pin.sym} 650 640 0 0 {name=lcd04 lab=VSS}
C {nfet_03v3.sym} 800 600 0 0 {name=MT03 model=nfet_03v3 W=0.5u L=2u nf=1 m=1}
C {lab_pin.sym} 780 600 0 0 {name=lcs01 lab=D3}
C {lab_pin.sym} 820 570 0 0 {name=lcs02 lab=NB0_3}
C {lab_pin.sym} 820 630 0 0 {name=lcs03 lab=NB0_3}
C {lab_pin.sym} 820 600 0 0 {name=lcs04 lab=VSS}
C {inv_3v3.sym} 650 900 0 0 {name=XNB13}
C {lab_pin.sym} 610 900 0 0 {name=lcd11 lab=T1}
C {lab_pin.sym} 690 900 0 0 {name=lcd12 lab=NB1_3}
C {lab_pin.sym} 650 860 0 0 {name=lcd13 lab=VDD}
C {lab_pin.sym} 650 940 0 0 {name=lcd14 lab=VSS}
C {nfet_03v3.sym} 800 900 0 0 {name=MT13 model=nfet_03v3 W=1u L=2u nf=1 m=1}
C {lab_pin.sym} 780 900 0 0 {name=lcs11 lab=D3}
C {lab_pin.sym} 820 870 0 0 {name=lcs12 lab=NB1_3}
C {lab_pin.sym} 820 930 0 0 {name=lcs13 lab=NB1_3}
C {lab_pin.sym} 820 900 0 0 {name=lcs14 lab=VSS}
C {inv_3v3.sym} 650 1200 0 0 {name=XNB23}
C {lab_pin.sym} 610 1200 0 0 {name=lcd21 lab=T2}
C {lab_pin.sym} 690 1200 0 0 {name=lcd22 lab=NB2_3}
C {lab_pin.sym} 650 1160 0 0 {name=lcd23 lab=VDD}
C {lab_pin.sym} 650 1240 0 0 {name=lcd24 lab=VSS}
C {nfet_03v3.sym} 800 1200 0 0 {name=MT23 model=nfet_03v3 W=2u L=2u nf=1 m=1}
C {lab_pin.sym} 780 1200 0 0 {name=lcs21 lab=D3}
C {lab_pin.sym} 820 1170 0 0 {name=lcs22 lab=NB2_3}
C {lab_pin.sym} 820 1230 0 0 {name=lcs23 lab=NB2_3}
C {lab_pin.sym} 820 1200 0 0 {name=lcs24 lab=VSS}
C {inv_3v3.sym} 650 1500 0 0 {name=XNB33}
C {lab_pin.sym} 610 1500 0 0 {name=lcd31 lab=T3}
C {lab_pin.sym} 690 1500 0 0 {name=lcd32 lab=NB3_3}
C {lab_pin.sym} 650 1460 0 0 {name=lcd33 lab=VDD}
C {lab_pin.sym} 650 1540 0 0 {name=lcd34 lab=VSS}
C {nfet_03v3.sym} 800 1500 0 0 {name=MT33 model=nfet_03v3 W=4u L=2u nf=1 m=1}
C {lab_pin.sym} 780 1500 0 0 {name=lcs31 lab=D3}
C {lab_pin.sym} 820 1470 0 0 {name=lcs32 lab=NB3_3}
C {lab_pin.sym} 820 1530 0 0 {name=lcs33 lab=NB3_3}
C {lab_pin.sym} 820 1500 0 0 {name=lcs34 lab=VSS}
C {inv_3v3.sym} 1200 0 0 0 {name=XI4}
C {lab_pin.sym} 1160 0 0 0 {name=ld1 lab=D3}
C {lab_pin.sym} 1240 0 0 0 {name=ld2 lab=Y}
C {lab_pin.sym} 1200 -40 0 0 {name=ld3 lab=VDD}
C {lab_pin.sym} 1200 40 0 0 {name=ld4 lab=VSS}
C {nfet_03v3.sym} 1200 300 0 0 {name=MB4 model=nfet_03v3 W=5u L=2u nf=1 m=1}
C {lab_pin.sym} 1180 300 0 0 {name=ldb1 lab=Y}
C {lab_pin.sym} 1220 270 0 0 {name=ldb2 lab=VSS}
C {lab_pin.sym} 1220 330 0 0 {name=ldb3 lab=VSS}
C {lab_pin.sym} 1220 300 0 0 {name=ldb4 lab=VSS}
C {inv_3v3.sym} 1050 600 0 0 {name=XNB04}
C {lab_pin.sym} 1010 600 0 0 {name=ldd01 lab=T0}
C {lab_pin.sym} 1090 600 0 0 {name=ldd02 lab=NB0_4}
C {lab_pin.sym} 1050 560 0 0 {name=ldd03 lab=VDD}
C {lab_pin.sym} 1050 640 0 0 {name=ldd04 lab=VSS}
C {nfet_03v3.sym} 1200 600 0 0 {name=MT04 model=nfet_03v3 W=0.5u L=2u nf=1 m=1}
C {lab_pin.sym} 1180 600 0 0 {name=lds01 lab=Y}
C {lab_pin.sym} 1220 570 0 0 {name=lds02 lab=NB0_4}
C {lab_pin.sym} 1220 630 0 0 {name=lds03 lab=NB0_4}
C {lab_pin.sym} 1220 600 0 0 {name=lds04 lab=VSS}
C {inv_3v3.sym} 1050 900 0 0 {name=XNB14}
C {lab_pin.sym} 1010 900 0 0 {name=ldd11 lab=T1}
C {lab_pin.sym} 1090 900 0 0 {name=ldd12 lab=NB1_4}
C {lab_pin.sym} 1050 860 0 0 {name=ldd13 lab=VDD}
C {lab_pin.sym} 1050 940 0 0 {name=ldd14 lab=VSS}
C {nfet_03v3.sym} 1200 900 0 0 {name=MT14 model=nfet_03v3 W=1u L=2u nf=1 m=1}
C {lab_pin.sym} 1180 900 0 0 {name=lds11 lab=Y}
C {lab_pin.sym} 1220 870 0 0 {name=lds12 lab=NB1_4}
C {lab_pin.sym} 1220 930 0 0 {name=lds13 lab=NB1_4}
C {lab_pin.sym} 1220 900 0 0 {name=lds14 lab=VSS}
C {inv_3v3.sym} 1050 1200 0 0 {name=XNB24}
C {lab_pin.sym} 1010 1200 0 0 {name=ldd21 lab=T2}
C {lab_pin.sym} 1090 1200 0 0 {name=ldd22 lab=NB2_4}
C {lab_pin.sym} 1050 1160 0 0 {name=ldd23 lab=VDD}
C {lab_pin.sym} 1050 1240 0 0 {name=ldd24 lab=VSS}
C {nfet_03v3.sym} 1200 1200 0 0 {name=MT24 model=nfet_03v3 W=2u L=2u nf=1 m=1}
C {lab_pin.sym} 1180 1200 0 0 {name=lds21 lab=Y}
C {lab_pin.sym} 1220 1170 0 0 {name=lds22 lab=NB2_4}
C {lab_pin.sym} 1220 1230 0 0 {name=lds23 lab=NB2_4}
C {lab_pin.sym} 1220 1200 0 0 {name=lds24 lab=VSS}
C {inv_3v3.sym} 1050 1500 0 0 {name=XNB34}
C {lab_pin.sym} 1010 1500 0 0 {name=ldd31 lab=T3}
C {lab_pin.sym} 1090 1500 0 0 {name=ldd32 lab=NB3_4}
C {lab_pin.sym} 1050 1460 0 0 {name=ldd33 lab=VDD}
C {lab_pin.sym} 1050 1540 0 0 {name=ldd34 lab=VSS}
C {nfet_03v3.sym} 1200 1500 0 0 {name=MT34 model=nfet_03v3 W=4u L=2u nf=1 m=1}
C {lab_pin.sym} 1180 1500 0 0 {name=lds31 lab=Y}
C {lab_pin.sym} 1220 1470 0 0 {name=lds32 lab=NB3_4}
C {lab_pin.sym} 1220 1530 0 0 {name=lds33 lab=NB3_4}
C {lab_pin.sym} 1220 1500 0 0 {name=lds34 lab=VSS}
