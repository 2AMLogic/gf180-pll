v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
T {pfd - tri-state phase-frequency detector (DR-001 Decision 1)} 100 -60 0 0 0.3 0.3 {layer=8}
T {* Tri-state phase-frequency detector: each input's rising edge fires an\n* edge detector that SETs its own NAND SR latch; both latches share one RESET\n* generated as AND(UP, DN) passed through an explicit 24-inverter delay chain\n* (xd1..xd24).\n* \n* That delay chain IS the dead-zone-elimination element, and its length is set\n* by the CHARGE PUMP, not by the logic.  The requirement is not merely that UP\n* and DN both toggle at zero phase error -- they do that for any non-zero reset\n* delay -- but that the minimum UP/DN pulse be long enough for the charge pump's\n* output current to actually ESTABLISH.  The pump's steering switch has to drag\n* its tail node from the dump-node voltage to the control-node voltage before\n* full current reaches the output, and that recovery takes on the order of a\n* nanosecond at the slow/cold/low-supply corners.  A reset delay comparable to\n* that recovery leaves the pump delivering only a fraction of Icp for the whole\n* pulse, so the detector gain collapses near the lock point -- a dead zone in\n* the charge domain even though the logic waveforms look perfect.\n* \n* That is not hypothetical: a 6-inverter chain (about 9 gate delays, giving a\n* 0.5-1.1 ns minimum pulse) was built and measured, and the phase-to-charge\n* transfer went flat at 9 of the 45 PVT corners, all of them slow/cold/low\n* supply.  24 stages carries roughly three times the delay, so the pulse stays\n* several times the tail recovery at every corner.\n* \n* The cost of the longer chain is small and bounded: the constant UP/DN overlap\n* grows, and that overlap converts charge-pump up/down CURRENT mismatch into\n* static phase error at a rate of (overlap x mismatch fraction) -- a few percent\n* of a few nanoseconds, i.e. tens of picoseconds, which is far below the\n* tail-charge offset that dominates the budget (design/README.md).  It also\n* consumes a larger fraction of the reference period, which is why the\n* pfd-deadzone campaign runs at 25 MHz, the top of the ratified range.} 1900 -300 0 0 0.25 0.25 {layer=8}
C {edgedet.sym} 300 -300 0 0 {name=xed_ref}
C {devices/lab_pin.sym} 210 -300 0 0 {name=l_xed_ref_X lab=REF}
C {devices/lab_pin.sym} 390 -300 0 0 {name=l_xed_ref_PULSE lab=PR}
C {devices/lab_pin.sym} 300 -390 0 0 {name=l_xed_ref_VDD lab=VDD}
C {devices/lab_pin.sym} 300 -210 0 0 {name=l_xed_ref_VSS lab=VSS}
C {edgedet.sym} 300 -520 0 0 {name=xed_fb}
C {devices/lab_pin.sym} 210 -520 0 0 {name=l_xed_fb_X lab=FB}
C {devices/lab_pin.sym} 390 -520 0 0 {name=l_xed_fb_PULSE lab=PF}
C {devices/lab_pin.sym} 300 -610 0 0 {name=l_xed_fb_VDD lab=VDD}
C {devices/lab_pin.sym} 300 -430 0 0 {name=l_xed_fb_VSS lab=VSS}
C {inv_3v3.sym} 560 -300 0 0 {name=xinv_sr}
C {devices/lab_pin.sym} 470 -300 0 0 {name=l_xinv_sr_A lab=PR}
C {devices/lab_pin.sym} 650 -300 0 0 {name=l_xinv_sr_Y lab=SBR}
C {devices/lab_pin.sym} 560 -390 0 0 {name=l_xinv_sr_VDD lab=VDD}
C {devices/lab_pin.sym} 560 -210 0 0 {name=l_xinv_sr_VSS lab=VSS}
C {inv_3v3.sym} 560 -520 0 0 {name=xinv_sf}
C {devices/lab_pin.sym} 470 -520 0 0 {name=l_xinv_sf_A lab=PF}
C {devices/lab_pin.sym} 650 -520 0 0 {name=l_xinv_sf_Y lab=SBF}
C {devices/lab_pin.sym} 560 -610 0 0 {name=l_xinv_sf_VDD lab=VDD}
C {devices/lab_pin.sym} 560 -430 0 0 {name=l_xinv_sf_VSS lab=VSS}
C {srlatch.sym} 820 -300 0 0 {name=xlat_ref}
C {devices/lab_pin.sym} 730 -360 0 0 {name=l_xlat_ref_SB lab=SBR}
C {devices/lab_pin.sym} 730 -240 0 0 {name=l_xlat_ref_RB lab=RB}
C {devices/lab_pin.sym} 910 -360 0 0 {name=l_xlat_ref_Q lab=UP}
C {devices/lab_pin.sym} 910 -240 0 0 {name=l_xlat_ref_QB lab=UPB}
C {devices/lab_pin.sym} 820 -390 0 0 {name=l_xlat_ref_VDD lab=VDD}
C {devices/lab_pin.sym} 820 -210 0 0 {name=l_xlat_ref_VSS lab=VSS}
C {srlatch.sym} 820 -520 0 0 {name=xlat_fb}
C {devices/lab_pin.sym} 730 -580 0 0 {name=l_xlat_fb_SB lab=SBF}
C {devices/lab_pin.sym} 730 -460 0 0 {name=l_xlat_fb_RB lab=RB}
C {devices/lab_pin.sym} 910 -580 0 0 {name=l_xlat_fb_Q lab=DN}
C {devices/lab_pin.sym} 910 -460 0 0 {name=l_xlat_fb_QB lab=DNB}
C {devices/lab_pin.sym} 820 -610 0 0 {name=l_xlat_fb_VDD lab=VDD}
C {devices/lab_pin.sym} 820 -430 0 0 {name=l_xlat_fb_VSS lab=VSS}
C {nand2_3v3.sym} 1080 -300 0 0 {name=xnand_rst}
C {devices/lab_pin.sym} 990 -360 0 0 {name=l_xnand_rst_A lab=UP}
C {devices/lab_pin.sym} 990 -240 0 0 {name=l_xnand_rst_B lab=DN}
C {devices/lab_pin.sym} 1170 -300 0 0 {name=l_xnand_rst_Y lab=NRST}
C {devices/lab_pin.sym} 1080 -390 0 0 {name=l_xnand_rst_VDD lab=VDD}
C {devices/lab_pin.sym} 1080 -210 0 0 {name=l_xnand_rst_VSS lab=VSS}
C {inv_3v3.sym} 1340 -300 0 0 {name=xinv_r0}
C {devices/lab_pin.sym} 1250 -300 0 0 {name=l_xinv_r0_A lab=NRST}
C {devices/lab_pin.sym} 1430 -300 0 0 {name=l_xinv_r0_Y lab=RST_RAW}
C {devices/lab_pin.sym} 1340 -390 0 0 {name=l_xinv_r0_VDD lab=VDD}
C {devices/lab_pin.sym} 1340 -210 0 0 {name=l_xinv_r0_VSS lab=VSS}
C {inv_3v3.sym} 300 -740 0 0 {name=xd1}
C {devices/lab_pin.sym} 210 -740 0 0 {name=l_xd1_A lab=RST_RAW}
C {devices/lab_pin.sym} 390 -740 0 0 {name=l_xd1_Y lab=RD1}
C {devices/lab_pin.sym} 300 -830 0 0 {name=l_xd1_VDD lab=VDD}
C {devices/lab_pin.sym} 300 -650 0 0 {name=l_xd1_VSS lab=VSS}
C {inv_3v3.sym} 560 -740 0 0 {name=xd2}
C {devices/lab_pin.sym} 470 -740 0 0 {name=l_xd2_A lab=RD1}
C {devices/lab_pin.sym} 650 -740 0 0 {name=l_xd2_Y lab=RD2}
C {devices/lab_pin.sym} 560 -830 0 0 {name=l_xd2_VDD lab=VDD}
C {devices/lab_pin.sym} 560 -650 0 0 {name=l_xd2_VSS lab=VSS}
C {inv_3v3.sym} 820 -740 0 0 {name=xd3}
C {devices/lab_pin.sym} 730 -740 0 0 {name=l_xd3_A lab=RD2}
C {devices/lab_pin.sym} 910 -740 0 0 {name=l_xd3_Y lab=RD3}
C {devices/lab_pin.sym} 820 -830 0 0 {name=l_xd3_VDD lab=VDD}
C {devices/lab_pin.sym} 820 -650 0 0 {name=l_xd3_VSS lab=VSS}
C {inv_3v3.sym} 1080 -740 0 0 {name=xd4}
C {devices/lab_pin.sym} 990 -740 0 0 {name=l_xd4_A lab=RD3}
C {devices/lab_pin.sym} 1170 -740 0 0 {name=l_xd4_Y lab=RD4}
C {devices/lab_pin.sym} 1080 -830 0 0 {name=l_xd4_VDD lab=VDD}
C {devices/lab_pin.sym} 1080 -650 0 0 {name=l_xd4_VSS lab=VSS}
C {inv_3v3.sym} 1340 -740 0 0 {name=xd5}
C {devices/lab_pin.sym} 1250 -740 0 0 {name=l_xd5_A lab=RD4}
C {devices/lab_pin.sym} 1430 -740 0 0 {name=l_xd5_Y lab=RD5}
C {devices/lab_pin.sym} 1340 -830 0 0 {name=l_xd5_VDD lab=VDD}
C {devices/lab_pin.sym} 1340 -650 0 0 {name=l_xd5_VSS lab=VSS}
C {inv_3v3.sym} 1600 -740 0 0 {name=xd6}
C {devices/lab_pin.sym} 1510 -740 0 0 {name=l_xd6_A lab=RD5}
C {devices/lab_pin.sym} 1690 -740 0 0 {name=l_xd6_Y lab=RD6}
C {devices/lab_pin.sym} 1600 -830 0 0 {name=l_xd6_VDD lab=VDD}
C {devices/lab_pin.sym} 1600 -650 0 0 {name=l_xd6_VSS lab=VSS}
C {inv_3v3.sym} 1860 -740 0 0 {name=xd7}
C {devices/lab_pin.sym} 1770 -740 0 0 {name=l_xd7_A lab=RD6}
C {devices/lab_pin.sym} 1950 -740 0 0 {name=l_xd7_Y lab=RD7}
C {devices/lab_pin.sym} 1860 -830 0 0 {name=l_xd7_VDD lab=VDD}
C {devices/lab_pin.sym} 1860 -650 0 0 {name=l_xd7_VSS lab=VSS}
C {inv_3v3.sym} 2120 -740 0 0 {name=xd8}
C {devices/lab_pin.sym} 2030 -740 0 0 {name=l_xd8_A lab=RD7}
C {devices/lab_pin.sym} 2210 -740 0 0 {name=l_xd8_Y lab=RD8}
C {devices/lab_pin.sym} 2120 -830 0 0 {name=l_xd8_VDD lab=VDD}
C {devices/lab_pin.sym} 2120 -650 0 0 {name=l_xd8_VSS lab=VSS}
C {inv_3v3.sym} 300 -960 0 0 {name=xd9}
C {devices/lab_pin.sym} 210 -960 0 0 {name=l_xd9_A lab=RD8}
C {devices/lab_pin.sym} 390 -960 0 0 {name=l_xd9_Y lab=RD9}
C {devices/lab_pin.sym} 300 -1050 0 0 {name=l_xd9_VDD lab=VDD}
C {devices/lab_pin.sym} 300 -870 0 0 {name=l_xd9_VSS lab=VSS}
C {inv_3v3.sym} 560 -960 0 0 {name=xd10}
C {devices/lab_pin.sym} 470 -960 0 0 {name=l_xd10_A lab=RD9}
C {devices/lab_pin.sym} 650 -960 0 0 {name=l_xd10_Y lab=RD10}
C {devices/lab_pin.sym} 560 -1050 0 0 {name=l_xd10_VDD lab=VDD}
C {devices/lab_pin.sym} 560 -870 0 0 {name=l_xd10_VSS lab=VSS}
C {inv_3v3.sym} 820 -960 0 0 {name=xd11}
C {devices/lab_pin.sym} 730 -960 0 0 {name=l_xd11_A lab=RD10}
C {devices/lab_pin.sym} 910 -960 0 0 {name=l_xd11_Y lab=RD11}
C {devices/lab_pin.sym} 820 -1050 0 0 {name=l_xd11_VDD lab=VDD}
C {devices/lab_pin.sym} 820 -870 0 0 {name=l_xd11_VSS lab=VSS}
C {inv_3v3.sym} 1080 -960 0 0 {name=xd12}
C {devices/lab_pin.sym} 990 -960 0 0 {name=l_xd12_A lab=RD11}
C {devices/lab_pin.sym} 1170 -960 0 0 {name=l_xd12_Y lab=RD12}
C {devices/lab_pin.sym} 1080 -1050 0 0 {name=l_xd12_VDD lab=VDD}
C {devices/lab_pin.sym} 1080 -870 0 0 {name=l_xd12_VSS lab=VSS}
C {inv_3v3.sym} 1340 -960 0 0 {name=xd13}
C {devices/lab_pin.sym} 1250 -960 0 0 {name=l_xd13_A lab=RD12}
C {devices/lab_pin.sym} 1430 -960 0 0 {name=l_xd13_Y lab=RD13}
C {devices/lab_pin.sym} 1340 -1050 0 0 {name=l_xd13_VDD lab=VDD}
C {devices/lab_pin.sym} 1340 -870 0 0 {name=l_xd13_VSS lab=VSS}
C {inv_3v3.sym} 1600 -960 0 0 {name=xd14}
C {devices/lab_pin.sym} 1510 -960 0 0 {name=l_xd14_A lab=RD13}
C {devices/lab_pin.sym} 1690 -960 0 0 {name=l_xd14_Y lab=RD14}
C {devices/lab_pin.sym} 1600 -1050 0 0 {name=l_xd14_VDD lab=VDD}
C {devices/lab_pin.sym} 1600 -870 0 0 {name=l_xd14_VSS lab=VSS}
C {inv_3v3.sym} 1860 -960 0 0 {name=xd15}
C {devices/lab_pin.sym} 1770 -960 0 0 {name=l_xd15_A lab=RD14}
C {devices/lab_pin.sym} 1950 -960 0 0 {name=l_xd15_Y lab=RD15}
C {devices/lab_pin.sym} 1860 -1050 0 0 {name=l_xd15_VDD lab=VDD}
C {devices/lab_pin.sym} 1860 -870 0 0 {name=l_xd15_VSS lab=VSS}
C {inv_3v3.sym} 2120 -960 0 0 {name=xd16}
C {devices/lab_pin.sym} 2030 -960 0 0 {name=l_xd16_A lab=RD15}
C {devices/lab_pin.sym} 2210 -960 0 0 {name=l_xd16_Y lab=RD16}
C {devices/lab_pin.sym} 2120 -1050 0 0 {name=l_xd16_VDD lab=VDD}
C {devices/lab_pin.sym} 2120 -870 0 0 {name=l_xd16_VSS lab=VSS}
C {inv_3v3.sym} 300 -1180 0 0 {name=xd17}
C {devices/lab_pin.sym} 210 -1180 0 0 {name=l_xd17_A lab=RD16}
C {devices/lab_pin.sym} 390 -1180 0 0 {name=l_xd17_Y lab=RD17}
C {devices/lab_pin.sym} 300 -1270 0 0 {name=l_xd17_VDD lab=VDD}
C {devices/lab_pin.sym} 300 -1090 0 0 {name=l_xd17_VSS lab=VSS}
C {inv_3v3.sym} 560 -1180 0 0 {name=xd18}
C {devices/lab_pin.sym} 470 -1180 0 0 {name=l_xd18_A lab=RD17}
C {devices/lab_pin.sym} 650 -1180 0 0 {name=l_xd18_Y lab=RD18}
C {devices/lab_pin.sym} 560 -1270 0 0 {name=l_xd18_VDD lab=VDD}
C {devices/lab_pin.sym} 560 -1090 0 0 {name=l_xd18_VSS lab=VSS}
C {inv_3v3.sym} 820 -1180 0 0 {name=xd19}
C {devices/lab_pin.sym} 730 -1180 0 0 {name=l_xd19_A lab=RD18}
C {devices/lab_pin.sym} 910 -1180 0 0 {name=l_xd19_Y lab=RD19}
C {devices/lab_pin.sym} 820 -1270 0 0 {name=l_xd19_VDD lab=VDD}
C {devices/lab_pin.sym} 820 -1090 0 0 {name=l_xd19_VSS lab=VSS}
C {inv_3v3.sym} 1080 -1180 0 0 {name=xd20}
C {devices/lab_pin.sym} 990 -1180 0 0 {name=l_xd20_A lab=RD19}
C {devices/lab_pin.sym} 1170 -1180 0 0 {name=l_xd20_Y lab=RD20}
C {devices/lab_pin.sym} 1080 -1270 0 0 {name=l_xd20_VDD lab=VDD}
C {devices/lab_pin.sym} 1080 -1090 0 0 {name=l_xd20_VSS lab=VSS}
C {inv_3v3.sym} 1340 -1180 0 0 {name=xd21}
C {devices/lab_pin.sym} 1250 -1180 0 0 {name=l_xd21_A lab=RD20}
C {devices/lab_pin.sym} 1430 -1180 0 0 {name=l_xd21_Y lab=RD21}
C {devices/lab_pin.sym} 1340 -1270 0 0 {name=l_xd21_VDD lab=VDD}
C {devices/lab_pin.sym} 1340 -1090 0 0 {name=l_xd21_VSS lab=VSS}
C {inv_3v3.sym} 1600 -1180 0 0 {name=xd22}
C {devices/lab_pin.sym} 1510 -1180 0 0 {name=l_xd22_A lab=RD21}
C {devices/lab_pin.sym} 1690 -1180 0 0 {name=l_xd22_Y lab=RD22}
C {devices/lab_pin.sym} 1600 -1270 0 0 {name=l_xd22_VDD lab=VDD}
C {devices/lab_pin.sym} 1600 -1090 0 0 {name=l_xd22_VSS lab=VSS}
C {inv_3v3.sym} 1860 -1180 0 0 {name=xd23}
C {devices/lab_pin.sym} 1770 -1180 0 0 {name=l_xd23_A lab=RD22}
C {devices/lab_pin.sym} 1950 -1180 0 0 {name=l_xd23_Y lab=RD23}
C {devices/lab_pin.sym} 1860 -1270 0 0 {name=l_xd23_VDD lab=VDD}
C {devices/lab_pin.sym} 1860 -1090 0 0 {name=l_xd23_VSS lab=VSS}
C {inv_3v3.sym} 2120 -1180 0 0 {name=xd24}
C {devices/lab_pin.sym} 2030 -1180 0 0 {name=l_xd24_A lab=RD23}
C {devices/lab_pin.sym} 2210 -1180 0 0 {name=l_xd24_Y lab=RST_DLY}
C {devices/lab_pin.sym} 2120 -1270 0 0 {name=l_xd24_VDD lab=VDD}
C {devices/lab_pin.sym} 2120 -1090 0 0 {name=l_xd24_VSS lab=VSS}
C {inv_3v3.sym} 300 -1400 0 0 {name=xinv_rb}
C {devices/lab_pin.sym} 210 -1400 0 0 {name=l_xinv_rb_A lab=RST_DLY}
C {devices/lab_pin.sym} 390 -1400 0 0 {name=l_xinv_rb_Y lab=RB}
C {devices/lab_pin.sym} 300 -1490 0 0 {name=l_xinv_rb_VDD lab=VDD}
C {devices/lab_pin.sym} 300 -1310 0 0 {name=l_xinv_rb_VSS lab=VSS}
C {devices/ipin.sym} 100 -100 0 0 {name=P0 lab=REF}
C {devices/ipin.sym} 100 -120 0 0 {name=P1 lab=FB}
C {devices/opin.sym} 100 -140 0 0 {name=P2 lab=UP}
C {devices/opin.sym} 100 -160 0 0 {name=P3 lab=DN}
C {devices/iopin.sym} 100 -180 0 0 {name=P4 lab=VDD}
C {devices/iopin.sym} 100 -200 0 0 {name=P5 lab=VSS}
