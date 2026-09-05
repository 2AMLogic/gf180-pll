* gf180-pll :: period-jitter :: closed-loop deterministic period jitter (#13)
*
* WHAT THIS DECK MEASURES.  The DETERMINISTIC component of period jitter --
* control-line ripple, at the naturally-occurring per-reference-cycle
* magnitude the PFD/charge-pump produce once the loop is locked -- is
* measured directly from the period-to-period spacing of the locked output
* `CLK`, over a settled measurement window.  This is the same charge-pump
* per-event ripple mechanism sim/reference-spur (#145) reads out of the
* output SPECTRUM; this deck reads the same physical ripple out of the
* output's TIME-DOMAIN edge sequence instead, which is the form
* `spec/pll.md#period-jitter` states the spec'd quantity in (percent of
* period, RMS).
*
* RANDOM / NOISE-DRIVEN JITTER IS NOT MEASURED BY THIS DECK.  DR-002
* Decision 5 ratifies (status: proposed) a VCO-dominated transient-noise
* testbench plus a jitter-transfer argument through the closed loop as the
* intended method for that component.  Before writing this deck, `.option
* TRANNOISE=1` was tried against ngspice-46 (this repo's pinned build,
* sim/README.md's "ngspice binary pin") on a trivial R-driven-by-DC-source
* circuit: the transient it produced carried NO noise (a bit-for-bit flat
* waveform), so this build does not inject automatic device noise into a
* `.tran` analysis.  ngspice DOES support a synthesized `trnoise()` PWL
* source function (confirmed working the same way, injecting an explicit
* current/voltage waveform) -- but turning that into a credible
* DEVICE-noise-equivalent number requires calibrating the injected
* amplitude against a validated noise-PSD measurement of the dominant VCO
* noise source (thermal + flicker in the current-starved ring's bias and
* switching devices) first, which is real, separately-scoped methodology
* work this record does not attempt.  This record's own Methodology field
* states this gap explicitly rather than publishing an uncalibrated,
* not-credible number -- exactly the outcome sim/README.md's own worked
* example for this campaign ("A recorded methodology gap instead of a
* number (#13)") anticipates.
*
* DUT: `pll_top` -- design/pll_top.sch, netlisted by design/netlist.sh into
* design/netlist/pll_top.spice, composed ahead of this fragment by tb.json's
* `dut` key (sim/harness/testbench.py).  Operating point, static
* configuration bits, and the per-corner `vstart` release voltage are
* IDENTICAL to sim/reference-spur's (#145) manifest: f_ref = 25 MHz, N = 6,
* f_out = 150 MHz, VCO band code 6, Icp trim code 0.  Reusing that exact,
* already-vetted operating point (rather than deriving a new one) is a
* deliberate scope reduction, stated plainly: it is inside the ratified
* (1-25 MHz reference, 10-200 MHz output, N=4-64) space, it is the highest
* output frequency one static band code holds across the whole PVT grid
* (sim/vco-tuning-range record 20260804-162735-72883fb, see
* sim/reference-spur/testbench/tb.json's own methodology note), and its
* per-corner `vstart` release voltages are already committed evidence this
* deck can cite rather than re-derive.  Every configuration bit below is
* copied verbatim from sim/reference-spur/testbench/tb_ref_spur.sp, which
* itself is checked against sim/lib/pll_top_dut.sh's `cloop_divider_params`,
* `cloop_band_params`, `cloop_trim_params` by that directory's own
* check_config.sh.
*
* Expects from the harness-generated header:
*   vdd_val   supply for this PVT point        vdd_nom  nominal supply
*   temp_c    temperature for this PVT point
* and from tb.json's `params` / `sweeps`:
*   fref      reference frequency, Hz
*   nratio    the divide ratio the SEL/P bits below encode
*   b*_code   VCO band-select bits            (sim/lib/pll_top_dut.sh)
*   cpb*_code charge-pump Icp trim bits       (   "   )
*   sel*_code, p*_code  divider chain-length / modulus bits   (   "   )
*   vstart    control-node voltage the loop is released from, per corner
*   ta, tb    the two late instants the lock criterion is evaluated at
*   wa, wb    the period-sequence measurement window (start, end)
*   ktstep, ktstop, ktstart, ktmax   transient controls (see tb.json)

*--------------------------------------------------------------- stimulus ---
* Charge-pump bias references.  Ideal 4x-unit-leg sources, exactly as
* sim/reference-spur, sim/pll-top-smoke, sim/lock-time and sim/output-range
* drive them: the bias generator is a separate, not-yet-designed block
* (design/README.md, "Bias generation is out of scope for this block").
.param iunit=8u

* Reference clock.  200 ps edges, matching sim/reference-spur/sim/pll-top-smoke
* for the same reason: a zero-rise-time stimulus flatters the PFD's set-path
* delay, which is what this campaign's internal-timestep ceiling is sized
* from.  The reference is IDEAL -- no reference jitter, no duty-cycle error;
* that is a LIMITATION of this record (a jitter contribution driven by
* reference-clock imperfection is out of scope here by construction, exactly
* as it is for sim/reference-spur).
.param tref='1/fref'
.param tstart='0.5*tref'

vvdd     vdd     0 dc 'vdd_val'
vvddvco  vdd_vco 0 dc 'vdd_val'
vvdddiv  vdd_div 0 dc 'vdd_val'
vgndvco  gnd_vco 0 dc 0
vvss     vss     0 dc 0

vref ref 0 pulse(0 'vdd_val' 'tstart' 200p 200p '0.5*tref' 'tref')

* Static configuration -- identical codes to sim/reference-spur/testbench/tb_ref_spur.sp.
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
* (same 32-port order as sim/reference-spur's).
xdut ref b0 b1 b2 cpb0 cpb1 p0 p1 p2 p3 p4 p5 sel0 sel1 sel2 sel3 sel4 sel5
+ ibn icn ibp icp clk divout fb lock vctrl vdd vdd_vco gnd_vco vdd_div vss
+ pll_top

*--------------------------------------------------------- initial state ---
* Released near the corner's own predicted lock point, exactly as
* sim/reference-spur does and for the same reason: this campaign measures a
* STEADY-STATE property (the period sequence once locked), not lock time
* (sim/lock-time, #12, owns that claim), so starting close to the lock point
* reaches steady state for the least simulated time.  `vstart` per corner
* is sim/reference-spur's own committed value (its tb.json `sweeps.vs`,
* itself sourced from sim/vco-tuning-range record 20260804-162735-72883fb).
.ic v(vctrl)='vstart'

* Break the ring's DC symmetry, same constraint sim/vco-tuning-range and
* sim/reference-spur apply.  `uic` is deliberately NOT used: the VCO's
* constant-gm bias generator must reach its own operating point before t=0.
.ic v(xdut.xvco.y1)=0 v(xdut.xvco.y2)='vdd_val' v(xdut.xvco.y3)=0
+ v(xdut.xvco.y4)='vdd_val' v(xdut.xvco.y5)=0

*-------------------------------------------------------------- lock criterion
* Same frequency/phase criterion sim/pll-top-smoke and sim/reference-spur
* use: a period-jitter number read off an unlocked loop is not evidence of
* anything.  The `.measure` cards live in tb.json's `raw_measures` (a
* fragment may not carry `.meas`).

*------------------------------------------------------------------ analysis
* rshunt: the charge pump's disabled trim legs leave a floating DC node
* without it -- same 1 Tohm shunt every closed-loop campaign in this repo
* uses.  itl4 is a solver-EFFORT knob; every convergence TOLERANCE matches
* the other closed-loop campaigns' so this deck's converged solution is
* comparable with theirs.  These live in tb.json's `options`, not here, for
* the same reason as the `.measure` cards.
