* gf180-pll :: reference-phase-transfer :: closed-loop REF-to-output phase
* transfer, measured against a KNOWN reference-phase perturbation (#509)
*
* WHAT THIS DECK MEASURES, AND WHY.
* spec/pll.md's Reference input row excludes reference-source quality from
* this block's own jitter/spur numbers and asserts, by theory only, that a
* phase perturbation on REF is multiplied onto the output by 20*log10(N) --
* the divider ratio -- inside the loop bandwidth.  Every closed-loop record
* committed before this one (lock-time, output-range, supply-sensitivity,
* period-jitter, period-jitter-band-top, reference-spur) drives REF from a
* perfectly periodic pulse source, so that multiplication has never been
* MEASURED on this design, only quoted from theory.  This deck perturbs REF
* in time -- a single, known phase STEP applied to the reference edge -- and
* reads what the closed loop does with it, which is the deterministic,
* single-perturbation bench #509 recommends as the cheap first increment
* (a transient, not a noise/spectral methodology).
*
* METHOD.  A type-II PFD/CP loop drives its own static phase error back to
* whatever it was before any DC-like (in-band) disturbance, once settled --
* that is what "infinite DC loop gain" means operationally.  So instead of
* trying to resolve the OUTPUT'S absolute phase shift directly (which for
* the higher end of the ratified N=4-64 range is amplified onto an output
* period far too short to resolve a real-world REF phase step directly --
* N*dphi approaches or exceeds a whole output cycle long before dphi is
* large enough to be distinguishable from edge-rate and solver noise), this
* deck reads the loop's own REF-vs-FB static phase error:
*
*   phi(t) = t(first FB rising edge after t) - t(first REF rising edge after t)
*
* DIFFERENTIALLY, AGAINST A PAIRED CONTROL RUN, NOT AGAINST ITS OWN PAST.
* This is the one thing record 20260925-073001-ed38ff1 got wrong and this
* version fixes.  That record differenced phi AFTER the step against phi
* BEFORE it, inside one run, and the differencing was confounded: at this
* release point the loop's static phase error is still winding at ~1e-4
* fractional frequency error 9.2 us in (0.12-0.19 ns per microsecond,
* monotonic at every corner, consistent with the +72 ppm the same points
* measure on `ffb`), so over the 6.4 us between the two readings the baseline
* moves 0.4-1.4 ns against a 1 ns step.  Subtracting a drifting baseline from
* a step response measures their sum, and nothing separates them.
*
* So the campaign now runs TWO decks per PVT point (tb.json's `phases`),
* identical in every respect except the phase selector `apply`:
*
*   ctl   apply=0   dstep = 0      -- no step is applied
*   stp   apply=1   dstep = dphi   -- the KNOWN step is applied at tphase
*
* Both decks are bit-identical up to `tphase` -- same netlist, same PVT point,
* same `.ic` release, same gate -- so the winding baseline is common-mode by
* construction and the DIFFERENCE of their phi readings at the same instant is
* the step response alone:
*
*   d(t) = unwrap( phi_stp(t) - phi_ctl(t) )
*
* d is 0 before the step (both runs are the same run), -dphi immediately after
* it (REF's edges moved by +dphi and FB's have not moved yet), and returns to 0
* as the loop re-tracks.  Whatever is left of it long after the step is exactly
* the fraction of the step FB failed to track, with the drift removed rather
* than assumed small.  Because the divider is an exact digital ratio (CLK =
* N*FB, structurally, not statistically), the same fraction applies to the
* OUTPUT: the measured REF-to-output transfer is N*(1 + d/dphi), i.e.
* 20*log10(N*(1 + d/dphi)) in dB, which derive.py compares against the spec's
* 20*log10(N).
*
* FOUR INSTANTS, AND WHAT EACH ONE IS FOR.
*   ta      before the step        d(ta) is the differential's own
*                                  solver-noise floor -- `pair_resid`.  A
*                                  value far ABOVE that floor means the two
*                                  decks were not the same run before tphase,
*                                  which would invalidate the whole
*                                  differential; it is checked at +/-50 ps
*                                  (5% of dphi), not argued.  DR-026 records
*                                  why that band and not the +/-1 ps a
*                                  bit-identical pairing would imply.
*   tfast   ~0.3-1.2 loop time     d(tfast)/dphi is the transfer to a
*           constants after it     perturbation FASTER than the loop can
*                                  follow -- near -1, i.e. a transfer near
*                                  ZERO, which is the roll-off ABOVE the loop
*                                  bandwidth the same spec paragraph asserts.
*   tc, tb  15-60 loop time        the settled, in-band readings.  Two of them,
*           constants after it     3 us apart, so the run proves it waited:
*                                  `settle_resid` = d(tb) - d(tc) near zero.
*
* WHY A PHASE STEP AND NOT A TONE.  #509's methodology note treats a
* deterministic step and a deterministic single tone as equivalent first
* increments -- a step's own frequency content is broadband, so a residual
* read out long after the step (many loop time constants later) is exactly
* the loop's own DC / deep-in-band response, i.e. one frequency point at the
* bottom of the spectrum, which is what the exclusion's 20*log10(N) line
* claims holds "inside the loop bandwidth".  It needs no noise methodology
* (sim/README.md's "Verification owed" for a NUMERIC reference-jitter limit
* is sequenced behind #520's still-unavailable noise/cyclostationary bridge,
* DR-020) -- this is a transient, exactly like sim/lock-time or
* sim/reference-spur.
*
* HOW THE STEP IS APPLIED.  Two ideal periodic pulse sources, `refa`
* (unperturbed) and `refb` (identical, delayed by `dstep` = `dphi`*`apply`),
* are blended by a
* B-source through a fast (200 ps) linear gate that transitions from
* refa->refb at `tphase`.  `tphase` is placed in the middle of a reference
* LOW gap common to both trains (the gap `refb`'s own delay shrinks by
* `dphi`, so the deck only needs `dphi` small against half a reference
* period, which it is by two orders of magnitude), so the blend is a plain
* sum of two IDENTICAL zero-valued signals throughout the whole gate
* transition -- REF is refa exactly before tphase and refb exactly after,
* with a genuinely glitch-free stitch, not merely a small one. Verified in
* isolation before this deck was written (a standalone prototype's `.tran`
* trace shows one 41 ns gap where every neighbour reads 40 ns, i.e. exactly
* one clean +1 ns step and nothing else).
*
* DUT: `pll_top`, assembled by sim/lib/pll_top_dut.sh exactly as every other
* closed-loop campaign in this tree (#52).  Every configuration bit below is
* GENERATED by that file's `cloop_instance`/`cloop_divider_params`/
* `cloop_band_params`/`cloop_trim_params`/`cloop_window_trim_params` and
* re-checked against it by check_config.sh in this directory.
*
* OPERATING POINT.  N = 6, VCO band code 6, Icp trim code 0 (one unit leg,
* the trim-code rule REQUIRES it there per spec/pll.md from DR-006 Decision
* 5), f_ref = 25 MHz -- IDENTICAL to sim/reference-spur's operating point,
* on purpose: this campaign reuses that record's own vco-tuning-range-derived
* `vstart` release table (record 20260804-162735-72883fb, band 6) verbatim,
* rather than re-deriving it, because it is the exact same (N, band, f_out)
* triple.  See sim/reference-spur/testbench/vstart_from_vco_record.py for the
* derivation this campaign cites rather than duplicates -- the per-corner
* values it produced live in tb.json's `sweeps.vs`, not in a separate file in
* this directory.
*
* Expects from the harness-generated header:
*   vdd_val   supply for this PVT point        vdd_nom  nominal supply
*   temp_c    temperature for this PVT point
* and from tb.json's `params` / `sweeps` / `phases`:
*   fref      reference frequency, Hz (25 MHz, fixed across this campaign)
*   dphi      the KNOWN reference phase step size, seconds (shared, so
*             derive.py can see it -- see `apply` for which deck applies it)
*   apply     PHASE SELECTOR: 0 in the `ctl` control deck, 1 in `stp`
*   tphase    the instant the step is applied
*   ta        pre-step instant (the pairing check: d(ta) must be 0)
*   tfast     post-step instant ~0.3-1.2 loop time constants after the step
*   tc        intermediate settled post-step instant
*   tb        final settled post-step instant
*   b*_code, cpb*_code, ldt*_code, sel*_code, p*_code  static config bits
*     (sim/lib/pll_top_dut.sh)
*   vstart    control-node voltage the loop is released from, per corner
*   ktstep, ktstop, ktmax   transient controls

*--------------------------------------------------------------- stimulus ---
* Charge-pump bias references.  Four ideal sources at 4x the unit-leg
* current, exactly as sim/reference-spur, sim/pfd-deadzone, sim/cp-compliance
* and sim/pll-top-smoke drive them: the bias generator is a separate,
* not-yet-designed block (design/README.md), so driving these ideally keeps
* the measured behaviour the LOOP's own.
.param iunit=8u

.param tref='1/fref'
.param tstart='0.5*tref'
.param gate_tr=200p

vvdd     vdd     0 dc 'vdd_val'
vvddvco  vdd_vco 0 dc 'vdd_val'
vvdddiv  vdd_div 0 dc 'vdd_val'
vgndvco  gnd_vco 0 dc 0
vvss     vss     0 dc 0

* Reference clock, phase-STEPPED at tphase by a KNOWN dphi.  200 ps edges,
* the same as every other closed-loop campaign's reference source -- a
* zero-rise-time stimulus flatters every delay in the PFD's set path, and the
* PFD set path is precisely what this campaign's timestep ceiling is sized
* from (sim/README.md, "Closed-loop internal-timestep bound").
*
* `apply` is the PHASE SELECTOR (tb.json's `phases`): 0 for the `ctl` control
* deck and 1 for the `stp` stepped deck.  `dstep` is therefore 0 in the control
* deck, which makes `refb` bit-identical to `refa` and the blend below a sum of
* two identical signals for the whole run -- a control that is the stepped deck
* in every other respect, gate included, so the gate's own 200 ps blend
* transient is common-mode too and cancels with everything else.
.param dstep='dphi*apply'
vrefa refa 0 pulse(0 'vdd_val' 'tstart' 200p 200p '0.5*tref' 'tref')
vrefb refb 0 pulse(0 'vdd_val' 'tstart+dstep' 200p 200p '0.5*tref' 'tref')
vgate gate 0 pwl(0 0 'tphase' 0 'tphase+gate_tr' 'vdd_val')
bref  ref  0 v='v(refa)*(1-v(gate)/vdd_val) + v(refb)*(v(gate)/vdd_val)'

* Static configuration.  Every one of these is a real pin on the block: DR-001
* Decision 2 keeps band select a static input with no calibration FSM, and
* DR-001 Decision 3 does the same for N.  The codes come from tb.json.
vb0   b0   0 dc 'vdd_val*b0_code'
vb1   b1   0 dc 'vdd_val*b1_code'
vb2   b2   0 dc 'vdd_val*b2_code'
vcpb0 cpb0 0 dc 'vdd_val*cpb0_code'
vcpb1 cpb1 0 dc 'vdd_val*cpb1_code'

* Lock-detector window trim (DR-014, #411): a 4-bit STATIC process trim, held
* for the life of the part, so a DC source like the band and Icp codes.  This
* campaign runs the cell at the middle of its range, same as sim/reference-spur.
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

* The DUT.  This instance line is `cloop_instance`'s output verbatim, so the
* 32-port order is never transcribed by hand.
xdut ref b0 b1 b2 cpb0 cpb1 ldt0 ldt1 ldt2 ldt3 p0 p1 p2 p3 p4 p5 sel0 sel1 sel2 sel3 sel4 sel5
+ ibn icn ibp icp clk divout fb lock vctrl vdd vdd_vco gnd_vco vdd_div vss
+ pll_top

*--------------------------------------------------------------- initial state ---
* The control node is RELEASED at `vstart`, the per-corner lock-point
* estimate sim/reference-spur already computed and committed for this exact
* (N=6, band 6, f_out=150 MHz) operating point (record 20260804-162735-72883fb
* via that campaign's vstart_from_vco_record.py).  Reused verbatim rather than
* re-derived: same interpolation, same source record, same justification --
* see that campaign's own testbench comment for why releasing near the lock
* point (rather than at a common voltage) is what makes an 8-9 us run enough.
* The residual this estimate leaves is not assumed away: it is exactly what
* `phi_pre` measures, and the injected step's effect is read as a DIFFERENCE
* against that residual, not against zero.
.ic v(vctrl)='vstart'

* Break the ring's DC symmetry so the operating point is not the metastable
* all-nodes-at-mid solution.  Same constraint sim/vco-tuning-range and
* sim/reference-spur apply.  `uic` is deliberately NOT used: the VCO's
* constant-gm bias generator must be solved to its operating point before
* t=0, or the first microseconds would be a bias start-up transient
* masquerading as loop settling.
.ic v(xdut.xvco.y1)=0 v(xdut.xvco.y2)='vdd_val' v(xdut.xvco.y3)=0
+ v(xdut.xvco.y4)='vdd_val' v(xdut.xvco.y5)=0

*------------------------------------------------------------------ analysis
* rshunt: the charge pump's disabled trim legs leave their cascode mid-node
* driven only by two off devices -- a floating node for the DC operating
* point.  Same 1 Tohm shunt sim/pfd-deadzone, sim/pll-top-smoke and
* sim/reference-spur use; at 3.3 V it is 3.3 pA against a multi-microamp
* signal.  itl4: transient Newton-iteration limit, a solver-EFFORT knob, left
* at the value the other closed-loop campaigns use so this deck's converged
* solution is comparable with theirs.
*
* These, and the `.measure` cards for phi_pre/phi_mid/phi_post/the standing
* guards, live in tb.json's `options`/`raw_measures` -- the harness owns the
* generated deck's directives, which is why this block is a comment here.
