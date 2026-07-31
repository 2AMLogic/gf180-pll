v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
T {gf180-pll :: tgate_3v3 -- complementary CMOS transmission gate.
Conducts when GN = 1 and GP = 0. Used for the master-slave latch pairs of
dff_tg_3v3 (DR-001 Decision 3: transmission-gate master-slave flops).} -500 -400 0 0 0.4 0.4 {}
C {iopin.sym} -500 0 0 0 {name=p1 lab=A}
C {iopin.sym} 500 0 0 0 {name=p2 lab=Y}
C {ipin.sym} -500 -200 0 0 {name=p3 lab=GN}
C {ipin.sym} -500 -300 0 0 {name=p4 lab=GP}
C {iopin.sym} -500 200 0 0 {name=p5 lab=VDD}
C {iopin.sym} -500 300 0 0 {name=p6 lab=VSS}
C {pfet_03v3.sym} 0 -100 0 0 {name=MP model=pfet_03v3 W=2.5u L=0.28u nf=1 m=1}
C {lab_pin.sym} -20 -100 0 0 {name=la1 lab=GP}
C {lab_pin.sym} 20 -70 0 0 {name=la2 lab=Y}
C {lab_pin.sym} 20 -130 0 0 {name=la3 lab=A}
C {lab_pin.sym} 20 -100 0 0 {name=la4 lab=VDD}
C {nfet_03v3.sym} 0 100 0 0 {name=MN model=nfet_03v3 W=1u L=0.28u nf=1 m=1}
C {lab_pin.sym} -20 100 0 0 {name=lb1 lab=GN}
C {lab_pin.sym} 20 70 0 0 {name=lb2 lab=A}
C {lab_pin.sym} 20 130 0 0 {name=lb3 lab=Y}
C {lab_pin.sym} 20 100 0 0 {name=lb4 lab=VSS}
