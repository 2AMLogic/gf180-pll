v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
T {pfd - tri-state phase-frequency detector (DR-001 Decision 1)} 100 -60 0 0 0.3 0.3 {layer=8}
T {* Tri-state phase-frequency detector: each input's rising edge fires an\n* edge detector that SETs its own NAND SR latch; both latches share one RESET\n* generated as AND(UP, DN) passed through an explicit 6-inverter delay chain\n* (xd1..xd6).\n* \n* That delay chain IS the dead-zone-elimination element.  With it, UP and DN\n* both stay asserted for the reset-path delay even when REF and FB coincide\n* exactly, so the charge pump's switches are fully turned on at zero phase error\n* and the phase-to-charge transfer stays linear through zero.  Shortening it\n* saves nothing that matters and reintroduces the dead zone; lengthening it\n* raises the constant UP/DN overlap that converts charge-pump up/down current\n* mismatch into static phase error, so it is a budgeted quantity, not a free\n* parameter -- see design/README.md and the pfd-deadzone / pfd-cp-charge\n* campaigns under sim/.} 1900 -300 0 0 0.25 0.25 {layer=8}
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
C {devices/lab_pin.sym} 1690 -740 0 0 {name=l_xd6_Y lab=RST_DLY}
C {devices/lab_pin.sym} 1600 -830 0 0 {name=l_xd6_VDD lab=VDD}
C {devices/lab_pin.sym} 1600 -650 0 0 {name=l_xd6_VSS lab=VSS}
C {inv_3v3.sym} 1860 -740 0 0 {name=xinv_rb}
C {devices/lab_pin.sym} 1770 -740 0 0 {name=l_xinv_rb_A lab=RST_DLY}
C {devices/lab_pin.sym} 1950 -740 0 0 {name=l_xinv_rb_Y lab=RB}
C {devices/lab_pin.sym} 1860 -830 0 0 {name=l_xinv_rb_VDD lab=VDD}
C {devices/lab_pin.sym} 1860 -650 0 0 {name=l_xinv_rb_VSS lab=VSS}
C {devices/ipin.sym} 100 -100 0 0 {name=P0 lab=REF}
C {devices/ipin.sym} 100 -120 0 0 {name=P1 lab=FB}
C {devices/opin.sym} 100 -140 0 0 {name=P2 lab=UP}
C {devices/opin.sym} 100 -160 0 0 {name=P3 lab=DN}
C {devices/iopin.sym} 100 -180 0 0 {name=P4 lab=VDD}
C {devices/iopin.sym} 100 -200 0 0 {name=P5 lab=VSS}
