* gf180-pll :: divider-ratio :: setup/hold characterisation of dff_tg_3v3
*
* The retiming flop's setup budget is the load-bearing timing check DR-001
* Decision 3 hands to #11: "one VCO period minus the chain's accumulated
* clk->Q ... #11 must close this at the slow corner (SS, 125 C, 2.97 V)".
* Closing it needs a NUMBER for the flop's own setup time at each PVT point,
* which is what this deck produces; tb_divider_chain.sp produces the data
* arrival time, and the divider-ratio record combines them into the margin.
*
* Method
* ------
* SETUP (banks A and B, 10 copies each). Every copy of dff_tg_3v3 shares one
* clock and sees its data transition ti seconds before the clock's 50%
* crossing, ti stepping from 1.00 ns (relaxed) down to -0.15 ns (data moving
* AFTER the clock edge). Bank A captures 0->1, bank B captures 1->0. The
* FIRST clock edge (5 ns) preconditions every flop to the opposite state and
* the SECOND (25.05 ns) is the one measured, so nothing here depends on the
* DC operating point of a bistable latch. Every output measurement carries
* TD = 20 ns for the same reason and it is load-bearing, not cosmetic: the
* operating-point solver can leave a latch's feedback loop on its metastable
* midpoint, and the transient then resolves it to an arbitrary state within
* the first nanosecond. Observed on this cell at ff/125 C, where Q resolved
* HIGH at t ~ 1 ns and an unwindowed "first rising edge" search locked onto
* that resolution instead of the captured edge, reporting a negative clk->Q.
* Setup time is the smallest ti whose clk->Q has not yet
* degraded by more than 10% relative to the ti = 1.00 ns reference of the same
* bank -- the standard degradation criterion. The ladder deliberately extends
* past ti = 0: a transmission-gate master-slave flop closes its input gate a
* gate delay after the clock edge arrives, so its setup time can legitimately
* be a small negative number, and a ladder that stops at 0 would report a
* floor rather than a measurement.
*
* HOLD (bank C, 10 copies). Data is held at 0 through the measured clock edge
* and transitions 0->1 only th seconds AFTER it, th stepping from +0.50 ns
* down to -0.70 ns (data moving BEFORE the edge). The flop must still capture
* the OLD value, so Q must stay low until the next clock edge. Bank C's Q is
* averaged over a window that starts 2 ns after the measured edge and ends
* before the following edge; a copy whose hold time is violated shows ~vsup
* there instead of ~0. Hold matters here because the retiming flop's data
* arrives a fixed 2-5 ns after the VCO edge that caused it, and at the fast
* corner that arrival moves toward the edge itself.
*
* Expects from the generated header (sim/lib/simenv.sh):
*   .lib <process corner section>   one of typical/ff/ss/fs/sf
*   .temp <temp_c>
*   .param vsup=<supply volts>
*
* The dff_tg_3v3 subcircuit is prepended to this file by the campaign runner
* from design/netlist/dff_tg_3v3.spice (exported from design/dff_tg_3v3.sch),
* so the frozen netlist snapshot is deck + DUT in one file.

* Setup ladder, seconds of data-before-clock at the 50% crossings.
.param ti0=1.00n ti1=0.20n ti2=0.10n ti3=0.05n ti4=0.02n
.param ti5=0.00n ti6=-0.02n ti7=-0.05n ti8=-0.10n ti9=-0.15n
* Hold ladder, seconds of data-after-clock at the 50% crossings.
.param th0=0.50n th1=0.20n th2=0.10n th3=0.00n th4=-0.10n
.param th5=-0.20n th6=-0.30n th7=-0.40n th8=-0.50n th9=-0.70n

* Edge slew used for every stimulus, and the 50% crossing of the measured
* (second) clock edge. vck rises at 5 ns and 25 ns with a 100 ps edge, so its
* second 50% crossing is at 25.05 ns.
.param tsl=100p
.param tedge=25.05n

vdd vdd 0 dc 'vsup'
vck ck 0 pulse(0 'vsup' 5n 'tsl' 'tsl' 9.8n 20n)

