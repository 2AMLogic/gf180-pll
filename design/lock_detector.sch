v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
T {gf180-pll :: lock_detector -- phase-error WINDOW COMPARATOR producing the
digital LOCK status output. DR-002 Decision 4.

It is a PASSIVE MONITOR only: no band-search / self-calibration FSM, no
counter, no state machine, and nothing in it drives any loop node. DR-001
Decision 2 keeps band select a static input and DR-002 Decision 4 preserves
that unchanged.

Signal path (inputs are the tri-state PFD's UP / DN pair from #9):
  ERR   = XOR(UP, DN)          high for exactly |phase error| -- the PFD's
                               common reset pulse cancels in the XOR
  ERRD  = ERR delayed by t_win (delaywin_3v3)
  WIDE  = ERR . ERRD           high only if the error pulse OUTLASTED the
                               window, i.e. |phase error| > t_win.
                               |phase error| < t_win produces NO pulse at all.
  VWIN  integrating node: MUPW (a deliberately weak, always-on long-channel
        pfet) charges it; MDNW discharges it hard whenever WIDE is high;
        MCW is the integrating MOS capacitor.
  LOCK  = /schmitt(VWIN)       VWIN high (no out-of-window errors for a long
                               time) -> LOCK = 1.

Deliberate asymmetry: assert is SLOW (weak pull-up must charge MCW, i.e. the
error must stay inside the window for many reference cycles) and deassert is
FAST (one out-of-window error pulse dumps the node). A lock flag that is slow
to rise and quick to fall is the safe direction for a consumer gating logic
on it.

Power-on state is LOCK = 0: MCW starts discharged, so the flag only rises
after the loop has genuinely held the window. Testbenches must therefore
start from .ic v(vwin)=0 rather than the DC operating point (which would
start the node already charged and mask the acquisition behaviour).

VWIN is brought out as an observability pin for the characterisation
testbench; it is not part of the block's functional interface.

LDT3 LDT0 -- the window's TRIM CODE, passed straight through to delaywin_3v3's
T3..T0 (DR-014, issue #411). A fixed, test-set process trim: the code is
chosen once from a measurement of the part's own window and held for the life
of the part, exactly as spec/pll.md's Icp trim-code rule works. It is NOT a
calibration input and nothing on-chip writes it -- DR-002 Decision 4's "passive
monitor, no band-search or calibration FSM" boundary is unchanged. Code is
active high and monotonic (8*LDT3 + 4*LDT2 + 2*LDT1 + LDT0; larger code = wider
window); see design/delaywin_3v3.sch for how a segment is switched and
sim/lock-window-trim for the measured per-bundle code table.

t_win, the assert/deassert thresholds and the assert delay are all
PVT-dependent and are characterised over the full 45-point grid in
sim/lock-detector.} -900 -900 0 0 0.4 0.4 {}
C {ipin.sym} -900 0 0 0 {name=p1 lab=UP}
C {ipin.sym} -900 100 0 0 {name=p2 lab=DN}
C {ipin.sym} -900 200 0 0 {name=p3 lab=LDT0}
C {ipin.sym} -900 300 0 0 {name=p4 lab=LDT1}
C {ipin.sym} -900 400 0 0 {name=p5 lab=LDT2}
C {ipin.sym} -900 500 0 0 {name=p6 lab=LDT3}
C {opin.sym} 2200 0 0 0 {name=p7 lab=LOCK}
C {opin.sym} 2200 100 0 0 {name=p8 lab=VWIN}
C {iopin.sym} -900 600 0 0 {name=p9 lab=VDD}
C {iopin.sym} -900 700 0 0 {name=p10 lab=VSS}
C {xor2_3v3.sym} 0 0 0 0 {name=XERR}
C {lab_pin.sym} -40 -20 0 0 {name=la1 lab=UP}
C {lab_pin.sym} -40 20 0 0 {name=la2 lab=DN}
C {lab_pin.sym} 40 0 0 0 {name=la3 lab=ERR}
C {lab_pin.sym} 0 -40 0 0 {name=la4 lab=VDD}
C {lab_pin.sym} 0 40 0 0 {name=la5 lab=VSS}
C {delaywin_3v3.sym} 400 0 0 0 {name=XDLY}
C {lab_pin.sym} 360 0 0 0 {name=lb1 lab=ERR}
C {lab_pin.sym} 440 0 0 0 {name=lb2 lab=ERRD}
C {lab_pin.sym} 400 -80 0 0 {name=lb3 lab=VDD}
C {lab_pin.sym} 400 80 0 0 {name=lb4 lab=VSS}
C {lab_pin.sym} 360 20 0 0 {name=lb5 lab=LDT0}
C {lab_pin.sym} 360 40 0 0 {name=lb6 lab=LDT1}
C {lab_pin.sym} 360 60 0 0 {name=lb7 lab=LDT2}
C {lab_pin.sym} 360 -40 0 0 {name=lb8 lab=LDT3}
C {nand2_3v3.sym} 800 0 0 0 {name=XNW}
C {lab_pin.sym} 760 -20 0 0 {name=lc1 lab=ERR}
C {lab_pin.sym} 760 20 0 0 {name=lc2 lab=ERRD}
C {lab_pin.sym} 840 0 0 0 {name=lc3 lab=WIDEB}
C {lab_pin.sym} 800 -40 0 0 {name=lc4 lab=VDD}
C {lab_pin.sym} 800 40 0 0 {name=lc5 lab=VSS}
C {inv_3v3.sym} 1100 0 0 0 {name=XIW}
C {lab_pin.sym} 1060 0 0 0 {name=ld1 lab=WIDEB}
C {lab_pin.sym} 1140 0 0 0 {name=ld2 lab=WIDE}
C {lab_pin.sym} 1100 -40 0 0 {name=ld3 lab=VDD}
C {lab_pin.sym} 1100 40 0 0 {name=ld4 lab=VSS}
C {nfet_03v3.sym} 1400 400 0 0 {name=MDNW model=nfet_03v3 W=2u L=0.5u nf=1 m=1}
C {lab_pin.sym} 1380 400 0 0 {name=le1 lab=WIDE}
C {lab_pin.sym} 1420 370 0 0 {name=le2 lab=VWIN}
C {lab_pin.sym} 1420 430 0 0 {name=le3 lab=VSS}
C {lab_pin.sym} 1420 400 0 0 {name=le4 lab=VSS}
C {pfet_03v3.sym} 1400 0 0 0 {name=MUPW model=pfet_03v3 W=0.22u L=20u nf=1 m=1}
C {lab_pin.sym} 1380 0 0 0 {name=lf1 lab=VSS}
C {lab_pin.sym} 1420 30 0 0 {name=lf2 lab=VWIN}
C {lab_pin.sym} 1420 -30 0 0 {name=lf3 lab=VDD}
C {lab_pin.sym} 1420 0 0 0 {name=lf4 lab=VDD}
C {nfet_03v3.sym} 1400 800 0 0 {name=MCW model=nfet_03v3 W=30u L=6u nf=1 m=1}
C {lab_pin.sym} 1380 800 0 0 {name=lg1 lab=VWIN}
C {lab_pin.sym} 1420 770 0 0 {name=lg2 lab=VSS}
C {lab_pin.sym} 1420 830 0 0 {name=lg3 lab=VSS}
C {lab_pin.sym} 1420 800 0 0 {name=lg4 lab=VSS}
C {schmitt_3v3.sym} 1800 0 0 0 {name=XSCH}
C {lab_pin.sym} 1760 0 0 0 {name=lh1 lab=VWIN}
C {lab_pin.sym} 1840 0 0 0 {name=lh2 lab=LOCKB}
C {lab_pin.sym} 1800 -40 0 0 {name=lh3 lab=VDD}
C {lab_pin.sym} 1800 40 0 0 {name=lh4 lab=VSS}
C {inv_3v3.sym} 2100 -300 0 0 {name=XILK}
C {lab_pin.sym} 2060 -300 0 0 {name=li1 lab=LOCKB}
C {lab_pin.sym} 2140 -300 0 0 {name=li2 lab=LOCK}
C {lab_pin.sym} 2100 -340 0 0 {name=li3 lab=VDD}
C {lab_pin.sym} 2100 -260 0 0 {name=li4 lab=VSS}
