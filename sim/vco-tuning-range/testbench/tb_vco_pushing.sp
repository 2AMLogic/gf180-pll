* gf180-pll :: vco-tuning-range :: supply pushing, f_osc vs. vdd_vco
*
* DUT: design/vco.sch, exported by design/netlist.sh and frozen per record as
* sim/vco-tuning-range/netlist-snapshots/<record-id>.spice. The runner copies
* that snapshot into the run directory as vco.spice.
*
* Measurement topology
*   Seven independent copies of the whole VCO, one per supply voltage, spanning
*   the ratified 3.3 V +/-10 % rail in 0.11 V steps (2.97 .. 3.63 V). Each copy
*   has its OWN supply source, its OWN supply ammeter and its OWN band-code
*   sources referenced to that copy's rail -- a shared logic-level band code
*   would leave the band-select pass gates of the higher-rail copies partly on
*   and corrupt the very quantity being measured.
*
*   Frequency is measured at the buffered output CLK of each copy, over four
*   whole cycles after `tsettle`, against that copy's own half-supply threshold.
*
*   This deck characterizes STATIC pushing (dc supply -> dc frequency). It says
*   nothing about the jitter a supply *transient* produces; that is
*   tb_vco_supply_jitter.sp, and DR-001 names it the top risk for this topology.
*
* Expects from the generated header (see sim/lib/simenv.sh):
*   .lib <mos corner> / <res corner> / <moscap corner> sections
*   .temp <temp_c>
*   .param b0 b1 b2       band-code bits as 0/1 flags
*   .param vctrl          fine control voltage
*   .param tstop tstep tmax tsettle
*
* Devices are PDK 3.3 V thick-oxide wrappers only (DR-002 Decision 3).

.include "vco.spice"

.param vs1=2.97 vs2=3.08 vs3=3.19 vs4=3.30 vs5=3.41 vs6=3.52 vs7=3.63

vc vctl 0 dc 'vctrl'

* --- copy 1
v1  n1  0 dc 'vs1'
vam1 n1  m1 dc 0
vq1a q1a 0 dc 'b0*vs1'
vq1b q1b 0 dc 'b1*vs1'
vq1c q1c 0 dc 'b2*vs1'
x1 vctl q1a q1b q1c clk1 m1 0 vco
* --- copy 2
v2  n2  0 dc 'vs2'
vam2 n2  m2 dc 0
vq2a q2a 0 dc 'b0*vs2'
vq2b q2b 0 dc 'b1*vs2'
vq2c q2c 0 dc 'b2*vs2'
x2 vctl q2a q2b q2c clk2 m2 0 vco
* --- copy 3
v3  n3  0 dc 'vs3'
vam3 n3  m3 dc 0
vq3a q3a 0 dc 'b0*vs3'
vq3b q3b 0 dc 'b1*vs3'
vq3c q3c 0 dc 'b2*vs3'
x3 vctl q3a q3b q3c clk3 m3 0 vco
* --- copy 4
v4  n4  0 dc 'vs4'
vam4 n4  m4 dc 0
vq4a q4a 0 dc 'b0*vs4'
vq4b q4b 0 dc 'b1*vs4'
vq4c q4c 0 dc 'b2*vs4'
x4 vctl q4a q4b q4c clk4 m4 0 vco
* --- copy 5
v5  n5  0 dc 'vs5'
vam5 n5  m5 dc 0
vq5a q5a 0 dc 'b0*vs5'
vq5b q5b 0 dc 'b1*vs5'
vq5c q5c 0 dc 'b2*vs5'
x5 vctl q5a q5b q5c clk5 m5 0 vco
* --- copy 6
v6  n6  0 dc 'vs6'
vam6 n6  m6 dc 0
vq6a q6a 0 dc 'b0*vs6'
vq6b q6b 0 dc 'b1*vs6'
vq6c q6c 0 dc 'b2*vs6'
x6 vctl q6a q6b q6c clk6 m6 0 vco
* --- copy 7
v7  n7  0 dc 'vs7'
vam7 n7  m7 dc 0
vq7a q7a 0 dc 'b0*vs7'
vq7b q7b 0 dc 'b1*vs7'
vq7c q7c 0 dc 'b2*vs7'
x7 vctl q7a q7b q7c clk7 m7 0 vco

* Break the ring's metastable all-nodes-at-mid DC solution. `uic` is NOT used:
* every bias generator is solved to its operating point before t=0.
.ic v(x1.Y1)=0 v(x1.Y2)='vs1' v(x1.Y3)=0 v(x1.Y4)='vs1' v(x1.Y5)=0
.ic v(x2.Y1)=0 v(x2.Y2)='vs2' v(x2.Y3)=0 v(x2.Y4)='vs2' v(x2.Y5)=0
.ic v(x3.Y1)=0 v(x3.Y2)='vs3' v(x3.Y3)=0 v(x3.Y4)='vs3' v(x3.Y5)=0
.ic v(x4.Y1)=0 v(x4.Y2)='vs4' v(x4.Y3)=0 v(x4.Y4)='vs4' v(x4.Y5)=0
.ic v(x5.Y1)=0 v(x5.Y2)='vs5' v(x5.Y3)=0 v(x5.Y4)='vs5' v(x5.Y5)=0
.ic v(x6.Y1)=0 v(x6.Y2)='vs6' v(x6.Y3)=0 v(x6.Y4)='vs6' v(x6.Y5)=0
.ic v(x7.Y1)=0 v(x7.Y2)='vs7' v(x7.Y3)=0 v(x7.Y4)='vs7' v(x7.Y5)=0

.tran 'tstep' 'tstop' 0 'tmax'

.meas tran tp1 trig v(clk1) val='vs1/2' rise=1 td='tsettle' targ v(clk1) val='vs1/2' rise=5 td='tsettle'
.meas tran tp2 trig v(clk2) val='vs2/2' rise=1 td='tsettle' targ v(clk2) val='vs2/2' rise=5 td='tsettle'
.meas tran tp3 trig v(clk3) val='vs3/2' rise=1 td='tsettle' targ v(clk3) val='vs3/2' rise=5 td='tsettle'
.meas tran tp4 trig v(clk4) val='vs4/2' rise=1 td='tsettle' targ v(clk4) val='vs4/2' rise=5 td='tsettle'
.meas tran tp5 trig v(clk5) val='vs5/2' rise=1 td='tsettle' targ v(clk5) val='vs5/2' rise=5 td='tsettle'
.meas tran tp6 trig v(clk6) val='vs6/2' rise=1 td='tsettle' targ v(clk6) val='vs6/2' rise=5 td='tsettle'
.meas tran tp7 trig v(clk7) val='vs7/2' rise=1 td='tsettle' targ v(clk7) val='vs7/2' rise=5 td='tsettle'

.meas tran f1 param='4/tp1'
.meas tran f2 param='4/tp2'
.meas tran f3 param='4/tp3'
.meas tran f4 param='4/tp4'
.meas tran f5 param='4/tp5'
.meas tran f6 param='4/tp6'
.meas tran f7 param='4/tp7'

.meas tran i1 avg i(vam1) from='tsettle' to='tstop'
.meas tran i2 avg i(vam2) from='tsettle' to='tstop'
.meas tran i3 avg i(vam3) from='tsettle' to='tstop'
.meas tran i4 avg i(vam4) from='tsettle' to='tstop'
.meas tran i5 avg i(vam5) from='tsettle' to='tstop'
.meas tran i6 avg i(vam6) from='tsettle' to='tstop'
.meas tran i7 avg i(vam7) from='tsettle' to='tstop'