* ---- bank A: 0 -> 1 capture -----------------------------------------------
va0 da0 0 pulse(0 'vsup' 'tedge-ti0-tsl/2' 'tsl' 'tsl' 10n 100n)
va1 da1 0 pulse(0 'vsup' 'tedge-ti1-tsl/2' 'tsl' 'tsl' 10n 100n)
va2 da2 0 pulse(0 'vsup' 'tedge-ti2-tsl/2' 'tsl' 'tsl' 10n 100n)
va3 da3 0 pulse(0 'vsup' 'tedge-ti3-tsl/2' 'tsl' 'tsl' 10n 100n)
va4 da4 0 pulse(0 'vsup' 'tedge-ti4-tsl/2' 'tsl' 'tsl' 10n 100n)
va5 da5 0 pulse(0 'vsup' 'tedge-ti5-tsl/2' 'tsl' 'tsl' 10n 100n)
va6 da6 0 pulse(0 'vsup' 'tedge-ti6-tsl/2' 'tsl' 'tsl' 10n 100n)
va7 da7 0 pulse(0 'vsup' 'tedge-ti7-tsl/2' 'tsl' 'tsl' 10n 100n)
va8 da8 0 pulse(0 'vsup' 'tedge-ti8-tsl/2' 'tsl' 'tsl' 10n 100n)
va9 da9 0 pulse(0 'vsup' 'tedge-ti9-tsl/2' 'tsl' 'tsl' 10n 100n)
xa0 da0 ck qa0 na0 vdd 0 dff_tg_3v3
xa1 da1 ck qa1 na1 vdd 0 dff_tg_3v3
xa2 da2 ck qa2 na2 vdd 0 dff_tg_3v3
xa3 da3 ck qa3 na3 vdd 0 dff_tg_3v3
xa4 da4 ck qa4 na4 vdd 0 dff_tg_3v3
xa5 da5 ck qa5 na5 vdd 0 dff_tg_3v3
xa6 da6 ck qa6 na6 vdd 0 dff_tg_3v3
xa7 da7 ck qa7 na7 vdd 0 dff_tg_3v3
xa8 da8 ck qa8 na8 vdd 0 dff_tg_3v3
xa9 da9 ck qa9 na9 vdd 0 dff_tg_3v3

* ---- bank B: 1 -> 0 capture -----------------------------------------------
vb0 db0 0 pulse('vsup' 0 'tedge-ti0-tsl/2' 'tsl' 'tsl' 10n 100n)
vb1 db1 0 pulse('vsup' 0 'tedge-ti1-tsl/2' 'tsl' 'tsl' 10n 100n)
vb2 db2 0 pulse('vsup' 0 'tedge-ti2-tsl/2' 'tsl' 'tsl' 10n 100n)
vb3 db3 0 pulse('vsup' 0 'tedge-ti3-tsl/2' 'tsl' 'tsl' 10n 100n)
vb4 db4 0 pulse('vsup' 0 'tedge-ti4-tsl/2' 'tsl' 'tsl' 10n 100n)
vb5 db5 0 pulse('vsup' 0 'tedge-ti5-tsl/2' 'tsl' 'tsl' 10n 100n)
vb6 db6 0 pulse('vsup' 0 'tedge-ti6-tsl/2' 'tsl' 'tsl' 10n 100n)
vb7 db7 0 pulse('vsup' 0 'tedge-ti7-tsl/2' 'tsl' 'tsl' 10n 100n)
vb8 db8 0 pulse('vsup' 0 'tedge-ti8-tsl/2' 'tsl' 'tsl' 10n 100n)
vb9 db9 0 pulse('vsup' 0 'tedge-ti9-tsl/2' 'tsl' 'tsl' 10n 100n)
xb0 db0 ck qb0 nb0 vdd 0 dff_tg_3v3
xb1 db1 ck qb1 nb1 vdd 0 dff_tg_3v3
xb2 db2 ck qb2 nb2 vdd 0 dff_tg_3v3
xb3 db3 ck qb3 nb3 vdd 0 dff_tg_3v3
xb4 db4 ck qb4 nb4 vdd 0 dff_tg_3v3
xb5 db5 ck qb5 nb5 vdd 0 dff_tg_3v3
xb6 db6 ck qb6 nb6 vdd 0 dff_tg_3v3
xb7 db7 ck qb7 nb7 vdd 0 dff_tg_3v3
xb8 db8 ck qb8 nb8 vdd 0 dff_tg_3v3
xb9 db9 ck qb9 nb9 vdd 0 dff_tg_3v3

* ---- bank C: hold. Data must NOT be captured by the measured edge. --------
vc0 dc0 0 pulse(0 'vsup' 'tedge+th0-tsl/2' 'tsl' 'tsl' 10n 100n)
vc1 dc1 0 pulse(0 'vsup' 'tedge+th1-tsl/2' 'tsl' 'tsl' 10n 100n)
vc2 dc2 0 pulse(0 'vsup' 'tedge+th2-tsl/2' 'tsl' 'tsl' 10n 100n)
vc3 dc3 0 pulse(0 'vsup' 'tedge+th3-tsl/2' 'tsl' 'tsl' 10n 100n)
vc4 dc4 0 pulse(0 'vsup' 'tedge+th4-tsl/2' 'tsl' 'tsl' 10n 100n)
vc5 dc5 0 pulse(0 'vsup' 'tedge+th5-tsl/2' 'tsl' 'tsl' 10n 100n)
vc6 dc6 0 pulse(0 'vsup' 'tedge+th6-tsl/2' 'tsl' 'tsl' 10n 100n)
vc7 dc7 0 pulse(0 'vsup' 'tedge+th7-tsl/2' 'tsl' 'tsl' 10n 100n)
vc8 dc8 0 pulse(0 'vsup' 'tedge+th8-tsl/2' 'tsl' 'tsl' 10n 100n)
vc9 dc9 0 pulse(0 'vsup' 'tedge+th9-tsl/2' 'tsl' 'tsl' 10n 100n)
xc0 dc0 ck qc0 nc0 vdd 0 dff_tg_3v3
xc1 dc1 ck qc1 nc1 vdd 0 dff_tg_3v3
xc2 dc2 ck qc2 nc2 vdd 0 dff_tg_3v3
xc3 dc3 ck qc3 nc3 vdd 0 dff_tg_3v3
xc4 dc4 ck qc4 nc4 vdd 0 dff_tg_3v3
xc5 dc5 ck qc5 nc5 vdd 0 dff_tg_3v3
xc6 dc6 ck qc6 nc6 vdd 0 dff_tg_3v3
xc7 dc7 ck qc7 nc7 vdd 0 dff_tg_3v3
xc8 dc8 ck qc8 nc8 vdd 0 dff_tg_3v3
xc9 dc9 ck qc9 nc9 vdd 0 dff_tg_3v3

