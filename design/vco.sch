v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
T {vco: 5-stage current-starved ring VCO, dedicated VDD_VCO/GND_VCO domain (DR-001 Decision 2)} -700 -620 0 0 0.4 0.4 {}
C {ipin.sym} -700 -300 0 0 {name=p_vctrl lab=VCTRL}
C {ipin.sym} -700 -260 0 0 {name=p_b0 lab=B0}
C {ipin.sym} -700 -220 0 0 {name=p_b1 lab=B1}
C {ipin.sym} -700 -180 0 0 {name=p_b2 lab=B2}
C {opin.sym} -700 -140 0 0 {name=p_clk lab=CLK}
C {iopin.sym} -700 -100 0 0 {name=p_vdd lab=VDD_VCO}
C {iopin.sym} -700 -60 0 0 {name=p_gnd lab=GND_VCO}
C {vco_bias.sym} -300 0 0 0 {name=XBIAS}
C {lab_pin.sym} -400 -60 0 0 {name=l_XBIAS_VCTRL lab=VCTRL}
C {lab_pin.sym} -400 -20 0 0 {name=l_XBIAS_B0 lab=B0}
C {lab_pin.sym} -400 20 0 0 {name=l_XBIAS_B1 lab=B1}
C {lab_pin.sym} -400 60 0 0 {name=l_XBIAS_B2 lab=B2}
C {lab_pin.sym} -200 -60 0 0 {name=l_XBIAS_VBP lab=VBP}
C {lab_pin.sym} -200 -20 0 0 {name=l_XBIAS_VBN lab=VBN}
C {lab_pin.sym} -200 20 0 0 {name=l_XBIAS_VDD lab=VDD_VCO}
C {lab_pin.sym} -200 60 0 0 {name=l_XBIAS_VSS lab=GND_VCO}
C {vco_stage.sym} 100 0 0 0 {name=XS1}
C {lab_pin.sym} 0 -60 0 0 {name=l_XS1_A lab=Y5}
C {lab_pin.sym} 0 -20 0 0 {name=l_XS1_Y lab=Y1}
C {lab_pin.sym} 0 20 0 0 {name=l_XS1_VDD lab=VDD_VCO}
C {lab_pin.sym} 200 -60 0 0 {name=l_XS1_VSS lab=GND_VCO}
C {lab_pin.sym} 200 -20 0 0 {name=l_XS1_VBP lab=VBP}
C {lab_pin.sym} 200 20 0 0 {name=l_XS1_VBN lab=VBN}
C {vco_stage.sym} 400 0 0 0 {name=XS2}
C {lab_pin.sym} 300 -60 0 0 {name=l_XS2_A lab=Y1}
C {lab_pin.sym} 300 -20 0 0 {name=l_XS2_Y lab=Y2}
C {lab_pin.sym} 300 20 0 0 {name=l_XS2_VDD lab=VDD_VCO}
C {lab_pin.sym} 500 -60 0 0 {name=l_XS2_VSS lab=GND_VCO}
C {lab_pin.sym} 500 -20 0 0 {name=l_XS2_VBP lab=VBP}
C {lab_pin.sym} 500 20 0 0 {name=l_XS2_VBN lab=VBN}
C {vco_stage.sym} 700 0 0 0 {name=XS3}
C {lab_pin.sym} 600 -60 0 0 {name=l_XS3_A lab=Y2}
C {lab_pin.sym} 600 -20 0 0 {name=l_XS3_Y lab=Y3}
C {lab_pin.sym} 600 20 0 0 {name=l_XS3_VDD lab=VDD_VCO}
C {lab_pin.sym} 800 -60 0 0 {name=l_XS3_VSS lab=GND_VCO}
C {lab_pin.sym} 800 -20 0 0 {name=l_XS3_VBP lab=VBP}
C {lab_pin.sym} 800 20 0 0 {name=l_XS3_VBN lab=VBN}
C {vco_stage.sym} 1000 0 0 0 {name=XS4}
C {lab_pin.sym} 900 -60 0 0 {name=l_XS4_A lab=Y3}
C {lab_pin.sym} 900 -20 0 0 {name=l_XS4_Y lab=Y4}
C {lab_pin.sym} 900 20 0 0 {name=l_XS4_VDD lab=VDD_VCO}
C {lab_pin.sym} 1100 -60 0 0 {name=l_XS4_VSS lab=GND_VCO}
C {lab_pin.sym} 1100 -20 0 0 {name=l_XS4_VBP lab=VBP}
C {lab_pin.sym} 1100 20 0 0 {name=l_XS4_VBN lab=VBN}
C {vco_stage.sym} 1300 0 0 0 {name=XS5}
C {lab_pin.sym} 1200 -60 0 0 {name=l_XS5_A lab=Y4}
C {lab_pin.sym} 1200 -20 0 0 {name=l_XS5_Y lab=Y5}
C {lab_pin.sym} 1200 20 0 0 {name=l_XS5_VDD lab=VDD_VCO}
C {lab_pin.sym} 1400 -60 0 0 {name=l_XS5_VSS lab=GND_VCO}
C {lab_pin.sym} 1400 -20 0 0 {name=l_XS5_VBP lab=VBP}
C {lab_pin.sym} 1400 20 0 0 {name=l_XS5_VBN lab=VBN}
T {tapered output buffer (small first stage keeps crowbar current low on slow ring edges)} 100 500 0 0 0.4 0.4 {}
C {pfet_03v3.sym} 200 700 0 0 {name=MBP1 model=pfet_03v3 W=1.25u L=0.28u nf=1 m=1}
C {lab_pin.sym} 220 730 0 0 {name=l_MBP1_D lab=NB1}
C {lab_pin.sym} 180 700 0 0 {name=l_MBP1_G lab=Y5}
C {lab_pin.sym} 220 670 0 0 {name=l_MBP1_S lab=VDD_VCO}
C {lab_pin.sym} 220 700 0 0 {name=l_MBP1_B lab=VDD_VCO}
C {nfet_03v3.sym} 200 900 0 0 {name=MBN1 model=nfet_03v3 W=0.5u L=0.28u nf=1 m=1}
C {lab_pin.sym} 220 870 0 0 {name=l_MBN1_D lab=NB1}
C {lab_pin.sym} 180 900 0 0 {name=l_MBN1_G lab=Y5}
C {lab_pin.sym} 220 930 0 0 {name=l_MBN1_S lab=GND_VCO}
C {lab_pin.sym} 220 900 0 0 {name=l_MBN1_B lab=GND_VCO}
C {pfet_03v3.sym} 500 700 0 0 {name=MBP2 model=pfet_03v3 W=3.75u L=0.28u nf=1 m=1}
C {lab_pin.sym} 520 730 0 0 {name=l_MBP2_D lab=NB2}
C {lab_pin.sym} 480 700 0 0 {name=l_MBP2_G lab=NB1}
C {lab_pin.sym} 520 670 0 0 {name=l_MBP2_S lab=VDD_VCO}
C {lab_pin.sym} 520 700 0 0 {name=l_MBP2_B lab=VDD_VCO}
C {nfet_03v3.sym} 500 900 0 0 {name=MBN2 model=nfet_03v3 W=1.5u L=0.28u nf=1 m=1}
C {lab_pin.sym} 520 870 0 0 {name=l_MBN2_D lab=NB2}
C {lab_pin.sym} 480 900 0 0 {name=l_MBN2_G lab=NB1}
C {lab_pin.sym} 520 930 0 0 {name=l_MBN2_S lab=GND_VCO}
C {lab_pin.sym} 520 900 0 0 {name=l_MBN2_B lab=GND_VCO}
C {pfet_03v3.sym} 800 700 0 0 {name=MBP3 model=pfet_03v3 W=11.25u L=0.28u nf=1 m=1}
C {lab_pin.sym} 820 730 0 0 {name=l_MBP3_D lab=CLK}
C {lab_pin.sym} 780 700 0 0 {name=l_MBP3_G lab=NB2}
C {lab_pin.sym} 820 670 0 0 {name=l_MBP3_S lab=VDD_VCO}
C {lab_pin.sym} 820 700 0 0 {name=l_MBP3_B lab=VDD_VCO}
C {nfet_03v3.sym} 800 900 0 0 {name=MBN3 model=nfet_03v3 W=4.5u L=0.28u nf=1 m=1}
C {lab_pin.sym} 820 870 0 0 {name=l_MBN3_D lab=CLK}
C {lab_pin.sym} 780 900 0 0 {name=l_MBN3_G lab=NB2}
C {lab_pin.sym} 820 930 0 0 {name=l_MBN3_S lab=GND_VCO}
C {lab_pin.sym} 820 900 0 0 {name=l_MBN3_B lab=GND_VCO}
T {dedicated on-chip decoupling on the VCO domain (~22 pF)} 1100 500 0 0 0.4 0.4 {}
C {cap_nmos_03v3.sym} 1200 700 0 0 {name=CDEC1 model=cap_nmos_03v3 W=50u L=50u m=1}
C {lab_pin.sym} 1200 670 0 0 {name=l_CDEC1_G lab=VDD_VCO}
C {lab_pin.sym} 1200 730 0 0 {name=l_CDEC1_B lab=GND_VCO}
C {cap_nmos_03v3.sym} 1400 700 0 0 {name=CDEC2 model=cap_nmos_03v3 W=50u L=50u m=1}
C {lab_pin.sym} 1400 670 0 0 {name=l_CDEC2_G lab=VDD_VCO}
C {lab_pin.sym} 1400 730 0 0 {name=l_CDEC2_B lab=GND_VCO}
