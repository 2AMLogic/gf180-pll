* gf180-pll :: cp-compliance :: charge-pump output compliance, UP/DN current
* mismatch, and 2-bit Icp trim (DC)
*
* DUT: `cp` from the xschem hierarchy in design/, netlisted by
* design/netlist.sh and included below -- stimulus and measurement only here,
* no hand-transcribed copy of the design.
*
* Measurement topology (the same trick sim/devchar-cp/testbench/tb_cp_mirror.sp
* uses): TWO charge-pump instances share one swept output node `sw`, one
* hardwired UP-active and the other hardwired DN-active, each reaching `sw`
* through its own 0 V ammeter.  One DC sweep of `sw` from 0 to 3.63 V therefore
* traces the complete output characteristic of BOTH polarities -- through the
* saturation knee and into triode, not just the flat region -- and does so at
* identical output voltages, which is what makes the point-by-point UP/DN
* difference a real mismatch number rather than a comparison of two runs.
*
* Both instances carry the SAME trim code: DR-001's 2-bit trim is one shared
* code, not an independent per-polarity trim, so the mismatch reported at a
* code is a property of the design at that code.
*
* Expects from the generated header (see sim/lib/simenv.sh):
*   .lib <process corner section>   one of typical/ff/ss/fs/sf
*   .temp <temp_c>
*   .param vsup=<supply volts>
*   .param b0_code=<0|1>  .param b1_code=<0|1>   (2-bit Icp trim code)
* and expects `dut.spice` (the xschem export of design/) to have been copied
* into the run directory by testbench/run.sh.

.include "dut.spice"

* Unit bias reference.  Reference GENERATION is a separate block and out of
* this issue's scope, so -- exactly as in sim/devchar-cp -- the four bias nodes
* are driven from ideal current sources at 4x the unit-leg
* current (the bias diodes are 4x the unit geometry, so each leg still mirrors
* one unit).  The mismatch this deck measures is
* therefore the OUTPUT STAGE's own; a real bias generator adds to it, and that
* addition is carried explicitly in the budget in design/README.md.
.param iunit=8u

.csparam vsup_c={vsup}

*------------------------------------------------------------------ supplies
vdd vdd 0 dc 'vsup'
vss vss 0 dc 0
* Swept output node, shared by both polarities.
vsw sw 0 dc 0
* Static logic levels for the hardwired steering inputs.
vhi hi 0 dc 'vsup'
vlo lo 0 dc 0
* Static 2-bit trim code, shared by both instances.
vb0 b0 0 dc 'vsup*b0_code'
vb1 b1 0 dc 'vsup*b1_code'

*---------------------------------------------------------- UP-only instance
* up=1 (sourcing into sw), dn=0 (idle, steered to VSS).
xcpu hi lo b0 b1 ibn_u icn_u ibp_u icp_u d_up vdd vss cp
iibn_u vdd ibn_u dc 'iunit'
iicn_u vdd icn_u dc 'iunit'
iibp_u ibp_u 0 dc 'iunit'
iicp_u icp_u 0 dc 'iunit'
* Ammeter oriented so i(vam_up) is positive for current the pump SOURCES.
vam_up d_up sw 0

*---------------------------------------------------------- DN-only instance
* up=0 (idle, steered to VSS), dn=1 (sinking from sw).
xcpd lo hi b0 b1 ibn_d icn_d ibp_d icp_d d_dn vdd vss cp
iibn_d vdd ibn_d dc 'iunit'
iicn_d vdd icn_d dc 'iunit'
iibp_d ibp_d 0 dc 'iunit'
iicp_d icp_d 0 dc 'iunit'
* Ammeter oriented so i(vam_dn) is positive for current the pump SINKS.
vam_dn sw d_dn 0

*------------------------------------------------------------------- analysis
* rshunt: a disabled trim leg's cascode mid-node is driven only by two off
* devices, i.e. floating for the DC solution.  1 Tohm to ground resolves it and
* contributes 3.3 pA at 3.3 V -- six orders below the microamp signal, and
* below the abstol floor set here.
.option abstol=1e-14 reltol=1e-4 vntol=1e-7 rshunt=1e12
.control
  set noaskquit

  * --- full output characteristic of both polarities ----------------------
  * NOTE: ngspice's control-mode `dc` does not accept a .param reference for
  * its sweep bounds ('vsup' and $&vsup both fail with a syntax error, even
  * though the same substitution works in a device line or a .meas argument),
  * so the sweep runs to a fixed 3.63 V -- the top of the repo's supply grid,
  * hence a superset of every corner's own 0..vsup range.  run.sh extracts
  * against each corner's actual vsup and ignores the surplus points.
  dc vsw 0 3.63 0.020
  let i_up = i(vam_up)
  let i_dn = i(vam_dn)
  wrdata iv_cp.dat i_up i_dn

  * --- saturation margin at the two ends of the Vctrl window ---------------
  * "Both current sources stay in saturation across the compliance range" is
  * checked directly on the devices rather than inferred from the flatness of
  * the I-V: for each polarity's always-on unit leg, report |vds| - |vdsat| for
  * the bottom mirror device and for the cascode device.  A positive margin at
  * both ends of the window, at every corner, is the acceptance criterion.
  alter vsw = 0.9
  op
  echo "SATLO nbot_vds $&@m.xcpd.xn_base.xmbot.m0[vds] nbot_vdsat $&@m.xcpd.xn_base.xmbot.m0[vdsat] ncasc_vds $&@m.xcpd.xn_base.xmcasc.m0[vds] ncasc_vdsat $&@m.xcpd.xn_base.xmcasc.m0[vdsat] ptop_vds $&@m.xcpu.xp_base.xmtop.m0[vds] ptop_vdsat $&@m.xcpu.xp_base.xmtop.m0[vdsat] pcasc_vds $&@m.xcpu.xp_base.xmcasc.m0[vds] pcasc_vdsat $&@m.xcpu.xp_base.xmcasc.m0[vdsat]"
  alter vsw = 2.4
  op
  echo "SATHI nbot_vds $&@m.xcpd.xn_base.xmbot.m0[vds] nbot_vdsat $&@m.xcpd.xn_base.xmbot.m0[vdsat] ncasc_vds $&@m.xcpd.xn_base.xmcasc.m0[vds] ncasc_vdsat $&@m.xcpd.xn_base.xmcasc.m0[vdsat] ptop_vds $&@m.xcpu.xp_base.xmtop.m0[vds] ptop_vdsat $&@m.xcpu.xp_base.xmtop.m0[vdsat] pcasc_vds $&@m.xcpu.xp_base.xmcasc.m0[vds] pcasc_vdsat $&@m.xcpu.xp_base.xmcasc.m0[vdsat]"
.endc
