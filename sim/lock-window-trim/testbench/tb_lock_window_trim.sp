* gf180-pll :: lock-window-trim :: the trimmed delaywin_3v3's code-to-window map
*
* ONE question, asked of the lock detector's window and nothing else: with the
* 3-bit process trim DR-014 chose now drawn into design/delaywin_3v3.sch, what
* does the comparator window t_win do as the trim code walks 0 -> 7 at every
* one of the 13 corner bundles, and is there a per-bundle code that holds the
* window inside the ratified two-sided band at every PVT point at once with
* its PVT spread at or under DR-013 Decision 4's 1.65x target?
*
* Relationship to sim/lock-window-sizing.  That campaign swept the load's
* GEOMETRY (a parameterised replica at W = 8..26 um) and measured what DR-013
* Decision 4 then turned into a target: geometry re-centres the window but
* does not narrow its 1.93x PVT spread.  This campaign sweeps the CODE of the
* trimmed cell that replaced it.  The two are deliberately separate slugs, not
* a second axis bolted onto the first: the DUT is a different circuit, the
* swept quantity is a real pin rather than a replica's parameter, and the
* older record stays exactly as taken (sim/README.md's append-only rule).
*
* The DUT is the COMMITTED cell, not a replica.  delaywin_3v3 now carries the
* trim code on its own pins (T2:T1:T0), so the code can be swept by driving
* those pins on the drawn cell -- there is nothing left for a parameterised
* stand-in to do, and no replica-vs-control agreement column is needed because
* there is no replica.  What is measured here is exactly the netlist
* sim/lock-detector instantiates.
*
* Which edge IS the window.  ERR rises at t0 and falls at t0 + tau (tau = the
* phase error).  ERRD rises at t0 + twin_r and falls at t0 + tau + twin_f.
* WIDE = ERR . ERRD is therefore non-empty exactly when tau > twin_r, so the
* discrimination threshold is twin_r; twin_f only sets how wide the resulting
* WIDE pulse is once the threshold has been crossed.  twin_f is measured and
* reported anyway so the chain's rise/fall asymmetry stays visible rather than
* assumed away -- it matters more here than it did for the untrimmed cell,
* because each trim segment's pass gate is itself an asymmetric device.
*
* The stimulus is an IDEAL step (a 100 ps-edge voltage source), not a PFD
* pulse pair, for the same reason sim/lock-window-sizing's deck and
* sim/lock-detector's own XW probe use one: the quantity under test is a
* propagation delay, and driving it from a real XOR output would fold that
* gate's own corner-dependent edge rate into the number.
*
* Expects from the harness-generated header:
*   .lib <process corner section>, .temp <temp_c>
*   .param vdd_val=<supply volts>  vdd_nom=<nominal volts>
*   .param ktb0/ktb1/ktb2=<0 or 1>  the trim code's bits, LSB first
*   .param ktstep=<max timestep>  ktstop=<stop>
*
* design/netlist/lock_detector.spice is composed ahead of this fragment by the
* harness (tb.json "dut"), which is where delaywin_3v3 and its leaf cells come
* from.

.param ttr='100p'
.param ttd='2n'
.param twide='ktstop/2'

vdd vdd 0 dc 'vdd_val'

* ---- the static trim code -------------------------------------------------
* A trim code is a CONFIGURATION input held for the life of the part (DR-014
* Decision 2), so it is driven from DC sources at the rails, not toggled.
vt0 t0 0 dc 'vdd_val*ktb0'
vt1 t1 0 dc 'vdd_val*ktb1'
vt2 t2 0 dc 'vdd_val*ktb2'

* ---- the ideal step -------------------------------------------------------
* One rising edge at ttd and one falling edge at ttd + twide, so a single
* transient yields both twin_r and twin_f.
vstep step 0 pulse(0 'vdd_val' 'ttd' 'ttr' 'ttr' 'twide' '1000*ktstop')

* ---- the committed trimmed cell, driven at this point's code --------------
xdly step wout t0 t1 t2 vdd 0 delaywin_3v3
