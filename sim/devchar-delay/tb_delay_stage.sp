* gf180-pll :: devchar-delay :: 3.3 V CMOS delay-stage characterization
*
* Measurement topology (recorded per repo evidence convention):
*   R1  5-stage self-loaded ring oscillator, minimum-length CMOS inverters,
*       "1x" sizing (Wn = w_n1, Wp = w_p1). Stage delay is extracted from the
*       oscillation period as td = T/(2*N).  This is the quantity a ring VCO
*       (issue #8) directly consumes: f_osc = 1/(2*N*td).
*   R4  identical 5-stage ring at "4x" sizing, to show how much of the ring
*       delay is self-loading (size-invariant) versus fixed parasitics.
*   CH  open inverter chain driven by an ideal step, stage 3 of 4 measured, so
*       the measured stage sees a realistic input slew and a fan-out-1 load.
*       Gives tpHL / tpLH separately (rise/fall asymmetry) and the 10-90 %
*       output transition times.
*   DC  single "1x" NMOS and PMOS biased at Vgs = Vds = vsup: on-current
*       (drive) and the derived effective switched charge, so #8 can rebuild
*       delay for a different fan-out or a current-starved stage.
*
* Expects from the generated header (see sim/lib/simenv.sh):
*   .lib <process corner section>   one of typical/ff/ss/fs/sf
*   .temp <temp_c>
*   .param vsup=<supply volts>
*
* Devices are the PDK 3.3 V wrapper subcircuits nfet_03v3 / pfet_03v3, which
* carry the statistical delvto/mulu0 hooks (disabled here: design.ngspice sets
* sw_stat_global = sw_stat_mismatch = 0).

.param l_min=0.28u
.param w_n1=1u
.param w_p1=2.5u
.param w_n4=4u
.param w_p4=10u
* Contacted-diffusion extension used for as/ad/ps/pd. 0.44 um is the drawn
* source/drain length of a single-contact-row 3.3 V device in this PDK.
.param sab=0.44u

*------------------------------------------------------------------ 1x inverter
.subckt inv1x a y vdd vss
xmn y a vss vss nfet_03v3 w=w_n1 l=l_min nf=1
+ as='w_n1*sab' ad='w_n1*sab' ps='2*sab+w_n1' pd='2*sab+w_n1'
xmp y a vdd vdd pfet_03v3 w=w_p1 l=l_min nf=1
+ as='w_p1*sab' ad='w_p1*sab' ps='2*sab+w_p1' pd='2*sab+w_p1'
.ends inv1x

*------------------------------------------------------------------ 4x inverter
.subckt inv4x a y vdd vss
xmn y a vss vss nfet_03v3 w=w_n4 l=l_min nf=1
+ as='w_n4*sab' ad='w_n4*sab' ps='2*sab+w_n4' pd='2*sab+w_n4'
xmp y a vdd vdd pfet_03v3 w=w_p4 l=l_min nf=1
+ as='w_p4*sab' ad='w_p4*sab' ps='2*sab+w_p4' pd='2*sab+w_p4'
.ends inv4x

*------------------------------------------------------------------ supplies
vdd  vdd  0 dc 'vsup'
vdd4 vdd4 0 dc 'vsup'
vddc vddc 0 dc 'vsup'
vddd vddd 0 dc 'vsup'

*------------------------------------------------------- R1: 5-stage ring, 1x
xa1 a1 a2 vdd 0 inv1x
xa2 a2 a3 vdd 0 inv1x
xa3 a3 a4 vdd 0 inv1x
xa4 a4 a5 vdd 0 inv1x
xa5 a5 a1 vdd 0 inv1x
.ic v(a1)=0 v(a2)='vsup' v(a3)=0 v(a4)='vsup' v(a5)=0

*------------------------------------------------------- R4: 5-stage ring, 4x
xb1 b1 b2 vdd4 0 inv4x
xb2 b2 b3 vdd4 0 inv4x
xb3 b3 b4 vdd4 0 inv4x
xb4 b4 b5 vdd4 0 inv4x
xb5 b5 b1 vdd4 0 inv4x
.ic v(b1)=0 v(b2)='vsup' v(b3)=0 v(b4)='vsup' v(b5)=0

*--------------------------------------------- CH: fan-out-1 chain, 1x devices
* Ideal step in; stage 3 (c2 -> c3) is the measured stage: driven by an
* identical inverter, loaded by an identical inverter.
vin  in 0 pulse(0 'vsup' 3n 20p 20p 10n 20n)
xc1 in c1 vddc 0 inv1x
xc2 c1 c2 vddc 0 inv1x
xc3 c2 c3 vddc 0 inv1x
xc4 c3 c4 vddc 0 inv1x
* Start the chain at its DC-correct state so edge indices below count only
* real switching events (uic would otherwise start every node at 0 V and add a
* spurious settling edge).
.ic v(c1)='vsup' v(c2)=0 v(c3)='vsup' v(c4)=0

*------------------------------------------------- DC: device drive current
* Vgs = Vds = vsup, i.e. the peak drive an output stage can deliver.
vgn  gn 0 dc 'vsup'
vdn  dn 0 dc 'vsup'
xmdn dn gn 0 0 nfet_03v3 w=w_n1 l=l_min nf=1
+ as='w_n1*sab' ad='w_n1*sab' ps='2*sab+w_n1' pd='2*sab+w_n1'

vgp  gp 0 dc 0
vdp  dp 0 dc 0
xmdp dp gp vddd vddd pfet_03v3 w=w_p1 l=l_min nf=1
+ as='w_p1*sab' ad='w_p1*sab' ps='2*sab+w_p1' pd='2*sab+w_p1'

*------------------------------------------------------------------- analysis
.tran 1p 24n uic

* --- ring 1x: 8 periods between the 2nd and 10th rising half-supply crossing
.meas tran r1_t0 when v(a1)='vsup/2' rise=2
.meas tran r1_t1 when v(a1)='vsup/2' rise=10
.meas tran r1_period param='(r1_t1-r1_t0)/8'
.meas tran r1_fosc   param='8/(r1_t1-r1_t0)'
.meas tran r1_tstage param='(r1_t1-r1_t0)/(8*2*5)'
.meas tran r1_iavg avg i(vdd) from=15n to=23n

* --- ring 4x
.meas tran r4_t0 when v(b1)='vsup/2' rise=2
.meas tran r4_t1 when v(b1)='vsup/2' rise=10
.meas tran r4_period param='(r4_t1-r4_t0)/8'
.meas tran r4_fosc   param='8/(r4_t1-r4_t0)'
.meas tran r4_tstage param='(r4_t1-r4_t0)/(8*2*5)'
.meas tran r4_iavg avg i(vdd4) from=15n to=23n

* --- fan-out-1 chain, measured stage c2 -> c3
* Input rises at 3 ns and falls at 13 ns. TD= windows the edge search so a
* start-up glitch at t=0 (the .ic state is not exactly the DC solution) cannot
* be mistaken for a switching edge.
*   input rise -> c1 falls -> c2 rises -> c3 falls  == tpHL of measured stage
.meas tran ch_tphl trig v(c2) val='vsup/2' td=2n rise=1 targ v(c3) val='vsup/2' td=2n fall=1
*   input fall -> c1 rises -> c2 falls -> c3 rises  == tpLH of measured stage
.meas tran ch_tplh trig v(c2) val='vsup/2' td=12n fall=1 targ v(c3) val='vsup/2' td=12n rise=1
.meas tran ch_tpd  param='(ch_tphl+ch_tplh)/2'
.meas tran ch_tf   trig v(c3) val='0.9*vsup' td=2n fall=1 targ v(c3) val='0.1*vsup' td=2n fall=1
.meas tran ch_tr   trig v(c3) val='0.1*vsup' td=12n rise=1 targ v(c3) val='0.9*vsup' td=12n rise=1

* --- device drive currents (DC operating point held through the transient)
.meas tran dc_idn avg i(vdn) from=20n to=23n
.meas tran dc_idp avg i(vdp) from=20n to=23n
