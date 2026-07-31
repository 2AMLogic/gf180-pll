* gf180-pll :: supply-sensitivity :: locked steady-state deck
*
* DUT: `pll_top` -- the whole PLL, from design/pll_top.sch, netlisted by
* design/netlist.sh into design/netlist/pll_top.spice and prepended to this
* fragment by sim/lib/assemble_closed_loop.sh (#52).  No campaign in this repo
* assembles a top level of its own, this one included.
*
* WHAT THIS DECK MEASURES.  One PVT point, the loop held in lock at a fixed
* output frequency, long enough for the loop's slowest pole to settle, and
* then read out in a late window for
*
*   1. output frequency and the residual frequency error         (#14 crit. 1)
*   2. static phase offset, two independent ways                 (#14 crit. 2)
*        (a) the REF -> FB edge skew the loop stands off, and
*        (b) the UP/DN pulse-WIDTH difference at the PFD that produces it
*   3. per-domain supply current with the loop locked            (#14 crit. 4)
*
* The supply is a `.param` (`vsup`), so the whole supply axis of the corner
* grid is swept by re-running this same deck -- the deck itself has no notion
* of a nominal supply.  Supply STEPS and RAMPS are a different deck
* (tb_supply_dyn.sp) because a stepped rail has no single steady state to
* measure.
*
* WARM START, and why this deck does not cold-start.  sim/pll-top-smoke
* (#52) already owns the cold-start acquisition claim; repeating it 45 times
* buys nothing here and costs the settling of the loop's slowest pole
* (1/(2*pi*R*C1) = 17.1 kHz, sim/loop-dynamics) on top of the acquisition
* ramp at every corner.  Instead the control node is pre-charged with `.ic`
* to the lock point PREDICTED for this corner from #8's measured f(Vctrl)
* table (sim/vco-tuning-range), and the loop then pulls it the rest of the
* way on its own.  The residual is not assumed away: the record's lock
* criterion is applied to the measured late-window numbers exactly as it
* would be after a cold start, and a corner whose prediction was poor simply
* fails the residual-frequency-error check rather than quietly reporting a
* half-settled number.
*
* Expects from the generated header (sim/lib/simenv.sh):
*   .lib <corner sections>   .temp <temp_c>   .param vsup=<volts>
* and from the runner, one .param each:
*   fref        reference frequency, Hz
*   nratio      the divide ratio the SEL/P bits encode (reported, not applied)
*   vctrl0      warm-start control voltage for this corner, V
*   b*_code     VCO band select bits        (sim/lib/assemble_closed_loop.sh)
*   cpb*_code   charge-pump Icp trim bits   (   "   )
*   sel*_code, p*_code   divider chain-length / modulus bits   (   "   )
*   tstop, tstep, tmax   transient controls
*   ta, tb      the two late measurement instants

*--------------------------------------------------------------- stimulus ---
* Charge-pump bias references: four ideal sources at 4x the unit-leg current,
* exactly as sim/devchar-cp, sim/pfd-deadzone, sim/cp-compliance and
* sim/pll-top-smoke drive them.  The bias generator is a separate,
* not-yet-designed block (design/README.md), so driving these ideally keeps
* the measured supply sensitivity the LOOP's own rather than folding in the
* supply sensitivity of a reference that has no design behind it yet.  That is
* a stated limitation of every number below, not a modelling convenience.
.param iunit=8u

.param tref='1/fref'
.param tstart='0.5*tref'

* Three supply domains, one rail.  They are separate PINS on pll_top (the VCO
* has its own VDD_VCO/GND_VCO pair) so the per-domain current is separable,
* but they are tied to ONE source here because the block has one package
* supply: a supply-sensitivity claim about a rail that moved only under the
* VCO would not be a claim about this block.
vvdd     vdd     0 dc 'vsup'
vvddvco  vdd_vco 0 dc 'vsup'
vvdddiv  vdd_div 0 dc 'vsup'
vgndvco  gnd_vco 0 dc 0
vvss     vss     0 dc 0

* Reference clock, 200 ps edges (not an ideal step, which flatters every delay
* in the PFD's set path -- same reason sim/pfd-deadzone uses finite edges).
* The reference amplitude tracks the supply, because a real reference on this
* die is a CMOS input at the same rail; an amplitude-fixed reference would
* hide part of the supply sensitivity in the input receiver.
vref ref 0 pulse(0 'vsup' 'tstart' 200p 200p '0.5*tref' 'tref')

* Static configuration.  DR-001 Decision 2 keeps band select a static input
* with no calibration FSM, and DR-001 Decision 3 does the same for N -- so
* these are DC sources, and the band code CANNOT be re-chosen when the supply
* moves.  That constraint is the substance of this campaign's frequency
* criterion, not an artefact of the deck.
vb0   b0   0 dc 'vsup*b0_code'
vb1   b1   0 dc 'vsup*b1_code'
vb2   b2   0 dc 'vsup*b2_code'
vcpb0 cpb0 0 dc 'vsup*cpb0_code'
vcpb1 cpb1 0 dc 'vsup*cpb1_code'
vp0   p0   0 dc 'vsup*p0_code'
vp1   p1   0 dc 'vsup*p1_code'
vp2   p2   0 dc 'vsup*p2_code'
vp3   p3   0 dc 'vsup*p3_code'
vp4   p4   0 dc 'vsup*p4_code'
vp5   p5   0 dc 'vsup*p5_code'
vs0   sel0 0 dc 'vsup*sel0_code'
vs1   sel1 0 dc 'vsup*sel1_code'
vs2   sel2 0 dc 'vsup*sel2_code'
vs3   sel3 0 dc 'vsup*sel3_code'
vs4   sel4 0 dc 'vsup*sel4_code'
vs5   sel5 0 dc 'vsup*sel5_code'

iibn vdd ibn dc 'iunit'
iicn vdd icn dc 'iunit'
iibp ibp 0   dc 'iunit'
iicp icp 0   dc 'iunit'

* The DUT.  Port order generated by sim/lib/assemble_closed_loop.sh's
* `cloop_instance`, never transcribed by hand.
xdut ref b0 b1 b2 cpb0 cpb1 p0 p1 p2 p3 p4 p5 sel0 sel1 sel2 sel3 sel4 sel5
+ ibn icn ibp icp clk divout fb lock vctrl vdd vdd_vco gnd_vco vdd_div vss
+ pll_top

*--------------------------------------------------------- initial state ---
* Warm start: the control node begins at this corner's PREDICTED lock point.
.ic v(vctrl)='vctrl0'

* Break the ring's DC symmetry so the operating point is not the metastable
* all-nodes-at-mid solution -- same constraint sim/vco-tuning-range and
* sim/pll-top-smoke apply.  `uic` is deliberately NOT used: the VCO's
* constant-gm bias generator must be solved to its operating point before
* t = 0, or the first microseconds would be a bias start-up transient
* masquerading as loop settling.
.ic v(xdut.xvco.y1)=0 v(xdut.xvco.y2)='vsup' v(xdut.xvco.y3)=0
+ v(xdut.xvco.y4)='vsup' v(xdut.xvco.y5)=0

*---------------------------------------------------------------- analysis ---
* rshunt / itl4 / tolerances: identical to sim/pll-top-smoke, for the reasons
* documented there (floating cascode mid-nodes on the charge pump's disabled
* trim legs; the dump-node buffer's two MOS gates on the control node).
.option rshunt=1e12 itl4=200 reltol=1e-3 abstol=1e-13 vntol=1e-6

.csparam c_tstep={tstep}
.csparam c_tstop={tstop}
.csparam c_tmax={tmax}

*------------------------------------------------------------ lock criterion
* Identical in form to sim/pll-top-smoke's, so the two campaigns' verdicts are
* comparable:
*   (a) FREQUENCY -- a residual frequency error makes the REF->FB phase slip
*       linearly at exactly (df/f) seconds per second, so differencing the
*       phase at ta against the phase at tb measures it directly.
*   (b) PHASE -- that static phase error is itself small against a reference
*       period.
* ta and tb are placed by the runner on a reference HALF-period, so "the first
* REF rise after t" and "the first FB rise after t" are the same cycle's pair
* and the measurement cannot alias by a whole reference period.
.meas tran phi_a trig v(ref) val='vsup/2' rise=1 td='ta' targ v(fb) val='vsup/2' rise=1 td='ta'
.meas tran phi_b trig v(ref) val='vsup/2' rise=1 td='tb' targ v(fb) val='vsup/2' rise=1 td='tb'
.meas tran dphi param='phi_b-phi_a'
.meas tran ferr param='-(phi_b-phi_a)/(tb-ta)'

*----------------------------------------------------- static phase, mechanism
* The SAME static offset read at the PFD outputs rather than at the loop's
* edges.  In a reset-type PFD both outputs pulse every reference cycle for the
* reset delay; the loop stands off exactly the phase that makes the UP pulse
* longer than the DN pulse by the amount whose charge cancels the pump's own
* per-event charge asymmetry.  So
*
*     w_up - w_dn  ==  the REF->FB skew,
*
* and the two measurements are an independent cross-check of each other: they
* come from different nodes, different edges and different `.meas` cards.  A
* disagreement between them is a measurement error, not a design result.
*
* #24 (merged as PR #46) is why this is worth measuring per supply at all: the
* pre-mitigation charge pump had a Vctrl-DEPENDENT static offset, and Vctrl at
* a fixed output frequency moves with supply, so the offset moved with supply
* through the design rather than through the loop.  The DUT here is the
* POST-#24 charge pump (design/cp_dumpbuf.sch in design/pll_top.sch's
* pfd_cp -> cp), which is what the record states.
*
* Three instants, two reference periods apart, so a single anomalous cycle is
* visible as a spread rather than being reported as the value.  Each td sits
* on a reference half-period, i.e. between pulses, so "first rise after td"
* and "first fall after td" bracket one whole pulse.
.meas tran tup_r1 when v(xdut.up)='vsup/2' rise=1 td='tb'
.meas tran tup_f1 when v(xdut.up)='vsup/2' fall=1 td='tb'
.meas tran tdn_r1 when v(xdut.dn)='vsup/2' rise=1 td='tb'
.meas tran tdn_f1 when v(xdut.dn)='vsup/2' fall=1 td='tb'
.meas tran wup1 param='tup_f1-tup_r1'
.meas tran wdn1 param='tdn_f1-tdn_r1'
.meas tran skew1 param='(tup_f1-tup_r1)-(tdn_f1-tdn_r1)'

.meas tran tup_r2 when v(xdut.up)='vsup/2' rise=1 td='tb+2/fref'
.meas tran tup_f2 when v(xdut.up)='vsup/2' fall=1 td='tb+2/fref'
.meas tran tdn_r2 when v(xdut.dn)='vsup/2' rise=1 td='tb+2/fref'
.meas tran tdn_f2 when v(xdut.dn)='vsup/2' fall=1 td='tb+2/fref'
.meas tran skew2 param='(tup_f2-tup_r2)-(tdn_f2-tdn_r2)'

.meas tran tup_r3 when v(xdut.up)='vsup/2' rise=1 td='tb+4/fref'
.meas tran tup_f3 when v(xdut.up)='vsup/2' fall=1 td='tb+4/fref'
.meas tran tdn_r3 when v(xdut.dn)='vsup/2' rise=1 td='tb+4/fref'
.meas tran tdn_f3 when v(xdut.dn)='vsup/2' fall=1 td='tb+4/fref'
.meas tran skew3 param='(tup_f3-tup_r3)-(tdn_f3-tdn_r3)'

*--------------------------------------------------------------- frequency ---
* Output frequency over 200 WHOLE VCO cycles inside the late window -- a fixed
* cycle COUNT rather than a fixed time, so the same deck measures the same way
* at any output frequency (2 us at 100 MHz, 4 us at 50 MHz; the runner leaves
* at least 6 us of run after `tb`).  The count is a literal because ngspice's
* `.meas ... rise=` index is not an expression context.
.meas tran tclkn trig v(clk) val='vsup/2' rise=1 td='tb' targ v(clk) val='vsup/2' rise=201 td='tb'
.meas tran fout param='200/tclkn'

* Feedback frequency over 20 whole FB cycles: must be fref.  Measured
* independently of fout, so a divider running at the wrong N shows up as
* fout/ffb != N rather than hiding inside a single reading.
.meas tran tfb20 trig v(fb) val='vsup/2' rise=1 td='tb' targ v(fb) val='vsup/2' rise=21 td='tb'
.meas tran ffb param='20/tfb20'
.meas tran nmeas param='fout/ffb'

*------------------------------------------------------------- control node ---
.meas tran vctrl_avg avg v(vctrl) from='ta' to='tstop'
.meas tran vctrl_min min v(vctrl) from='tb' to='tstop'
.meas tran vctrl_max max v(vctrl) from='tb' to='tstop'
.meas tran vctrl_a   find v(vctrl) at='ta'
.meas tran vctrl_b   find v(vctrl) at='tb'

* The block's own LOCK flag (#11's window comparator), averaged over the late
* window so a chattering flag reads as a fraction rather than rounding to a
* verdict.
.meas tran lock_lvl avg v(lock) from='tb' to='tstop'

*-------------------------------------------------------------------- power ---
* Per-DOMAIN supply current, averaged over the late window.  pll_top brings
* out three separate supply pins, and that is exactly the granularity at
* which current is separable without editing the design:
*
*   i(vvdd)     -> pfd_cp (PFD + charge pump) + lock_detector.  loop_filter is
*                  passive (VCTRL/VSS only) and draws no supply current.
*   i(vvddvco)  -> vco: constant-gm bias, band mirrors, V->I converter, the
*                  5-stage starved ring, and the output buffer that squares
*                  CLK.  Returns through GND_VCO, measured separately so the
*                  domain's own current balance can be checked.
*   i(vvdddiv)  -> divider_chain: the div-2/3 cells, the VCO-rate retiming
*                  flop and the CLK-rate input inverters that drive them.
*
* The window is [ta, tstop] rather than [tb, tstop] so the average spans more
* reference cycles than the phase measurements need; the current is periodic
* at f_ref once locked, and averaging over a whole number of reference periods
* is what makes the number a DC supply current rather than a sample of the
* ripple.  ta and tstop are both runner-placed on the reference grid.
.meas tran i_core avg i(vvdd)    from='ta' to='tstop'
.meas tran i_vco  avg i(vvddvco) from='ta' to='tstop'
.meas tran i_div  avg i(vvdddiv) from='ta' to='tstop'
.meas tran i_gvco avg i(vgndvco) from='ta' to='tstop'
.meas tran i_vss  avg i(vvss)    from='ta' to='tstop'

* Peak instantaneous rail current, for the decap/IR budget #17 consumes.
.meas tran i_core_pk min i(vvdd)    from='ta' to='tstop'
.meas tran i_vco_pk  min i(vvddvco) from='ta' to='tstop'
.meas tran i_div_pk  min i(vvdddiv) from='ta' to='tstop'

*---------------------------------------------------------------- transient ---
* Issued from the .control block, NOT from a top-level `.tran` card: with both
* present ngspice batch mode runs the analysis twice.  The `.meas` cards above
* still evaluate against this run.
.control
  set noaskquit
  tran $&c_tstep $&c_tstop 0 $&c_tmax
.endc