.options reltol=1e-3 abstol=1e-10 vntol=1e-5 chgtol=1e-13
.tran 10p 35n

.meas tran cqa0 trig v(ck) val='vsup/2' rise=2 targ v(qa0) val='vsup/2' rise=1 td=20n
.meas tran cqa1 trig v(ck) val='vsup/2' rise=2 targ v(qa1) val='vsup/2' rise=1 td=20n
.meas tran cqa2 trig v(ck) val='vsup/2' rise=2 targ v(qa2) val='vsup/2' rise=1 td=20n
.meas tran cqa3 trig v(ck) val='vsup/2' rise=2 targ v(qa3) val='vsup/2' rise=1 td=20n
.meas tran cqa4 trig v(ck) val='vsup/2' rise=2 targ v(qa4) val='vsup/2' rise=1 td=20n
.meas tran cqa5 trig v(ck) val='vsup/2' rise=2 targ v(qa5) val='vsup/2' rise=1 td=20n
.meas tran cqa6 trig v(ck) val='vsup/2' rise=2 targ v(qa6) val='vsup/2' rise=1 td=20n
.meas tran cqa7 trig v(ck) val='vsup/2' rise=2 targ v(qa7) val='vsup/2' rise=1 td=20n
.meas tran cqa8 trig v(ck) val='vsup/2' rise=2 targ v(qa8) val='vsup/2' rise=1 td=20n
.meas tran cqa9 trig v(ck) val='vsup/2' rise=2 targ v(qa9) val='vsup/2' rise=1 td=20n
.meas tran cqb0 trig v(ck) val='vsup/2' rise=2 targ v(qb0) val='vsup/2' fall=1 td=20n
.meas tran cqb1 trig v(ck) val='vsup/2' rise=2 targ v(qb1) val='vsup/2' fall=1 td=20n
.meas tran cqb2 trig v(ck) val='vsup/2' rise=2 targ v(qb2) val='vsup/2' fall=1 td=20n
.meas tran cqb3 trig v(ck) val='vsup/2' rise=2 targ v(qb3) val='vsup/2' fall=1 td=20n
.meas tran cqb4 trig v(ck) val='vsup/2' rise=2 targ v(qb4) val='vsup/2' fall=1 td=20n
.meas tran cqb5 trig v(ck) val='vsup/2' rise=2 targ v(qb5) val='vsup/2' fall=1 td=20n
.meas tran cqb6 trig v(ck) val='vsup/2' rise=2 targ v(qb6) val='vsup/2' fall=1 td=20n
.meas tran cqb7 trig v(ck) val='vsup/2' rise=2 targ v(qb7) val='vsup/2' fall=1 td=20n
.meas tran cqb8 trig v(ck) val='vsup/2' rise=2 targ v(qb8) val='vsup/2' fall=1 td=20n
.meas tran cqb9 trig v(ck) val='vsup/2' rise=2 targ v(qb9) val='vsup/2' fall=1 td=20n

* Hold: Q of each bank-C copy, averaged between the measured edge and the
* next one. ~0 means the old value was held (hold satisfied); ~vsup means the
* late data leaked through (hold violated).
.meas tran hqc0 avg v(qc0) from='tedge+2n' to='tedge+9n'
.meas tran hqc1 avg v(qc1) from='tedge+2n' to='tedge+9n'
.meas tran hqc2 avg v(qc2) from='tedge+2n' to='tedge+9n'
.meas tran hqc3 avg v(qc3) from='tedge+2n' to='tedge+9n'
.meas tran hqc4 avg v(qc4) from='tedge+2n' to='tedge+9n'
.meas tran hqc5 avg v(qc5) from='tedge+2n' to='tedge+9n'
.meas tran hqc6 avg v(qc6) from='tedge+2n' to='tedge+9n'
.meas tran hqc7 avg v(qc7) from='tedge+2n' to='tedge+9n'
.meas tran hqc8 avg v(qc8) from='tedge+2n' to='tedge+9n'
.meas tran hqc9 avg v(qc9) from='tedge+2n' to='tedge+9n'
