* gf180-pll :: divider-ratio-chain :: full divider_chain testbench (DR-001 Decision 3)
*
* One divider_chain instance (six div23_cells + chain-length termination +
* output multiplexer + VCO-clocked retiming flop) driven at kf, programmed to
* one integer N per run through the one-hot chain-length code SEL and the
* modulus bits P:
*
*   N = 2^k + sum(P_i . 2^i)  for i < k,  SEL_(k-1) = 1
*
* Measured per run:
*   n_fb      the retimed FB period in units of the VCO period -- must equal N
*   ndo       the same for the un-retimed DIVOUT node, over the same interval
*
* Both are measured only AFTER a full output period (kn VCO periods) has been
* skipped. That skip is not padding: the thirteen flops come out of the DC
* operating point in an arbitrary state, and the modulus chain needs one full
* pass -- one output period -- before its ripple-back mod signals are correct.
* Measured without the skip, the FIRST output period reads N-1 at some N and
* corners (observed at ff/-40 C/3.63 V for N = 12, 13, 16, 17) while every
* period after it is exact. That is a start-up transient, not a division
* error, and skipping it is the honest way to exclude it -- as opposed to
* widening the tolerance until it disappears.
*   t_arr     DIVOUT arrival time referred to the VCO rising edge that caused
*             it = the chain's accumulated clk->Q plus the output-mux delay.
*             This is the quantity the retiming flop's setup budget is spent
*             on (DR-001: "one VCO period minus the chain's accumulated
*             clk->Q"), so setup margin = T_vco - t_arr - t_setup, with
*             t_setup joined from sim/divider-ratio-dff at the same PVT point
*             (this manifest's 'derived' retiming_margin.csv table).
*   t_rtcq    the retiming flop's own clk->Q, i.e. the constant, N-independent
*             feedback delay the PFD sees (DR-001's interface contract to #9).
*   fbpw      FB high time -- must be >= the PFD reset delay (#9's contract).
*
* Fed by sim/harness: process/temp/vdd_val as usual, plus this manifest's
* 'point' sweep axis params kf/ktstep/ktstop/kn/ksel0..5/kp0..5 (one point per
* (input rate, programmed N) combination actually run -- see
* sim/harness/README.md "Sweeping beyond the PVT grid").
*
* divider_chain is composed ahead of this fragment by the manifest's 'dut' key
* (design/netlist/divider_chain.spice, exported from design/divider_chain.sch,
* itself instantiating design/div23_cell.sch), so the frozen netlist snapshot
* is DUT + this file in one self-contained deck.

.param tvco='1/kf'
.param ttr='tvco/50'
.param ttd='tvco'
.param tck0='ttd+ttr/2'

vdiv vdd_div 0 dc 'vdd_val'
vvco vco 0 pulse(0 'vdd_val' 'ttd' 'ttr' 'ttr' 'tvco/2-ttr' 'tvco')

vs0 sel0 0 dc 'ksel0*vdd_val'
vs1 sel1 0 dc 'ksel1*vdd_val'
vs2 sel2 0 dc 'ksel2*vdd_val'
vs3 sel3 0 dc 'ksel3*vdd_val'
vs4 sel4 0 dc 'ksel4*vdd_val'
vs5 sel5 0 dc 'ksel5*vdd_val'
vq0 pb0 0 dc 'kp0*vdd_val'
vq1 pb1 0 dc 'kp1*vdd_val'
vq2 pb2 0 dc 'kp2*vdd_val'
vq3 pb3 0 dc 'kp3*vdd_val'
vq4 pb4 0 dc 'kp4*vdd_val'
vq5 pb5 0 dc 'kp5*vdd_val'

xchain vco pb0 pb1 pb2 pb3 pb4 pb5 sel0 sel1 sel2 sel3 sel4 sel5
+ divout fb vdd_div 0 divider_chain

* Skip one full output period of start-up before looking for any edge.
.param tskip='ttd+kn*tvco'
