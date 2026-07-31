v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
T {gf180-pll :: dff_tg_3v3 -- rising-edge D flip-flop, transmission-gate
master-slave, fully static CMOS (DR-001 Decision 3).

  master latch : NM  <- D    through XTGMI (conducts while CK = 0)
                 NM  -> NMA -> NMB -> NM through XTGMF (conducts while CK = 1)
  slave  latch : NS  <- NMA  through XTGSI (conducts while CK = 1)
                 NS  -> Q   -> QB  -> NS  through XTGSF (conducts while CK = 0)

Static in both phases (no dynamic storage node), so the flop has no minimum
clock frequency -- the property DR-001 Decision 3 requires of the divider and
the reason dynamic/TSPC logic was rejected as the default.

CKB / CKBB are locally generated: the master input gate closes one inverter
delay before the slave input gate opens, which is the master-slave race margin.} -900 -600 0 0 0.4 0.4 {}
C {ipin.sym} -900 0 0 0 {name=p1 lab=D}
C {ipin.sym} -900 100 0 0 {name=p2 lab=CK}
C {opin.sym} 1300 0 0 0 {name=p3 lab=Q}
C {opin.sym} 1300 100 0 0 {name=p4 lab=QB}
C {iopin.sym} -900 200 0 0 {name=p5 lab=VDD}
C {iopin.sym} -900 300 0 0 {name=p6 lab=VSS}
C {inv_3v3.sym} 0 0 0 0 {name=XICKB}
C {lab_pin.sym} -40 0 0 0 {name=la1 lab=CK}
C {lab_pin.sym} 40 0 0 0 {name=la2 lab=CKB}
C {lab_pin.sym} 0 -40 0 0 {name=la3 lab=VDD}
C {lab_pin.sym} 0 40 0 0 {name=la4 lab=VSS}
C {inv_3v3.sym} 300 0 0 0 {name=XICKBB}
C {lab_pin.sym} 260 0 0 0 {name=lb1 lab=CKB}
C {lab_pin.sym} 340 0 0 0 {name=lb2 lab=CKBB}
C {lab_pin.sym} 300 -40 0 0 {name=lb3 lab=VDD}
C {lab_pin.sym} 300 40 0 0 {name=lb4 lab=VSS}
C {tgate_3v3.sym} 0 300 0 0 {name=XTGMI}
C {lab_pin.sym} -40 300 0 0 {name=lc1 lab=D}
C {lab_pin.sym} 40 300 0 0 {name=lc2 lab=NM}
C {lab_pin.sym} -20 260 0 0 {name=lc3 lab=CKB}
C {lab_pin.sym} 20 260 0 0 {name=lc4 lab=CKBB}
C {lab_pin.sym} -20 340 0 0 {name=lc5 lab=VDD}
C {lab_pin.sym} 20 340 0 0 {name=lc6 lab=VSS}
C {inv_3v3.sym} 300 300 0 0 {name=XIA}
C {lab_pin.sym} 260 300 0 0 {name=ld1 lab=NM}
C {lab_pin.sym} 340 300 0 0 {name=ld2 lab=NMA}
C {lab_pin.sym} 300 260 0 0 {name=ld3 lab=VDD}
C {lab_pin.sym} 300 340 0 0 {name=ld4 lab=VSS}
C {inv_3v3.sym} 600 300 0 0 {name=XIB}
C {lab_pin.sym} 560 300 0 0 {name=le1 lab=NMA}
C {lab_pin.sym} 640 300 0 0 {name=le2 lab=NMB}
C {lab_pin.sym} 600 260 0 0 {name=le3 lab=VDD}
C {lab_pin.sym} 600 340 0 0 {name=le4 lab=VSS}
C {tgate_3v3.sym} 900 300 0 0 {name=XTGMF}
C {lab_pin.sym} 860 300 0 0 {name=lf1 lab=NMB}
C {lab_pin.sym} 940 300 0 0 {name=lf2 lab=NM}
C {lab_pin.sym} 880 260 0 0 {name=lf3 lab=CKBB}
C {lab_pin.sym} 920 260 0 0 {name=lf4 lab=CKB}
C {lab_pin.sym} 880 340 0 0 {name=lf5 lab=VDD}
C {lab_pin.sym} 920 340 0 0 {name=lf6 lab=VSS}
C {tgate_3v3.sym} 0 600 0 0 {name=XTGSI}
C {lab_pin.sym} -40 600 0 0 {name=lg1 lab=NMA}
C {lab_pin.sym} 40 600 0 0 {name=lg2 lab=NS}
C {lab_pin.sym} -20 560 0 0 {name=lg3 lab=CKBB}
C {lab_pin.sym} 20 560 0 0 {name=lg4 lab=CKB}
C {lab_pin.sym} -20 640 0 0 {name=lg5 lab=VDD}
C {lab_pin.sym} 20 640 0 0 {name=lg6 lab=VSS}
C {inv_3v3.sym} 300 600 0 0 {name=XIC}
C {lab_pin.sym} 260 600 0 0 {name=lh1 lab=NS}
C {lab_pin.sym} 340 600 0 0 {name=lh2 lab=Q}
C {lab_pin.sym} 300 560 0 0 {name=lh3 lab=VDD}
C {lab_pin.sym} 300 640 0 0 {name=lh4 lab=VSS}
C {inv_3v3.sym} 600 600 0 0 {name=XID}
C {lab_pin.sym} 560 600 0 0 {name=li1 lab=Q}
C {lab_pin.sym} 640 600 0 0 {name=li2 lab=QB}
C {lab_pin.sym} 600 560 0 0 {name=li3 lab=VDD}
C {lab_pin.sym} 600 640 0 0 {name=li4 lab=VSS}
C {tgate_3v3.sym} 900 600 0 0 {name=XTGSF}
C {lab_pin.sym} 860 600 0 0 {name=lj1 lab=QB}
C {lab_pin.sym} 940 600 0 0 {name=lj2 lab=NS}
C {lab_pin.sym} 880 560 0 0 {name=lj3 lab=CKB}
C {lab_pin.sym} 920 560 0 0 {name=lj4 lab=CKBB}
C {lab_pin.sym} 880 640 0 0 {name=lj5 lab=VDD}
C {lab_pin.sym} 920 640 0 0 {name=lj6 lab=VSS}
