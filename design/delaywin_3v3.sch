v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
T {gf180-pll :: delaywin_3v3 -- the lock detector's phase-error WINDOW.

Four 1x inverters (even count, so the block is non-inverting), each loaded by
an nfet_03v3 wired as a MOS capacitor (drain = source = bulk = VSS, gate on
the delayed node). The resulting propagation delay t_win is the half-width of
the lock window: lock_detector only reacts to a phase-error pulse that is
still high t_win later, so any |phase error| < t_win is inside the window.

The load is a MOS capacitor built from the SAME nfet_03v3 primitive as the
logic, not a MIM or poly device -- deliberately, so the window's PVT spread
rides entirely on the MOS corner axis that the default 45-point grid already
sweeps, with no independent passive corner axis to leave silently at typical
(sim/README.md "Default corner matrix"). t_win therefore tracks gate delay
over PVT rather than moving against it.} -700 -700 0 0 0.4 0.4 {}
C {ipin.sym} -700 0 0 0 {name=p1 lab=A}
C {opin.sym} 1700 0 0 0 {name=p2 lab=Y}
C {iopin.sym} -700 200 0 0 {name=p3 lab=VDD}
C {iopin.sym} -700 300 0 0 {name=p4 lab=VSS}
C {inv_3v3.sym} 0 0 0 0 {name=XI1}
C {lab_pin.sym} -40 0 0 0 {name=la1 lab=A}
C {lab_pin.sym} 40 0 0 0 {name=la2 lab=D1}
C {lab_pin.sym} 0 -40 0 0 {name=la3 lab=VDD}
C {lab_pin.sym} 0 40 0 0 {name=la4 lab=VSS}
C {nfet_03v3.sym} 0 300 0 0 {name=MC1 model=nfet_03v3 W=8u L=2u nf=1 m=1}
C {lab_pin.sym} -20 300 0 0 {name=lb1 lab=D1}
C {lab_pin.sym} 20 270 0 0 {name=lb2 lab=VSS}
C {lab_pin.sym} 20 330 0 0 {name=lb3 lab=VSS}
C {lab_pin.sym} 20 300 0 0 {name=lb4 lab=VSS}
C {inv_3v3.sym} 400 0 0 0 {name=XI2}
C {lab_pin.sym} 360 0 0 0 {name=lc1 lab=D1}
C {lab_pin.sym} 440 0 0 0 {name=lc2 lab=D2}
C {lab_pin.sym} 400 -40 0 0 {name=lc3 lab=VDD}
C {lab_pin.sym} 400 40 0 0 {name=lc4 lab=VSS}
C {nfet_03v3.sym} 400 300 0 0 {name=MC2 model=nfet_03v3 W=8u L=2u nf=1 m=1}
C {lab_pin.sym} 380 300 0 0 {name=ld1 lab=D2}
C {lab_pin.sym} 420 270 0 0 {name=ld2 lab=VSS}
C {lab_pin.sym} 420 330 0 0 {name=ld3 lab=VSS}
C {lab_pin.sym} 420 300 0 0 {name=ld4 lab=VSS}
C {inv_3v3.sym} 800 0 0 0 {name=XI3}
C {lab_pin.sym} 760 0 0 0 {name=le1 lab=D2}
C {lab_pin.sym} 840 0 0 0 {name=le2 lab=D3}
C {lab_pin.sym} 800 -40 0 0 {name=le3 lab=VDD}
C {lab_pin.sym} 800 40 0 0 {name=le4 lab=VSS}
C {nfet_03v3.sym} 800 300 0 0 {name=MC3 model=nfet_03v3 W=8u L=2u nf=1 m=1}
C {lab_pin.sym} 780 300 0 0 {name=lf1 lab=D3}
C {lab_pin.sym} 820 270 0 0 {name=lf2 lab=VSS}
C {lab_pin.sym} 820 330 0 0 {name=lf3 lab=VSS}
C {lab_pin.sym} 820 300 0 0 {name=lf4 lab=VSS}
C {inv_3v3.sym} 1200 0 0 0 {name=XI4}
C {lab_pin.sym} 1160 0 0 0 {name=lg1 lab=D3}
C {lab_pin.sym} 1240 0 0 0 {name=lg2 lab=Y}
C {lab_pin.sym} 1200 -40 0 0 {name=lg3 lab=VDD}
C {lab_pin.sym} 1200 40 0 0 {name=lg4 lab=VSS}
C {nfet_03v3.sym} 1200 300 0 0 {name=MC4 model=nfet_03v3 W=8u L=2u nf=1 m=1}
C {lab_pin.sym} 1180 300 0 0 {name=lh1 lab=Y}
C {lab_pin.sym} 1220 270 0 0 {name=lh2 lab=VSS}
C {lab_pin.sym} 1220 330 0 0 {name=lh3 lab=VSS}
C {lab_pin.sym} 1220 300 0 0 {name=lh4 lab=VSS}
