v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
T {vco_bias: supply-independent bias + source-degenerated V->I + 3-bit geometric band-select mirror} -700 -720 0 0 0.4 0.4 {}
T {I_stage = ((VCTRL + Voff)/Rdeg) * A0 * g^code,  g = 1.65  (see spec/decision-records/DR-003)} -700 -690 0 0 0.4 0.4 {}
C {ipin.sym} -700 -300 0 0 {name=p_vctrl lab=VCTRL}
C {ipin.sym} -700 -260 0 0 {name=p_b0 lab=B0}
C {ipin.sym} -700 -220 0 0 {name=p_b1 lab=B1}
C {ipin.sym} -700 -180 0 0 {name=p_b2 lab=B2}
C {iopin.sym} -700 -140 0 0 {name=p_vbp lab=VBP}
C {iopin.sym} -700 -100 0 0 {name=p_vbn lab=VBN}
C {iopin.sym} -700 -60 0 0 {name=p_vdd lab=VDD}
C {iopin.sym} -700 -20 0 0 {name=p_vss lab=VSS}
T {constant-gm core (beta-multiplier, K=4) + startup} -300 -520 0 0 0.4 0.4 {}
C {pfet_03v3.sym} -200 -400 0 0 {name=MP1 model=pfet_03v3 W=10u L=1u nf=1 m=1}
C {lab_pin.sym} -180 -370 0 0 {name=l_MP1_D lab=NA}
C {lab_pin.sym} -220 -400 0 0 {name=l_MP1_G lab=VBPC}
C {lab_pin.sym} -180 -430 0 0 {name=l_MP1_S lab=VDD}
C {lab_pin.sym} -180 -400 0 0 {name=l_MP1_B lab=VDD}
C {pfet_03v3.sym} 0 -400 0 0 {name=MP2 model=pfet_03v3 W=10u L=1u nf=1 m=1}
C {lab_pin.sym} 20 -370 0 0 {name=l_MP2_D lab=VBPC}
C {lab_pin.sym} -20 -400 0 0 {name=l_MP2_G lab=VBPC}
C {lab_pin.sym} 20 -430 0 0 {name=l_MP2_S lab=VDD}
C {lab_pin.sym} 20 -400 0 0 {name=l_MP2_B lab=VDD}
C {nfet_03v3.sym} -200 -200 0 0 {name=MN1 model=nfet_03v3 W=1.4u L=1u nf=1 m=1}
C {lab_pin.sym} -180 -230 0 0 {name=l_MN1_D lab=NA}
C {lab_pin.sym} -220 -200 0 0 {name=l_MN1_G lab=NA}
C {lab_pin.sym} -180 -170 0 0 {name=l_MN1_S lab=VSS}
C {lab_pin.sym} -180 -200 0 0 {name=l_MN1_B lab=VSS}
C {nfet_03v3.sym} 0 -200 0 0 {name=MN2 model=nfet_03v3 W=5.6u L=1u nf=1 m=1}
C {lab_pin.sym} 20 -230 0 0 {name=l_MN2_D lab=VBPC}
C {lab_pin.sym} -20 -200 0 0 {name=l_MN2_G lab=NA}
C {lab_pin.sym} 20 -170 0 0 {name=l_MN2_S lab=NC}
C {lab_pin.sym} 20 -200 0 0 {name=l_MN2_B lab=VSS}
C {ppolyf_u_3k.sym} 0 0 0 0 {name=RCG model=ppolyf_u_3k W=1u L=5.6u m=1}
C {lab_pin.sym} 0 30 0 0 {name=l_RCG_M lab=NC}
C {lab_pin.sym} 0 -30 0 0 {name=l_RCG_P lab=VSS}
C {lab_pin.sym} -20 0 0 0 {name=l_RCG_B lab=VSS}
C {pfet_03v3.sym} -400 -400 0 0 {name=MSU1 model=pfet_03v3 W=0.22u L=20u nf=1 m=1}
C {lab_pin.sym} -380 -370 0 0 {name=l_MSU1_D lab=NSU}
C {lab_pin.sym} -420 -400 0 0 {name=l_MSU1_G lab=VSS}
C {lab_pin.sym} -380 -430 0 0 {name=l_MSU1_S lab=VDD}
C {lab_pin.sym} -380 -400 0 0 {name=l_MSU1_B lab=VDD}
C {nfet_03v3.sym} -400 -200 0 0 {name=MSU2 model=nfet_03v3 W=2u L=1u nf=1 m=1}
C {lab_pin.sym} -380 -230 0 0 {name=l_MSU2_D lab=NSU}
C {lab_pin.sym} -420 -200 0 0 {name=l_MSU2_G lab=NA}
C {lab_pin.sym} -380 -170 0 0 {name=l_MSU2_S lab=VSS}
C {lab_pin.sym} -380 -200 0 0 {name=l_MSU2_B lab=VSS}
C {nfet_03v3.sym} -400 0 0 0 {name=MSU3 model=nfet_03v3 W=1u L=1u nf=1 m=1}
C {lab_pin.sym} -380 -30 0 0 {name=l_MSU3_D lab=VBPC}
C {lab_pin.sym} -420 0 0 0 {name=l_MSU3_G lab=NSU}
C {lab_pin.sym} -380 30 0 0 {name=l_MSU3_S lab=VSS}
C {lab_pin.sym} -380 0 0 0 {name=l_MSU3_B lab=VSS}
T {2*Vgs reference stack} 200 -520 0 0 0.4 0.4 {}
C {pfet_03v3.sym} 200 -400 0 0 {name=MPR model=pfet_03v3 W=2.5u L=1u nf=1 m=1}
C {lab_pin.sym} 220 -370 0 0 {name=l_MPR_D lab=VFIX}
C {lab_pin.sym} 180 -400 0 0 {name=l_MPR_G lab=VBPC}
C {lab_pin.sym} 220 -430 0 0 {name=l_MPR_S lab=VDD}
C {lab_pin.sym} 220 -400 0 0 {name=l_MPR_B lab=VDD}
C {nfet_03v3.sym} 200 -200 0 0 {name=MD1 model=nfet_03v3 W=2u L=1u nf=1 m=1}
C {lab_pin.sym} 220 -230 0 0 {name=l_MD1_D lab=VFIX}
C {lab_pin.sym} 180 -200 0 0 {name=l_MD1_G lab=VFIX}
C {lab_pin.sym} 220 -170 0 0 {name=l_MD1_S lab=NMD}
C {lab_pin.sym} 220 -200 0 0 {name=l_MD1_B lab=VSS}
C {nfet_03v3.sym} 200 0 0 0 {name=MD2 model=nfet_03v3 W=2u L=1u nf=1 m=1}
C {lab_pin.sym} 220 -30 0 0 {name=l_MD2_D lab=NMD}
C {lab_pin.sym} 180 0 0 0 {name=l_MD2_G lab=NMD}
C {lab_pin.sym} 220 30 0 0 {name=l_MD2_S lab=VSS}
C {lab_pin.sym} 220 0 0 0 {name=l_MD2_B lab=VSS}
T {offset branch / source-degenerated V->I / summing node} 500 -520 0 0 0.4 0.4 {}
C {nfet_03v3.sym} 500 -300 0 0 {name=MOFF model=nfet_03v3 W=10u L=1u nf=1 m=1}
C {lab_pin.sym} 520 -330 0 0 {name=l_MOFF_D lab=VBP0}
C {lab_pin.sym} 480 -300 0 0 {name=l_MOFF_G lab=VFIX}
C {lab_pin.sym} 520 -270 0 0 {name=l_MOFF_S lab=NOFF}
C {lab_pin.sym} 520 -300 0 0 {name=l_MOFF_B lab=VSS}
C {ppolyf_u_3k.sym} 500 -100 0 0 {name=ROFF model=ppolyf_u_3k W=1u L=33u m=1}
C {lab_pin.sym} 500 -70 0 0 {name=l_ROFF_M lab=NOFF}
C {lab_pin.sym} 500 -130 0 0 {name=l_ROFF_P lab=VSS}
C {lab_pin.sym} 480 -100 0 0 {name=l_ROFF_B lab=VSS}
C {nfet_03v3.sym} 800 -300 0 0 {name=MVI model=nfet_03v3 W=10u L=1u nf=1 m=1}
C {lab_pin.sym} 820 -330 0 0 {name=l_MVI_D lab=VBP0}
C {lab_pin.sym} 780 -300 0 0 {name=l_MVI_G lab=VCTRL}
C {lab_pin.sym} 820 -270 0 0 {name=l_MVI_S lab=NVI}
C {lab_pin.sym} 820 -300 0 0 {name=l_MVI_B lab=VSS}
C {ppolyf_u_3k.sym} 800 -100 0 0 {name=RDEG model=ppolyf_u_3k W=1u L=33u m=1}
C {lab_pin.sym} 800 -70 0 0 {name=l_RDEG_M lab=NVI}
C {lab_pin.sym} 800 -130 0 0 {name=l_RDEG_P lab=VSS}
C {lab_pin.sym} 780 -100 0 0 {name=l_RDEG_B lab=VSS}
C {pfet_03v3.sym} 1100 -300 0 0 {name=MSUM model=pfet_03v3 W=60u L=1u nf=4 m=1}
C {lab_pin.sym} 1120 -270 0 0 {name=l_MSUM_D lab=VBP0}
C {lab_pin.sym} 1080 -300 0 0 {name=l_MSUM_G lab=VBP0}
C {lab_pin.sym} 1120 -330 0 0 {name=l_MSUM_S lab=VDD}
C {lab_pin.sym} 1120 -300 0 0 {name=l_MSUM_B lab=VDD}
T {band-code inverters} -300 200 0 0 0.4 0.4 {}
C {pfet_03v3.sym} -300 300 0 0 {name=MIP0 model=pfet_03v3 W=2u L=0.28u nf=1 m=1}
C {lab_pin.sym} -280 330 0 0 {name=l_MIP0_D lab=B0B}
C {lab_pin.sym} -320 300 0 0 {name=l_MIP0_G lab=B0}
C {lab_pin.sym} -280 270 0 0 {name=l_MIP0_S lab=VDD}
C {lab_pin.sym} -280 300 0 0 {name=l_MIP0_B lab=VDD}
C {nfet_03v3.sym} -300 500 0 0 {name=MIN0 model=nfet_03v3 W=1u L=0.28u nf=1 m=1}
C {lab_pin.sym} -280 470 0 0 {name=l_MIN0_D lab=B0B}
C {lab_pin.sym} -320 500 0 0 {name=l_MIN0_G lab=B0}
C {lab_pin.sym} -280 530 0 0 {name=l_MIN0_S lab=VSS}
C {lab_pin.sym} -280 500 0 0 {name=l_MIN0_B lab=VSS}
C {pfet_03v3.sym} -100 300 0 0 {name=MIP1 model=pfet_03v3 W=2u L=0.28u nf=1 m=1}
C {lab_pin.sym} -80 330 0 0 {name=l_MIP1_D lab=B1B}
C {lab_pin.sym} -120 300 0 0 {name=l_MIP1_G lab=B1}
C {lab_pin.sym} -80 270 0 0 {name=l_MIP1_S lab=VDD}
C {lab_pin.sym} -80 300 0 0 {name=l_MIP1_B lab=VDD}
C {nfet_03v3.sym} -100 500 0 0 {name=MIN1 model=nfet_03v3 W=1u L=0.28u nf=1 m=1}
C {lab_pin.sym} -80 470 0 0 {name=l_MIN1_D lab=B1B}
C {lab_pin.sym} -120 500 0 0 {name=l_MIN1_G lab=B1}
C {lab_pin.sym} -80 530 0 0 {name=l_MIN1_S lab=VSS}
C {lab_pin.sym} -80 500 0 0 {name=l_MIN1_B lab=VSS}
C {pfet_03v3.sym} 100 300 0 0 {name=MIP2 model=pfet_03v3 W=2u L=0.28u nf=1 m=1}
C {lab_pin.sym} 120 330 0 0 {name=l_MIP2_D lab=B2B}
C {lab_pin.sym} 80 300 0 0 {name=l_MIP2_G lab=B2}
C {lab_pin.sym} 120 270 0 0 {name=l_MIP2_S lab=VDD}
C {lab_pin.sym} 120 300 0 0 {name=l_MIP2_B lab=VDD}
C {nfet_03v3.sym} 100 500 0 0 {name=MIN2 model=nfet_03v3 W=1u L=0.28u nf=1 m=1}
C {lab_pin.sym} 120 470 0 0 {name=l_MIN2_D lab=B2B}
C {lab_pin.sym} 80 500 0 0 {name=l_MIN2_G lab=B2}
C {lab_pin.sym} 120 530 0 0 {name=l_MIN2_S lab=VSS}
C {lab_pin.sym} 120 500 0 0 {name=l_MIN2_B lab=VSS}
T {band cascade A (x1.65 when B0)} 300 200 0 0 0.4 0.4 {}
C {pfet_03v3.sym} 300 300 0 0 {name=MA0 model=pfet_03v3 W=26.5u L=1u nf=2 m=1}
C {lab_pin.sym} 320 330 0 0 {name=l_MA0_D lab=VBN1}
C {lab_pin.sym} 280 300 0 0 {name=l_MA0_G lab=VBP0}
C {lab_pin.sym} 320 270 0 0 {name=l_MA0_S lab=VDD}
C {lab_pin.sym} 320 300 0 0 {name=l_MA0_B lab=VDD}
C {pfet_03v3.sym} 500 300 0 0 {name=MA1 model=pfet_03v3 W=17.225u L=1u nf=2 m=1}
C {lab_pin.sym} 520 330 0 0 {name=l_MA1_D lab=VBN1}
C {lab_pin.sym} 480 300 0 0 {name=l_MA1_G lab=GA}
C {lab_pin.sym} 520 270 0 0 {name=l_MA1_S lab=VDD}
C {lab_pin.sym} 520 300 0 0 {name=l_MA1_B lab=VDD}
C {pfet_03v3.sym} 300 500 0 0 {name=MSWA0 model=pfet_03v3 W=2u L=0.5u nf=1 m=1}
C {lab_pin.sym} 320 530 0 0 {name=l_MSWA0_D lab=GA}
C {lab_pin.sym} 280 500 0 0 {name=l_MSWA0_G lab=B0B}
C {lab_pin.sym} 320 470 0 0 {name=l_MSWA0_S lab=VBP0}
C {lab_pin.sym} 320 500 0 0 {name=l_MSWA0_B lab=VDD}
C {pfet_03v3.sym} 500 500 0 0 {name=MSWA1 model=pfet_03v3 W=2u L=0.5u nf=1 m=1}
C {lab_pin.sym} 520 530 0 0 {name=l_MSWA1_D lab=GA}
C {lab_pin.sym} 480 500 0 0 {name=l_MSWA1_G lab=B0}
C {lab_pin.sym} 520 470 0 0 {name=l_MSWA1_S lab=VDD}
C {lab_pin.sym} 520 500 0 0 {name=l_MSWA1_B lab=VDD}
C {nfet_03v3.sym} 700 300 0 0 {name=MDA model=nfet_03v3 W=10u L=1u nf=1 m=1}
C {lab_pin.sym} 720 270 0 0 {name=l_MDA_D lab=VBN1}
C {lab_pin.sym} 680 300 0 0 {name=l_MDA_G lab=VBN1}
C {lab_pin.sym} 720 330 0 0 {name=l_MDA_S lab=VSS}
C {lab_pin.sym} 720 300 0 0 {name=l_MDA_B lab=VSS}
T {band cascade B (x2.7225 when B1)} 900 200 0 0 0.4 0.4 {}
C {nfet_03v3.sym} 900 300 0 0 {name=MB0 model=nfet_03v3 W=5u L=1u nf=1 m=1}
C {lab_pin.sym} 920 270 0 0 {name=l_MB0_D lab=VBP2}
C {lab_pin.sym} 880 300 0 0 {name=l_MB0_G lab=VBN1}
C {lab_pin.sym} 920 330 0 0 {name=l_MB0_S lab=VSS}
C {lab_pin.sym} 920 300 0 0 {name=l_MB0_B lab=VSS}
C {nfet_03v3.sym} 1100 300 0 0 {name=MB1 model=nfet_03v3 W=8.6125u L=1u nf=1 m=1}
C {lab_pin.sym} 1120 270 0 0 {name=l_MB1_D lab=VBP2}
C {lab_pin.sym} 1080 300 0 0 {name=l_MB1_G lab=GB}
C {lab_pin.sym} 1120 330 0 0 {name=l_MB1_S lab=VSS}
C {lab_pin.sym} 1120 300 0 0 {name=l_MB1_B lab=VSS}
C {nfet_03v3.sym} 900 500 0 0 {name=MSWB0 model=nfet_03v3 W=2u L=0.5u nf=1 m=1}
C {lab_pin.sym} 920 470 0 0 {name=l_MSWB0_D lab=GB}
C {lab_pin.sym} 880 500 0 0 {name=l_MSWB0_G lab=B1}
C {lab_pin.sym} 920 530 0 0 {name=l_MSWB0_S lab=VBN1}
C {lab_pin.sym} 920 500 0 0 {name=l_MSWB0_B lab=VSS}
C {nfet_03v3.sym} 1100 500 0 0 {name=MSWB1 model=nfet_03v3 W=2u L=0.5u nf=1 m=1}
C {lab_pin.sym} 1120 470 0 0 {name=l_MSWB1_D lab=GB}
C {lab_pin.sym} 1080 500 0 0 {name=l_MSWB1_G lab=B1B}
C {lab_pin.sym} 1120 530 0 0 {name=l_MSWB1_S lab=VSS}
C {lab_pin.sym} 1120 500 0 0 {name=l_MSWB1_B lab=VSS}
C {pfet_03v3.sym} 1300 300 0 0 {name=MDB model=pfet_03v3 W=20u L=1u nf=1 m=1}
C {lab_pin.sym} 1320 330 0 0 {name=l_MDB_D lab=VBP2}
C {lab_pin.sym} 1280 300 0 0 {name=l_MDB_G lab=VBP2}
C {lab_pin.sym} 1320 270 0 0 {name=l_MDB_S lab=VDD}
C {lab_pin.sym} 1320 300 0 0 {name=l_MDB_B lab=VDD}
T {band cascade C (x7.4120 when B2)} 300 700 0 0 0.4 0.4 {}
C {pfet_03v3.sym} 300 800 0 0 {name=MC0 model=pfet_03v3 W=12.3u L=1u nf=1 m=1}
C {lab_pin.sym} 320 830 0 0 {name=l_MC0_D lab=VBN}
C {lab_pin.sym} 280 800 0 0 {name=l_MC0_G lab=VBP2}
C {lab_pin.sym} 320 770 0 0 {name=l_MC0_S lab=VDD}
C {lab_pin.sym} 320 800 0 0 {name=l_MC0_B lab=VDD}
C {pfet_03v3.sym} 500 800 0 0 {name=MC1 model=pfet_03v3 W=78.87u L=1u nf=8 m=1}
C {lab_pin.sym} 520 830 0 0 {name=l_MC1_D lab=VBN}
C {lab_pin.sym} 480 800 0 0 {name=l_MC1_G lab=GC}
C {lab_pin.sym} 520 770 0 0 {name=l_MC1_S lab=VDD}
C {lab_pin.sym} 520 800 0 0 {name=l_MC1_B lab=VDD}
C {pfet_03v3.sym} 300 1000 0 0 {name=MSWC0 model=pfet_03v3 W=2u L=0.5u nf=1 m=1}
C {lab_pin.sym} 320 1030 0 0 {name=l_MSWC0_D lab=GC}
C {lab_pin.sym} 280 1000 0 0 {name=l_MSWC0_G lab=B2B}
C {lab_pin.sym} 320 970 0 0 {name=l_MSWC0_S lab=VBP2}
C {lab_pin.sym} 320 1000 0 0 {name=l_MSWC0_B lab=VDD}
C {pfet_03v3.sym} 500 1000 0 0 {name=MSWC1 model=pfet_03v3 W=2u L=0.5u nf=1 m=1}
C {lab_pin.sym} 520 1030 0 0 {name=l_MSWC1_D lab=GC}
C {lab_pin.sym} 480 1000 0 0 {name=l_MSWC1_G lab=B2}
C {lab_pin.sym} 520 970 0 0 {name=l_MSWC1_S lab=VDD}
C {lab_pin.sym} 520 1000 0 0 {name=l_MSWC1_B lab=VDD}
T {output bias diodes (1:1 with the stage starving devices)} 900 700 0 0 0.4 0.4 {}
C {nfet_03v3.sym} 900 800 0 0 {name=MDN model=nfet_03v3 W=4u L=0.5u nf=1 m=1}
C {lab_pin.sym} 920 770 0 0 {name=l_MDN_D lab=VBN}
C {lab_pin.sym} 880 800 0 0 {name=l_MDN_G lab=VBN}
C {lab_pin.sym} 920 830 0 0 {name=l_MDN_S lab=VSS}
C {lab_pin.sym} 920 800 0 0 {name=l_MDN_B lab=VSS}
C {nfet_03v3.sym} 1100 800 0 0 {name=MMN model=nfet_03v3 W=4u L=0.5u nf=1 m=1}
C {lab_pin.sym} 1120 770 0 0 {name=l_MMN_D lab=VBP}
C {lab_pin.sym} 1080 800 0 0 {name=l_MMN_G lab=VBN}
C {lab_pin.sym} 1120 830 0 0 {name=l_MMN_S lab=VSS}
C {lab_pin.sym} 1120 800 0 0 {name=l_MMN_B lab=VSS}
C {pfet_03v3.sym} 1300 800 0 0 {name=MDP model=pfet_03v3 W=10u L=0.5u nf=1 m=1}
C {lab_pin.sym} 1320 830 0 0 {name=l_MDP_D lab=VBP}
C {lab_pin.sym} 1280 800 0 0 {name=l_MDP_G lab=VBP}
C {lab_pin.sym} 1320 770 0 0 {name=l_MDP_S lab=VDD}
C {lab_pin.sym} 1320 800 0 0 {name=l_MDP_B lab=VDD}
