v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
T {inv_3v3 - unit CMOS inverter (3.3 V thick oxide)} 100 -60 0 0 0.3 0.3 {layer=8}
T {* Unit static CMOS inverter, gf180mcu 3.3 V thick-oxide devices only\n* (DR-002 Decision 3).  Wp/Wn = 1.5u/0.5u at L = 0.3u -- a 3:1 ratio sized for\n* symmetric rise/fall, because every UP/DN path asymmetry in the PFD lands\n* directly in the charge pump's timing-mismatch budget.} 1900 -300 0 0 0.25 0.25 {layer=8}
C {symbols/pfet_03v3.sym} 300 -300 0 0 {name=MP
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
C {devices/lab_pin.sym} 320 -270 0 0 {name=l_MP_D lab=Y}
C {devices/lab_pin.sym} 280 -300 0 0 {name=l_MP_G lab=A}
C {devices/lab_pin.sym} 320 -330 0 0 {name=l_MP_S lab=VDD}
C {devices/lab_pin.sym} 320 -300 0 0 {name=l_MP_B lab=VDD}
T {MP} 260 -355 0 0 0.25 0.25 {layer=15}
C {symbols/nfet_03v3.sym} 560 -300 0 0 {name=MN
L=0.3u
W=0.5u
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
C {devices/lab_pin.sym} 580 -330 0 0 {name=l_MN_D lab=Y}
C {devices/lab_pin.sym} 540 -300 0 0 {name=l_MN_G lab=A}
C {devices/lab_pin.sym} 580 -270 0 0 {name=l_MN_S lab=VSS}
C {devices/lab_pin.sym} 580 -300 0 0 {name=l_MN_B lab=VSS}
T {MN} 520 -355 0 0 0.25 0.25 {layer=15}
C {devices/ipin.sym} 100 -100 0 0 {name=P0 lab=A}
C {devices/opin.sym} 100 -120 0 0 {name=P1 lab=Y}
C {devices/iopin.sym} 100 -140 0 0 {name=P2 lab=VDD}
C {devices/iopin.sym} 100 -160 0 0 {name=P3 lab=VSS}
