v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
T {gf180-pll :: schmitt_3v3 -- classic 6-transistor inverting CMOS Schmitt
trigger, 3.3 V thick-oxide devices.

MN3 / MP3 are the hysteresis feedback devices: they hold the internal source
nodes N1 / P1 away from the rails so the input has to travel further to flip
the output. In lock_detector this is what stops the LOCK flag chattering when
the phase error sits right on the window boundary.} -700 -600 0 0 0.4 0.4 {}
C {ipin.sym} -700 0 0 0 {name=p1 lab=A}
C {opin.sym} 900 0 0 0 {name=p2 lab=Y}
C {iopin.sym} -700 200 0 0 {name=p3 lab=VDD}
C {iopin.sym} -700 300 0 0 {name=p4 lab=VSS}
C {pfet_03v3.sym} 0 -400 0 0 {name=MP1 model=pfet_03v3 W=2.5u L=0.28u nf=1 m=1}
C {lab_pin.sym} -20 -400 0 0 {name=la1 lab=A}
C {lab_pin.sym} 20 -370 0 0 {name=la2 lab=P1}
C {lab_pin.sym} 20 -430 0 0 {name=la3 lab=VDD}
C {lab_pin.sym} 20 -400 0 0 {name=la4 lab=VDD}
C {pfet_03v3.sym} 400 -400 0 0 {name=MP2 model=pfet_03v3 W=2.5u L=0.28u nf=1 m=1}
C {lab_pin.sym} 380 -400 0 0 {name=lb1 lab=A}
C {lab_pin.sym} 420 -370 0 0 {name=lb2 lab=Y}
C {lab_pin.sym} 420 -430 0 0 {name=lb3 lab=P1}
C {lab_pin.sym} 420 -400 0 0 {name=lb4 lab=VDD}
C {pfet_03v3.sym} 800 -400 0 0 {name=MP3 model=pfet_03v3 W=1.2u L=0.28u nf=1 m=1}
C {lab_pin.sym} 780 -400 0 0 {name=lc1 lab=Y}
C {lab_pin.sym} 820 -370 0 0 {name=lc2 lab=VSS}
C {lab_pin.sym} 820 -430 0 0 {name=lc3 lab=P1}
C {lab_pin.sym} 820 -400 0 0 {name=lc4 lab=VDD}
C {nfet_03v3.sym} 0 0 0 0 {name=MN1 model=nfet_03v3 W=1u L=0.28u nf=1 m=1}
C {lab_pin.sym} -20 0 0 0 {name=ld1 lab=A}
C {lab_pin.sym} 20 -30 0 0 {name=ld2 lab=N1}
C {lab_pin.sym} 20 30 0 0 {name=ld3 lab=VSS}
C {lab_pin.sym} 20 0 0 0 {name=ld4 lab=VSS}
C {nfet_03v3.sym} 400 0 0 0 {name=MN2 model=nfet_03v3 W=1u L=0.28u nf=1 m=1}
C {lab_pin.sym} 380 0 0 0 {name=le1 lab=A}
C {lab_pin.sym} 420 -30 0 0 {name=le2 lab=Y}
C {lab_pin.sym} 420 30 0 0 {name=le3 lab=N1}
C {lab_pin.sym} 420 0 0 0 {name=le4 lab=VSS}
C {nfet_03v3.sym} 800 0 0 0 {name=MN3 model=nfet_03v3 W=0.5u L=0.28u nf=1 m=1}
C {lab_pin.sym} 780 0 0 0 {name=lf1 lab=Y}
C {lab_pin.sym} 820 -30 0 0 {name=lf2 lab=VDD}
C {lab_pin.sym} 820 30 0 0 {name=lf3 lab=N1}
C {lab_pin.sym} 820 0 0 0 {name=lf4 lab=VSS}
