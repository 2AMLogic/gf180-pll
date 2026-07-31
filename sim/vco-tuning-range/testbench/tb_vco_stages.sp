* gf180-pll :: vco-tuning-range :: odd-stage-count confirmation (3 vs 5 vs 7)
*
* DR-001 Decision 2 fixes the delay cell and leaves the stage count open:
* "odd stage count (5 nominal; #8 to confirm against the 200 MHz top of band
* and the power budget)". This deck is that confirmation.
*
* Measurement topology -- three rings in one deck at one PVT point, one band
* code and one control voltage, differing ONLY in stage count:
*
*   X3  3-stage ring     X5  5-stage ring (the nominal)     X7  7-stage ring
*
* Each ring is built from the SAME `vco_stage` cell and driven by its OWN
* `vco_bias` instance, both taken from design/netlist/vco.spice -- the frozen
* export of the same schematics the 5-stage top level uses. So the comparison
* isolates the stage count and nothing else: same cell, same bias generator,
* same band code, same control voltage, same corner, same transient.
*
* Each ring has its own supply ammeter, so the comparison is (f_osc, I_supply)
* per stage count, which is what "against the 200 MHz top of band and the power
* budget" requires. Frequency is measured on a ring node rather than through a
* buffer: the buffer is common to all three counts and would only add a
* constant, and this deck is a relative comparison.
*
* The three rings share the ideal supply and ground nodes and nothing else.
*
* Expects from the generated header (see sim/lib/simenv.sh):
*   .lib <mos corner> / <res corner> / <moscap corner> sections
*   .temp <temp_c>
*   .param vsup vctrl b0 b1 b2
*   .param tstop tstep tmax tsettle
*
* Devices are PDK 3.3 V thick-oxide wrappers only (DR-002 Decision 3).

.include "vco.spice"

vc vctl 0 dc 'vctrl'
vq q0 0 dc 0
vq1 q1 0 dc 'b0*vsup'
vq2 q2 0 dc 'b1*vsup'
vq3 q3 0 dc 'b2*vsup'

vs3 nsup3 0 dc 'vsup'
vs5 nsup5 0 dc 'vsup'
vs7 nsup7 0 dc 'vsup'
vam3 nsup3 n3 dc 0
vam5 nsup5 n5 dc 0
vam7 nsup7 n7 dc 0

* Start-up kick. `.ic` alone is not enough: a noiseless transient solver can sit
* on a ring's metastable all-nodes-at-mid DC solution indefinitely, and the
* 3-stage ring was observed doing exactly that at the fast corner while the 5-
* and 7-stage rings escaped. An identical 50 uA / 200 ps current pulse into the
* first node of each ring removes that failure mode deterministically and
* removes it EQUALLY from all three counts, so it cannot bias the comparison.
* The kick is over ~two orders of magnitude before `tsettle`, which is >= 4
* periods of the slowest ring, so it is absent from every measured cycle.
.param tkick=200p

*------------------------------------------------------------------ 3 stages
ik3 0 c1 pulse(0 50u 0 10p 10p 'tkick' 1)
xb3 vctl q1 q2 q3 p3 m3 n3 0 vco_bias
xa1 c3 c1 n3 0 p3 m3 vco_stage
xa2 c1 c2 n3 0 p3 m3 vco_stage
xa3 c2 c3 n3 0 p3 m3 vco_stage
.ic v(c1)=0 v(c2)='vsup' v(c3)=0

*------------------------------------------------------------------ 5 stages
ik5 0 e1 pulse(0 50u 0 10p 10p 'tkick' 1)
xb5 vctl q1 q2 q3 p5 m5 n5 0 vco_bias
xe1 e5 e1 n5 0 p5 m5 vco_stage
xe2 e1 e2 n5 0 p5 m5 vco_stage
xe3 e2 e3 n5 0 p5 m5 vco_stage
xe4 e3 e4 n5 0 p5 m5 vco_stage
xe5 e4 e5 n5 0 p5 m5 vco_stage
.ic v(e1)=0 v(e2)='vsup' v(e3)=0 v(e4)='vsup' v(e5)=0

*------------------------------------------------------------------ 7 stages
ik7 0 g1 pulse(0 50u 0 10p 10p 'tkick' 1)
xb7 vctl q1 q2 q3 p7 m7 n7 0 vco_bias
xg1 g7 g1 n7 0 p7 m7 vco_stage
xg2 g1 g2 n7 0 p7 m7 vco_stage
xg3 g2 g3 n7 0 p7 m7 vco_stage
xg4 g3 g4 n7 0 p7 m7 vco_stage
xg5 g4 g5 n7 0 p7 m7 vco_stage
xg6 g5 g6 n7 0 p7 m7 vco_stage
xg7 g6 g7 n7 0 p7 m7 vco_stage
.ic v(g1)=0 v(g2)='vsup' v(g3)=0 v(g4)='vsup' v(g5)=0 v(g6)='vsup' v(g7)=0

.tran 'tstep' 'tstop' 0 'tmax'

.meas tran t3a when v(c1)='vsup/2' rise=1 td='tsettle'
.meas tran t3b when v(c1)='vsup/2' rise=5 td='tsettle'
.meas tran f3 param='4/(t3b-t3a)'
.meas tran i3 avg i(vam3) from='tsettle' to='tstop'
.meas tran s3hi max v(c1) from='tsettle' to='tstop'
.meas tran s3lo min v(c1) from='tsettle' to='tstop'

.meas tran t5a when v(e1)='vsup/2' rise=1 td='tsettle'
.meas tran t5b when v(e1)='vsup/2' rise=5 td='tsettle'
.meas tran f5 param='4/(t5b-t5a)'
.meas tran i5 avg i(vam5) from='tsettle' to='tstop'
.meas tran s5hi max v(e1) from='tsettle' to='tstop'
.meas tran s5lo min v(e1) from='tsettle' to='tstop'

.meas tran t7a when v(g1)='vsup/2' rise=1 td='tsettle'
.meas tran t7b when v(g1)='vsup/2' rise=5 td='tsettle'
.meas tran f7 param='4/(t7b-t7a)'
.meas tran i7 avg i(vam7) from='tsettle' to='tstop'
.meas tran s7hi max v(g1) from='tsettle' to='tstop'
.meas tran s7lo min v(g1) from='tsettle' to='tstop'
