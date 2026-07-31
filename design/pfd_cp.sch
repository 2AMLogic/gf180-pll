v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
T {pfd_cp - PFD + charge pump (the DR-001 Decision 1 phase-detect front end)} 100 -60 0 0 0.3 0.3 {layer=8}
T {* The DR-001 Decision 1 phase-detect front end: tri-state PFD driving the\n* charge pump, with VOUT the node the passive second-order loop filter (#10) and\n* the VCO control input (#8) attach to.  UP/DN are brought out for observation\n* only.\n* \n* FB is the divider's retimed feedback edge (DR-001 Decision 3 / #11): a VCO\n* edge delayed by exactly one flop's clk->Q independent of N, shaped to be at\n* least as wide as this PFD's reset delay.  The measured reset delay in the\n* pfd-deadzone record is the number #11's retiming pulse width must be checked\n* against.} 1900 -300 0 0 0.25 0.25 {layer=8}
C {pfd.sym} 300 -300 0 0 {name=xpfd}
C {devices/lab_pin.sym} 210 -360 0 0 {name=l_xpfd_REF lab=REF}
C {devices/lab_pin.sym} 210 -240 0 0 {name=l_xpfd_FB lab=FB}
C {devices/lab_pin.sym} 390 -360 0 0 {name=l_xpfd_UP lab=UP}
C {devices/lab_pin.sym} 390 -240 0 0 {name=l_xpfd_DN lab=DN}
C {devices/lab_pin.sym} 300 -390 0 0 {name=l_xpfd_VDD lab=VDD}
C {devices/lab_pin.sym} 300 -210 0 0 {name=l_xpfd_VSS lab=VSS}
C {cp.sym} 820 -300 0 0 {name=xcp}
C {devices/lab_pin.sym} 730 -540 0 0 {name=l_xcp_UP lab=UP}
C {devices/lab_pin.sym} 730 -470 0 0 {name=l_xcp_DN lab=DN}
C {devices/lab_pin.sym} 730 -405 0 0 {name=l_xcp_B0 lab=B0}
C {devices/lab_pin.sym} 730 -335 0 0 {name=l_xcp_B1 lab=B1}
C {devices/lab_pin.sym} 730 -265 0 0 {name=l_xcp_IBN lab=IBN}
C {devices/lab_pin.sym} 730 -195 0 0 {name=l_xcp_ICN lab=ICN}
C {devices/lab_pin.sym} 730 -130 0 0 {name=l_xcp_IBP lab=IBP}
C {devices/lab_pin.sym} 730 -60 0 0 {name=l_xcp_ICP lab=ICP}
C {devices/lab_pin.sym} 910 -300 0 0 {name=l_xcp_VOUT lab=VOUT}
C {devices/lab_pin.sym} 820 -570 0 0 {name=l_xcp_VDD lab=VDD}
C {devices/lab_pin.sym} 820 -30 0 0 {name=l_xcp_VSS lab=VSS}
C {devices/ipin.sym} 100 -100 0 0 {name=P0 lab=REF}
C {devices/ipin.sym} 100 -120 0 0 {name=P1 lab=FB}
C {devices/ipin.sym} 100 -140 0 0 {name=P2 lab=B0}
C {devices/ipin.sym} 100 -160 0 0 {name=P3 lab=B1}
C {devices/iopin.sym} 100 -180 0 0 {name=P4 lab=IBN}
C {devices/iopin.sym} 100 -200 0 0 {name=P5 lab=ICN}
C {devices/iopin.sym} 100 -220 0 0 {name=P6 lab=IBP}
C {devices/iopin.sym} 100 -240 0 0 {name=P7 lab=ICP}
C {devices/iopin.sym} 100 -260 0 0 {name=P8 lab=VOUT}
C {devices/opin.sym} 100 -280 0 0 {name=P9 lab=UP}
C {devices/opin.sym} 100 -300 0 0 {name=P10 lab=DN}
C {devices/iopin.sym} 100 -320 0 0 {name=P11 lab=VDD}
C {devices/iopin.sym} 100 -340 0 0 {name=P12 lab=VSS}
