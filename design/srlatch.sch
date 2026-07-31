v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
T {srlatch - NAND SR latch, active-low set/reset} 100 -60 0 0 0.3 0.3 {layer=8}
T {* Cross-coupled NAND SR latch with active-low SET (SB) and RESET (RB).\n* Q = NAND(SB, QB), QB = NAND(RB, Q).  One instance per PFD branch; both share\n* the same delayed RB, which is what makes the two output pulses overlap for the\n* reset-delay interval and eliminates the dead zone.} 1900 -300 0 0 0.25 0.25 {layer=8}
C {pfdcp_nand2_3v3.sym} 300 -300 0 0 {name=xn1}
C {devices/lab_pin.sym} 210 -360 0 0 {name=l_xn1_A lab=SB}
C {devices/lab_pin.sym} 210 -240 0 0 {name=l_xn1_B lab=QB}
C {devices/lab_pin.sym} 390 -300 0 0 {name=l_xn1_Y lab=Q}
C {devices/lab_pin.sym} 300 -390 0 0 {name=l_xn1_VDD lab=VDD}
C {devices/lab_pin.sym} 300 -210 0 0 {name=l_xn1_VSS lab=VSS}
C {pfdcp_nand2_3v3.sym} 560 -300 0 0 {name=xn2}
C {devices/lab_pin.sym} 470 -360 0 0 {name=l_xn2_A lab=RB}
C {devices/lab_pin.sym} 470 -240 0 0 {name=l_xn2_B lab=Q}
C {devices/lab_pin.sym} 650 -300 0 0 {name=l_xn2_Y lab=QB}
C {devices/lab_pin.sym} 560 -390 0 0 {name=l_xn2_VDD lab=VDD}
C {devices/lab_pin.sym} 560 -210 0 0 {name=l_xn2_VSS lab=VSS}
C {devices/ipin.sym} 100 -100 0 0 {name=P0 lab=SB}
C {devices/ipin.sym} 100 -120 0 0 {name=P1 lab=RB}
C {devices/opin.sym} 100 -140 0 0 {name=P2 lab=Q}
C {devices/opin.sym} 100 -160 0 0 {name=P3 lab=QB}
C {devices/iopin.sym} 100 -180 0 0 {name=P4 lab=VDD}
C {devices/iopin.sym} 100 -200 0 0 {name=P5 lab=VSS}
