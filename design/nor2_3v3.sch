v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
T {gf180-pll :: nor2_3v3 -- 2-input static CMOS NOR, 3.3 V thick-oxide devices
PMOS stack widened 2x so the series pull-up matches a 1x inverter.} -500 -500 0 0 0.4 0.4 {}
C {ipin.sym} -500 -300 0 0 {name=p1 lab=A}
C {ipin.sym} -500 -100 0 0 {name=p2 lab=B}
C {opin.sym} 600 0 0 0 {name=p3 lab=Y}
C {iopin.sym} -500 -450 0 0 {name=p4 lab=VDD}
C {iopin.sym} -500 250 0 0 {name=p5 lab=VSS}
C {pfet_03v3.sym} 0 -300 0 0 {name=MPA model=pfet_03v3 W=5u L=0.28u nf=1 m=1}
C {lab_pin.sym} -20 -300 0 0 {name=la1 lab=A}
C {lab_pin.sym} 20 -270 0 0 {name=la2 lab=PMID}
C {lab_pin.sym} 20 -330 0 0 {name=la3 lab=VDD}
C {lab_pin.sym} 20 -300 0 0 {name=la4 lab=VDD}
C {pfet_03v3.sym} 0 -100 0 0 {name=MPB model=pfet_03v3 W=5u L=0.28u nf=1 m=1}
C {lab_pin.sym} -20 -100 0 0 {name=lb1 lab=B}
C {lab_pin.sym} 20 -70 0 0 {name=lb2 lab=Y}
C {lab_pin.sym} 20 -130 0 0 {name=lb3 lab=PMID}
C {lab_pin.sym} 20 -100 0 0 {name=lb4 lab=VDD}
C {nfet_03v3.sym} 0 100 0 0 {name=MNA model=nfet_03v3 W=1u L=0.28u nf=1 m=1}
C {lab_pin.sym} -20 100 0 0 {name=lc1 lab=A}
C {lab_pin.sym} 20 70 0 0 {name=lc2 lab=Y}
C {lab_pin.sym} 20 130 0 0 {name=lc3 lab=VSS}
C {lab_pin.sym} 20 100 0 0 {name=lc4 lab=VSS}
C {nfet_03v3.sym} 300 100 0 0 {name=MNB model=nfet_03v3 W=1u L=0.28u nf=1 m=1}
C {lab_pin.sym} 280 100 0 0 {name=ld1 lab=B}
C {lab_pin.sym} 320 70 0 0 {name=ld2 lab=Y}
C {lab_pin.sym} 320 130 0 0 {name=ld3 lab=VSS}
C {lab_pin.sym} 320 100 0 0 {name=ld4 lab=VSS}
