* gf180-pll :: lock-window-bisection :: symmetric REF phase-step read at LOCK
* (#527, DR-022 Decision 5 route 1)
*
* WHAT THIS DECK IS FOR.  `spec/pll.md`'s Lock-detector window trim-code rule
* is normative and its measurand -- t_win, the ERR -> ERRD delay inside
* `delaywin_3v3` -- is internal: neither node is a port of `pll_top`.  DR-022
* measured every quantity the pads DO expose against it and found none that
* selects the code to the accuracy the spec's own window-spread figure assumes.
* Its Decision 5 names two routes that might still close the gap; this deck is
* the first, the one that needs no design change and no new pad.
*
* THE PROCEDURE, stated so it can fail.  With the loop locked, step REF's
* phase by a known signed Delta -- once, instantaneously -- and watch the
* design's own LOCK output.  The detector sees the loop's settled static
* offset phi_ss PLUS Delta immediately, while the loop's own <= 430 kHz
* bandwidth takes microseconds to absorb the step, so LOCK should drop for a
* while once |phi_ss +/- Delta| exceeds the flag window t_flag.  Because
* `ERR = XOR(UP, DN)` responds to the MAGNITUDE of the phase error regardless
* of sign, the two directions give
*
*     Delta+ = t_flag - phi_ss        Delta- = t_flag + phi_ss
*     t_flag = (Delta+ + Delta-)/2    phi_ss = (Delta- - Delta+)/2
*
* i.e. the static offset cancels out of t_flag.  That cancellation is the
* whole claim, and it is what disqualifies the naive in-loop selector DR-022's
* Alternatives section rejects.  This deck runs ONE (bundle, code, Delta)
* point; the threshold, and therefore t_flag and phi_ss, are a reduction over
* a ladder of Delta at one point -- testbench/derive.py.
*
* DUT: `pll_top` -- design/pll_top.sch, netlisted by design/netlist.sh into
* design/netlist/pll_top.spice and composed ahead of this fragment by tb.json's
* `dut` key (sim/harness/testbench.py).  Nothing here re-implements any block,
* and nothing here reads an internal node the procedure itself is allowed to
* use: `REF` is an ipin and `LOCK` an opin, which is the entire point.
*
* WHAT IS READ FROM INSIDE THE PART, AND WHY THAT IS NOT CHEATING.  The
* procedure under test uses REF and LOCK only.  This deck ALSO probes
* `xdut.vwin`, `xdut.up`, `xdut.dn` and `xdut.fb` -- not as inputs to the
* procedure but as the ground truth the procedure is graded against:
*   - `v(xdut.vwin)` is the detector's integrator node.  LOCK is a Schmitt
*     trigger on it, so vwin's minimum after the step is the SAME threshold
*     crossing LOCK reports, read as a continuous quantity instead of a bit.
*     A binary bisection needs ~9 transients per threshold; a graded observable
*     brackets the same crossing from a ladder and interpolates inside the
*     bracket.  On silicon a tester has only the bit -- so the record's verdict
*     is taken from LOCK, and vwin is what makes the ladder affordable and what
*     explains a threshold that does not reproduce t_flag.
*   - the UP/DN pulse widths and the REF->FB skew are the loop's own settled
*     static offset measured directly, two independent ways, over the last
*     pre-step reference cycles -- the same cross-check
*     sim/supply-sensitivity's tb_supply_lock.sp applies (w_up - w_dn ==
*     REF->FB skew for a reset-type PFD).  The bisection DERIVES phi_ss from
*     (Delta- - Delta+)/2; comparing that against this directly-measured one is
*     exactly issue #527's checkbox 3, "does the +/- cancellation hold in the
*     presence of the loop's own correction".
*
* THE PHASE STEP, and why it is two `pulse` sources and a select rather than a
* generated PWL.  An ngspice `pulse()` source has no notion of a one-time
* phase discontinuity, and a literal PWL with one breakpoint per edge cannot be
* parameterised by the harness (which substitutes named `.param`s, not
* generated files).  Two identical periodic sources whose start times differ by
* exactly `delta`, selected between at an instant when BOTH are at 0 V, give a
* phase step that is exact by construction, fully parameterised, and leaves no
* stimulus glitch: `tsw` sits 0.2 reference periods before the nominal step
* boundary, and the preceding high plateau of both sources ended 0.3 periods
* before that, so the select changes a 0 V node to a 0 V node.  The guard
* `|delta| < 0.2*tref` is what keeps that true and is checked by
* testbench/check_config.py.
*
* WARM START.  Three state nodes are pre-set, each for a reason, and the
* record reports the measurement that shows none of them decides the answer:
*   1. `vctrl` and the loop filter's R-C1 node `xdut.xlf.nz` to this corner's
*      own predicted lock control voltage (from `vstart`, the `op` sweep
*      axis).  Same technique, and the same seed table, as
*      sim/supply-sensitivity's tb_supply_lock.sp -- setting `vctrl` alone
*      dumps C1's charge through R in one RC and re-acquires from near zero.
*   2. `xdut.vwin` to the supply.  The detector's assert path is a ~0.011 W/L
*      pfet charging a 6u x 30u MOS cap, so its hold-off is MICROSECONDS (this
*      is the same absolute-time hold-off spec/pll.md flags as the reason T4/T5
*      are uncharacterized below 25 MHz).  Pre-charging it removes that
*      hold-off from the pre-step window instead of paying for it in every one
*      of the ladder's transients.  It cannot manufacture a false `lock`: the
*      DISCHARGE path is a 4 W/L nfet, nanoseconds per wide ERR pulse, so if
*      this operating point's own steady state is below the Schmitt threshold
*      the node gets there within the first few reference cycles and
*      `lock_pre` reads it.  `lock_pre` is a reported measurement at every
*      point, and a point where it is not at the rail is not evidence about
*      any threshold.
*   3. the ring's five stage nodes, to break its DC symmetry -- the same
*      constraint sim/vco-tuning-range, sim/period-jitter and sim/lock-time
*      apply.  `uic` is deliberately NOT used, so the VCO's constant-gm bias
*      generator solves its own operating point before t = 0.
*
* Expects from the harness-generated header:
*   vdd_val   supply at this PVT point      vdd_nom   nominal supply
*   temp_c    temperature at this PVT point
* and from tb.json's `params` / `sweeps`:
*   fref      reference frequency, Hz
*   nstep     reference cycles before the phase step
*   delta     the phase step, SECONDS, signed (+ = REF retarded, - = advanced;
*             0 = no step, the baseline point)
*   vstart    control-node warm-start voltage, per (bundle, temp, supply)
*   b*_code   VCO band-select bits                 (per bundle, `op` axis)
*   ldt*_code lock-detector window trim bits       (per bundle, `op` axis)
*   cpb*_code charge-pump Icp trim bits
*   sel*_code, p*_code   divider chain-length / modulus bits
*   ktstep, ktstop, ktmax   transient controls (see tb.json)

