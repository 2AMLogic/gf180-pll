* gf180-pll :: divider-ratio :: single div23_cell testbench (DR-001 Decision 3)
*
* Six independent copies of the SAME cell, so one transient covers every
* single-cell acceptance check at a given PVT point:
*
*   XA  P=0, 50% duty clock          -> divide by 2
*   XB  P=1, 50% duty clock          -> divide by 3   (MODIN tied high, i.e.
*                                       the chain-terminated last-cell case)
*   XC  P=0, 33% duty clock          -> divide by 2
*   XD  P=1, 67% duty clock          -> divide by 3
*   XE  P=1, clock at 1.5x kf        -> divide by 3   (speed margin)
*   XF  P=1, clock at 2.0x kf        -> divide by 3   (speed margin)
*
* XC / XD are the "both edges" check and they are not academic: a cell that is
* swallowing emits a 33%-duty CKOUT, and the 67% case is its complement, so
* every cell downstream of a swallowing cell is clocked by a duty-distorted
* waveform. Division must be exact for both, which is only true if the cell is
* purely rising-edge triggered.
*
* XE / XF quantify first-cell speed margin above the 200 MHz v1 ceiling
* (DR-002 Decision 2 budgets margin to the target, not the 400 MHz stretch);
* at kf = 200 MHz they are the 300 MHz and 400 MHz points.
*
* Running the same deck with a low kf is the "no minimum clock frequency"
* check that DR-001 Decision 3 requires of static CMOS -- it is the property
* dynamic/TSPC logic was rejected for, and it must hold at 125 C where
* leakage off a would-be dynamic node is worst.
*
* Expects from the generated header (sim/lib/simenv.sh):
*   .lib <process corner section>   one of typical/ff/ss/fs/sf
*   .temp <temp_c>
*   .param vsup=<supply volts>
*   .param kf=<input clock Hz>  ktstep=<max timestep>  ktstop=<transient stop>
*
* The div23_cell subcircuit is prepended to this file by the campaign runner
* (from design/netlist/div23_cell.spice, exported from design/div23_cell.sch),
* so the frozen netlist snapshot is deck + DUT in one file.

.param tvco='1/kf'
.param ttr='tvco/50'
.param ttd='tvco'
* 50% crossing of the first rising clock edge -- the phase reference used to
* extract clk->Q without depending on which edge index the output happens to
* land on.
.param tck0='ttd+ttr/2'

vdd vdd 0 dc 'vsup'
vhi hi 0 dc 'vsup'
vlo lo 0 dc 0

vck50 ck50 0 pulse(0 'vsup' 'ttd' 'ttr' 'ttr' 'tvco/2-ttr' 'tvco')
vck33 ck33 0 pulse(0 'vsup' 'ttd' 'ttr' 'ttr' 'tvco/3-ttr' 'tvco')
vck67 ck67 0 pulse(0 'vsup' 'ttd' 'ttr' 'ttr' '2*tvco/3-ttr' 'tvco')
vcke  cke  0 pulse(0 'vsup' 'ttd' 'ttr/1.5' 'ttr/1.5' 'tvco/3-ttr/1.5' 'tvco/1.5')
vckf  ckf  0 pulse(0 'vsup' 'ttd' 'ttr/2' 'ttr/2' 'tvco/4-ttr/2' 'tvco/2')

xa ck50 hi lo ckoa moa vdd 0 div23_cell
xb ck50 hi hi ckob mob vdd 0 div23_cell
xc ck33 hi lo ckoc moc vdd 0 div23_cell
xd ck67 hi hi ckod mdd vdd 0 div23_cell
xe cke  hi hi ckoe moe vdd 0 div23_cell
xf ckf  hi hi ckof mof vdd 0 div23_cell

.options reltol=1e-3 abstol=1e-10 vntol=1e-5 chgtol=1e-13
.tran {ktstep} {ktstop}

* --- division ratios: two output periods each, measured against the cell's
*     own input period (XE and XF run 1.5x and 2x faster than kf).
.meas tran ta1 when v(ckoa)='vsup/2' rise=1
.meas tran ta3 when v(ckoa)='vsup/2' rise=3
.meas tran na param='(ta3-ta1)/(2*tvco)'
.meas tran tb1 when v(ckob)='vsup/2' rise=1
.meas tran tb3 when v(ckob)='vsup/2' rise=3
.meas tran nb param='(tb3-tb1)/(2*tvco)'
.meas tran tc1 when v(ckoc)='vsup/2' rise=1
.meas tran tc3 when v(ckoc)='vsup/2' rise=3
.meas tran nc param='(tc3-tc1)/(2*tvco)'
.meas tran td1 when v(ckod)='vsup/2' rise=1
.meas tran td3 when v(ckod)='vsup/2' rise=3
.meas tran nd param='(td3-td1)/(2*tvco)'
.meas tran te1 when v(ckoe)='vsup/2' rise=1
.meas tran te3 when v(ckoe)='vsup/2' rise=3
.meas tran ne param='(te3-te1)/(2*tvco/1.5)'
.meas tran tf1 when v(ckof)='vsup/2' rise=1
.meas tran tf3 when v(ckof)='vsup/2' rise=3
.meas tran nf param='(tf3-tf1)/(2*tvco/2)'

* --- clk->Q of the cell, extracted modulo the input period so it does not
*     depend on which input edge produced output rise #1.
.meas tran tcq param='(ta1-tck0)-tvco*floor((ta1-tck0)/tvco)'

* --- output high times. The sign is corrected in the runner by adding one
*     output period when the DC operating point happens to start the cell high
*     (rise #3 and fall #3 are then one period apart in the other order).
.meas tran fa3 when v(ckoa)='vsup/2' fall=3
.meas tran pwa param='fa3-ta3'
.meas tran fb3 when v(ckob)='vsup/2' fall=3
.meas tran pwb param='fb3-tb3'

* --- MODOUT pulse width of the divide-by-3 cell: must be exactly one CKIN
*     period, because the previous (2x faster) cell has to see it as one of
*     ITS output periods.
.meas tran rmb2 when v(mob)='vsup/2' rise=2
.meas tran fmb2 when v(mob)='vsup/2' fall=2
.meas tran pwmb param='fmb2-rmb2'

* --- supply current (both moduli running, 6 cells) for a first-order power
*     figure; divided by 6 in the runner to give per-cell average.
.meas tran iavg avg i(vdd) from='ttd+2*tvco' to='ktstop'
