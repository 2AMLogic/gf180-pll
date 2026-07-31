v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
T {dut_export - netlist-export root (not a design cell)} 100 -60 0 0 0.3 0.3 {layer=8}
T {* Netlist-export root; see design/netlist.sh.} 1900 -300 0 0 0.25 0.25 {layer=8}
C {pfd_cp.sym} 300 -300 0 0 {name=xdut}
C {devices/lab_pin.sym} 210 -540 0 0 {name=l_xdut_REF lab=REF}
C {devices/lab_pin.sym} 210 -470 0 0 {name=l_xdut_FB lab=FB}
C {devices/lab_pin.sym} 210 -405 0 0 {name=l_xdut_B0 lab=B0}
C {devices/lab_pin.sym} 210 -335 0 0 {name=l_xdut_B1 lab=B1}
C {devices/lab_pin.sym} 210 -265 0 0 {name=l_xdut_IBN lab=IBN}
C {devices/lab_pin.sym} 210 -195 0 0 {name=l_xdut_ICN lab=ICN}
C {devices/lab_pin.sym} 210 -130 0 0 {name=l_xdut_IBP lab=IBP}
C {devices/lab_pin.sym} 210 -60 0 0 {name=l_xdut_ICP lab=ICP}
C {devices/lab_pin.sym} 390 -540 0 0 {name=l_xdut_VOUT lab=VOUT}
C {devices/lab_pin.sym} 390 -300 0 0 {name=l_xdut_UP lab=UP}
C {devices/lab_pin.sym} 390 -60 0 0 {name=l_xdut_DN lab=DN}
C {devices/lab_pin.sym} 300 -570 0 0 {name=l_xdut_VDD lab=VDD}
C {devices/lab_pin.sym} 300 -30 0 0 {name=l_xdut_VSS lab=VSS}
T {Netlist-export root only. Netlisting this schematic emits .subckt definitions for pfd_cp and every cell below it (pfd, cp, cp_leg_n/p, srlatch, edgedet, pfdcp_nand2_3v3, pfdcp_inv_3v3), which the stimulus decks under sim/ include. Not part of the design hierarchy - do not instantiate.} 100 -160 0 0 0.3 0.3 {layer=4}
