* gf180-pll :: pfd-deadzone :: phase-to-charge transfer through zero phase error
*
* DUT: `pfd_cp` from the xschem hierarchy in design/ -- the tri-state PFD
* driving the real charge pump, netlisted by design/netlist.sh and included
* below.  The DUT netlist is NOT hand-transcribed: this deck is stimulus and
* measurement only, so a schematic edit that this deck does not track is a
* netlist error, not a silently divergent second copy of the design.
*
* What this measures, and why the charge domain rather than the logic domain:
* a PFD "dead zone" is only incidentally a digital-logic property.  What the
* loop actually sees is the CHARGE the pump delivers per reference cycle as a
* function of phase error, and a PFD whose UP/DN pulses are technically
* non-zero but too narrow to turn the charge-pump switches fully on still has
* a dead zone -- a flat region of Q(dphi) around zero where the loop has no
* gain.  So the DUT here is the PFD *with its real charge-pump load*, the
* measured quantity is net charge per reference cycle into the control node,
* and the acceptance criterion is that Q(dphi) stays proportional through
* dphi = 0 rather than flattening.  The UP/DN pulse widths are recorded
* alongside as the supporting logic-level evidence (and because the minimum
* UP/DN width IS the PFD reset delay that #11's retiming pulse must exceed).
*
* Expects from the generated header (see sim/lib/simenv.sh):
*   .lib <process corner section>   one of typical/ff/ss/fs/sf
*   .temp <temp_c>
*   .param vsup=<supply volts>
*   .param dphi=<FB-relative-to-REF phase offset, seconds>
* and expects `dut.spice` -- the xschem export of the design hierarchy -- to
* have been copied into the run directory by testbench/run.sh (ngspice runs
* with the run directory as its cwd, and `.include` takes no parameter
* substitution, so the netlist is placed rather than pointed at).
* dphi is swept EXTERNALLY, one ngspice invocation per (corner, dphi) point,
* by testbench/run.sh -- ngspice's `alterparam` does not resolve a
* vector-indexed RHS at parameter-substitution time, so an in-deck loop over a
* dphi list is not available.

.include "dut.spice"

* Charge-pump bias reference.  As in sim/devchar-cp, the four bias nodes are
* driven from ideal current sources: reference generation is a separate block,
* and driving it ideally here keeps the measured behaviour the PFD+CP's own.
.param iunit=2u
* Trim code: b1 b0 = 1 0 -> Icp = 3 units (the nominal setting, mid-range of
* the 2-bit trim -- see design/README.md).
.param b0_code=0
.param b1_code=1

* Control-node voltage this measurement is taken at: mid of the ~0.9-2.4 V
* Vctrl window from DR-001 Decision 2.  Held by an ideal source so the
* measured quantity is the pump's delivered charge, not the loop filter's
* response to it (the filter is #10).
.param vctrl=1.65

.csparam vsup_c={vsup}

*------------------------------------------------------------------ supplies
vdd vdd 0 dc 'vsup'
vss vss 0 dc 0

* Reference period 40 ns (25 MHz) -- the TOP of DR-002 Decision 1's ratified
* 1-25 MHz v1 reference range, deliberately: the reset-and-recover window is
* the smallest fraction of the reference period there, so 25 MHz is the
* demanding end for a dead-zone claim, and a result that holds here holds for
* every slower reference in the range.  Edges get a 200 ps rise/fall rather
* than an ideal step: a zero-rise-time stimulus would flatter every delay in
* the PFD's set path and understate the reset delay this record reports.
.param period=40n
.param tstart=20n
vref ref 0 pulse(0 'vsup' 'tstart' 200p 200p '0.5*period' period)
vfb  fb  0 pulse(0 'vsup' 'tstart+dphi' 200p 200p '0.5*period' period)

* Static trim code.
vb0 b0 0 dc 'vsup*b0_code'
vb1 b1 0 dc 'vsup*b1_code'

* Ideal bias references (see note above).
iibn vdd ibn dc 'iunit'
iicn vdd icn dc 'iunit'
iibp ibp 0 dc 'iunit'
iicp icp 0 dc 'iunit'

xdut ref fb b0 b1 ibn icn ibp icp vout up dn vdd vss pfd_cp

* Control node held at vctrl through an ammeter, so i(vam) is exactly the
* charge-pump output current (positive = pump sourcing into the control node).
vam vout vctrl_src 0
vctrl vctrl_src 0 dc 'vctrl'

*------------------------------------------------------------------- analysis
* rshunt: the disabled trim legs leave their cascode mid-node driven only by
* two off devices, which is a floating node for the DC operating point.  A
* 1 Tohm shunt to ground resolves it; at 3.3 V that is 3.3 pA against a
* multi-microamp signal, i.e. below the abstol floor of the measurement.
.option abstol=1e-14 reltol=1e-4 vntol=1e-7 rshunt=1e12
.control
  set noaskquit
  let vmid = vsup_c / 2
  * Three reference cycles; the first is startup (the PFD powers up with both
  * latches reset and needs one full cycle to reach its steady pattern), charge
  * is integrated over the last two and divided by two.
  tran 20p 140n

  * Net charge per reference cycle delivered into the control node.  This is
  * the dead-zone-critical quantity: it must stay proportional to dphi through
  * zero, not flatten.
  meas tran qnet2 integ i(vam) from=60n to=140n
  let qnet = qnet2 / 2

  * Supporting logic-domain evidence: UP/DN pulse width on the third reference
  * cycle (steady state), measured at the per-corner mid-supply crossing.
  let up_hi = vecmax(v(up))
  let dn_hi = vecmax(v(dn))
  if up_hi > $&vmid
    meas tran width_up trig v(up) val=$&vmid rise=3 targ v(up) val=$&vmid fall=3
  else
    let width_up = 0
  end
  if dn_hi > $&vmid
    meas tran width_dn trig v(dn) val=$&vmid rise=3 targ v(dn) val=$&vmid fall=3
  else
    let width_dn = 0
  end
  echo "PFD_RESULT qnet=$&qnet width_up=$&width_up width_dn=$&width_dn up_hi=$&up_hi dn_hi=$&dn_hi"
.endc
