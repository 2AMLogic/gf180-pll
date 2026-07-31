v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
T {gf180-pll :: divider_chain -- programmable integer-N feedback divider,
N = 4..64 continuous. DR-001 Decision 3, DR-002 Decision 3 (3.3 V flavour only).

Six IDENTICAL div23_cell instances (XD0 = fastest, sees the VCO) plus:
  - chain-length termination : MODIN_i = MO_(i+1) + SEL_i, so the modulus
    chain is terminated at the last ACTIVE cell (the one with SEL_i = 1);
  - output multiplexer       : DIVOUT = OR_i (CKOUT_i . SEL_i), an AND-OR
    tree (XM0..XM5 / XMA / XMB / XMNO / XIDO);
  - retiming flop XFRT       : FB = DFF(DIVOUT) clocked by the VCO, so the
    edge the PFD sees is a VCO edge delayed by exactly one clk->Q,
    independent of N.

SEL is a one-hot chain-length code: SEL_i = 1 selects cell i as the last
active cell, i.e. k = i+1 active cells and N = 2^k + sum(P_j . 2^j), j < k.
  SEL1 -> k=2 -> N = 4..7      SEL4 -> k=5 -> N = 32..63
  SEL2 -> k=3 -> N = 8..15     SEL5 -> k=6 -> N = 64..127
  SEL3 -> k=4 -> N = 16..31
(SEL0 -> k=1 -> N=2..3 exists for free and is outside the ratified 4..64
range; N > 64 likewise, and per DR-001 neither is a spec claim.)

N is a STATIC configuration (DR-001: glitch-free on-the-fly modulus switching
is out of v1 scope); the loop re-locks after a change.

Supply: dedicated vdd_div domain (DR-001 Decision 3), brought out as the
VDD_DIV pin, so divider switching noise does not land on vdd_vco.

The first cell XD0 is the only cell that runs at the full VCO rate and is
therefore the only one that has to be optimised (DR-001: divider power is
~2x the first cell, not k x). It is instantiated separately from the rest
precisely so it stays swappable for the 400 MHz stretch (DR-001's documented
TSPC fallback) without touching the chain.} -1000 -1400 0 0 0.4 0.4 {}
C {ipin.sym} -1000 -300 0 0 {name=pv lab=VCO}
C {ipin.sym} -1000 -200 0 0 {name=pp0 lab=P0}
C {ipin.sym} -1000 -180 0 0 {name=pp1 lab=P1}
C {ipin.sym} -1000 -160 0 0 {name=pp2 lab=P2}
C {ipin.sym} -1000 -140 0 0 {name=pp3 lab=P3}
C {ipin.sym} -1000 -120 0 0 {name=pp4 lab=P4}
C {ipin.sym} -1000 -100 0 0 {name=pp5 lab=P5}
C {ipin.sym} -1000 -80 0 0 {name=ps0 lab=SEL0}
C {ipin.sym} -1000 -60 0 0 {name=ps1 lab=SEL1}
C {ipin.sym} -1000 -40 0 0 {name=ps2 lab=SEL2}
C {ipin.sym} -1000 -20 0 0 {name=ps3 lab=SEL3}
C {ipin.sym} -1000 0 0 0 {name=ps4 lab=SEL4}
C {ipin.sym} -1000 20 0 0 {name=ps5 lab=SEL5}
C {opin.sym} -1000 60 0 0 {name=pdo lab=DIVOUT}
C {opin.sym} -1000 80 0 0 {name=pfb lab=FB}
C {iopin.sym} -1000 120 0 0 {name=pvd lab=VDD_DIV}
C {iopin.sym} -1000 160 0 0 {name=pvs lab=VSS}
C {div23_cell.sym} 0 0 0 0 {name=XD0}
C {lab_pin.sym} -60 -30 0 0 {name=a01 lab=VCO}
C {lab_pin.sym} -60 0 0 0 {name=a02 lab=MI0}
C {lab_pin.sym} -60 30 0 0 {name=a03 lab=P0}
C {lab_pin.sym} 60 -30 0 0 {name=a04 lab=CK1}
C {lab_pin.sym} 60 0 0 0 {name=a05 lab=MO0}
C {lab_pin.sym} 0 -60 0 0 {name=a06 lab=VDD_DIV}
C {lab_pin.sym} 0 60 0 0 {name=a07 lab=VSS}
C {div23_cell.sym} 400 0 0 0 {name=XD1}
C {lab_pin.sym} 340 -30 0 0 {name=a11 lab=CK1}
C {lab_pin.sym} 340 0 0 0 {name=a12 lab=MI1}
C {lab_pin.sym} 340 30 0 0 {name=a13 lab=P1}
C {lab_pin.sym} 460 -30 0 0 {name=a14 lab=CK2}
C {lab_pin.sym} 460 0 0 0 {name=a15 lab=MO1}
C {lab_pin.sym} 400 -60 0 0 {name=a16 lab=VDD_DIV}
C {lab_pin.sym} 400 60 0 0 {name=a17 lab=VSS}
C {div23_cell.sym} 800 0 0 0 {name=XD2}
C {lab_pin.sym} 740 -30 0 0 {name=a21 lab=CK2}
C {lab_pin.sym} 740 0 0 0 {name=a22 lab=MI2}
C {lab_pin.sym} 740 30 0 0 {name=a23 lab=P2}
C {lab_pin.sym} 860 -30 0 0 {name=a24 lab=CK3}
C {lab_pin.sym} 860 0 0 0 {name=a25 lab=MO2}
C {lab_pin.sym} 800 -60 0 0 {name=a26 lab=VDD_DIV}
C {lab_pin.sym} 800 60 0 0 {name=a27 lab=VSS}
C {div23_cell.sym} 1200 0 0 0 {name=XD3}
C {lab_pin.sym} 1140 -30 0 0 {name=a31 lab=CK3}
C {lab_pin.sym} 1140 0 0 0 {name=a32 lab=MI3}
C {lab_pin.sym} 1140 30 0 0 {name=a33 lab=P3}
C {lab_pin.sym} 1260 -30 0 0 {name=a34 lab=CK4}
C {lab_pin.sym} 1260 0 0 0 {name=a35 lab=MO3}
C {lab_pin.sym} 1200 -60 0 0 {name=a36 lab=VDD_DIV}
C {lab_pin.sym} 1200 60 0 0 {name=a37 lab=VSS}
C {div23_cell.sym} 1600 0 0 0 {name=XD4}
C {lab_pin.sym} 1540 -30 0 0 {name=a41 lab=CK4}
C {lab_pin.sym} 1540 0 0 0 {name=a42 lab=MI4}
C {lab_pin.sym} 1540 30 0 0 {name=a43 lab=P4}
C {lab_pin.sym} 1660 -30 0 0 {name=a44 lab=CK5}
C {lab_pin.sym} 1660 0 0 0 {name=a45 lab=MO4}
C {lab_pin.sym} 1600 -60 0 0 {name=a46 lab=VDD_DIV}
C {lab_pin.sym} 1600 60 0 0 {name=a47 lab=VSS}
C {div23_cell.sym} 2000 0 0 0 {name=XD5}
C {lab_pin.sym} 1940 -30 0 0 {name=a51 lab=CK5}
C {lab_pin.sym} 1940 0 0 0 {name=a52 lab=SEL5}
C {lab_pin.sym} 1940 30 0 0 {name=a53 lab=P5}
C {lab_pin.sym} 2060 -30 0 0 {name=a54 lab=CK6}
C {lab_pin.sym} 2060 0 0 0 {name=a55 lab=MO5}
C {lab_pin.sym} 2000 -60 0 0 {name=a56 lab=VDD_DIV}
C {lab_pin.sym} 2000 60 0 0 {name=a57 lab=VSS}
C {nor2_3v3.sym} 0 400 0 0 {name=XNR0}
C {lab_pin.sym} -40 380 0 0 {name=b01 lab=MO1}
C {lab_pin.sym} -40 420 0 0 {name=b02 lab=SEL0}
C {lab_pin.sym} 40 400 0 0 {name=b03 lab=NMI0}
C {lab_pin.sym} 0 360 0 0 {name=b04 lab=VDD_DIV}
C {lab_pin.sym} 0 440 0 0 {name=b05 lab=VSS}
C {inv_3v3.sym} 200 400 0 0 {name=XIV0}
C {lab_pin.sym} 160 400 0 0 {name=b06 lab=NMI0}
C {lab_pin.sym} 240 400 0 0 {name=b07 lab=MI0}
C {lab_pin.sym} 200 360 0 0 {name=b08 lab=VDD_DIV}
C {lab_pin.sym} 200 440 0 0 {name=b09 lab=VSS}
C {nor2_3v3.sym} 400 400 0 0 {name=XNR1}
C {lab_pin.sym} 360 380 0 0 {name=b11 lab=MO2}
C {lab_pin.sym} 360 420 0 0 {name=b12 lab=SEL1}
C {lab_pin.sym} 440 400 0 0 {name=b13 lab=NMI1}
C {lab_pin.sym} 400 360 0 0 {name=b14 lab=VDD_DIV}
C {lab_pin.sym} 400 440 0 0 {name=b15 lab=VSS}
C {inv_3v3.sym} 600 400 0 0 {name=XIV1}
C {lab_pin.sym} 560 400 0 0 {name=b16 lab=NMI1}
C {lab_pin.sym} 640 400 0 0 {name=b17 lab=MI1}
C {lab_pin.sym} 600 360 0 0 {name=b18 lab=VDD_DIV}
C {lab_pin.sym} 600 440 0 0 {name=b19 lab=VSS}
C {nor2_3v3.sym} 800 400 0 0 {name=XNR2}
C {lab_pin.sym} 760 380 0 0 {name=b21 lab=MO3}
C {lab_pin.sym} 760 420 0 0 {name=b22 lab=SEL2}
C {lab_pin.sym} 840 400 0 0 {name=b23 lab=NMI2}
C {lab_pin.sym} 800 360 0 0 {name=b24 lab=VDD_DIV}
C {lab_pin.sym} 800 440 0 0 {name=b25 lab=VSS}
C {inv_3v3.sym} 1000 400 0 0 {name=XIV2}
C {lab_pin.sym} 960 400 0 0 {name=b26 lab=NMI2}
C {lab_pin.sym} 1040 400 0 0 {name=b27 lab=MI2}
C {lab_pin.sym} 1000 360 0 0 {name=b28 lab=VDD_DIV}
C {lab_pin.sym} 1000 440 0 0 {name=b29 lab=VSS}
C {nor2_3v3.sym} 1200 400 0 0 {name=XNR3}
C {lab_pin.sym} 1160 380 0 0 {name=b31 lab=MO4}
C {lab_pin.sym} 1160 420 0 0 {name=b32 lab=SEL3}
C {lab_pin.sym} 1240 400 0 0 {name=b33 lab=NMI3}
C {lab_pin.sym} 1200 360 0 0 {name=b34 lab=VDD_DIV}
C {lab_pin.sym} 1200 440 0 0 {name=b35 lab=VSS}
C {inv_3v3.sym} 1400 400 0 0 {name=XIV3}
C {lab_pin.sym} 1360 400 0 0 {name=b36 lab=NMI3}
C {lab_pin.sym} 1440 400 0 0 {name=b37 lab=MI3}
C {lab_pin.sym} 1400 360 0 0 {name=b38 lab=VDD_DIV}
C {lab_pin.sym} 1400 440 0 0 {name=b39 lab=VSS}
C {nor2_3v3.sym} 1600 400 0 0 {name=XNR4}
C {lab_pin.sym} 1560 380 0 0 {name=b41 lab=MO5}
C {lab_pin.sym} 1560 420 0 0 {name=b42 lab=SEL4}
C {lab_pin.sym} 1640 400 0 0 {name=b43 lab=NMI4}
C {lab_pin.sym} 1600 360 0 0 {name=b44 lab=VDD_DIV}
C {lab_pin.sym} 1600 440 0 0 {name=b45 lab=VSS}
C {inv_3v3.sym} 1800 400 0 0 {name=XIV4}
C {lab_pin.sym} 1760 400 0 0 {name=b46 lab=NMI4}
C {lab_pin.sym} 1840 400 0 0 {name=b47 lab=MI4}
C {lab_pin.sym} 1800 360 0 0 {name=b48 lab=VDD_DIV}
C {lab_pin.sym} 1800 440 0 0 {name=b49 lab=VSS}
C {nand2_3v3.sym} 0 800 0 0 {name=XM0}
C {lab_pin.sym} -40 780 0 0 {name=c01 lab=CK1}
C {lab_pin.sym} -40 820 0 0 {name=c02 lab=SEL0}
C {lab_pin.sym} 40 800 0 0 {name=c03 lab=T0}
C {lab_pin.sym} 0 760 0 0 {name=c04 lab=VDD_DIV}
C {lab_pin.sym} 0 840 0 0 {name=c05 lab=VSS}
C {nand2_3v3.sym} 300 800 0 0 {name=XM1}
C {lab_pin.sym} 260 780 0 0 {name=c11 lab=CK2}
C {lab_pin.sym} 260 820 0 0 {name=c12 lab=SEL1}
C {lab_pin.sym} 340 800 0 0 {name=c13 lab=T1}
C {lab_pin.sym} 300 760 0 0 {name=c14 lab=VDD_DIV}
C {lab_pin.sym} 300 840 0 0 {name=c15 lab=VSS}
C {nand2_3v3.sym} 600 800 0 0 {name=XM2}
C {lab_pin.sym} 560 780 0 0 {name=c21 lab=CK3}
C {lab_pin.sym} 560 820 0 0 {name=c22 lab=SEL2}
C {lab_pin.sym} 640 800 0 0 {name=c23 lab=T2}
C {lab_pin.sym} 600 760 0 0 {name=c24 lab=VDD_DIV}
C {lab_pin.sym} 600 840 0 0 {name=c25 lab=VSS}
C {nand2_3v3.sym} 900 800 0 0 {name=XM3}
C {lab_pin.sym} 860 780 0 0 {name=c31 lab=CK4}
C {lab_pin.sym} 860 820 0 0 {name=c32 lab=SEL3}
C {lab_pin.sym} 940 800 0 0 {name=c33 lab=T3}
C {lab_pin.sym} 900 760 0 0 {name=c34 lab=VDD_DIV}
C {lab_pin.sym} 900 840 0 0 {name=c35 lab=VSS}
C {nand2_3v3.sym} 1200 800 0 0 {name=XM4}
C {lab_pin.sym} 1160 780 0 0 {name=c41 lab=CK5}
C {lab_pin.sym} 1160 820 0 0 {name=c42 lab=SEL4}
C {lab_pin.sym} 1240 800 0 0 {name=c43 lab=T4}
C {lab_pin.sym} 1200 760 0 0 {name=c44 lab=VDD_DIV}
C {lab_pin.sym} 1200 840 0 0 {name=c45 lab=VSS}
C {nand2_3v3.sym} 1500 800 0 0 {name=XM5}
C {lab_pin.sym} 1460 780 0 0 {name=c51 lab=CK6}
C {lab_pin.sym} 1460 820 0 0 {name=c52 lab=SEL5}
C {lab_pin.sym} 1540 800 0 0 {name=c53 lab=T5}
C {lab_pin.sym} 1500 760 0 0 {name=c54 lab=VDD_DIV}
C {lab_pin.sym} 1500 840 0 0 {name=c55 lab=VSS}
C {nand3_3v3.sym} 0 1100 0 0 {name=XMA}
C {lab_pin.sym} -40 1080 0 0 {name=d01 lab=T0}
C {lab_pin.sym} -40 1100 0 0 {name=d02 lab=T1}
C {lab_pin.sym} -40 1120 0 0 {name=d03 lab=T2}
C {lab_pin.sym} 40 1100 0 0 {name=d04 lab=MA}
C {lab_pin.sym} 0 1060 0 0 {name=d05 lab=VDD_DIV}
C {lab_pin.sym} 0 1140 0 0 {name=d06 lab=VSS}
C {nand3_3v3.sym} 400 1100 0 0 {name=XMB}
C {lab_pin.sym} 360 1080 0 0 {name=d11 lab=T3}
C {lab_pin.sym} 360 1100 0 0 {name=d12 lab=T4}
C {lab_pin.sym} 360 1120 0 0 {name=d13 lab=T5}
C {lab_pin.sym} 440 1100 0 0 {name=d14 lab=MB}
C {lab_pin.sym} 400 1060 0 0 {name=d15 lab=VDD_DIV}
C {lab_pin.sym} 400 1140 0 0 {name=d16 lab=VSS}
C {nor2_3v3.sym} 800 1100 0 0 {name=XMNO}
C {lab_pin.sym} 760 1080 0 0 {name=d21 lab=MA}
C {lab_pin.sym} 760 1120 0 0 {name=d22 lab=MB}
C {lab_pin.sym} 840 1100 0 0 {name=d23 lab=DIVOUTB}
C {lab_pin.sym} 800 1060 0 0 {name=d24 lab=VDD_DIV}
C {lab_pin.sym} 800 1140 0 0 {name=d25 lab=VSS}
C {inv2x_3v3.sym} 1100 1100 0 0 {name=XIDO}
C {lab_pin.sym} 1060 1100 0 0 {name=d31 lab=DIVOUTB}
C {lab_pin.sym} 1140 1100 0 0 {name=d32 lab=DIVOUT}
C {lab_pin.sym} 1100 1060 0 0 {name=d33 lab=VDD_DIV}
C {lab_pin.sym} 1100 1140 0 0 {name=d34 lab=VSS}
C {dff_tg_3v3.sym} 0 1400 0 0 {name=XFRT}
C {lab_pin.sym} -50 1380 0 0 {name=e01 lab=DIVOUT}
C {lab_pin.sym} -50 1420 0 0 {name=e02 lab=VCO}
C {lab_pin.sym} 50 1380 0 0 {name=e03 lab=FB}
C {lab_pin.sym} 50 1420 0 0 {name=e04 lab=FBB}
C {lab_pin.sym} 0 1350 0 0 {name=e05 lab=VDD_DIV}
C {lab_pin.sym} 0 1450 0 0 {name=e06 lab=VSS}
