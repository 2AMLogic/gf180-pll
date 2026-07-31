v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
T {gf180-pll :: inv_3v3 -- 1x static CMOS inverter, 3.3 V thick-oxide devices
Connectivity in this library is expressed with net labels (lab_pin) placed
directly on device pins; see design/README.md for the convention.} -400 -400 0 0 0.4 0.4 {}
C {ipin.sym} -400 0 0 0 {name=p1 lab=A}
C {opin.sym} 400 0 0 0 {name=p2 lab=Y}
C {iopin.sym} -400 -200 0 0 {name=p3 lab=VDD}
C {iopin.sym} -400 200 0 0 {name=p4 lab=VSS}
C {pfet_03v3.sym} 0 -100 0 0 {name=MP model=pfet_03v3 W=2.5u L=0.28u nf=1 m=1}
C {lab_pin.sym} -20 -100 0 0 {name=lp1 lab=A}
C {lab_pin.sym} 20 -70 0 0 {name=lp2 lab=Y}
C {lab_pin.sym} 20 -130 0 0 {name=lp3 lab=VDD}
C {lab_pin.sym} 20 -100 0 0 {name=lp4 lab=VDD}
C {nfet_03v3.sym} 0 100 0 0 {name=MN model=nfet_03v3 W=1u L=0.28u nf=1 m=1}
C {lab_pin.sym} -20 100 0 0 {name=ln1 lab=A}
C {lab_pin.sym} 20 70 0 0 {name=ln2 lab=Y}
C {lab_pin.sym} 20 130 0 0 {name=ln3 lab=VSS}
C {lab_pin.sym} 20 100 0 0 {name=ln4 lab=VSS}
