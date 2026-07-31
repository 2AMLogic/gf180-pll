* gf180-pll :: mc-cp-mismatch :: divider-retiming flop clk->Q delay spread,
* RANDOM device mismatch enabled (Monte Carlo)
*
* DUT: `dff_tg_3v3` (design/netlist/dff_tg_3v3.spice, the committed export
* sim/divider-ratio's tb_dff_setup.sp also uses) -- the retiming flop DR-001
* Decision 3 puts between the feedback divider's output and the PFD's FB
* input ("FB is a VCO edge retimed by exactly one flop's clk->Q, independent
* of N"). This is the "divider-retiming mismatch contribution to static
* phase offset" half of #15's acceptance criteria (the charge-pump/PFD half
* is tb_mc_pfd_cp.sp).
*
* Unlike the charge-domain campaigns above, a clk->Q delay SPREAD converts to
* a phase-offset contribution directly, one-for-one, with no Kd division: a
* retiming flop that fires t seconds later presents FB to the PFD t seconds
* later, which is t seconds of phase error at the PFD input -- there is no
* charge-pump gain in between for this particular error source.
*
* Two independent replicas per invocation (one 0->1 capture, one 1->0
* capture), each getting its own mismatch draw exactly as tb_mc_cp_dc.sp's
* two `cp` instances do -- this DOES scale safely to N-way replication
* (unlike the switching decks above): a single static CMOS flop has no
* op-amp-loaded control node, so there is no analogue of the `cp_dumpbuf`
* convergence hazard tb_mc_cp_dc.sp's header documents. run.sh relies on
* this: it runs MORE replicas per invocation here to reach its sample count
* in fewer, cheaper ngspice calls.
*
* Method: a single clean, well-inside-timing-margin data transition (2 ns
* before the measured clock edge -- see sim/divider-ratio's tb_dff_setup.sp
* for the corner setup-time numbers this comfortably clears at every PVT
* point), so the measured clk->Q reflects normal propagation, not a
* setup/hold-limited degraded delay. The first clock edge preconditions the
* flop to the opposite state (as tb_dff_setup.sp), so nothing here depends on
* the DC operating point of a bistable latch.
*
* Expects from the generated header (see sim/lib/simenv.sh):
*   .lib <process corner section>   typical (nominal PVT only)
*   .temp <temp_c>
*   .param vsup=<supply volts>
*   .param sw_stat_mismatch=1
*   .option rndseed=<seed>          (via run.sh / simenv_run_deck)
* run.sh prepends design/netlist/dff_tg_3v3.spice to this file (as
* sim/divider-ratio's run.sh does), so the frozen netlist snapshot of a
* record is deck + DUT in one file -- there is no `dut.spice` staging step
* here.

.param tsl=100p
.param tedge=25.05n

vdd vdd 0 dc 'vsup'
vck ck 0 pulse(0 'vsup' 5n 'tsl' 'tsl' 9.8n 20n)

* ---- replica R: 0 -> 1 capture ---------------------------------------
vdr dr 0 pulse(0 'vsup' 'tedge-2n-tsl/2' 'tsl' 'tsl' 10n 100n)
xr dr ck qr nr vdd 0 dff_tg_3v3

* ---- replica F: 1 -> 0 capture ---------------------------------------
vdf df 0 pulse('vsup' 0 'tedge-2n-tsl/2' 'tsl' 'tsl' 10n 100n)
xf df ck qf nf vdd 0 dff_tg_3v3

.options reltol=1e-3 abstol=1e-10 vntol=1e-5 chgtol=1e-13
.tran 5p 30n

.meas tran tcq_r trig v(ck) val='vsup/2' rise=2 targ v(qr) val='vsup/2' rise=1 td=20n
.meas tran tcq_f trig v(ck) val='vsup/2' rise=2 targ v(qf) val='vsup/2' fall=1 td=20n
