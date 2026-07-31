v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
T {cp - charge pump: 2-bit unit-element Icp trim, wide-swing cascode output} 100 -60 0 0 0.3 0.3 {layer=8}
T {* Charge pump for the type-II loop of DR-001 Decision 1.\n* \n* Trim: Icp = Iunit * (1 + B0 + 2*B1) -- one always-on unit leg plus one\n* B0-gated unit and two B1-gated units per polarity.  Binary weight is built\n* from IDENTICAL unit legs rather than a 2x-wide device, so the per-leg\n* overdrive (and therefore the compliance limit) does not move with the trim\n* code.  This 2-bit coarse Icp trim is the ONLY loop-side programmability DR-001\n* permits: the band-switched current-starved VCO makes Kvco/N self-compensating,\n* so the filter R and C stay fixed and there are no R/C trim banks (switches on\n* the control node are a spur mechanism).\n* \n* Output stage: wide-swing cascode sink (cp_leg_n) and source (cp_leg_p) with\n* current-steering switches.  MSWDN/MSWUP route each polarity's tail to VOUT\n* when its PFD output is asserted; MDMPDN/MDMPUP steer the tail to the shared\n* dump node VDUMP otherwise, so the mirrors stay biased and only the steering\n* switch, not the mirror, sees a turn-on transient.\n* \n* VDUMP is a SHARED dump node held near mid-supply by the MCLPN*/MCLPP* clamp,\n* and both of those properties are load-bearing.  What the charge pump must\n* avoid is a large step in a tail node's voltage at switch-on: that step is paid\n* for out of the control node through the switch, once per reference cycle, as a\n* charge error the loop cannot distinguish from phase error.  Parking each idle\n* tail on its own rail -- the obvious first design, built and measured -- puts\n* the two tails at very different distances from VOUT (about 0.4 V on the P side\n* against 0.95 V on the N side), so the two charge errors do not cancel: the\n* residue measured about -10 fC per reference cycle at ZERO phase error, i.e. a\n* static phase offset near 2 ns.  Simply tying the two dump switches together\n* without a clamp is not enough either, and for an instructive reason: with both\n* legs idle the node carries only the difference of two nominally equal\n* currents, so it is degenerate -- any mismatch walks it to whichever end\n* saturates first (measured: 0.18 V, effectively a rail).\n* \n* The clamp removes the degeneracy without adding a control loop.  Two stacked\n* NMOS diodes to VSS and two stacked PMOS diodes from VDD are sized NARROW\n* enough (1u / 3u) that their turn-on thresholds leave a dead band between them:\n* neither conducts near mid-supply, so there is no static crowbar current, but\n* the node cannot leave the band either.  VDUMP therefore idles close to the\n* middle of the ~0.9-2.4 V Vctrl window, both tail excursions become small and\n* roughly symmetric about VOUT, and their charge errors largely cancel.\n* \n* A unity-gain buffer holding the dump node exactly at VOUT would cancel the\n* residue outright, and is the textbook answer; it is rejected here because\n* DR-001 keeps opamps out of the loop path.  What survives is measured, not\n* assumed: the pfd-cp charge measurement reports the residual net charge at zero\n* phase error at every corner, and design/README.md carries it in the budget.\n* \n* Switch sizing and MDUMN/MDUMP: the steering switches carry only a few\n* microamps, so they are sized for CHARGE SYMMETRY, not for on-resistance.  Both\n* are the same 6u/0.3u device -- an earlier 3u(N)/9u(P) pair, sized by the usual\n* mobility ratio, put roughly three times more channel and overlap charge on the\n* P side than the N side and injected a net residue onto the control node at\n* every switching event, a far larger error here than the few tens of millivolts\n* of switch IR drop the wide P device was buying.  Equal widths, not equal\n* strengths, is the right rule when the switch passes microamps.  They are not\n* shrunk, either: the switch also has to re-establish its tail node at turn-on,\n* and that recovery time is what bounds how short the PFD's minimum pulse may be\n* (see pfd.sch).  A 1u pair measurably lowered the delivered charge per unit\n* phase -- the detector gain -- by slowing it, and 6u was chosen over 3u to keep\n* the recovery comfortably shorter than the minimum pulse at the slow/cold\n* corners.  MDUMN/MDUMP are the\n* standard half-width dummies with both diffusions tied to VOUT, gated by the\n* complementary control, absorbing the channel charge each switch expels when it\n* turns off.  Injection is a first-order term at this current level: at a few\n* microamps and a sub-nanosecond minimum pulse, the SIGNAL charge per pulse is\n* only a few femtocoulombs, so an uncancelled tens-of-femtocoulomb injection\n* would dominate it outright.\n* \n* Bias: IBN/ICN/IBP/ICP are the four bias-network reference nodes (bottom-mirror\n* diode and wide-swing cascode diode, per polarity).  Each diode is 4x the unit\n* geometry and expects 4x the unit current, so the mirror ratio into each leg is\n* unchanged (4 x Iunit through a 4x device mirrors Iunit into a 1x leg) while\n* every bias node gets 4x the transconductance.  That is not cosmetic: each bias\n* node drives the paralleled gates of four legs, and the cascode-bias node in\n* particular drives four wide cascode gates, so at 1x bias current the node's\n* 1/gm against that capacitance gives a recovery time constant comparable to the\n* PFD pulse itself.  A bias node that is still recovering while the pump is\n* delivering charge modulates the delivered current for the whole pulse, which\n* shows up as a collapse of the phase-to-charge gain at the slow corners.  Reference generation is\n* out of this block's scope -- as in sim/devchar-cp, the testbenches drive them\n* from ideal current sources so the measured up/down mismatch is the OUTPUT\n* STAGE's own, not a bias generator's.  The integrated block must supply four\n* matched references from one constant-gm reference; that contribution is\n* additive to the budget in design/README.md.} 1900 -300 0 0 0.25 0.25 {layer=8}
C {symbols/nfet_03v3.sym} 300 -300 0 0 {name=MBN
L=1u
W=16u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {devices/lab_pin.sym} 320 -330 0 0 {name=l_MBN_D lab=IBN}
C {devices/lab_pin.sym} 280 -300 0 0 {name=l_MBN_G lab=IBN}
C {devices/lab_pin.sym} 320 -270 0 0 {name=l_MBN_S lab=VSS}
C {devices/lab_pin.sym} 320 -300 0 0 {name=l_MBN_B lab=VSS}
T {MBN} 260 -355 0 0 0.25 0.25 {layer=15}
C {symbols/nfet_03v3.sym} 560 -300 0 0 {name=MCN
L=1u
W=4u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {devices/lab_pin.sym} 580 -330 0 0 {name=l_MCN_D lab=ICN}
C {devices/lab_pin.sym} 540 -300 0 0 {name=l_MCN_G lab=ICN}
C {devices/lab_pin.sym} 580 -270 0 0 {name=l_MCN_S lab=VSS}
C {devices/lab_pin.sym} 580 -300 0 0 {name=l_MCN_B lab=VSS}
T {MCN} 520 -355 0 0 0.25 0.25 {layer=15}
C {symbols/pfet_03v3.sym} 820 -300 0 0 {name=MBP
L=1u
W=48u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {devices/lab_pin.sym} 840 -270 0 0 {name=l_MBP_D lab=IBP}
C {devices/lab_pin.sym} 800 -300 0 0 {name=l_MBP_G lab=IBP}
C {devices/lab_pin.sym} 840 -330 0 0 {name=l_MBP_S lab=VDD}
C {devices/lab_pin.sym} 840 -300 0 0 {name=l_MBP_B lab=VDD}
T {MBP} 780 -355 0 0 0.25 0.25 {layer=15}
C {symbols/pfet_03v3.sym} 1080 -300 0 0 {name=MCP
L=1u
W=12u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {devices/lab_pin.sym} 1100 -270 0 0 {name=l_MCP_D lab=ICP}
C {devices/lab_pin.sym} 1060 -300 0 0 {name=l_MCP_G lab=ICP}
C {devices/lab_pin.sym} 1100 -330 0 0 {name=l_MCP_S lab=VDD}
C {devices/lab_pin.sym} 1100 -300 0 0 {name=l_MCP_B lab=VDD}
T {MCP} 1040 -355 0 0 0.25 0.25 {layer=15}
C {pfdcp_inv_3v3.sym} 1340 -300 0 0 {name=xi_b0}
C {devices/lab_pin.sym} 1250 -300 0 0 {name=l_xi_b0_A lab=B0}
C {devices/lab_pin.sym} 1430 -300 0 0 {name=l_xi_b0_Y lab=B0B}
C {devices/lab_pin.sym} 1340 -390 0 0 {name=l_xi_b0_VDD lab=VDD}
C {devices/lab_pin.sym} 1340 -210 0 0 {name=l_xi_b0_VSS lab=VSS}
C {pfdcp_inv_3v3.sym} 1600 -300 0 0 {name=xi_b1}
C {devices/lab_pin.sym} 1510 -300 0 0 {name=l_xi_b1_A lab=B1}
C {devices/lab_pin.sym} 1690 -300 0 0 {name=l_xi_b1_Y lab=B1B}
C {devices/lab_pin.sym} 1600 -390 0 0 {name=l_xi_b1_VDD lab=VDD}
C {devices/lab_pin.sym} 1600 -210 0 0 {name=l_xi_b1_VSS lab=VSS}
C {pfdcp_inv_3v3.sym} 1860 -300 0 0 {name=xi_up}
C {devices/lab_pin.sym} 1770 -300 0 0 {name=l_xi_up_A lab=UP}
C {devices/lab_pin.sym} 1950 -300 0 0 {name=l_xi_up_Y lab=UPB}
C {devices/lab_pin.sym} 1860 -390 0 0 {name=l_xi_up_VDD lab=VDD}
C {devices/lab_pin.sym} 1860 -210 0 0 {name=l_xi_up_VSS lab=VSS}
C {pfdcp_inv_3v3.sym} 2120 -300 0 0 {name=xi_dn}
C {devices/lab_pin.sym} 2030 -300 0 0 {name=l_xi_dn_A lab=DN}
C {devices/lab_pin.sym} 2210 -300 0 0 {name=l_xi_dn_Y lab=DNB}
C {devices/lab_pin.sym} 2120 -390 0 0 {name=l_xi_dn_VDD lab=VDD}
C {devices/lab_pin.sym} 2120 -210 0 0 {name=l_xi_dn_VSS lab=VSS}
C {cp_leg_n.sym} 300 -520 0 0 {name=xn_base}
C {devices/lab_pin.sym} 210 -640 0 0 {name=l_xn_base_VBN lab=IBN}
C {devices/lab_pin.sym} 210 -560 0 0 {name=l_xn_base_VCASCN lab=ICN}
C {devices/lab_pin.sym} 210 -480 0 0 {name=l_xn_base_EN lab=VDD}
C {devices/lab_pin.sym} 210 -400 0 0 {name=l_xn_base_ENB lab=VSS}
C {devices/lab_pin.sym} 390 -520 0 0 {name=l_xn_base_TAIL lab=DNT}
C {devices/lab_pin.sym} 300 -370 0 0 {name=l_xn_base_VSS lab=VSS}
C {cp_leg_n.sym} 560 -520 0 0 {name=xn_t0}
C {devices/lab_pin.sym} 470 -640 0 0 {name=l_xn_t0_VBN lab=IBN}
C {devices/lab_pin.sym} 470 -560 0 0 {name=l_xn_t0_VCASCN lab=ICN}
C {devices/lab_pin.sym} 470 -480 0 0 {name=l_xn_t0_EN lab=B0}
C {devices/lab_pin.sym} 470 -400 0 0 {name=l_xn_t0_ENB lab=B0B}
C {devices/lab_pin.sym} 650 -520 0 0 {name=l_xn_t0_TAIL lab=DNT}
C {devices/lab_pin.sym} 560 -370 0 0 {name=l_xn_t0_VSS lab=VSS}
C {cp_leg_n.sym} 820 -520 0 0 {name=xn_t1a}
C {devices/lab_pin.sym} 730 -640 0 0 {name=l_xn_t1a_VBN lab=IBN}
C {devices/lab_pin.sym} 730 -560 0 0 {name=l_xn_t1a_VCASCN lab=ICN}
C {devices/lab_pin.sym} 730 -480 0 0 {name=l_xn_t1a_EN lab=B1}
C {devices/lab_pin.sym} 730 -400 0 0 {name=l_xn_t1a_ENB lab=B1B}
C {devices/lab_pin.sym} 910 -520 0 0 {name=l_xn_t1a_TAIL lab=DNT}
C {devices/lab_pin.sym} 820 -370 0 0 {name=l_xn_t1a_VSS lab=VSS}
C {cp_leg_n.sym} 1080 -520 0 0 {name=xn_t1b}
C {devices/lab_pin.sym} 990 -640 0 0 {name=l_xn_t1b_VBN lab=IBN}
C {devices/lab_pin.sym} 990 -560 0 0 {name=l_xn_t1b_VCASCN lab=ICN}
C {devices/lab_pin.sym} 990 -480 0 0 {name=l_xn_t1b_EN lab=B1}
C {devices/lab_pin.sym} 990 -400 0 0 {name=l_xn_t1b_ENB lab=B1B}
C {devices/lab_pin.sym} 1170 -520 0 0 {name=l_xn_t1b_TAIL lab=DNT}
C {devices/lab_pin.sym} 1080 -370 0 0 {name=l_xn_t1b_VSS lab=VSS}
C {cp_leg_p.sym} 300 -740 0 0 {name=xp_base}
C {devices/lab_pin.sym} 210 -860 0 0 {name=l_xp_base_VBP lab=IBP}
C {devices/lab_pin.sym} 210 -780 0 0 {name=l_xp_base_VCASCP lab=ICP}
C {devices/lab_pin.sym} 210 -700 0 0 {name=l_xp_base_EN lab=VDD}
C {devices/lab_pin.sym} 210 -620 0 0 {name=l_xp_base_ENB lab=VSS}
C {devices/lab_pin.sym} 390 -740 0 0 {name=l_xp_base_TAIL lab=UPT}
C {devices/lab_pin.sym} 300 -890 0 0 {name=l_xp_base_VDD lab=VDD}
C {cp_leg_p.sym} 560 -740 0 0 {name=xp_t0}
C {devices/lab_pin.sym} 470 -860 0 0 {name=l_xp_t0_VBP lab=IBP}
C {devices/lab_pin.sym} 470 -780 0 0 {name=l_xp_t0_VCASCP lab=ICP}
C {devices/lab_pin.sym} 470 -700 0 0 {name=l_xp_t0_EN lab=B0}
C {devices/lab_pin.sym} 470 -620 0 0 {name=l_xp_t0_ENB lab=B0B}
C {devices/lab_pin.sym} 650 -740 0 0 {name=l_xp_t0_TAIL lab=UPT}
C {devices/lab_pin.sym} 560 -890 0 0 {name=l_xp_t0_VDD lab=VDD}
C {cp_leg_p.sym} 820 -740 0 0 {name=xp_t1a}
C {devices/lab_pin.sym} 730 -860 0 0 {name=l_xp_t1a_VBP lab=IBP}
C {devices/lab_pin.sym} 730 -780 0 0 {name=l_xp_t1a_VCASCP lab=ICP}
C {devices/lab_pin.sym} 730 -700 0 0 {name=l_xp_t1a_EN lab=B1}
C {devices/lab_pin.sym} 730 -620 0 0 {name=l_xp_t1a_ENB lab=B1B}
C {devices/lab_pin.sym} 910 -740 0 0 {name=l_xp_t1a_TAIL lab=UPT}
C {devices/lab_pin.sym} 820 -890 0 0 {name=l_xp_t1a_VDD lab=VDD}
C {cp_leg_p.sym} 1080 -740 0 0 {name=xp_t1b}
C {devices/lab_pin.sym} 990 -860 0 0 {name=l_xp_t1b_VBP lab=IBP}
C {devices/lab_pin.sym} 990 -780 0 0 {name=l_xp_t1b_VCASCP lab=ICP}
C {devices/lab_pin.sym} 990 -700 0 0 {name=l_xp_t1b_EN lab=B1}
C {devices/lab_pin.sym} 990 -620 0 0 {name=l_xp_t1b_ENB lab=B1B}
C {devices/lab_pin.sym} 1170 -740 0 0 {name=l_xp_t1b_TAIL lab=UPT}
C {devices/lab_pin.sym} 1080 -890 0 0 {name=l_xp_t1b_VDD lab=VDD}
C {symbols/nfet_03v3.sym} 1340 -520 0 0 {name=MSWDN
L=0.3u
W=6u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {devices/lab_pin.sym} 1360 -550 0 0 {name=l_MSWDN_D lab=VOUT}
C {devices/lab_pin.sym} 1320 -520 0 0 {name=l_MSWDN_G lab=DN}
C {devices/lab_pin.sym} 1360 -490 0 0 {name=l_MSWDN_S lab=DNT}
C {devices/lab_pin.sym} 1360 -520 0 0 {name=l_MSWDN_B lab=VSS}
T {MSWDN} 1300 -575 0 0 0.25 0.25 {layer=15}
C {symbols/nfet_03v3.sym} 1600 -520 0 0 {name=MDMPDN
L=0.3u
W=6u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {devices/lab_pin.sym} 1620 -550 0 0 {name=l_MDMPDN_D lab=VDUMP}
C {devices/lab_pin.sym} 1580 -520 0 0 {name=l_MDMPDN_G lab=DNB}
C {devices/lab_pin.sym} 1620 -490 0 0 {name=l_MDMPDN_S lab=DNT}
C {devices/lab_pin.sym} 1620 -520 0 0 {name=l_MDMPDN_B lab=VSS}
T {MDMPDN} 1560 -575 0 0 0.25 0.25 {layer=15}
C {symbols/pfet_03v3.sym} 1340 -740 0 0 {name=MSWUP
L=0.3u
W=6u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {devices/lab_pin.sym} 1360 -710 0 0 {name=l_MSWUP_D lab=VOUT}
C {devices/lab_pin.sym} 1320 -740 0 0 {name=l_MSWUP_G lab=UPB}
C {devices/lab_pin.sym} 1360 -770 0 0 {name=l_MSWUP_S lab=UPT}
C {devices/lab_pin.sym} 1360 -740 0 0 {name=l_MSWUP_B lab=VDD}
T {MSWUP} 1300 -795 0 0 0.25 0.25 {layer=15}
C {symbols/pfet_03v3.sym} 1600 -740 0 0 {name=MDMPUP
L=0.3u
W=6u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {devices/lab_pin.sym} 1620 -710 0 0 {name=l_MDMPUP_D lab=VDUMP}
C {devices/lab_pin.sym} 1580 -740 0 0 {name=l_MDMPUP_G lab=UP}
C {devices/lab_pin.sym} 1620 -770 0 0 {name=l_MDMPUP_S lab=UPT}
C {devices/lab_pin.sym} 1620 -740 0 0 {name=l_MDMPUP_B lab=VDD}
T {MDMPUP} 1560 -795 0 0 0.25 0.25 {layer=15}
C {symbols/nfet_03v3.sym} 1860 -520 0 0 {name=MDUMN
L=0.3u
W=3u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {devices/lab_pin.sym} 1880 -550 0 0 {name=l_MDUMN_D lab=VOUT}
C {devices/lab_pin.sym} 1840 -520 0 0 {name=l_MDUMN_G lab=DNB}
C {devices/lab_pin.sym} 1880 -490 0 0 {name=l_MDUMN_S lab=VOUT}
C {devices/lab_pin.sym} 1880 -520 0 0 {name=l_MDUMN_B lab=VSS}
T {MDUMN} 1820 -575 0 0 0.25 0.25 {layer=15}
C {symbols/pfet_03v3.sym} 1860 -740 0 0 {name=MDUMP
L=0.3u
W=3u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {devices/lab_pin.sym} 1880 -710 0 0 {name=l_MDUMP_D lab=VOUT}
C {devices/lab_pin.sym} 1840 -740 0 0 {name=l_MDUMP_G lab=UP}
C {devices/lab_pin.sym} 1880 -770 0 0 {name=l_MDUMP_S lab=VOUT}
C {devices/lab_pin.sym} 1880 -740 0 0 {name=l_MDUMP_B lab=VDD}
T {MDUMP} 1820 -795 0 0 0.25 0.25 {layer=15}
C {symbols/nfet_03v3.sym} 2120 -520 0 0 {name=MCLPN1
L=1u
W=4u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {devices/lab_pin.sym} 2140 -550 0 0 {name=l_MCLPN1_D lab=VDUMP}
C {devices/lab_pin.sym} 2100 -520 0 0 {name=l_MCLPN1_G lab=VDUMP}
C {devices/lab_pin.sym} 2140 -490 0 0 {name=l_MCLPN1_S lab=NCLP}
C {devices/lab_pin.sym} 2140 -520 0 0 {name=l_MCLPN1_B lab=VSS}
T {MCLPN1} 2080 -575 0 0 0.25 0.25 {layer=15}
C {symbols/nfet_03v3.sym} 2380 -520 0 0 {name=MCLPN2
L=1u
W=4u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {devices/lab_pin.sym} 2400 -550 0 0 {name=l_MCLPN2_D lab=NCLP}
C {devices/lab_pin.sym} 2360 -520 0 0 {name=l_MCLPN2_G lab=NCLP}
C {devices/lab_pin.sym} 2400 -490 0 0 {name=l_MCLPN2_S lab=VSS}
C {devices/lab_pin.sym} 2400 -520 0 0 {name=l_MCLPN2_B lab=VSS}
T {MCLPN2} 2340 -575 0 0 0.25 0.25 {layer=15}
C {symbols/pfet_03v3.sym} 2120 -740 0 0 {name=MCLPP1
L=1u
W=12u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {devices/lab_pin.sym} 2140 -710 0 0 {name=l_MCLPP1_D lab=VDUMP}
C {devices/lab_pin.sym} 2100 -740 0 0 {name=l_MCLPP1_G lab=VDUMP}
C {devices/lab_pin.sym} 2140 -770 0 0 {name=l_MCLPP1_S lab=PCLP}
C {devices/lab_pin.sym} 2140 -740 0 0 {name=l_MCLPP1_B lab=VDD}
T {MCLPP1} 2080 -795 0 0 0.25 0.25 {layer=15}
C {symbols/pfet_03v3.sym} 2380 -740 0 0 {name=MCLPP2
L=1u
W=12u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {devices/lab_pin.sym} 2400 -710 0 0 {name=l_MCLPP2_D lab=PCLP}
C {devices/lab_pin.sym} 2360 -740 0 0 {name=l_MCLPP2_G lab=PCLP}
C {devices/lab_pin.sym} 2400 -770 0 0 {name=l_MCLPP2_S lab=VDD}
C {devices/lab_pin.sym} 2400 -740 0 0 {name=l_MCLPP2_B lab=VDD}
T {MCLPP2} 2340 -795 0 0 0.25 0.25 {layer=15}
C {devices/ipin.sym} 100 -100 0 0 {name=P0 lab=UP}
C {devices/ipin.sym} 100 -120 0 0 {name=P1 lab=DN}
C {devices/ipin.sym} 100 -140 0 0 {name=P2 lab=B0}
C {devices/ipin.sym} 100 -160 0 0 {name=P3 lab=B1}
C {devices/iopin.sym} 100 -180 0 0 {name=P4 lab=IBN}
C {devices/iopin.sym} 100 -200 0 0 {name=P5 lab=ICN}
C {devices/iopin.sym} 100 -220 0 0 {name=P6 lab=IBP}
C {devices/iopin.sym} 100 -240 0 0 {name=P7 lab=ICP}
C {devices/iopin.sym} 100 -260 0 0 {name=P8 lab=VOUT}
C {devices/iopin.sym} 100 -280 0 0 {name=P9 lab=VDD}
C {devices/iopin.sym} 100 -300 0 0 {name=P10 lab=VSS}
