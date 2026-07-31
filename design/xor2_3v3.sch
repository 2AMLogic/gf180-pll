v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
T {gf180-pll :: xor2_3v3 -- 2-input XOR built from four static NAND2 gates.
Used by lock_detector to turn the PFD's UP / DN pair into a single phase-error
pulse: a tri-state PFD drives UP and DN with a COMMON reset-delay pulse, so
XOR(UP,DN) is high for exactly |phase error| and zero-width when the loop sits
at zero static phase error.} -700 -400 0 0 0.4 0.4 {}
C {ipin.sym} -700 0 0 0 {name=p1 lab=A}
C {ipin.sym} -700 100 0 0 {name=p2 lab=B}
C {opin.sym} 1300 0 0 0 {name=p3 lab=Y}
C {iopin.sym} -700 200 0 0 {name=p4 lab=VDD}
C {iopin.sym} -700 300 0 0 {name=p5 lab=VSS}
C {nand2_3v3.sym} 0 0 0 0 {name=XG1}
C {lab_pin.sym} -40 -20 0 0 {name=la1 lab=A}
C {lab_pin.sym} -40 20 0 0 {name=la2 lab=B}
C {lab_pin.sym} 40 0 0 0 {name=la3 lab=N1}
C {lab_pin.sym} 0 -40 0 0 {name=la4 lab=VDD}
C {lab_pin.sym} 0 40 0 0 {name=la5 lab=VSS}
C {nand2_3v3.sym} 400 0 0 0 {name=XG2}
C {lab_pin.sym} 360 -20 0 0 {name=lb1 lab=A}
C {lab_pin.sym} 360 20 0 0 {name=lb2 lab=N1}
C {lab_pin.sym} 440 0 0 0 {name=lb3 lab=N2}
C {lab_pin.sym} 400 -40 0 0 {name=lb4 lab=VDD}
C {lab_pin.sym} 400 40 0 0 {name=lb5 lab=VSS}
C {nand2_3v3.sym} 400 300 0 0 {name=XG3}
C {lab_pin.sym} 360 280 0 0 {name=lc1 lab=B}
C {lab_pin.sym} 360 320 0 0 {name=lc2 lab=N1}
C {lab_pin.sym} 440 300 0 0 {name=lc3 lab=N3}
C {lab_pin.sym} 400 260 0 0 {name=lc4 lab=VDD}
C {lab_pin.sym} 400 340 0 0 {name=lc5 lab=VSS}
C {nand2_3v3.sym} 900 0 0 0 {name=XG4}
C {lab_pin.sym} 860 -20 0 0 {name=ld1 lab=N2}
C {lab_pin.sym} 860 20 0 0 {name=ld2 lab=N3}
C {lab_pin.sym} 940 0 0 0 {name=ld3 lab=Y}
C {lab_pin.sym} 900 -40 0 0 {name=ld4 lab=VDD}
C {lab_pin.sym} 900 40 0 0 {name=ld5 lab=VSS}
