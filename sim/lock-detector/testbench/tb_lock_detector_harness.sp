* gf180-pll :: lock-detector :: window-comparator testbench (DR-002 Decision 4)
* -- sim/harness fragment (see testbench/tb_lock_detector.sp for the
*    pre-harness / sim/lib/simenv.sh deck this was ported from; the two are
*    electrically identical, only the parameter name for the supply rail
*    ('vdd_val' here, harness-supplied, vs. 'vsup' there) and the mechanics of
*    getting .options/.tran/.measure onto the deck differ).
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
*   XA  tau = kterr        the SWEPT point (this manifest's 'terr' sweep
*                          axis). Running the deck over a ladder of kterr
*                          values walks the phase error across the
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
*                          wide train that starts at ktpert (built here as
*                          NAND(NOT a, NOT b) = a OR b via inv_3v3 + inv_3v3
*                          + nand2_3v3, leaf cells that arrive with the DUT
*                          netlist).
*
* XW is a bare delaywin_3v3 with an ideal step in: it reports the comparator
* window t_win directly per corner, so the swept threshold from XA can be
* checked against the delay that sets it rather than only inferred.  It shares
* the same trim code as the five detector copies, so twin_r stays the bare-chain
* counterpart of the observable window measured at the flag.
*
* Fed by sim/harness: process/temp/vdd_val as usual, plus this manifest's
* fixed 'params' (kfref, ktrst, kterrbig, ktpert, ktstep, ktstop) and its
* 'terr' sweep axis (kterr, one point per distinct phase error actually run).
*
* lock_detector is composed ahead of this fragment by the manifest's 'dut'
* key (design/netlist/lock_detector.spice, exported from
* design/lock_detector.sch), so the frozen netlist snapshot is DUT + this
* file in one self-contained deck.

.param tref='1/kfref'
.param ttr='100p'
.param ttd='tref'
.param tbig='tref/4'

vdd vdd 0 dc 'vdd_val'

* ---- the lock-window trim code, as four static rails ----------------------
* design/delaywin_3v3.sch carries a fixed, test-set trim code since #411
* (DR-014): the window's delay is set once per part from a test-time
* measurement and held for life.  kldt<j> is 0 or 1 and the rail is that bit
* times the supply, so a code is the same code at every supply corner.
* code = 8*kldt3 + 4*kldt2 + 2*kldt1 + kldt0, active high, larger = wider
* window.  The manifest's default is the code design/pll_top.sch ties off,
* i.e. the `typical` bundle's own code; sweeping this axis at the per-bundle
* codes sim/lock-window-trim picks is the in-situ re-characterisation DR-013
* Decision 1 requires, and is this campaign's own owed re-take.
vldt0 ldt0 0 dc 'kldt0*vdd_val'
vldt1 ldt1 0 dc 'kldt1*vdd_val'
vldt2 ldt2 0 dc 'kldt2*vdd_val'
vldt3 ldt3 0 dc 'kldt3*vdd_val'

* ---- XA: swept phase error ------------------------------------------------
vupa upa 0 pulse(0 'vdd_val' 'ttd'          'ttr' 'ttr' 'kterr+ktrst' 'tref')
vdna dna 0 pulse(0 'vdd_val' 'ttd+kterr'    'ttr' 'ttr' 'ktrst'       'tref')
xa upa dna ldt0 ldt1 ldt2 ldt3 locka vwina vdd 0 lock_detector

* ---- XB: deep in lock (zero phase error, reset overlap only) --------------
vupb upb 0 pulse(0 'vdd_val' 'ttd' 'ttr' 'ttr' 'ktrst' 'tref')
vdnb dnb 0 pulse(0 'vdd_val' 'ttd' 'ttr' 'ttr' 'ktrst' 'tref')
xb upb dnb ldt0 ldt1 ldt2 ldt3 lockb vwinb vdd 0 lock_detector

* ---- XC: deep out of lock (static quarter-period phase error) -------------
vupc upc 0 pulse(0 'vdd_val' 'ttd'        'ttr' 'ttr' 'tbig+ktrst' 'tref')
vdnc dnc 0 pulse(0 'vdd_val' 'ttd+tbig'   'ttr' 'ttr' 'ktrst'      'tref')
xc upc dnc ldt0 ldt1 ldt2 ldt3 lockc vwinc vdd 0 lock_detector

* ---- XD: frequency error (feedback train 25% slow) -------------------------
vupd upd 0 pulse(0 'vdd_val' 'ttd' 'ttr' 'ttr' 'tref/2-ttr' 'tref')
vdnd dnd 0 pulse(0 'vdd_val' 'ttd' 'ttr' 'ttr' 'tref/2-ttr' 'tref*1.25')
xd upd dnd ldt0 ldt1 ldt2 ldt3 lockd vwind vdd 0 lock_detector

* ---- XE: locked, then deliberately perturbed out of lock at ktpert --------
* The wide train's delay is an integer number of reference periods after the
* narrow train's, so the two stay edge-aligned and the OR simply widens the
* UP pulse from ktrst to kterrbig+ktrst.
vupe1 upe1 0 pulse(0 'vdd_val' 'ttd'     'ttr' 'ttr' 'ktrst'          'tref')
vupe2 upe2 0 pulse(0 'vdd_val' 'ktpert'  'ttr' 'ttr' 'kterrbig+ktrst' 'tref')
xoe1 upe1 upe1n vdd 0 inv_3v3
xoe2 upe2 upe2n vdd 0 inv_3v3
xoe3 upe1n upe2n upe vdd 0 nand2_3v3
vdne dne 0 pulse(0 'vdd_val' 'ttd' 'ttr' 'ttr' 'ktrst' 'tref')
xe upe dne ldt0 ldt1 ldt2 ldt3 locke vwine vdd 0 lock_detector

* ---- XW: bare comparator window, ideal step in ----------------------------
vwstep wstep 0 pulse(0 'vdd_val' 'ttd' 'ttr' 'ttr' '5*tref' '1000*tref')
xw wstep wout ldt0 ldt1 ldt2 ldt3 vdd 0 delaywin_3v3

* Every integrator node starts fully discharged, i.e. every copy starts in
* the NOT-LOCKED state. Asserting therefore has to be earned inside the run
* rather than inherited from the DC operating point.
.ic v(vwina)=0 v(vwinb)=0 v(vwinc)=0 v(vwind)=0 v(vwine)=0
