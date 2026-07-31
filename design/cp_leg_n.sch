v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
T {cp_leg_n - unit NMOS sink leg with wide-swing cascode and static enable} 100 -60 0 0 0.3 0.3 {layer=8}
T {* One UNIT of the charge pump's DN (sink) current.  Every trim code is\n* built from identical copies of this cell -- unit-element weighting, so the\n* per-leg current, and therefore the saturation headroom, is the same at every\n* trim code.\n* \n* MBOT/MCASC are the wide-swing (low-voltage) cascode pair picked from\n* sim/devchar-cp's six-stack comparison: about an order of magnitude more output\n* resistance than a simple mirror at materially less headroom than a self-biased\n* cascode, which is what lets the output stay in saturation across the whole\n* ~0.9-2.4 V Vctrl window.  MEN/MDIS steer the bottom device's gate to the\n* mirror bias (enabled) or to VSS (disabled); they carry no DC current, so they\n* add no mirror error.} 1900 -300 0 0 0.25 0.25 {layer=8}
C {symbols/nfet_03v3.sym} 300 -300 0 0 {name=MEN
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
C {devices/lab_pin.sym} 320 -330 0 0 {name=l_MEN_D lab=BG}
C {devices/lab_pin.sym} 280 -300 0 0 {name=l_MEN_G lab=EN}
C {devices/lab_pin.sym} 320 -270 0 0 {name=l_MEN_S lab=VBN}
C {devices/lab_pin.sym} 320 -300 0 0 {name=l_MEN_B lab=VSS}
T {MEN} 260 -355 0 0 0.25 0.25 {layer=15}
C {symbols/nfet_03v3.sym} 560 -300 0 0 {name=MDIS
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
C {devices/lab_pin.sym} 580 -330 0 0 {name=l_MDIS_D lab=BG}
C {devices/lab_pin.sym} 540 -300 0 0 {name=l_MDIS_G lab=ENB}
C {devices/lab_pin.sym} 580 -270 0 0 {name=l_MDIS_S lab=VSS}
C {devices/lab_pin.sym} 580 -300 0 0 {name=l_MDIS_B lab=VSS}
T {MDIS} 520 -355 0 0 0.25 0.25 {layer=15}
C {symbols/nfet_03v3.sym} 300 -520 0 0 {name=MBOT
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
C {devices/lab_pin.sym} 320 -550 0 0 {name=l_MBOT_D lab=MID}
C {devices/lab_pin.sym} 280 -520 0 0 {name=l_MBOT_G lab=BG}
C {devices/lab_pin.sym} 320 -490 0 0 {name=l_MBOT_S lab=VSS}
C {devices/lab_pin.sym} 320 -520 0 0 {name=l_MBOT_B lab=VSS}
T {MBOT} 260 -575 0 0 0.25 0.25 {layer=15}
C {symbols/nfet_03v3.sym} 560 -520 0 0 {name=MCASC
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
C {devices/lab_pin.sym} 580 -550 0 0 {name=l_MCASC_D lab=TAIL}
C {devices/lab_pin.sym} 540 -520 0 0 {name=l_MCASC_G lab=VCASCN}
C {devices/lab_pin.sym} 580 -490 0 0 {name=l_MCASC_S lab=MID}
C {devices/lab_pin.sym} 580 -520 0 0 {name=l_MCASC_B lab=VSS}
T {MCASC} 520 -575 0 0 0.25 0.25 {layer=15}
C {devices/ipin.sym} 100 -100 0 0 {name=P0 lab=VBN}
C {devices/ipin.sym} 100 -120 0 0 {name=P1 lab=VCASCN}
C {devices/ipin.sym} 100 -140 0 0 {name=P2 lab=EN}
C {devices/ipin.sym} 100 -160 0 0 {name=P3 lab=ENB}
C {devices/iopin.sym} 100 -180 0 0 {name=P4 lab=TAIL}
C {devices/iopin.sym} 100 -200 0 0 {name=P5 lab=VSS}
