* gf180-pll :: cp-compliance :: UP/DN switching timing mismatch (transient)
*
* DUT: `cp` from the xschem hierarchy in design/ (netlisted by
* design/netlist.sh, included below).  Companion to tb_cp_dc.sp: that deck
* measures the DC current mismatch and compliance, this one measures what the
* DC sweep cannot -- how much of each polarity's current actually reaches the
* control node during a pulse of finite width, and how far apart the two
* polarities are in time.
*
* Two instances are driven from the SAME control edge, one hardwired to
* exercise only the UP (source) branch and one only the DN (sink) branch, each
* into its own control node held at `vctrl` by an ideal source.  Sharing the
* stimulus edge is the point: any measured UP-vs-DN difference is then the
* charge pump's own asymmetry, with no stimulus skew mixed in.
*
* Reported per polarity:
*   i_ss      steady-state current, late in the pulse (the DC value the switch
*             eventually delivers)
*   ton/toff  50%-of-i_ss crossing, referenced to the 50% control edge
*   q         total charge delivered to the control node over the pulse,
*             INCLUDING the tail-node charge-sharing transient at switch-on
*   w_eff     q / i_ss -- the effective pulse width the loop actually sees
* The headline number is the difference of the two w_eff values: an effective
* UP/DN TIMING mismatch in seconds, which is exactly the quantity that turns
* charge-pump asymmetry into static phase error (and hence reference spurs).
*
* Expects from the generated header (see sim/lib/simenv.sh):
*   .lib <process corner section>   one of typical/ff/ss/fs/sf
*   .temp <temp_c>
*   .param vsup=<supply volts>
*   .param vctrl=<control-node voltage this measurement is taken at>
*   .param b0_code=<0|1>  .param b1_code=<0|1>
* and expects `dut.spice` (the xschem export of design/) to have been copied
* into the run directory by testbench/run.sh.

.include "dut.spice"

.param iunit=8u

.csparam vsup_c={vsup}

*------------------------------------------------------------------ supplies
vdd vdd 0 dc 'vsup'
vss vss 0 dc 0
vhi hi 0 dc 'vsup'
vlo lo 0 dc 0
vb0 b0 0 dc 'vsup*b0_code'
vb1 b1 0 dc 'vsup*b1_code'

* Control edge, shared by both instances.  5 ns asserted -- several times the
* PFD's own reset-delay pulse width, so the steady-state current is reached
* well before the pulse ends and can be separated from the switching
* transient.  200 ps edges, as in tb_pfd_deadzone.sp.
vctl ctl 0 pulse(0 'vsup' 10n 200p 200p 5n 100n)

*---------------------------------------------------------- UP-only instance
xcpu ctl lo b0 b1 ibn_u icn_u ibp_u icp_u outu vdd vss cp
iibn_u vdd ibn_u dc 'iunit'
iicn_u vdd icn_u dc 'iunit'
iibp_u ibp_u 0 dc 'iunit'
iicp_u icp_u 0 dc 'iunit'
* Control node held at vctrl; i(vou) > 0 when the pump SOURCES into it.
vou outu 0 dc 'vctrl'

*---------------------------------------------------------- DN-only instance
xcpd lo ctl b0 b1 ibn_d icn_d ibp_d icp_d outd vdd vss cp
iibn_d vdd ibn_d dc 'iunit'
iicn_d vdd icn_d dc 'iunit'
iibp_d ibp_d 0 dc 'iunit'
iicp_d icp_d 0 dc 'iunit'
* i(vod) < 0 when the pump SINKS from it.
vod outd 0 dc 'vctrl'

*------------------------------------------------------------------- analysis
.option abstol=1e-14 reltol=1e-4 vntol=1e-7 rshunt=1e12
.control
  set noaskquit
  let vmid = vsup_c / 2
  tran 5p 20n

  * Steady-state current, averaged over the last nanosecond of the pulse.
  meas tran iup_ss avg i(vou) from=14n to=15n
  meas tran idn_ss avg i(vod) from=14n to=15n
  let iup_h = iup_ss / 2
  let idn_h = idn_ss / 2

  * Charge delivered over the whole switching event: from just before the
  * control edge to just before the falling edge, so the window contains the
  * turn-on transient and the flat top but not the turn-off.
  meas tran qup integ i(vou) from=9.5n to=15n
  meas tran qdn integ i(vod) from=9.5n to=15n

  * Effective pulse width each polarity presents to the loop.
  let wup = qup / iup_ss
  let wdn = qdn / idn_ss
  let wskew = wup - wdn

  * 50 % turn-on / turn-off delay referenced to the 50 % control edge.
  * td= is load-bearing, and it is needed on the TARG clause as well as the
  * TRIG clause: ngspice searches each clause independently from t=0 unless
  * told otherwise, so without it the turn-OFF measurements latch onto a
  * crossing belonging to the turn-ON event and report a negative delay.
  * These four are diagnostics.  The headline switching number is `wskew`
  * above, which is derived from integrated charge and needs no edge search.
  meas tran ton_up trig v(ctl) val=$&vmid rise=1 td=9n targ i(vou) val=$&iup_h rise=1 td=9n
  meas tran ton_dn trig v(ctl) val=$&vmid rise=1 td=9n targ i(vod) val=$&idn_h fall=1 td=9n
  meas tran toff_up trig v(ctl) val=$&vmid fall=1 td=15n targ i(vou) val=$&iup_h fall=1 td=15n
  meas tran toff_dn trig v(ctl) val=$&vmid fall=1 td=15n targ i(vod) val=$&idn_h rise=1 td=15n

  echo "CPSW iup_ss=$&iup_ss idn_ss=$&idn_ss qup=$&qup qdn=$&qdn wup=$&wup wdn=$&wdn wskew=$&wskew ton_up=$&ton_up ton_dn=$&ton_dn toff_up=$&toff_up toff_dn=$&toff_dn"
.endc
