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
*   n1, n2    the divided FB period over each of two consecutive output
*             periods, in units of the VCO period -- must both equal N exactly
*   ndo       the same for the un-retimed DIVOUT node
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

* --- division ratio, two consecutive periods of the retimed feedback edge
.meas tran tfb1 when v(fb)='vsup/2' rise=1 td='ttd'
.meas tran tfb2 when v(fb)='vsup/2' rise=2 td='ttd'
.meas tran tfb3 when v(fb)='vsup/2' rise=3 td='ttd'
.meas tran n1 param='(tfb2-tfb1)/tvco'
.meas tran n2 param='(tfb3-tfb2)/tvco'

* --- same ratio on the raw (un-retimed) chain output
.meas tran tdo1 when v(divout)='vsup/2' rise=1 td='ttd'
.meas tran tdo2 when v(divout)='vsup/2' rise=2 td='ttd'
.meas tran ndo param='(tdo2-tdo1)/tvco'

* --- retiming timing, both referred to the VCO rising edge (modulo one VCO
*     period, so the result is independent of which edge index is involved)
.meas tran t_arr param='(tdo2-tck0)-tvco*floor((tdo2-tck0)/tvco)'
.meas tran t_rtcq param='(tfb2-tck0)-tvco*floor((tfb2-tck0)/tvco)'

* --- feedback pulse width (sign corrected in the runner, see tb_div23_cell)
.meas tran ffb2 when v(fb)='vsup/2' fall=2 td='ttd'
.meas tran fbpw param='ffb2-tfb2'

* --- divider supply current on the dedicated vdd_div domain
.meas tran iavg avg i(vdiv) from='ttd+2*tvco' to='ktstop'