*--------------------------------------------------------------- timebase ---
.param tref='1/fref'
.param tstart='0.5*tref'
* Nominal (pre-shift) boundary of the step: where the nstep-th rising edge
* would have landed with delta = 0.  Every measurement window below is placed
* against THIS instant, so the windows do not move with delta's sign or size.
.param tphi='tstart+nstep*tref'
* The select instant -- inside a low plateau common to both sources.
.param tsw='tphi-0.2*tref'
* Pre-step measurement windows.  `tqa..tphi` is the last two reference cycles
* (the settled read); `tqb..tqc` is ten cycles earlier, so the record can show
* whether the static offset was still drifting at the moment of the step
* instead of assuming it was not.
.param tqa='tphi-2*tref'
.param tqb='tphi-12*tref'
.param tqc='tphi-10*tref'

*--------------------------------------------------------------- stimulus ---
* Charge-pump bias references: ideal sources at 4x the unit-leg current,
* exactly as every other closed-loop campaign here drives these four nodes
* (the bias generator is a separate, not-yet-designed block).
.param iunit=8u

vvdd     vdd     0 dc 'vdd_val'
vvddvco  vdd_vco 0 dc 'vdd_val'
vvdddiv  vdd_div 0 dc 'vdd_val'
vgndvco  gnd_vco 0 dc 0
vvss     vss     0 dc 0

