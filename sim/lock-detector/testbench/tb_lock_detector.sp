* gf180-pll :: lock-detector :: window-comparator testbench (DR-002 Decision 4)
*
* DUT: design/lock_detector.sch -- XOR(UP,DN) phase-error extractor, an
* inverter-chain delay window (delaywin_3v3), a coincidence gate that fires
* only on error pulses WIDER than that window, and a leaky integrator node
* (VWIN: weak always-on PMOS pull-up, strong WIDE-gated NMOS pull-down, MOS
* cap) read out by a Schmitt trigger. LOCK is high when no over-window error
* pulse has been seen for long enough to let the pull-up recharge VWIN past
* the Schmitt's rising threshold.
*
* Stimulus model of the PFD interface (#9's contract). With the reference
* edge leading the divided feedback edge by tau, a tri-state PFD holds
*   UP high for tau + t_reset,   DN high for t_reset,
* both falling together on the reset path. XOR(UP,DN) is therefore high for
* exactly tau -- the phase error -- and the reset-path overlap common to both
* is rejected. That is the whole reason the DUT starts with an XOR rather
* than looking at UP alone.
*
* Five independent DUT copies share one transient, so one run covers the
* whole assert/deassert acceptance set at a given PVT point:
*
*   XA  tau = kterr        the SWEPT point. Running the deck over a ladder of
*                          kterr values walks the phase error across the
*                          comparator window and locates its edges, which is
*                          the acceptance criterion that "deep in lock" and
*                          "deep out of lock" alone cannot substantiate.
*   XB  tau = 0            deep in lock: must assert, and the time it takes
*                          to do so from a cold (VWIN = 0) start is the
*                          detector's own contribution to lock-flag latency.
*   XC  tau = Tref/4       deep out of lock (static phase error): must never
*                          assert.
*   XD  DN train at Tref/1.25 -- a FREQUENCY error, not a static phase error.
*                          The error pulse width beats through every value
*                          from 0 to Tref, so a detector that only sampled
*                          instantaneous phase could momentarily assert. It
*                          must not: this is the "frequency-error window"
*                          half of DR-002 Decision 4.
*   XE  tau = 0, then a sustained tau = kterrbig from t = ktpert
*                          the DEASSERT check: the loop is deliberately
*                          kicked out of lock after the flag has asserted.
*                          UP is the OR of a narrow always-on train and a
*                          wide train that starts at ktpert (built here from
*                          nor2_3v3 + inv_3v3, leaf cells that arrive with
*                          the DUT netlist).
*
* XW is a bare delaywin_3v3 with an ideal step in: it reports the comparator
* window t_win directly per corner, so the swept threshold from XA can be
* checked against the delay that sets it rather than only inferred.
*
* Expects from the generated header (sim/lib/simenv.sh):
*   .lib <process corner section>   one of typical/ff/ss/fs/sf
*   .temp <temp_c>
*   .param vsup=<supply volts>
*   .param kfref=<reference Hz>  ktrst=<PFD reset overlap s>
*   .param kterr=<swept phase error s>  kterrbig=<perturbation phase error s>
*   .param ktpert=<perturbation start s>  ktstep=<max timestep>
*   .param ktstop=<transient stop>
*
* The lock_detector subcircuit is prepended to this file by the campaign
* runner (from design/netlist/lock_detector.spice, exported from
* design/lock_detector.sch), so the frozen netlist snapshot is deck + DUT in
* one file.

.param tref='1/kfref'
.param ttr='100p'
.param ttd='tref'
.param tbig='tref/4'

vdd vdd 0 dc 'vsup'

* ---- XA: swept phase error ------------------------------------------------
vupa upa 0 pulse(0 'vsup' 'ttd'          'ttr' 'ttr' 'kterr+ktrst' 'tref')
vdna dna 0 pulse(0 'vsup' 'ttd+kterr'    'ttr' 'ttr' 'ktrst'       'tref')
xa upa dna locka vwina vdd 0 lock_detector

* ---- XB: deep in lock (zero phase error, reset overlap only) --------------
vupb upb 0 pulse(0 'vsup' 'ttd' 'ttr' 'ttr' 'ktrst' 'tref')
vdnb dnb 0 pulse(0 'vsup' 'ttd' 'ttr' 'ttr' 'ktrst' 'tref')
xb upb dnb lockb vwinb vdd 0 lock_detector

* ---- XC: deep out of lock (static quarter-period phase error) -------------
vupc upc 0 pulse(0 'vsup' 'ttd'        'ttr' 'ttr' 'tbig+ktrst' 'tref')
vdnc dnc 0 pulse(0 'vsup' 'ttd+tbig'   'ttr' 'ttr' 'ktrst'      'tref')
xc upc dnc lockc vwinc vdd 0 lock_detector

* ---- XD: frequency error (feedback train 25% slow) ------------------------
vupd upd 0 pulse(0 'vsup' 'ttd' 'ttr' 'ttr' 'tref/2-ttr' 'tref')
vdnd dnd 0 pulse(0 'vsup' 'ttd' 'ttr' 'ttr' 'tref/2-ttr' 'tref*1.25')
xd upd dnd lockd vwind vdd 0 lock_detector

* ---- XE: locked, then deliberately perturbed out of lock at ktpert --------
* The wide train's delay is an integer number of reference periods after the
* narrow train's, so the two stay edge-aligned and the OR simply widens the
* UP pulse from ktrst to kterrbig+ktrst.
vupe1 upe1 0 pulse(0 'vsup' 'ttd'     'ttr' 'ttr' 'ktrst'          'tref')
vupe2 upe2 0 pulse(0 'vsup' 'ktpert'  'ttr' 'ttr' 'kterrbig+ktrst' 'tref')
xoe1 upe1 upe1n vdd 0 inv_3v3
xoe2 upe2 upe2n vdd 0 inv_3v3
xoe3 upe1n upe2n upe vdd 0 nand2_3v3
vdne dne 0 pulse(0 'vsup' 'ttd' 'ttr' 'ttr' 'ktrst' 'tref')
xe upe dne locke vwine vdd 0 lock_detector

* ---- XW: bare comparator window, ideal step in ----------------------------
vwstep wstep 0 pulse(0 'vsup' 'ttd' 'ttr' 'ttr' '5*tref' '1000*tref')
xw wstep wout vdd 0 delaywin_3v3

* Every integrator node starts fully discharged, i.e. every copy starts in
* the NOT-LOCKED state. Asserting therefore has to be earned inside the run
* rather than inherited from the DC operating point.
.ic v(vwina)=0 v(vwinb)=0 v(vwinc)=0 v(vwind)=0 v(vwine)=0

.options reltol=1e-3 abstol=1e-10 vntol=1e-5 chgtol=1e-13
.tran {ktstep} {ktstop}

* --- comparator window: rise and fall delay of the bare delay element
.meas tran twin_r trig v(wstep) val='vsup/2' rise=1 targ v(wout) val='vsup/2' rise=1
.meas tran twin_f trig v(wstep) val='vsup/2' fall=1 targ v(wout) val='vsup/2' fall=1

* --- assert times (a copy that never asserts produces a FAILED measure,
*     which the runner records as "did not assert" -- the pass condition for
*     XC and XD, the fail condition for XA at small error and for XB)
.meas tran ta_asrt when v(locka)='vsup/2' rise=1
.meas tran tb_asrt when v(lockb)='vsup/2' rise=1
.meas tran tc_asrt when v(lockc)='vsup/2' rise=1
.meas tran td_asrt when v(lockd)='vsup/2' rise=1
.meas tran te_asrt when v(locke)='vsup/2' rise=1

* --- steady-state levels over the last 10% of the run. A settled LOCK reads
*     ~vsup or ~0; anything in between means the flag is chattering and is
*     reported as such rather than thresholded away.
.meas tran la_lvl avg v(locka) from='0.9*ktstop' to='ktstop'
.meas tran lb_lvl avg v(lockb) from='0.9*ktstop' to='ktstop'
.meas tran lc_lvl avg v(lockc) from='0.9*ktstop' to='ktstop'
.meas tran ld_lvl avg v(lockd) from='0.9*ktstop' to='ktstop'
.meas tran le_lvl avg v(locke) from='0.9*ktstop' to='ktstop'
.meas tran va_lvl avg v(vwina) from='0.9*ktstop' to='ktstop'

* --- XE deassert: LOCK must fall after the perturbation at ktpert
.meas tran te_deas when v(locke)='vsup/2' fall=1
.meas tran le_pre  avg v(locke) from='0.9*ktpert' to='ktpert'

* --- supply current of the five copies together (per-copy figure is derived
*     in the runner); the XE OR gate and the bare XW window are on the same
*     rail and are counted with them, which is stated in the record.
.meas tran iavg avg i(vdd) from='0.5*ktstop' to='ktstop'
