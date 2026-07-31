* gf180-pll :: vco-tuning-range :: open-loop f(Vctrl) / Kvco characterization
*
* DUT: design/vco.sch (5-stage current-starved ring VCO, DR-001 Decision 2),
* exported to SPICE by design/netlist.sh and frozen per record as
* sim/vco-tuning-range/netlist-snapshots/<record-id>.spice. The runner copies
* that snapshot into the run directory as vco.spice, so this deck always
* simulates the frozen netlist rather than whatever design/ happens to contain.
*
* Measurement topology
*   Seven independent copies of the whole VCO (bias generator + ring + output
*   buffer + on-chip decoupling) are instantiated in one deck, one per control
*   voltage, all at the same PVT point and the same band code. Each copy has its
*   own supply ammeter, so f(Vctrl) and I(Vctrl) at seven control points come out
*   of a single transient. The copies share only the ideal supply node and
*   ground; they are otherwise disjoint, so there is no interaction between them.
*
*   Frequency is measured at the *buffered output* CLK, not at an internal ring
*   node: CLK is what the divider (#11) and the closed-loop bench (#12) see, and
*   measuring there also proves the output buffer resolves the ring's slow edges
*   into a rail-to-rail clock at the bottom of the band.
*
*   Period is taken over four whole cycles between the first and fifth rising
*   half-supply crossing after `tsettle`, so the bias generator's own start-up
*   transient is excluded from the number.
*
* Expects from the generated header (see sim/lib/simenv.sh):
*   .lib <mos corner> / <res corner> / <moscap corner> sections
*   .temp <temp_c>
*   .param vsup      supply volts
*   .param b0v b1v b2v   band-code bit voltages (0 or vsup)
*   .param tstop tstep tmax tsettle   transient window, scaled per band/corner
*
* Devices are the PDK 3.3 V thick-oxide wrappers only (nfet_03v3 / pfet_03v3,
* ppolyf_u_3k, cap_nmos_03v3), per DR-002 Decision 3.

.include "vco.spice"

* --- control voltages: 0.9 .. 2.7 V in 0.3 V steps (the usable Vctrl window)
.param vc1=0.9 vc2=1.2 vc3=1.5 vc4=1.8 vc5=2.1 vc6=2.4 vc7=2.7

vdd  vdd 0 dc 'vsup'
vb0  nb0 0 dc 'b0v'
vb1  nb1 0 dc 'b1v'
vb2  nb2 0 dc 'b2v'

vv1 vc1 0 dc 'vc1'
vv2 vc2 0 dc 'vc2'
vv3 vc3 0 dc 'vc3'
vv4 vc4 0 dc 'vc4'
vv5 vc5 0 dc 'vc5'
vv6 vc6 0 dc 'vc6'
vv7 vc7 0 dc 'vc7'

vs1 vdd nv1 dc 0
vs2 vdd nv2 dc 0
vs3 vdd nv3 dc 0
vs4 vdd nv4 dc 0
vs5 vdd nv5 dc 0
vs6 vdd nv6 dc 0
vs7 vdd nv7 dc 0

x1 vc1 nb0 nb1 nb2 clk1 nv1 0 vco
x2 vc2 nb0 nb1 nb2 clk2 nv2 0 vco
x3 vc3 nb0 nb1 nb2 clk3 nv3 0 vco
x4 vc4 nb0 nb1 nb2 clk4 nv4 0 vco
x5 vc5 nb0 nb1 nb2 clk5 nv5 0 vco
x6 vc6 nb0 nb1 nb2 clk6 nv6 0 vco
x7 vc7 nb0 nb1 nb2 clk7 nv7 0 vco

* Break the ring's DC symmetry so the operating point is not the metastable
* all-nodes-at-mid solution; the constraint is released when the transient
* starts. `uic` is deliberately NOT used: the bias generator must be solved to
* its operating point before t=0 or the first microsecond of every run is a
* bias start-up transient rather than the oscillation being measured.
.ic v(x1.Y1)=0 v(x1.Y2)='vsup' v(x1.Y3)=0 v(x1.Y4)='vsup' v(x1.Y5)=0
.ic v(x2.Y1)=0 v(x2.Y2)='vsup' v(x2.Y3)=0 v(x2.Y4)='vsup' v(x2.Y5)=0
.ic v(x3.Y1)=0 v(x3.Y2)='vsup' v(x3.Y3)=0 v(x3.Y4)='vsup' v(x3.Y5)=0
.ic v(x4.Y1)=0 v(x4.Y2)='vsup' v(x4.Y3)=0 v(x4.Y4)='vsup' v(x4.Y5)=0
.ic v(x5.Y1)=0 v(x5.Y2)='vsup' v(x5.Y3)=0 v(x5.Y4)='vsup' v(x5.Y5)=0
.ic v(x6.Y1)=0 v(x6.Y2)='vsup' v(x6.Y3)=0 v(x6.Y4)='vsup' v(x6.Y5)=0
.ic v(x7.Y1)=0 v(x7.Y2)='vsup' v(x7.Y3)=0 v(x7.Y4)='vsup' v(x7.Y5)=0

.tran 'tstep' 'tstop' 0 'tmax'

.meas tran tp1 trig v(clk1) val='vsup/2' rise=1 td='tsettle' targ v(clk1) val='vsup/2' rise=5 td='tsettle'
.meas tran tp2 trig v(clk2) val='vsup/2' rise=1 td='tsettle' targ v(clk2) val='vsup/2' rise=5 td='tsettle'
.meas tran tp3 trig v(clk3) val='vsup/2' rise=1 td='tsettle' targ v(clk3) val='vsup/2' rise=5 td='tsettle'
.meas tran tp4 trig v(clk4) val='vsup/2' rise=1 td='tsettle' targ v(clk4) val='vsup/2' rise=5 td='tsettle'
.meas tran tp5 trig v(clk5) val='vsup/2' rise=1 td='tsettle' targ v(clk5) val='vsup/2' rise=5 td='tsettle'
.meas tran tp6 trig v(clk6) val='vsup/2' rise=1 td='tsettle' targ v(clk6) val='vsup/2' rise=5 td='tsettle'
.meas tran tp7 trig v(clk7) val='vsup/2' rise=1 td='tsettle' targ v(clk7) val='vsup/2' rise=5 td='tsettle'

.meas tran f1 param='4/tp1'
.meas tran f2 param='4/tp2'
.meas tran f3 param='4/tp3'
.meas tran f4 param='4/tp4'
.meas tran f5 param='4/tp5'
.meas tran f6 param='4/tp6'
.meas tran f7 param='4/tp7'

.meas tran i1 avg i(vs1) from='tsettle' to='tstop'
.meas tran i2 avg i(vs2) from='tsettle' to='tstop'
.meas tran i3 avg i(vs3) from='tsettle' to='tstop'
.meas tran i4 avg i(vs4) from='tsettle' to='tstop'
.meas tran i5 avg i(vs5) from='tsettle' to='tstop'
.meas tran i6 avg i(vs6) from='tsettle' to='tstop'
.meas tran i7 avg i(vs7) from='tsettle' to='tstop'

* Output swing at the slowest and fastest control points: proves the buffered
* output is rail-to-rail at both ends of the band (a starved ring's internal
* edges are slow, so this is not automatic).
.meas tran sw1hi max v(clk1) from='tsettle' to='tstop'
.meas tran sw1lo min v(clk1) from='tsettle' to='tstop'
.meas tran sw7hi max v(clk7) from='tsettle' to='tstop'
.meas tran sw7lo min v(clk7) from='tsettle' to='tstop'