* The two periodic references, identical but for a `delta` offset in start
* time, and the select between them.  200 ps edges, matching every other
* closed-loop deck here: a zero-rise-time stimulus flatters the PFD's set-path
* delay, which is what this deck's internal-timestep ceiling is sized from.
vrefa refa 0 pulse(0 'vdd_val' 'tstart'         200p 200p '0.5*tref' 'tref')
vrefb refb 0 pulse(0 'vdd_val' 'tstart+delta'   200p 200p '0.5*tref' 'tref')
bref  ref  0 v='time < tsw ? v(refa) : v(refb)'

* Static configuration.  Band and window-trim bits are per bundle (the `op`
* sweep axis); the rest are fixed in tb.json's `params` and diffed against
* sim/lib/pll_top_dut.sh's own encoders by testbench/check_config.py.
vb0   b0   0 dc 'vdd_val*b0_code'
vb1   b1   0 dc 'vdd_val*b1_code'
vb2   b2   0 dc 'vdd_val*b2_code'
vcpb0 cpb0 0 dc 'vdd_val*cpb0_code'
vcpb1 cpb1 0 dc 'vdd_val*cpb1_code'

* Lock-detector window trim (DR-014, #411): a 4-bit STATIC process trim, set
* once at test and held for the life of the part, so it is a DC source like
* the band and Icp codes beside it.  LDT3 is a real, connected `pll_top` port
* since DR-026 (#515); this campaign's `ff` bundle runs at code 11, so the
* MSB is exercised through the assembled part's own wiring of it.
vldt0 ldt0 0 dc 'vdd_val*ldt0_code'
vldt1 ldt1 0 dc 'vdd_val*ldt1_code'
vldt2 ldt2 0 dc 'vdd_val*ldt2_code'
vldt3 ldt3 0 dc 'vdd_val*ldt3_code'

vp0   p0   0 dc 'vdd_val*p0_code'
vp1   p1   0 dc 'vdd_val*p1_code'
vp2   p2   0 dc 'vdd_val*p2_code'
vp3   p3   0 dc 'vdd_val*p3_code'
vp4   p4   0 dc 'vdd_val*p4_code'
vp5   p5   0 dc 'vdd_val*p5_code'
vs0   sel0 0 dc 'vdd_val*sel0_code'
vs1   sel1 0 dc 'vdd_val*sel1_code'
vs2   sel2 0 dc 'vdd_val*sel2_code'
vs3   sel3 0 dc 'vdd_val*sel3_code'
vs4   sel4 0 dc 'vdd_val*sel4_code'
vs5   sel5 0 dc 'vdd_val*sel5_code'

iibn vdd ibn dc 'iunit'
iicn vdd icn dc 'iunit'
iibp ibp 0   dc 'iunit'
iicp icp 0   dc 'iunit'

*-------------------------------------------------------------------- DUT ---
* This instance line matches `cloop_instance`'s output verbatim -- the same
* 36-port order sim/period-jitter's and sim/supply-sensitivity's decks use.
xdut ref b0 b1 b2 cpb0 cpb1 ldt0 ldt1 ldt2 ldt3 p0 p1 p2 p3 p4 p5 sel0 sel1 sel2 sel3 sel4 sel5
+ ibn icn ibp icp clk divout fb lock vctrl vdd vdd_vco gnd_vco vdd_div vss
+ pll_top

*---------------------------------------------------------- initial state ---
* See the WARM START note in the header for why each of these three is set and
* what measurement keeps it honest.
.ic v(vctrl)='vstart'
.ic v(xdut.xlf.nz)='vstart'
.ic v(xdut.vwin)='vdd_val'
.ic v(xdut.xvco.y1)=0 v(xdut.xvco.y2)='vdd_val' v(xdut.xvco.y3)=0
+ v(xdut.xvco.y4)='vdd_val' v(xdut.xvco.y5)=0

*------------------------------------------------------------------ analysis
* `.measure`, `.options` and the `.tran` card all live in tb.json, not here:
* a harness fragment may not carry them (sim/harness/README.md).
