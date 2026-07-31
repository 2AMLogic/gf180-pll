* gf180-pll :: loop-dynamics :: phase-domain open-loop AC around the real filter
*
* An independent check on the impedance-plus-algebra path of
* tb_loop_filter_ac.sp + analyze.py: here the WHOLE linearized loop is handed to
* ngspice and the open-loop gain T(jw) is simulated directly, with the real
* `design/loop_filter.sch` devices sitting in it.
*
*   v(phe)  ... phase error at the PFD input, in radians (1 rad AC)
*   gcp     ... tri-state PFD + charge pump, small-signal gain Icp/2pi  [A/rad]
*   xf      ... THE REAL FILTER (design/netlist/loop_filter.spice)
*   gvco    ... ring VCO as an ideal integrator: dPhi/dt = 2pi*Kvco*v(vc)
*               realized as 2pi*Kvco amps into a 1 F capacitor, so
*               v(pout) = 2pi*Kvco*v(vc)/s  [rad]
*   ediv    ... feedback divider, 1/N, phase-domain (DR-001 Decision 3 / #11)
*
*   T(jw) = v(fb)/v(phe) = v(fb), since v(phe) = 1 rad.
*
* Everything except the filter is a behavioural small-signal model, and
* deliberately so: the PFD/CP and the divider are sampled, nonlinear blocks
* whose LARGE-signal behaviour is already recorded by #9 (`sim/pfd-deadzone`,
* `sim/cp-compliance`) and #11 (`sim/divider-ratio`).  What this deck adds is
* that the filter in the loop is not an idealization -- it carries the real
* poly-resistor tempco, the real MOS-cap C-V, the real MIM perimeter term, the
* resistor's field-oxide capacitance to substrate and the MIM's leakage
* resistor.  The continuous-time approximation this deck (and all classical
* loop analysis) makes is exactly why f_c < f_ref/10 is checked separately.
*
* Expects from the generated header (see sim/lib/simenv.sh):
*   .lib res_<corner> .lib moscap_<corner> .lib mimcap_<corner>
*   .temp <temp_c>
*   .param icp=<A> kvco=<Hz/V> ndiv=<-> vctrl=<V>
* and `dut.spice` staged beside the generated deck by run.sh.

.include "dut.spice"

.param twopi=6.283185307179586

vphe phe 0 dc 0 ac 1

* charge pump: Icp/2pi amps per radian, injected into the filter node
gcp 0 vc phe 0 {icp/twopi}

* the real loop filter
xf vc 0 loop_filter

* DC bias of the control node.  1 TH at the lowest swept frequency is 6.3e14
* ohm, six decades above |Z|, so the operating-point path is invisible to the
* AC result.
lbias vc nbias 1e12
vbias nbias 0 dc {vctrl}

* VCO as a phase integrator
gvco 0 pout vc 0 {twopi*kvco}
cint pout 0 1
rint pout 0 1e15

* feedback divider
ediv fb 0 pout 0 {1/ndiv}

.option rshunt=1e12

.control
  set noaskquit
  ac dec 40 10 1e8
  let tmag = mag(v(fb))
  let tdb  = db(v(fb))
  let tph  = 180/pi*ph(v(fb))
  set wr_singlescale
  wrdata t.dat tmag tph
.endc
