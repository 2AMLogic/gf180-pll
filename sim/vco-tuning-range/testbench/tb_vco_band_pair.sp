* gf180-pll :: vco-tuning-range :: JOINT two-band Monte Carlo mismatch bench
* for the band-select mirror -- both sides of one adjacent-band pair drawn
* from ONE mismatch draw (issue #597)
*
* --- What this deck does that tb_vco_mismatch.sp cannot -------------------
*
* tb_vco_mismatch.sp measures ONE band code per ngspice invocation. Both
* records minted from it (`20260817-143524-0e9cfc9`, `20260923-084925-1655e11`)
* therefore had to state the same limitation in their own text:
*
*   "A fully joint check would need band 0 and band 1 to share ONE
*    per-instance mismatch draw on their common always-on mirror legs (they
*    are the same physical devices on one die across band codes) within a
*    single simulation -- this script, like its predecessor, draws
*    independently instead."
*
* That limitation is not cosmetic. The quantity the band plan's
* coverage-hole check actually asks about is an INEQUALITY BETWEEN TWO BANDS
* ON ONE DIE -- `f_max(band b) >= f_min(band b+1)` -- and the two frequencies
* in it are produced by the same silicon, most of it literally the same
* transistors: bands 0 and 1 differ by one switched mirror leg in
* `design/vco_bias.sch`'s cascade and share every always-on leg, the V->I
* converter and all five ring stages. Drawing them independently throws away
* that sharing, and the only bound available from independent draws is to push
* one band down 3 sigma while pushing the other up 3 sigma -- which is
* enormously pessimistic, because the shared part of the draw is COMMON MODE
* and cancels in the ratio.
*
* This deck removes the limitation instead of bounding around it. The
* gf180mcu mismatch model's `agauss()` draws are evaluated ONCE, at netlist
* PARSE time (the confirmed model-capability finding in
* sim/mc-cp-mismatch/records/20260731-212614-640560e.md), so every analysis
* run inside a single invocation of this deck sees the SAME per-instance
* Vth/beta offsets. Two `tran` runs in one `.control` block therefore measure
* two band codes of ONE die, and their RATIO is a per-draw sample of exactly
* the quantity the overlap check needs. The band code is changed between the
* two runs with `alter` on the three band-select DC sources -- no device is
* added, removed or re-parameterised, so nothing about the draw changes.
*
* This is the same one-parse-many-analyses idiom sim/mc-cp-mismatch's
* tb_mc_cp_dc.sp already uses to get three Vctrl points out of one draw
* (`alter` + `op` + `echo`, `MCDC_LO/MID/HI`), and the same in-control-block
* `meas` + `$&` readback idiom sim/cp-compliance/testbench/tb_cp_switch.sp
* uses. Nothing here is a new mechanism; what is new is applying it across the
* BAND axis, which is the axis this campaign's Monte Carlo evidence was stuck
* at one point on.
*
* --- Which two points, and why -------------------------------------------
*
* `band_overlap` is defined as `f_max(band b) / f_min(band b+1)`, so:
*   run 1: band code 000 (band 0) at the TOP of the 0.9-2.7 V control
*          window -> f_max(band 0)
*   run 2: band code 001 (band 1) at the BOTTOM of that window
*          -> f_min(band 1)
* Both control voltages arrive as parameters (`vctrl0`, `vctrl1`) so the
* runner, not this deck, owns which pair of band codes and control points is
* being checked. The band codes themselves are parameters too (`b0c0..b2c0`
* for run 1, `b0c1..b2c1` for run 2, each 0 or 1), so the same deck can check
* any adjacent pair without editing.
*
* --- Ring-symmetry initial condition, applied to BOTH runs ---------------
*
* The `.ic` line below breaks the ring's DC symmetry so the operating point is
* not the metastable all-nodes-at-mid solution -- same convention as
* tb_vco_tuning.sp/.spice and tb_vco_mismatch.sp. It is a netlist-level card,
* so it is applied at EACH `tran`'s own operating-point solve, not just the
* first; the runner asserts both runs produced a plausible oscillation rather
* than trusting that.
*
* Expects from the generated header (see sim/lib/simenv.sh):
*   .lib <mos corner> section
*   .temp <temp_c>
*   .param vsup
*   .param vctrl0 vctrl1              control voltage for run 1 / run 2
*   .param b0c0 b1c0 b2c0             band-select bits for run 1 (0 or 1)
*   .param b0c1 b1c1 b2c1             band-select bits for run 2 (0 or 1)
*   .param ts0 tstop0 tmax0           transient window for run 1
*   .param ts1 tstop1 tmax1           transient window for run 2
*   .option rndseed=N   (parse-time; this is what makes the two runs below
*     share one draw, and what makes the whole invocation reproducible)
* Set directly in THIS file, for the same reason tb_vco_mismatch.sp sets them
* here rather than passing them as kv overrides (see run_mismatch.sh's header
* comment on the harness-ordering finding): `sw_stat_mismatch=1`,
* `sw_stat_global=0` -- mismatch only, matching every other Monte Carlo
* campaign in this repo. This line lands AFTER simenv_run_deck's
* `.include design.ngspice` (which sets the opposite default), and ngspice
* resolves `.param` redefinitions by LAST occurrence in the deck.
*
* Devices are the PDK 3.3 V thick-oxide wrappers only (nfet_03v3 / pfet_03v3,
* ppolyf_u_3k, cap_nmos_03v3), per DR-002 Decision 3 -- identical DUT to
* tb_vco_tuning.sp/.spice and tb_vco_mismatch.sp, one instance.
.param sw_stat_global=0
.param sw_stat_mismatch=1

.include "vco.spice"

* Reach the control block with the values the two runs need. `.csparam` is the
* mechanism every other campaign here uses for this (see
* sim/lock-time/testbench/tb_lock_time.sp's note).
.csparam c_half={vsup/2}
.csparam c_vctrl0={vctrl0}
.csparam c_vctrl1={vctrl1}
.csparam c_vb0c0={vsup*b0c0}
.csparam c_vb1c0={vsup*b1c0}
.csparam c_vb2c0={vsup*b2c0}
.csparam c_vb0c1={vsup*b0c1}
.csparam c_vb1c1={vsup*b1c1}
.csparam c_vb2c1={vsup*b2c1}
.csparam c_ts0={ts0}
.csparam c_tstop0={tstop0}
.csparam c_tmax0={tmax0}
.csparam c_ts1={ts1}
.csparam c_tstop1={tstop1}
.csparam c_tmax1={tmax1}

vdd  vdd 0 dc 'vsup'
vc   vc  0 dc 'vctrl0'
vb0  nb0 0 dc 'vsup*b0c0'
vb1  nb1 0 dc 'vsup*b1c0'
vb2  nb2 0 dc 'vsup*b2c0'
vs   vdd nvs dc 0

x1 vc nb0 nb1 nb2 clk1 nvs 0 vco

.ic v(x1.Y1)=0 v(x1.Y2)='vsup' v(x1.Y3)=0 v(x1.Y4)='vsup' v(x1.Y5)=0

.control
  set noaskquit

  *---------------------------------------------------- run 1: the lower band
  alter vc  = $&c_vctrl0
  alter vb0 = $&c_vb0c0
  alter vb1 = $&c_vb1c0
  alter vb2 = $&c_vb2c0
  tran $&c_tmax0 $&c_tstop0 0 $&c_tmax0
  meas tran tp_a trig v(clk1) val=$&c_half rise=1 td=$&c_ts0 targ v(clk1) val=$&c_half rise=5 td=$&c_ts0
  meas tran i_a avg i(vs) from=$&c_ts0 to=$&c_tstop0
  let f_a = 4 / tp_a
  echo "MCVCOPAIR_A tp=$&tp_a f=$&f_a i=$&i_a"

  *---------------------------------------------------- run 2: the upper band
  * SAME netlist parse, so SAME per-instance mismatch draw. Only the band
  * select bits and the control voltage move.
  alter vc  = $&c_vctrl1
  alter vb0 = $&c_vb0c1
  alter vb1 = $&c_vb1c1
  alter vb2 = $&c_vb2c1
  tran $&c_tmax1 $&c_tstop1 0 $&c_tmax1
  meas tran tp_b trig v(clk1) val=$&c_half rise=1 td=$&c_ts1 targ v(clk1) val=$&c_half rise=5 td=$&c_ts1
  meas tran i_b avg i(vs) from=$&c_ts1 to=$&c_tstop1
  let f_b = 4 / tp_b
  echo "MCVCOPAIR_B tp=$&tp_b f=$&f_b i=$&i_b"

  * The overlap RATIO -- `f_max(lower band) / f_min(upper band)` on ONE die,
  * which is the whole point of this deck -- is formed by the RUNNER from the
  * two lines above, not here. Each `tran` gets its own ngspice plot, and a
  * `let` in the second plot cannot see a vector belonging to the first
  * ("Error: RHS \"f_a / f_b\" invalid", observed during this deck's bring-up).
  * Cross-plot arithmetic is possible with explicit plot prefixes, but there is
  * nothing to gain from doing it here: both operands are echoed above and the
  * runner has to parse them anyway. What matters -- that the two numbers come
  * from ONE parse and therefore ONE draw -- is a property of this deck, and it
  * holds whichever side does the division.
.endc
