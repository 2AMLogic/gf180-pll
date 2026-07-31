v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
T {loop_filter: passive fixed 2nd-order loop filter (DR-001 Decision 1, sized by #10 / DR-005)} -700 -560 0 0 0.4 0.4 {}
T {VCTRL --+-- C2 -- VSS          zero  fz = 1/(2*pi*R*C1)     ~ 17 kHz typ} -700 -530 0 0 0.4 0.4 {}
T {        +-- R -- NZ -- C1 -- VSS    3rd pole fp = (C1+C2)/(2*pi*R*C1*C2) ~ 1.0 MHz typ} -700 -500 0 0 0.4 0.4 {}
T {No R/C trim banks: DR-001 Decision 1 rejects filter-side programmability.} -700 -470 0 0 0.4 0.4 {}
T {The only loop-side knob is the charge pump's 2-bit Icp trim (design/cp.sch).} -700 -440 0 0 0.4 0.4 {}
C {iopin.sym} -700 -380 0 0 {name=p_vctrl lab=VCTRL}
C {iopin.sym} -700 -340 0 0 {name=p_vss lab=VSS}

T {series R = 4 x ppolyf_u, W = 2 um, L = 107 um  ->  77.1 kOhm typ (61.6 .. 92.9 kOhm over res_ff/res_ss x -40..125 C)} -400 -280 0 0 0.4 0.4 {}
T {ppolyf_u is the near-zero-tempco poly option (-75 ppm/C) from sim/devchar-passives (#4)} -400 -250 0 0 0.4 0.4 {}
C {ppolyf_u.sym} -300 -100 0 0 {name=RF1 model=ppolyf_u W=2u L=107u m=1}
C {lab_pin.sym} -300 -130 0 0 {name=l_RF1_P lab=VCTRL}
C {lab_pin.sym} -300 -70 0 0 {name=l_RF1_M lab=NR1}
C {lab_pin.sym} -320 -100 0 0 {name=l_RF1_B lab=VSS}
C {ppolyf_u.sym} -150 -100 0 0 {name=RF2 model=ppolyf_u W=2u L=107u m=1}
C {lab_pin.sym} -150 -130 0 0 {name=l_RF2_P lab=NR1}
C {lab_pin.sym} -150 -70 0 0 {name=l_RF2_M lab=NR2}
C {lab_pin.sym} -170 -100 0 0 {name=l_RF2_B lab=VSS}
C {ppolyf_u.sym} 0 -100 0 0 {name=RF3 model=ppolyf_u W=2u L=107u m=1}
C {lab_pin.sym} 0 -130 0 0 {name=l_RF3_P lab=NR2}
C {lab_pin.sym} 0 -70 0 0 {name=l_RF3_M lab=NR3}
C {lab_pin.sym} -20 -100 0 0 {name=l_RF3_B lab=VSS}
C {ppolyf_u.sym} 150 -100 0 0 {name=RF4 model=ppolyf_u W=2u L=107u m=1}
C {lab_pin.sym} 150 -130 0 0 {name=l_RF4_P lab=NR3}
C {lab_pin.sym} 150 -70 0 0 {name=l_RF4_M lab=NZ}
C {lab_pin.sym} 130 -100 0 0 {name=l_RF4_B lab=VSS}

T {C1 = 4 x cap_nmos_03v3_b, 87 x 87 um = 30276 um^2 -> 120.7 pF typ (20.2 % of the 0.15 mm^2 area budget)} -400 60 0 0 0.4 0.4 {}
T {body-tied (accumulation-mode) MOS cap: cv_ratio 1.10 vs 45x for the raw cap_nmos_03v3 (sim/devchar-passives, #4)} -400 90 0 0 0.4 0.4 {}
T {gate (G) on the filter node, bulk (B) on VSS -- the gate has no junction to the substrate, the well would} -400 120 0 0 0.4 0.4 {}
C {cap_nmos_03v3_b.sym} -300 250 0 0 {name=CF1 model=cap_nmos_03v3_b W=87u L=87u m=1}
C {lab_pin.sym} -300 220 0 0 {name=l_CF1_G lab=NZ}
C {lab_pin.sym} -300 280 0 0 {name=l_CF1_B lab=VSS}
C {cap_nmos_03v3_b.sym} -150 250 0 0 {name=CF2 model=cap_nmos_03v3_b W=87u L=87u m=1}
C {lab_pin.sym} -150 220 0 0 {name=l_CF2_G lab=NZ}
C {lab_pin.sym} -150 280 0 0 {name=l_CF2_B lab=VSS}
C {cap_nmos_03v3_b.sym} 0 250 0 0 {name=CF3 model=cap_nmos_03v3_b W=87u L=87u m=1}
C {lab_pin.sym} 0 220 0 0 {name=l_CF3_G lab=NZ}
C {lab_pin.sym} 0 280 0 0 {name=l_CF3_B lab=VSS}
C {cap_nmos_03v3_b.sym} 150 250 0 0 {name=CF4 model=cap_nmos_03v3_b W=87u L=87u m=1}
C {lab_pin.sym} 150 220 0 0 {name=l_CF4_G lab=NZ}
C {lab_pin.sym} 150 280 0 0 {name=l_CF4_B lab=VSS}

T {C2 = 1 x cap_mim_2f0_m2m3_noshield, 31.4 x 31.4 um -> 1.99 pF typ (ideally linear, cv_ratio 1.0000)} 400 60 0 0 0.4 0.4 {}
T {MIM sits on the Vctrl node itself, where a voltage-dependent C would modulate the ripple pole} 400 90 0 0 0.4 0.4 {}
C {cap_mim_2f0fF.sym} 500 250 0 0 {name=CF5 model=cap_mim_2f0_m2m3_noshield W=31.4u L=31.4u m=1}
C {lab_pin.sym} 500 220 0 0 {name=l_CF5_G lab=VCTRL}
C {lab_pin.sym} 500 280 0 0 {name=l_CF5_B lab=VSS}
