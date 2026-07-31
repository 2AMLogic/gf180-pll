v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
T {gf180-pll :: div23_cell -- modular divide-by-2/3 cell (Vaucher-style),
static CMOS, 3.3 V thick-oxide devices only. DR-001 Decision 3.

Interface (identical for all six cells in the chain):
  CKIN    input clock
  MODIN   modulus request from the NEXT (slower) cell; high for exactly one
          CKOUT period, once per overall divider output period
  P       static modulus program bit for this cell
  CKOUT   divided clock to the next cell
  MODOUT  modulus request to the PREVIOUS (faster) cell; high for exactly one
          CKIN period

Synchronous state (both flops clocked by the rising edge of CKIN):
  Q       prescaler state, CKOUT = Q (buffered)
  MODOUT  registered, MODOUT+ = MODIN . Q

  s  = MODIN . P . MODOUT        (swallow this CKIN cycle)
  Q+ = /Q . /s                   ( = NOR(Q, s) )

With s = 0 the cell toggles (divide by 2). MODOUT is high for exactly the
first CKIN cycle of the MODIN window in which Q = 0, so s is asserted for
exactly one CKIN cycle per MODIN window: Q holds low one extra cycle and the
cell divides by 3 for that one output period. MODOUT therefore doubles as the
"already swallowed this window" marker, which is why the cell needs only two
flops. Chain ratio: N = 2^k + sum(P_i . 2^i) over the k active cells.

Gate mapping:
  SB  = NAND3(MODIN, P, MODOUT)   = /s
  DQN = NAND2(QB, SB)             DQ = /DQN = /Q . /s
  NMO = NAND2(MODIN, Q)           DMO = /NMO = MODIN . Q

Speed path: MODIN is produced by the next cell's flop, clocked by this cell's
CKOUT, so it settles roughly two clk->Q delays after a CKIN edge and must meet
setup before the following CKIN edge. That bound applies to the FIRST cell at
the full VCO rate and is the cell's speed limit (verified in
sim/divider-ratio).} -900 -1000 0 0 0.4 0.4 {}
C {ipin.sym} -900 0 0 0 {name=p1 lab=CKIN}
C {ipin.sym} -900 100 0 0 {name=p2 lab=MODIN}
C {ipin.sym} -900 200 0 0 {name=p3 lab=P}
C {opin.sym} 1600 0 0 0 {name=p4 lab=CKOUT}
C {opin.sym} 1600 100 0 0 {name=p5 lab=MODOUT}
C {iopin.sym} -900 300 0 0 {name=p6 lab=VDD}
C {iopin.sym} -900 400 0 0 {name=p7 lab=VSS}
C {nand3_3v3.sym} 0 0 0 0 {name=XN3}
C {lab_pin.sym} -40 -20 0 0 {name=la1 lab=MODIN}
C {lab_pin.sym} -40 0 0 0 {name=la2 lab=P}
C {lab_pin.sym} -40 20 0 0 {name=la3 lab=MODOUT}
C {lab_pin.sym} 40 0 0 0 {name=la4 lab=SB}
C {lab_pin.sym} 0 -40 0 0 {name=la5 lab=VDD}
C {lab_pin.sym} 0 40 0 0 {name=la6 lab=VSS}
C {nand2_3v3.sym} 300 0 0 0 {name=XN2Q}
C {lab_pin.sym} 260 -20 0 0 {name=lb1 lab=QB}
C {lab_pin.sym} 260 20 0 0 {name=lb2 lab=SB}
C {lab_pin.sym} 340 0 0 0 {name=lb3 lab=DQN}
C {lab_pin.sym} 300 -40 0 0 {name=lb4 lab=VDD}
C {lab_pin.sym} 300 40 0 0 {name=lb5 lab=VSS}
C {inv_3v3.sym} 600 0 0 0 {name=XIQ}
C {lab_pin.sym} 560 0 0 0 {name=lc1 lab=DQN}
C {lab_pin.sym} 640 0 0 0 {name=lc2 lab=DQ}
C {lab_pin.sym} 600 -40 0 0 {name=lc3 lab=VDD}
C {lab_pin.sym} 600 40 0 0 {name=lc4 lab=VSS}
C {dff_tg_3v3.sym} 900 0 0 0 {name=XFQ}
C {lab_pin.sym} 850 -20 0 0 {name=ld1 lab=DQ}
C {lab_pin.sym} 850 20 0 0 {name=ld2 lab=CKIN}
C {lab_pin.sym} 950 -20 0 0 {name=ld3 lab=Q}
C {lab_pin.sym} 950 20 0 0 {name=ld4 lab=QB}
C {lab_pin.sym} 900 -50 0 0 {name=ld5 lab=VDD}
C {lab_pin.sym} 900 50 0 0 {name=ld6 lab=VSS}
C {inv2x_3v3.sym} 1200 0 0 0 {name=XICKO}
C {lab_pin.sym} 1160 0 0 0 {name=le1 lab=QB}
C {lab_pin.sym} 1240 0 0 0 {name=le2 lab=CKOUT}
C {lab_pin.sym} 1200 -40 0 0 {name=le3 lab=VDD}
C {lab_pin.sym} 1200 40 0 0 {name=le4 lab=VSS}
C {nand2_3v3.sym} 300 300 0 0 {name=XN2M}
C {lab_pin.sym} 260 280 0 0 {name=lf1 lab=MODIN}
C {lab_pin.sym} 260 320 0 0 {name=lf2 lab=Q}
C {lab_pin.sym} 340 300 0 0 {name=lf3 lab=NMO}
C {lab_pin.sym} 300 260 0 0 {name=lf4 lab=VDD}
C {lab_pin.sym} 300 340 0 0 {name=lf5 lab=VSS}
C {inv_3v3.sym} 600 300 0 0 {name=XIM}
C {lab_pin.sym} 560 300 0 0 {name=lg1 lab=NMO}
C {lab_pin.sym} 640 300 0 0 {name=lg2 lab=DMO}
C {lab_pin.sym} 600 260 0 0 {name=lg3 lab=VDD}
C {lab_pin.sym} 600 340 0 0 {name=lg4 lab=VSS}
C {dff_tg_3v3.sym} 900 300 0 0 {name=XFMO}
C {lab_pin.sym} 850 280 0 0 {name=lh1 lab=DMO}
C {lab_pin.sym} 850 320 0 0 {name=lh2 lab=CKIN}
C {lab_pin.sym} 950 280 0 0 {name=lh3 lab=MODOUT}
C {lab_pin.sym} 950 320 0 0 {name=lh4 lab=MOB}
C {lab_pin.sym} 900 250 0 0 {name=lh5 lab=VDD}
C {lab_pin.sym} 900 350 0 0 {name=lh6 lab=VSS}
