v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
T {gf180-pll :: nand3_3v3 -- 3-input static CMOS NAND, 3.3 V thick-oxide devices
NMOS stack widened 3x so the three-high series pull-down matches a 1x inverter.} -500 -400 0 0 0.4 0.4 {}
C {ipin.sym} -500 -100 0 0 {name=p1 lab=A}
C {ipin.sym} -500 300 0 0 {name=p2 lab=B}
C {ipin.sym} -500 500 0 0 {name=p3 lab=C}
C {opin.sym} 900 0 0 0 {name=p4 lab=Y}
C {iopin.sym} -500 -250 0 0 {name=p5 lab=VDD}
C {iopin.sym} -500 650 0 0 {name=p6 lab=VSS}
C {pfet_03v3.sym} 0 -100 0 0 {name=MPA model=pfet_03v3 W=2.5u L=0.28u nf=1 m=1}
C {lab_pin.sym} -20 -100 0 0 {name=la1 lab=A}
C {lab_pin.sym} 20 -70 0 0 {name=la2 lab=Y}
C {lab_pin.sym} 20 -130 0 0 {name=la3 lab=VDD}
C {lab_pin.sym} 20 -100 0 0 {name=la4 lab=VDD}
C {pfet_03v3.sym} 300 -100 0 0 {name=MPB model=pfet_03v3 W=2.5u L=0.28u nf=1 m=1}
C {lab_pin.sym} 280 -100 0 0 {name=lb1 lab=B}
C {lab_pin.sym} 320 -70 0 0 {name=lb2 lab=Y}
C {lab_pin.sym} 320 -130 0 0 {name=lb3 lab=VDD}
C {lab_pin.sym} 320 -100 0 0 {name=lb4 lab=VDD}
C {pfet_03v3.sym} 600 -100 0 0 {name=MPC model=pfet_03v3 W=2.5u L=0.28u nf=1 m=1}
C {lab_pin.sym} 580 -100 0 0 {name=le1 lab=C}
C {lab_pin.sym} 620 -70 0 0 {name=le2 lab=Y}
C {lab_pin.sym} 620 -130 0 0 {name=le3 lab=VDD}
C {lab_pin.sym} 620 -100 0 0 {name=le4 lab=VDD}
C {nfet_03v3.sym} 0 100 0 0 {name=MNA model=nfet_03v3 W=3u L=0.28u nf=1 m=1}
C {lab_pin.sym} -20 100 0 0 {name=lc1 lab=A}
C {lab_pin.sym} 20 70 0 0 {name=lc2 lab=Y}
C {lab_pin.sym} 20 130 0 0 {name=lc3 lab=NM1}
C {lab_pin.sym} 20 100 0 0 {name=lc4 lab=VSS}
C {nfet_03v3.sym} 0 300 0 0 {name=MNB model=nfet_03v3 W=3u L=0.28u nf=1 m=1}
C {lab_pin.sym} -20 300 0 0 {name=ld1 lab=B}
C {lab_pin.sym} 20 270 0 0 {name=ld2 lab=NM1}
C {lab_pin.sym} 20 330 0 0 {name=ld3 lab=NM2}
C {lab_pin.sym} 20 300 0 0 {name=ld4 lab=VSS}
C {nfet_03v3.sym} 0 500 0 0 {name=MNC model=nfet_03v3 W=3u L=0.28u nf=1 m=1}
C {lab_pin.sym} -20 500 0 0 {name=lf1 lab=C}
C {lab_pin.sym} 20 470 0 0 {name=lf2 lab=NM2}
C {lab_pin.sym} 20 530 0 0 {name=lf3 lab=VSS}
C {lab_pin.sym} 20 500 0 0 {name=lf4 lab=VSS}
