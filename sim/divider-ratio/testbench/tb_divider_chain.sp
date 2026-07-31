* gf180-pll :: divider-ratio :: full divider_chain testbench (DR-001 Decision 3)
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
*             t_setup measured by tb_dff_setup.sp at the same PVT point.
*   t_rtcq    the retiming flop's own clk->Q, i.e. the constant, N-independent
*             feedback delay the PFD sees (DR-001's interface contract to #9).
*   fbpw      FB high time -- must be >= the PFD reset delay (#9's contract).
*
* Expects from the generated header (sim/lib/simenv.sh):
*   .lib <corner> / .temp <temp_c> / .param vsup=<V>
*   .param kf=<VCO Hz> ktstep=<max timestep> ktstop=<transient stop>
*   .param ksel0..ksel5, kp0..kp5   (0 or 1)
*   .param kn=<programmed divide ratio>   (sets the start-up skip)
*
* The divider_chain subcircuit is prepended by the campaign runner (from
* design/netlist/divider_chain.spice, exported from design/divider_chain.sch).

.param tvco='1/kf'
.param ttr='tvco/50'
.param ttd='tvco'
.param tck0='ttd+ttr/2'

vdiv vdd_div 0 dc 'vsup'
vvco vco 0 pulse(0 'vsup' 'ttd' 'ttr' 'ttr' 'tvco/2-ttr' 'tvco')

vs0 sel0 0 dc 'ksel0*vsup'
vs1 sel1 0 dc 'ksel1*vsup'
vs2 sel2 0 dc 'ksel2*vsup'
vs3 sel3 0 dc 'ksel3*vsup'
vs4 sel4 0 dc 'ksel4*vsup'
vs5 sel5 0 dc 'ksel5*vsup'
vq0 pb0 0 dc 'kp0*vsup'
vq1 pb1 0 dc 'kp1*vsup'
vq2 pb2 0 dc 'kp2*vsup'
vq3 pb3 0 dc 'kp3*vsup'
vq4 pb4 0 dc 'kp4*vsup'
vq5 pb5 0 dc 'kp5*vsup'

xchain vco pb0 pb1 pb2 pb3 pb4 pb5 sel0 sel1 sel2 sel3 sel4 sel5
+ divout fb vdd_div 0 divider_chain

.options reltol=1e-3 abstol=1e-10 vntol=1e-5 chgtol=1e-13
.tran {ktstep} {ktstop}

* Skip one full output period of start-up before looking for any edge.
.param tskip='ttd+kn*tvco'

* --- division ratio of the retimed feedback edge, first settled period
.meas tran tfb1 when v(fb)='vsup/2' rise=1 td='tskip'
.meas tran tfb2 when v(fb)='vsup/2' rise=2 td='tskip'
.meas tran n_fb param='(tfb2-tfb1)/tvco'

* --- same ratio on the raw (un-retimed) chain output, over the same interval
.meas tran tdo1 when v(divout)='vsup/2' rise=1 td='tskip'
.meas tran tdo2 when v(divout)='vsup/2' rise=2 td='tskip'
.meas tran ndo param='(tdo2-tdo1)/tvco'

* --- retiming timing, both referred to the VCO rising edge (modulo one VCO
*     period, so the result is independent of which edge index is involved)
.meas tran t_arr param='(tdo2-tck0)-tvco*floor((tdo2-tck0)/tvco)'
.meas tran t_rtcq param='(tfb2-tck0)-tvco*floor((tfb2-tck0)/tvco)'

* --- feedback pulse width (sign corrected in the runner, see tb_div23_cell)
.meas tran ffb2 when v(fb)='vsup/2' fall=2 td='tskip'
.meas tran fbpw param='ffb2-tfb2'

* --- divider supply current on the dedicated vdd_div domain
.meas tran iavg avg i(vdiv) from='tskip' to='ktstop'
