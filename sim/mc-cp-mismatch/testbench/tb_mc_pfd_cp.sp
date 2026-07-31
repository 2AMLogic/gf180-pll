* gf180-pll :: mc-cp-mismatch :: residual charge / static phase offset with
* the REAL PFD driving, RANDOM device mismatch enabled (Monte Carlo)
*
* DUT: `pfd_cp` -- the same top sim/pfd-deadzone/testbench/tb_pfd_deadzone.sp
* uses, i.e. the PFD driving the real charge pump (not an idealized
* detector). This is deliberate for TWO of this campaign's terms at once:
*
*   - term 3/4 (design/README.md's budget table): residual net charge per
*     reference cycle at zero phase error, and the resulting static phase
*     offset q_zero / Kd.  pfd-deadzone's record measures this SYSTEMATIC
*     ("sw_stat_mismatch=0"); this deck adds RANDOM mismatch on top.
*   - the "PFD path ... mismatch contributions to static phase offset"
*     acceptance criterion (#15): because the DUT is the whole PFD+CP
*     hierarchy, not an idealized phase detector, mismatch in the PFD's own
*     gates (edge detectors, SR latch, reset chain -- whichever polarity's
*     path is a transistor wider/narrower than nominal) is folded into the
*     SAME qnet measurement the charge pump's own mismatch is. The loop only
*     ever sees the combined charge-domain result of the two, and design/
*     README.md's own methodology note for the systematic record makes the
*     identical point ("term 3 measures the net the loop actually sees with
*     the real PFD driving"). This record does not, and cannot, separate a
*     PFD-only contribution from a charge-pump-only contribution within this
*     single measurement -- see run.sh / the record's Methodology field for
*     how that is stated honestly rather than fabricated as two numbers.
*
* dphi = {-1n, 0, +1n} (not pfd-deadzone's full 5-point sweep): a Monte Carlo
* sample needs qnet at zero phase error (term 3) and the local detector gain
* kd_wide = [q(+1n) - q(-1n)] / 2n to convert it to a phase offset (term 4),
* not the full dead-zone linearity check pfd-deadzone already owns.
*
* Expects from the generated header (see sim/lib/simenv.sh):
*   .lib <process corner section>   typical (nominal PVT only -- see
*                                   tb_mc_cp_dc.sp's header for why)
*   .temp <temp_c>
*   .param vsup=<supply volts>
*   .param dphi=<FB-relative-to-REF phase offset, seconds>
*   .param sw_stat_mismatch=1
*   .option rndseed=<seed>          (via run.sh / simenv_run_deck)
* and expects `dut.spice` to have been copied into the run directory by
* testbench/run.sh.

.include "dut.spice"

.param iunit=8u
.param b0_code=0
.param b1_code=1

* Control node held at mid of the ~0.9-2.4 V Vctrl window (DR-001 Decision
* 2), matching pfd-deadzone and design/README.md's term 3/4 (both stated "at
* Vctrl = 1.65 V").
.param vctrl=1.65

.csparam vsup_c={vsup}

*------------------------------------------------------------------ supplies
vdd vdd 0 dc 'vsup'
vss vss 0 dc 0

* Reference period 40 ns (25 MHz), as pfd-deadzone: the top of DR-002
* Decision 1's ratified 1-25 MHz range, the demanding end for a phase-offset
* claim stated as a fraction of the reference period.
.param period=40n
.param tstart=20n
vref ref 0 pulse(0 'vsup' 'tstart' 200p 200p '0.5*period' period)
vfb  fb  0 pulse(0 'vsup' 'tstart+dphi' 200p 200p '0.5*period' period)

vb0 b0 0 dc 'vsup*b0_code'
vb1 b1 0 dc 'vsup*b1_code'

iibn vdd ibn dc 'iunit'
iicn vdd icn dc 'iunit'
iibp ibp 0 dc 'iunit'
iicp icp 0 dc 'iunit'

xdut ref fb b0 b1 ibn icn ibp icp vout up dn vdd vss pfd_cp

vam vout vctrl_src 0
vctrl vctrl_src 0 dc 'vctrl'

*------------------------------------------------------------------- analysis
* itl4: see tb_mc_cp_switch.sp -- same cp_dumpbuf-loaded control node.
.option abstol=1e-14 reltol=1e-4 vntol=1e-7 rshunt=1e12 itl4=200
.control
  set noaskquit
  * Three reference cycles; charge integrated over the last two (pfd-deadzone
  * convention -- the first cycle is startup).
  tran 20p 140n
  meas tran qnet2 integ i(vam) from=60n to=140n
  let qnet = qnet2 / 2
  echo "MCPFD qnet=$&qnet"
.endc
