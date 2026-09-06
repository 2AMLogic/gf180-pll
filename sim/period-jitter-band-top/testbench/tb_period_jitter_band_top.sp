* gf180-pll :: period-jitter-band-top :: closed-loop deterministic period
* jitter at the 200 MHz TOP of the ratified output band (#13)
*
* WHY THIS DECK EXISTS SEPARATELY FROM sim/period-jitter's.  That campaign
* measures the same physical quantity -- the deterministic, control-ripple-
* driven period-to-period spacing of the locked output -- at f_out = 150 MHz,
* band 6, N = 6, and every one of its records is at that one output
* frequency.  `spec/pll.md#output-band` ratifies 10-200 MHz, and 200 MHz is
* the binding end: it is where `sim/reference-spur`'s two coldest corners
* already land over the -55 dBc line once scaled, and it is where the
* band-selection rule forces the loop onto its highest-Kvco configurations.
* Nothing in this repository bounds closed-loop period jitter there.  This
* deck is that measurement.
*
* A separate campaign rather than a second grid inside sim/period-jitter
* because the manifest-level `checks` -- `fout` inside its band, `nmeas` at
* the configured N -- are per-manifest, not per-point (sim/harness/README.md),
* and this operating point has a different N and a different output band.
* Same reason sim/divider-ratio-{cell,chain,dff} are siblings rather than
* one manifest.
*
* WHAT CHANGES FROM sim/period-jitter, AND WHAT DELIBERATELY DOES NOT.
* Changed, and only these:
*   f_out   150 MHz -> 200 MHz  (the whole point of this campaign)
*   N       6 -> 8              (f_ref is held, so N carries the change)
*   band    6 everywhere -> per corner, 6 at 34 points / 7 at 11
* Held identical, so the difference this campaign measures is attributable:
*   f_ref            25 MHz  -- the same reference rate, so the per-reference-
*                               cycle ripple mechanism is excited at the same
*                               rate as sim/period-jitter's; only the ring it
*                               modulates has changed
*   Icp trim code    0 (one unit leg) -- which is not a convenience: it is
*                               what spec/pll.md's Icp trim-code rule REQUIRES
*                               at f_ref = 25 MHz.  Holding f_ref is what lets
*                               this campaign hold the trim code too
*   bias sources     ideal, 4x unit-leg, exactly as every closed-loop campaign
*   timing           the same .tran controls, measurement window and lock
*                               baseline; at 200 MHz the same 2.0 us window is
*                               400 output cycles instead of 300
*
* THE BAND CODE IS NOT A FREE CHOICE.  `spec/pll.md#band-selection-rule`
* (normative, DR-003 Decision 4) requires the LOWEST 3-bit code that reaches
* the target frequency.  Applied to sim/vco-tuning-range's committed f(Vctrl)
* record at 200 MHz that is band 6 at 34 of the 45 PVT points and band 7 at
* the other 11 -- the cold and/or high-supply points where band 6 tops out
* below 200 MHz.  So `b0_code`/`b1_code`/`b2_code` arrive here from the
* manifest's `op` sweep axis, per point, not from a fixed `params` entry;
* band_and_vstart_from_vco_record.py in this directory derives all 45 from
* the committed record and the ratified rule and re-checks the manifest
* against them.  Configuring one convenient static band across the whole grid
* would be measuring a mis-configured part at some corners, and spec/pll.md
* says no row of the specification applies to such a part.
*
* RANDOM / NOISE-DRIVEN JITTER IS NOT MEASURED BY THIS DECK, for exactly the
* reasons sim/period-jitter/testbench/tb_period_jitter.sp states at length:
* DR-002 Decision 5's intended method needs a noise-PSD calibration this
* repository has not done, and this repo's pinned ngspice-46 injects no
* automatic device noise into a `.tran`.  This campaign answers the
* deterministic half of #13's claim at the top of the band, and nothing more.
*
* DUT: `pll_top` -- design/pll_top.sch, netlisted by design/netlist.sh into
* design/netlist/pll_top.spice, composed ahead of this fragment by tb.json's
* `dut` key (sim/harness/testbench.py).  The static divider bits below encode
* N = 8 under divider_chain.sch's documented rule, the same rule
* sim/lib/pll_top_dut.sh's `cloop_divider_params` implements; check_config.sh
* in this directory diffs every static bit in tb.json against that helper's
* own output rather than trusting this comment.
*
* Expects from the harness-generated header:
*   vdd_val   supply for this PVT point        vdd_nom  nominal supply
*   temp_c    temperature for this PVT point
* and from tb.json's `params` / `sweeps`:
*   fref      reference frequency, Hz
*   nratio    the divide ratio the SEL/P bits below encode
*   b*_code   VCO band-select bits            (per point, from the `op` axis)
*   cpb*_code charge-pump Icp trim bits       (sim/lib/pll_top_dut.sh)
*   sel*_code, p*_code  divider chain-length / modulus bits   (   "   )
*   vstart    control-node voltage the loop is released from, per corner
*   ta, tb    the two late instants the lock criterion is evaluated at
*   wa, wb    the period-sequence measurement window (start, end)
*   ktstep, ktstop, ktstart, ktmax   transient controls (see tb.json)

*--------------------------------------------------------------- stimulus ---
* Charge-pump bias references.  Ideal 4x-unit-leg sources, exactly as
* sim/period-jitter, sim/reference-spur, sim/pll-top-smoke, sim/lock-time and
* sim/output-range drive them: the bias generator is a separate,
* not-yet-designed block (design/README.md, "Bias generation is out of scope
* for this block").
.param iunit=8u

* Reference clock.  200 ps edges, matching sim/period-jitter and
* sim/reference-spur for the same reason: a zero-rise-time stimulus flatters
* the PFD's set-path delay, which is what this campaign's internal-timestep
* ceiling is sized from.  The reference is IDEAL -- no reference jitter, no
* duty-cycle error; a jitter contribution driven by reference-clock
* imperfection is out of scope here by construction.
.param tref='1/fref'
.param tstart='0.5*tref'

vvdd     vdd     0 dc 'vdd_val'
vvddvco  vdd_vco 0 dc 'vdd_val'
vvdddiv  vdd_div 0 dc 'vdd_val'
vgndvco  gnd_vco 0 dc 0
vvss     vss     0 dc 0

vref ref 0 pulse(0 'vdd_val' 'tstart' 200p 200p '0.5*tref' 'tref')

* Static configuration.  The band bits are per point (see above); everything
* else is fixed by tb.json's `params` and checked by check_config.sh.
vb0   b0   0 dc 'vdd_val*b0_code'
vb1   b1   0 dc 'vdd_val*b1_code'
vb2   b2   0 dc 'vdd_val*b2_code'
vcpb0 cpb0 0 dc 'vdd_val*cpb0_code'
vcpb1 cpb1 0 dc 'vdd_val*cpb1_code'
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

* The DUT.  This instance line matches `cloop_instance`'s output verbatim
* (same 32-port order as sim/period-jitter's and sim/reference-spur's).
xdut ref b0 b1 b2 cpb0 cpb1 p0 p1 p2 p3 p4 p5 sel0 sel1 sel2 sel3 sel4 sel5
+ ibn icn ibp icp clk divout fb lock vctrl vdd vdd_vco gnd_vco vdd_div vss
+ pll_top

*--------------------------------------------------------- initial state ---
* Released near this corner's own predicted lock point IN ITS OWN SELECTED
* BAND, exactly as sim/period-jitter does and for the same reason: this
* campaign measures a STEADY-STATE property (the period sequence once
* locked), not lock time (sim/lock-time, #12, owns that claim), so starting
* close to the lock point reaches steady state for the least simulated time.
.ic v(vctrl)='vstart'

* Break the ring's DC symmetry, same constraint sim/vco-tuning-range,
* sim/reference-spur and sim/period-jitter apply.  `uic` is deliberately NOT
* used: the VCO's constant-gm bias generator must reach its own operating
* point before t=0.
.ic v(xdut.xvco.y1)=0 v(xdut.xvco.y2)='vdd_val' v(xdut.xvco.y3)=0
+ v(xdut.xvco.y4)='vdd_val' v(xdut.xvco.y5)=0

*-------------------------------------------------------------- lock criterion
* Same frequency/phase criterion sim/pll-top-smoke, sim/reference-spur and
* sim/period-jitter use, retargeted to N = 8: a period-jitter number read off
* an unlocked loop is not evidence of anything.  The `.measure` cards live in
* tb.json's `raw_measures` (a fragment may not carry `.meas`).

*------------------------------------------------------------------ analysis
* rshunt: the charge pump's disabled trim legs leave a floating DC node
* without it -- same 1 Tohm shunt every closed-loop campaign in this repo
* uses.  itl4 is a solver-EFFORT knob; every convergence TOLERANCE matches
* sim/period-jitter's so this deck's converged solution is comparable with
* that campaign's, which is the whole point of a 150-vs-200 MHz comparison.
* These live in tb.json's `options`, not here, for the same reason as the
* `.measure` cards.
