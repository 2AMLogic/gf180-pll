v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
T {pfdcp_nand2_3v3 - PFD/CP unit 2-input NAND (3.3 V thick oxide)} 100 -60 0 0 0.3 0.3 {layer=8}
T {* Unit 2-input static CMOS NAND OWNED BY THE PFD/CP BLOCK (DR-004).  The\n* series NMOS stack is widened to 1u (vs. 0.5u in pfdcp_inv_3v3) so the pull-down\n* strength tracks the inverter's, keeping the PFD's reset path delay symmetric\n* between the UP and DN branches.\n*\n* NOT the same cell as the general-purpose logic-library nand2_3v3 (2.5u/2u at\n* L=0.28u).  See design/README.md :: Leaf-cell ownership.} 1900 -300 0 0 0.25 0.25 {layer=8}
C {symbols/pfet_03v3.sym} 300 -300 0 0 {name=MP1
L=0.3u
W=1.5u
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
C {devices/lab_pin.sym} 320 -270 0 0 {name=l_MP1_D lab=Y}
C {devices/lab_pin.sym} 280 -300 0 0 {name=l_MP1_G lab=A}
C {devices/lab_pin.sym} 320 -330 0 0 {name=l_MP1_S lab=VDD}
C {devices/lab_pin.sym} 320 -300 0 0 {name=l_MP1_B lab=VDD}
T {MP1} 260 -355 0 0 0.25 0.25 {layer=15}
C {symbols/pfet_03v3.sym} 560 -300 0 0 {name=MP2
L=0.3u
W=1.5u
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
C {devices/lab_pin.sym} 580 -270 0 0 {name=l_MP2_D lab=Y}
C {devices/lab_pin.sym} 540 -300 0 0 {name=l_MP2_G lab=B}
C {devices/lab_pin.sym} 580 -330 0 0 {name=l_MP2_S lab=VDD}
C {devices/lab_pin.sym} 580 -300 0 0 {name=l_MP2_B lab=VDD}
T {MP2} 520 -355 0 0 0.25 0.25 {layer=15}
C {symbols/nfet_03v3.sym} 300 -520 0 0 {name=MN1
L=0.3u
W=1u
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
C {devices/lab_pin.sym} 320 -550 0 0 {name=l_MN1_D lab=Y}
C {devices/lab_pin.sym} 280 -520 0 0 {name=l_MN1_G lab=A}
C {devices/lab_pin.sym} 320 -490 0 0 {name=l_MN1_S lab=NI}
C {devices/lab_pin.sym} 320 -520 0 0 {name=l_MN1_B lab=VSS}
T {MN1} 260 -575 0 0 0.25 0.25 {layer=15}
C {symbols/nfet_03v3.sym} 560 -520 0 0 {name=MN2
L=0.3u
W=1u
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
C {devices/lab_pin.sym} 580 -550 0 0 {name=l_MN2_D lab=NI}
C {devices/lab_pin.sym} 540 -520 0 0 {name=l_MN2_G lab=B}
C {devices/lab_pin.sym} 580 -490 0 0 {name=l_MN2_S lab=VSS}
C {devices/lab_pin.sym} 580 -520 0 0 {name=l_MN2_B lab=VSS}
T {MN2} 520 -575 0 0 0.25 0.25 {layer=15}
C {devices/ipin.sym} 100 -100 0 0 {name=P0 lab=A}
C {devices/ipin.sym} 100 -120 0 0 {name=P1 lab=B}
C {devices/opin.sym} 100 -140 0 0 {name=P2 lab=Y}
C {devices/iopin.sym} 100 -160 0 0 {name=P3 lab=VDD}
C {devices/iopin.sym} 100 -180 0 0 {name=P4 lab=VSS}
