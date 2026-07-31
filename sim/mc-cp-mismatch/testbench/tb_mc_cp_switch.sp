* gf180-pll :: mc-cp-mismatch :: UP/DN switching-time mismatch, RANDOM device
* mismatch enabled (Monte Carlo)
*
* Companion to tb_mc_cp_dc.sp -- same DUT and same idea (`sw_stat_mismatch=1`
* on top of the exact topology sim/cp-compliance/testbench/tb_cp_switch.sp
* uses), but the switching-timing mismatch term (2 / 2a in
* design/README.md's budget table) instead of the DC current-mismatch term.
* One UP/DN pair per invocation -- see tb_mc_cp_dc.sp's header for why this
* deck does not run several mismatched replicas in parallel in one
* invocation (a `Timestep too small` convergence failure that scaled with
* replica count).
*
* `itl4=200` (rather than ngspice's default 10) is carried over from
* tb_cp_switch.sp: the dump-node buffer (cp_dumpbuf, DR-005) puts two MOS
* gates on the `vctrl` node, and the ideal source holding it has to carry
* their displacement current, which the default Newton-iteration budget does
* not always settle within a timestep. It is a solver-EFFORT knob, not a
* tolerance -- abstol/reltol/vntol are unchanged.
*
* Expects from the generated header (see sim/lib/simenv.sh):
*   .lib <process corner section>   typical (nominal PVT only -- see
*                                   tb_mc_cp_dc.sp's header for why)
*   .temp <temp_c>
*   .param vsup=<supply volts>
*   .param vctrl=<control-node voltage this measurement is taken at>
*   .param sw_stat_mismatch=1
*   .option rndseed=<seed>          (via run.sh / simenv_run_deck)
* and expects `dut.spice` to have been copied into the run directory by
* testbench/run.sh.

.include "dut.spice"

.param iunit=8u
.param b0_code=0
.param b1_code=1

.csparam vsup_c={vsup}

*------------------------------------------------------------------ supplies
vdd vdd 0 dc 'vsup'
vss vss 0 dc 0
vhi hi 0 dc 'vsup'
vlo lo 0 dc 0
vb0 b0 0 dc 'vsup*b0_code'
vb1 b1 0 dc 'vsup*b1_code'

* Control edge, shared by both instances (as tb_cp_switch.sp).
vctl ctl 0 pulse(0 'vsup' 10n 200p 200p 5n 100n)

*---------------------------------------------------------- UP-only instance
xcpu ctl lo b0 b1 ibn_u icn_u ibp_u icp_u outu vdd vss cp
iibn_u vdd ibn_u dc 'iunit'
iicn_u vdd icn_u dc 'iunit'
iibp_u ibp_u 0 dc 'iunit'
iicp_u icp_u 0 dc 'iunit'
vou outu 0 dc 'vctrl'

*---------------------------------------------------------- DN-only instance
xcpd lo ctl b0 b1 ibn_d icn_d ibp_d icp_d outd vdd vss cp
iibn_d vdd ibn_d dc 'iunit'
iicn_d vdd icn_d dc 'iunit'
iibp_d ibp_d 0 dc 'iunit'
iicp_d icp_d 0 dc 'iunit'
vod outd 0 dc 'vctrl'

*------------------------------------------------------------------- analysis
.option abstol=1e-14 reltol=1e-4 vntol=1e-7 rshunt=1e12 itl4=200
.control
  set noaskquit
  tran 5p 20n

  meas tran iup_ss avg i(vou) from=14n to=15n
  meas tran idn_ss avg i(vod) from=14n to=15n
  meas tran qup integ i(vou) from=9.5n to=15n
  meas tran qdn integ i(vod) from=9.5n to=15n
  let wup = qup / iup_ss
  let wdn = qdn / idn_ss
  let wskew = wup - wdn

  echo "MCSW iup_ss=$&iup_ss idn_ss=$&idn_ss qup=$&qup qdn=$&qdn wup=$&wup wdn=$&wdn wskew=$&wskew"
.endc
