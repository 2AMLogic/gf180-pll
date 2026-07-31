v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
T {vco_stage: current-starved CMOS inverter delay cell (DR-001 Decision 2)} -400 -420 0 0 0.4 0.4 {}
T {matched PMOS-head / NMOS-tail starving devices, gates from the band-select bias mirror} -400 -390 0 0 0.4 0.4 {}
C {ipin.sym} -400 -100 0 0 {name=p_a lab=A}
C {opin.sym} -400 -60 0 0 {name=p_y lab=Y}
C {iopin.sym} -400 -20 0 0 {name=p_vdd lab=VDD}
C {iopin.sym} -400 20 0 0 {name=p_vss lab=VSS}
C {iopin.sym} -400 60 0 0 {name=p_vbp lab=VBP}
C {iopin.sym} -400 100 0 0 {name=p_vbn lab=VBN}
C {pfet_03v3.sym} 0 -300 0 0 {name=MPH model=pfet_03v3 W=10u L=0.5u nf=1 m=1}
C {lab_pin.sym} 20 -270 0 0 {name=l_MPH_D lab=NH}
C {lab_pin.sym} -20 -300 0 0 {name=l_MPH_G lab=VBP}
C {lab_pin.sym} 20 -330 0 0 {name=l_MPH_S lab=VDD}
C {lab_pin.sym} 20 -300 0 0 {name=l_MPH_B lab=VDD}
C {pfet_03v3.sym} 0 -100 0 0 {name=MP model=pfet_03v3 W=5u L=0.28u nf=1 m=1}
C {lab_pin.sym} 20 -70 0 0 {name=l_MP_D lab=Y}
C {lab_pin.sym} -20 -100 0 0 {name=l_MP_G lab=A}
C {lab_pin.sym} 20 -130 0 0 {name=l_MP_S lab=NH}
C {lab_pin.sym} 20 -100 0 0 {name=l_MP_B lab=VDD}
C {nfet_03v3.sym} 0 100 0 0 {name=MN model=nfet_03v3 W=2u L=0.28u nf=1 m=1}
C {lab_pin.sym} 20 70 0 0 {name=l_MN_D lab=Y}
C {lab_pin.sym} -20 100 0 0 {name=l_MN_G lab=A}
C {lab_pin.sym} 20 130 0 0 {name=l_MN_S lab=NT}
C {lab_pin.sym} 20 100 0 0 {name=l_MN_B lab=VSS}
C {nfet_03v3.sym} 0 300 0 0 {name=MNT model=nfet_03v3 W=4u L=0.5u nf=1 m=1}
C {lab_pin.sym} 20 270 0 0 {name=l_MNT_D lab=NT}
C {lab_pin.sym} -20 300 0 0 {name=l_MNT_G lab=VBN}
C {lab_pin.sym} 20 330 0 0 {name=l_MNT_S lab=VSS}
C {lab_pin.sym} 20 300 0 0 {name=l_MNT_B lab=VSS}
