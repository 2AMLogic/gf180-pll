* gf180-pll :: supply-sensitivity :: supply STEP and RAMP on a locked loop
*
* DUT: `pll_top`, assembled by sim/lib/pll_top_dut.sh (#52) from the
* committed export of design/pll_top.sch -- the same DUT tb_supply_lock.sp
* measures, so the disturbance numbers here and the steady-state numbers there
* describe one block and not two.  (`pll_top_dut.sh` was originally named
* `assemble_closed_loop.sh` too, before being renamed to avoid colliding with
* the differently-shaped #12 helper of the same pre-rename name -- see
* sim/README.md, "Closed-loop campaigns".)
*
* WHAT THIS DECK MEASURES (#14 criterion 3).  tb_supply_lock.sp answers "where
* does the loop sit at each supply"; a stepped rail has no single steady state,
* so this deck answers the other half:
*
*   - does the loop STAY locked through a fast supply step, and through a slow
*     supply ramp that crosses the whole ratified +/-10 % range;
*   - how much output-phase and output-frequency disturbance couples through
*     while it does;
*   - and does it re-settle to the same phase afterwards.
*
* The mechanism being exercised is the VCO's supply pushing, which #8 has
* already measured OPEN LOOP -- -50.7 %/V worst-case static, and -47.7 MHz/V
* transient for a 0.1 V step at the 100 MHz-class operating point
* (sim/vco-tuning-range record 20260731-184845-0a12e6c, sections 1 and 2).
* This deck deliberately does NOT re-derive that number: it measures what the
* CLOSED loop does with it.  The two are different quantities -- inside the
* loop bandwidth the PLL corrects the VCO's excursion, outside it does not --
* and conflating them is exactly the error #14 was scoped to avoid.
*
* PROFILE.  One transient carries both events, separated by enough settling
* that neither contaminates the other:
*
*   0            .. t_step     hold at v_lo (the nominal rail)
*   t_step       .. +t_edge    STEP up to v_hi          (fast: a step to a loop
*                                                        whose f_c is ~250 kHz)
*   .. t_ramp                  hold at v_hi (settle, then measure)
*   t_ramp .. t_rend           RAMP down to v_end       (slow, monotonic, spans
*                                                        the whole +/-10 % rail)
*   t_rend .. tstop            hold at v_end (settle, then measure)
*
* Expects from the generated header (sim/lib/simenv.sh):
*   .lib <corner sections>   .temp <temp_c>   .param vsup=<volts>
* `vsup` is the reference rail for every level-scaled DC input below; the
* time-varying rail is `v_lo`/`v_hi`/`v_end` and vsup is set equal to v_lo.
* From the runner, one .param each:
*   fref, nratio, vctrl0            operating point (as tb_supply_lock.sp)
*   v_lo, v_hi, v_end, t_step, t_edge, t_ramp, t_rend   the profile above
*   b*_code, cpb*_code, sel*_code, p*_code              configuration bits
*   tstop, tstep, tmax                                  transient controls
*   p1 .. p12                       phase-probe instants, each snapped by the
*                                   runner onto a reference HALF-period so the
*                                   REF and FB edges a probe pairs are the same
*                                   cycle's and cannot alias by a whole period
*
* END-PLATEAU SETTLING ESCALATION (#255).  p11/p12 -- the END-plateau probes
* that bound `ferr_end` -- and `tstop` are NOT hardcoded by the runner: a
* corner whose `ferr_end` misses the lock criterion at the default 8.0 us
* post-ramp hold (`t_rend`..`tstop`) is re-run by `run.sh` with p11/p12 and
* `tstop` pushed out to a longer hold, the same ambiguity-resolving mechanism
* `run.sh`'s criterion-1 settling escalation (`KTSTOP_X`/`KTA_X`/`KTB_X`)
* already applies to the steady-state deck -- see `run.sh`'s "END-plateau
* settling escalation" comment for the derivation.  It composes with #253's
* HIGH-plateau escalation (which moves `t_ramp`/`t_rend` instead): a corner
* that missed both plateaus is re-run once, on the high-plateau-escalated
* profile, with the post-ramp hold extended from that profile's own `t_rend`.
* This deck itself is unchanged by either escalation: p11/p12/`t_ramp`/
* `t_rend`/`tstop` are already generic `.param`s, so a longer hold is just a
* different value passed in, not a different deck.

.param iunit=8u
.param tref='1/fref'
.param tstart='0.5*tref'

*--------------------------------------------------------------- the rail ---
* All three supply domains move together, on one PWL waveform.  They are
* separate pins on pll_top so their currents stay separable, but a block has
* one package supply and a supply-transient claim about a rail that moved only
* under the VCO would not be a claim about this block.
.param vpwl_t0=0
vvdd     vdd     0 pwl(0 'v_lo' 't_step' 'v_lo' 't_step+t_edge' 'v_hi'
+ 't_ramp' 'v_hi' 't_rend' 'v_end' 'tstop' 'v_end')
vvddvco  vdd_vco 0 pwl(0 'v_lo' 't_step' 'v_lo' 't_step+t_edge' 'v_hi'
+ 't_ramp' 'v_hi' 't_rend' 'v_end' 'tstop' 'v_end')
vvdddiv  vdd_div 0 pwl(0 'v_lo' 't_step' 'v_lo' 't_step+t_edge' 'v_hi'
+ 't_ramp' 'v_hi' 't_rend' 'v_end' 'tstop' 'v_end')
vgndvco  gnd_vco 0 dc 0
vvss     vss     0 dc 0

* Reference clock at the NOMINAL rail amplitude.  Unlike tb_supply_lock.sp --
* where the reference tracks the supply because it is a CMOS input on the same
* die -- the reference here is deliberately held at v_lo while the rail moves,
* so the measured disturbance is the loop's response to the SUPPLY and not to
* a simultaneous change in its own input amplitude.  Holding it fixed is the
* conservative choice for the input receiver's threshold: the receiver sees a
* worst-case slicing offset when the rail is high and the reference is not.
vref ref 0 pulse(0 'v_lo' 'tstart' 200p 200p '0.5*tref' 'tref')

* Static configuration bits, referenced to the NOMINAL rail.  A real static
* configuration input is driven from the same moving rail as the block, but
* these are logic levels with a rail's worth of margin either way; scaling them
* to v_lo keeps the digital levels valid at every point on the profile and
* keeps them from injecting their own (meaningless) charge step at t_step.
vb0   b0   0 dc 'v_lo*b0_code'
vb1   b1   0 dc 'v_lo*b1_code'
vb2   b2   0 dc 'v_lo*b2_code'
vcpb0 cpb0 0 dc 'v_lo*cpb0_code'
vcpb1 cpb1 0 dc 'v_lo*cpb1_code'
vp0   p0   0 dc 'v_lo*p0_code'
vp1   p1   0 dc 'v_lo*p1_code'
vp2   p2   0 dc 'v_lo*p2_code'
vp3   p3   0 dc 'v_lo*p3_code'
vp4   p4   0 dc 'v_lo*p4_code'
vp5   p5   0 dc 'v_lo*p5_code'
vs0   sel0 0 dc 'v_lo*sel0_code'
vs1   sel1 0 dc 'v_lo*sel1_code'
vs2   sel2 0 dc 'v_lo*sel2_code'
vs3   sel3 0 dc 'v_lo*sel3_code'
vs4   sel4 0 dc 'v_lo*sel4_code'
vs5   sel5 0 dc 'v_lo*sel5_code'

* Ideal charge-pump bias references, as every charge-pump campaign in this repo
* drives them.  Holding them CONSTANT through the supply excursion is the
* deliberate choice: the bias generator is a separate, unbuilt block, so any
* supply dependence assigned to it here would be invented.  The consequence is
* stated as a limitation of the record -- the disturbance reported below
* excludes whatever the real bias generator will contribute.
iibn vdd ibn dc 'iunit'
iicn vdd icn dc 'iunit'
iibp ibp 0   dc 'iunit'
iicp icp 0   dc 'iunit'

xdut ref b0 b1 b2 cpb0 cpb1 p0 p1 p2 p3 p4 p5 sel0 sel1 sel2 sel3 sel4 sel5
+ ibn icn ibp icp clk divout fb lock vctrl vdd vdd_vco gnd_vco vdd_div vss
+ pll_top

*--------------------------------------------------------- initial state ---
* Both filter nodes pre-charged -- see tb_supply_lock.sp for why setting
* VCTRL alone is not a warm start: the loop's state lives on the filter's
* series capacitor C1 (node NZ), and leaving it at 0 V turns every run into a
* cold-start acquisition ramp.
.ic v(vctrl)='vctrl0'
.ic v(xdut.xlf.nz)='vctrl0'
.ic v(xdut.xvco.y1)=0 v(xdut.xvco.y2)='v_lo' v(xdut.xvco.y3)=0
+ v(xdut.xvco.y4)='v_lo' v(xdut.xvco.y5)=0

.option rshunt=1e12 itl4=200 reltol=1e-3 abstol=1e-13 vntol=1e-6

.csparam c_tstep={tstep}
.csparam c_tstop={tstop}
.csparam c_tmax={tmax}

*------------------------------------------------------------ phase probes ---
* The static REF->FB phase error, sampled at twelve instants across the
* profile.  Phase is the right observable for this question: in a locked
* type-II loop the OUTPUT frequency is pinned to N*f_ref by construction, so a
* supply disturbance shows up first and largest as a phase excursion, and only
* as a frequency error while that excursion is being accumulated.  Reporting
* only frequency would report a disturbance as almost zero.
.meas tran phi01 trig v(ref) val='v_lo/2' rise=1 td='p1'  targ v(fb) val='v_lo/2' rise=1 td='p1'
.meas tran phi02 trig v(ref) val='v_lo/2' rise=1 td='p2'  targ v(fb) val='v_lo/2' rise=1 td='p2'
.meas tran phi03 trig v(ref) val='v_lo/2' rise=1 td='p3'  targ v(fb) val='v_lo/2' rise=1 td='p3'
.meas tran phi04 trig v(ref) val='v_lo/2' rise=1 td='p4'  targ v(fb) val='v_lo/2' rise=1 td='p4'
.meas tran phi05 trig v(ref) val='v_lo/2' rise=1 td='p5'  targ v(fb) val='v_lo/2' rise=1 td='p5'
.meas tran phi06 trig v(ref) val='v_lo/2' rise=1 td='p6'  targ v(fb) val='v_lo/2' rise=1 td='p6'
.meas tran phi07 trig v(ref) val='v_lo/2' rise=1 td='p7'  targ v(fb) val='v_lo/2' rise=1 td='p7'
.meas tran phi08 trig v(ref) val='v_lo/2' rise=1 td='p8'  targ v(fb) val='v_lo/2' rise=1 td='p8'
.meas tran phi09 trig v(ref) val='v_lo/2' rise=1 td='p9'  targ v(fb) val='v_lo/2' rise=1 td='p9'
.meas tran phi10 trig v(ref) val='v_lo/2' rise=1 td='p10' targ v(fb) val='v_lo/2' rise=1 td='p10'
.meas tran phi11 trig v(ref) val='v_lo/2' rise=1 td='p11' targ v(fb) val='v_lo/2' rise=1 td='p11'
.meas tran phi12 trig v(ref) val='v_lo/2' rise=1 td='p12' targ v(fb) val='v_lo/2' rise=1 td='p12'

* Residual frequency error in the three SETTLED plateaus, each measured the
* same way tb_supply_lock.sp measures it: the drift of the static phase
* between two instants.  If any of these is not small the loop is not locked
* on that plateau, whatever the LOCK flag says.
.meas tran ferr_lo  param='-(phi02-phi01)/(p2-p1)'
.meas tran ferr_hi  param='-(phi08-phi07)/(p8-p7)'
.meas tran ferr_end param='-(phi12-phi11)/(p12-p11)'

*--------------------------------------------------------------- frequency ---
* Output frequency on each settled plateau, over 100 whole CLK cycles.
.meas tran tclk_lo  trig v(clk) val='v_lo/2' rise=1 td='p1'  targ v(clk) val='v_lo/2' rise=101 td='p1'
.meas tran fout_lo  param='100/tclk_lo'
.meas tran tclk_hi  trig v(clk) val='v_hi/2' rise=1 td='p7'  targ v(clk) val='v_hi/2' rise=101 td='p7'
.meas tran fout_hi  param='100/tclk_hi'
.meas tran tclk_end trig v(clk) val='v_end/2' rise=1 td='p11' targ v(clk) val='v_end/2' rise=101 td='p11'
.meas tran fout_end param='100/tclk_end'

* The output frequency during the two DISTURBANCES, over a short cycle count so
* the window is inside the excursion rather than averaging across it.  20 CLK
* cycles is 200 ns at 100 MHz, i.e. ~1/20 of the loop's own response time.
.meas tran tclk_s trig v(clk) val='v_hi/2' rise=1 td='t_step+t_edge' targ v(clk) val='v_hi/2' rise=21 td='t_step+t_edge'
.meas tran fout_s param='20/tclk_s'
.meas tran tclk_r trig v(clk) val='v_hi/2' rise=1 td='p9' targ v(clk) val='v_hi/2' rise=21 td='p9'
.meas tran fout_r param='20/tclk_r'

*------------------------------------------------------------ control node ---
* Vctrl is where the loop's correction of the supply excursion is visible: the
* loop holds f_out at N*f_ref by moving Vctrl against the VCO's supply
* pushing, so d(Vctrl) across the profile IS the pushing the loop absorbed.
.meas tran vc_lo   avg v(vctrl) from='p1' to='p2'
.meas tran vc_hi   avg v(vctrl) from='p7' to='p8'
.meas tran vc_end  avg v(vctrl) from='p11' to='p12'
.meas tran vc_smax max v(vctrl) from='t_step' to='p6'
.meas tran vc_smin min v(vctrl) from='t_step' to='p6'
.meas tran vc_rmax max v(vctrl) from='t_ramp' to='t_rend'
.meas tran vc_rmin min v(vctrl) from='t_ramp' to='t_rend'
.meas tran vc_all_max max v(vctrl) from='p1' to='tstop'
.meas tran vc_all_min min v(vctrl) from='p1' to='tstop'

*------------------------------------------------------------- LOCK flag -----
* #11's window comparator, averaged over each phase of the profile.  A flag
* that drops out during the step or the ramp and comes back is the honest
* signature of "lost lock and re-acquired", and it reads here as an average
* below the rail rather than being rounded to a verdict.
.meas tran lock_lo   avg v(lock) from='p1' to='p2'
.meas tran lock_stp  avg v(lock) from='t_step' to='p6'
.meas tran lock_hi   avg v(lock) from='p7' to='p8'
.meas tran lock_rmp  avg v(lock) from='t_ramp' to='t_rend'
.meas tran lock_end  avg v(lock) from='p11' to='p12'
.meas tran lock_min  min v(lock) from='p1' to='tstop'

*-------------------------------------------------------------------- power ---
* Per-domain current on each settled plateau, so the power reported by
* tb_supply_lock.sp at 2.97 / 3.30 / 3.63 V has an independent cross-check
* taken on a rail that ARRIVED at those voltages rather than starting there.
.meas tran i_core_lo  avg i(vvdd)    from='p1' to='p2'
.meas tran i_vco_lo   avg i(vvddvco) from='p1' to='p2'
.meas tran i_div_lo   avg i(vvdddiv) from='p1' to='p2'
.meas tran i_core_hi  avg i(vvdd)    from='p7' to='p8'
.meas tran i_vco_hi   avg i(vvddvco) from='p7' to='p8'
.meas tran i_div_hi   avg i(vvdddiv) from='p7' to='p8'
.meas tran i_core_end avg i(vvdd)    from='p11' to='p12'
.meas tran i_vco_end  avg i(vvddvco) from='p11' to='p12'
.meas tran i_div_end  avg i(vvdddiv) from='p11' to='p12'

*---------------------------------------------------------------- transient ---
* The disturbance transient IS the evidence for this criterion, so the trace is
* retained -- as a CSV of the four signals that carry the argument, decimated
* by the runner, never as a rawfile (sim/README.md's waveform rule).
.control
  set noaskquit
  tran $&c_tstep $&c_tstop 0 $&c_tmax
  wrdata supply_transient_full.csv v(vctrl) v(lock) v(vdd) v(fb)
.endc
