v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
T {edgedet - rising-edge pulse generator (AND of X and delayed-inverted X)} 100 -60 0 0 0.3 0.3 {layer=8}
T {* PULSE = AND(X, NOT(X delayed by 5 inverter stages)): a narrow high pulse\n* on every rising edge of X, about 5 inverter delays wide.  This pulse SETs one\n* of the PFD's two latches.\n* \n* The chain length is bounded on BOTH sides, and both bounds are ratios of gate\n* delays, so they hold across PVT rather than at one corner:\n* \n*   - Longer than the SR latch's own Q -> QB loop delay (one NAND).  A set pulse\n*     that is released before QB has responded lets the latch fall back for one\n*     NAND delay and re-set, which shows up as a narrow glitch splitting the\n*     UP pulse in two right at zero phase error -- i.e. a non-monotonic\n*     phase-to-charge transfer exactly where the loop lives.  A 3-stage chain\n*     was measured doing precisely that on the UP branch (the branch loaded by\n*     the reset NAND's inner input); 5 stages carries roughly 5x the latch loop\n*     delay.\n*   - Shorter than the PFD's reset delay (about 9 gate delays), else set and\n*     reset would be asserted together.\n* \n* The pfd-deadzone campaign measures both the UP/DN pulse width and the\n* phase-to-charge transfer that these bounds protect.} 1900 -300 0 0 0.25 0.25 {layer=8}
C {pfd_inv_3v3.sym} 300 -300 0 0 {name=xi1}
C {devices/lab_pin.sym} 210 -300 0 0 {name=l_xi1_A lab=X}
C {devices/lab_pin.sym} 390 -300 0 0 {name=l_xi1_Y lab=D1}
C {devices/lab_pin.sym} 300 -390 0 0 {name=l_xi1_VDD lab=VDD}
C {devices/lab_pin.sym} 300 -210 0 0 {name=l_xi1_VSS lab=VSS}
C {pfd_inv_3v3.sym} 560 -300 0 0 {name=xi2}
C {devices/lab_pin.sym} 470 -300 0 0 {name=l_xi2_A lab=D1}
C {devices/lab_pin.sym} 650 -300 0 0 {name=l_xi2_Y lab=D2}
C {devices/lab_pin.sym} 560 -390 0 0 {name=l_xi2_VDD lab=VDD}
C {devices/lab_pin.sym} 560 -210 0 0 {name=l_xi2_VSS lab=VSS}
C {pfd_inv_3v3.sym} 820 -300 0 0 {name=xi3}
C {devices/lab_pin.sym} 730 -300 0 0 {name=l_xi3_A lab=D2}
C {devices/lab_pin.sym} 910 -300 0 0 {name=l_xi3_Y lab=D3}
C {devices/lab_pin.sym} 820 -390 0 0 {name=l_xi3_VDD lab=VDD}
C {devices/lab_pin.sym} 820 -210 0 0 {name=l_xi3_VSS lab=VSS}
C {pfd_inv_3v3.sym} 1080 -300 0 0 {name=xi4}
C {devices/lab_pin.sym} 990 -300 0 0 {name=l_xi4_A lab=D3}
C {devices/lab_pin.sym} 1170 -300 0 0 {name=l_xi4_Y lab=D4}
C {devices/lab_pin.sym} 1080 -390 0 0 {name=l_xi4_VDD lab=VDD}
C {devices/lab_pin.sym} 1080 -210 0 0 {name=l_xi4_VSS lab=VSS}
C {pfd_inv_3v3.sym} 1340 -300 0 0 {name=xi5}
C {devices/lab_pin.sym} 1250 -300 0 0 {name=l_xi5_A lab=D4}
C {devices/lab_pin.sym} 1430 -300 0 0 {name=l_xi5_Y lab=D5}
C {devices/lab_pin.sym} 1340 -390 0 0 {name=l_xi5_VDD lab=VDD}
C {devices/lab_pin.sym} 1340 -210 0 0 {name=l_xi5_VSS lab=VSS}
C {pfd_nand2_3v3.sym} 300 -520 0 0 {name=xnd}
C {devices/lab_pin.sym} 210 -580 0 0 {name=l_xnd_A lab=X}
C {devices/lab_pin.sym} 210 -460 0 0 {name=l_xnd_B lab=D5}
C {devices/lab_pin.sym} 390 -520 0 0 {name=l_xnd_Y lab=NN}
C {devices/lab_pin.sym} 300 -610 0 0 {name=l_xnd_VDD lab=VDD}
C {devices/lab_pin.sym} 300 -430 0 0 {name=l_xnd_VSS lab=VSS}
C {pfd_inv_3v3.sym} 560 -520 0 0 {name=xi6}
C {devices/lab_pin.sym} 470 -520 0 0 {name=l_xi6_A lab=NN}
C {devices/lab_pin.sym} 650 -520 0 0 {name=l_xi6_Y lab=PULSE}
C {devices/lab_pin.sym} 560 -610 0 0 {name=l_xi6_VDD lab=VDD}
C {devices/lab_pin.sym} 560 -430 0 0 {name=l_xi6_VSS lab=VSS}
C {devices/ipin.sym} 100 -100 0 0 {name=P0 lab=X}
C {devices/opin.sym} 100 -120 0 0 {name=P1 lab=PULSE}
C {devices/iopin.sym} 100 -140 0 0 {name=P2 lab=VDD}
C {devices/iopin.sym} 100 -160 0 0 {name=P3 lab=VSS}
