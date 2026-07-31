* gf180-pll :: devchar-delay :: 3.3 V CMOS delay-stage characterization
*
* Measurement topology (recorded per repo evidence convention):
*   CS  three 5-stage CURRENT-STARVED rings -- the delay cell ratified by
*       DR-001 Decision 2 (single-ended CMOS inverter ring, matched PMOS-head
*       and NMOS-tail starving devices, odd stage count, 5 nominal). Each ring
*       is starved at a different fixed mirrored current (i_lo / i_md / i_hi)
*       so #8 gets both the per-corner frequency AND the f_osc-vs-I_ctrl slope
*       that sets Kvco. The starving current is mirrored from an ideal
*       reference, so this isolates the delay cell from bias-generator PVT.
*   R1  5-stage self-loaded ring of UNSTARVED minimum-length CMOS inverters,
*       "1x" sizing (Wn = w_n1, Wp = w_p1). This is the ceiling a starved ring
*       approaches as the starving devices are driven fully on -- the absolute
*       maximum frequency the cell can reach at each corner. Stage delay is
*       td = T/(2*N).
*   R4  identical unstarved 5-stage ring at "4x" sizing, to show how much of
*       the ring delay is self-loading (size-invariant) vs fixed parasitics.
*   CH  open inverter chain driven by an ideal step, stage 3 of 4 measured, so
*       the measured stage sees a realistic input slew and a fan-out-1 load.
*       Gives tpHL / tpLH separately (rise/fall asymmetry) and the 10-90 %
*       output transition times.
*   DC  single "1x" NMOS and PMOS biased at Vgs = Vds = vsup: on-current
*       (drive) and the derived effective switched charge, so #8 can rebuild
*       delay for a different fan-out or stage count.
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

* --- current-starved stage (DR-001 Decision 2) -------------------------------
* Starving devices are drawn longer than the switching devices so the head/tail
* mirrors hold their current against the drain-voltage swing at the internal
* nodes. Widths are matched for equal PMOS-head and NMOS-tail current.
.param l_st=0.5u
.param w_nt=2u
.param w_ph=5u
* Three starving currents per stage, spaced 5x apart. The low point puts the
* 5-stage ring inside the 10-200 MHz target output band even at the slow
* corner; the upper points expose where f_osc stops tracking I_ctrl linearly,
* which is where Kvco flattens and coarse band select has to take over.
.param i_lo=10u
.param i_md=50u
.param i_hi=250u

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

*---------------------------------------------------- current-starved inverter
* PMOS head (vbp) and NMOS tail (vbn) devices bracket a 1x inverter; both
* mirror the same starving current, so charge and discharge are symmetric.
.subckt invcs a y vdd vss vbp vbn
xmph nh vbp vdd vdd pfet_03v3 w=w_ph l=l_st nf=1
+ as='w_ph*sab' ad='w_ph*sab' ps='2*sab+w_ph' pd='2*sab+w_ph'
xmp  y  a   nh  vdd pfet_03v3 w=w_p1 l=l_min nf=1
+ as='w_p1*sab' ad='w_p1*sab' ps='2*sab+w_p1' pd='2*sab+w_p1'
xmn  y  a   nt  vss nfet_03v3 w=w_n1 l=l_min nf=1
+ as='w_n1*sab' ad='w_n1*sab' ps='2*sab+w_n1' pd='2*sab+w_n1'
xmnt nt vbn vss vss nfet_03v3 w=w_nt l=l_st nf=1
+ as='w_nt*sab' ad='w_nt*sab' ps='2*sab+w_nt' pd='2*sab+w_nt'
.ends invcs

*------------------------------------------------------------------ supplies
vdd  vdd  0 dc 'vsup'
vdd4 vdd4 0 dc 'vsup'
vddc vddc 0 dc 'vsup'
vddd vddd 0 dc 'vsup'
vddl vddl 0 dc 'vsup'
vddm vddm 0 dc 'vsup'
vddh vddh 0 dc 'vsup'

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

*=================================== CS: current-starved rings (DR-001 cell) ===
* Bias generator for one starving current: an ideal reference into an NMOS
* diode sets vbn, and a PMOS mirror leg reflects the same current to set vbp.
* The starving current is therefore exact by construction, isolating the delay
* cell from bias-generator PVT (the real bias network is #8's problem).
.subckt csbias vdd vss vbp vbn iref_val=50u
iref vdd vbn dc iref_val
xnd vbn vbn vss vss nfet_03v3 w=w_nt l=l_st nf=1
+ as='w_nt*sab' ad='w_nt*sab' ps='2*sab+w_nt' pd='2*sab+w_nt'
xnm nd vbn vss vss nfet_03v3 w=w_nt l=l_st nf=1
+ as='w_nt*sab' ad='w_nt*sab' ps='2*sab+w_nt' pd='2*sab+w_nt'
xpd nd vbp vdd vdd pfet_03v3 w=w_ph l=l_st nf=1
+ as='w_ph*sab' ad='w_ph*sab' ps='2*sab+w_ph' pd='2*sab+w_ph'
* Diode-connect the PMOS leg through a 0 V source so its branch current is
* observable and the gate/drain short is explicit.
vpd nd vbp 0
.ends csbias

* --- low starving current
xbl vddl 0 lbp lbn csbias iref_val=i_lo
xl1 l1 l2 vddl 0 lbp lbn invcs
xl2 l2 l3 vddl 0 lbp lbn invcs
xl3 l3 l4 vddl 0 lbp lbn invcs
xl4 l4 l5 vddl 0 lbp lbn invcs
xl5 l5 l1 vddl 0 lbp lbn invcs
.ic v(l1)=0 v(l2)='vsup' v(l3)=0 v(l4)='vsup' v(l5)=0

* --- mid starving current
xbm vddm 0 mbp mbn csbias iref_val=i_md
xm1 m1 m2 vddm 0 mbp mbn invcs
xm2 m2 m3 vddm 0 mbp mbn invcs
xm3 m3 m4 vddm 0 mbp mbn invcs
xm4 m4 m5 vddm 0 mbp mbn invcs
xm5 m5 m1 vddm 0 mbp mbn invcs
.ic v(m1)=0 v(m2)='vsup' v(m3)=0 v(m4)='vsup' v(m5)=0

* --- high starving current
xbh vddh 0 hbp hbn csbias iref_val=i_hi
xh1 h1 h2 vddh 0 hbp hbn invcs
xh2 h2 h3 vddh 0 hbp hbn invcs
xh3 h3 h4 vddh 0 hbp hbn invcs
xh4 h4 h5 vddh 0 hbp hbn invcs
xh5 h5 h1 vddh 0 hbp hbn invcs
.ic v(h1)=0 v(h2)='vsup' v(h3)=0 v(h4)='vsup' v(h5)=0

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
* 150 ns covers 6 periods of the slowest starved ring at the slowest corner
* (worst observed: 57 ns); the unstarved rings and the fan-out-1 chain finish
* inside the first 25 ns. 5 ps max step keeps the 2.3 GHz unstarved ring's
* half-supply crossings interpolated to well under 1 ps.
.tran 5p 150n uic

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

* --- current-starved rings: 4 periods between the 2nd and 6th rising crossing
.meas tran cs_lo_t0 when v(l1)='vsup/2' rise=2
.meas tran cs_lo_t1 when v(l1)='vsup/2' rise=6
.meas tran cs_lo_fosc   param='4/(cs_lo_t1-cs_lo_t0)'
.meas tran cs_lo_tstage param='(cs_lo_t1-cs_lo_t0)/(4*2*5)'
.meas tran cs_lo_iavg avg i(vddl) from=120n to=150n

.meas tran cs_md_t0 when v(m1)='vsup/2' rise=2
.meas tran cs_md_t1 when v(m1)='vsup/2' rise=6
.meas tran cs_md_fosc   param='4/(cs_md_t1-cs_md_t0)'
.meas tran cs_md_tstage param='(cs_md_t1-cs_md_t0)/(4*2*5)'
.meas tran cs_md_iavg avg i(vddm) from=120n to=150n

.meas tran cs_hi_t0 when v(h1)='vsup/2' rise=2
.meas tran cs_hi_t1 when v(h1)='vsup/2' rise=6
.meas tran cs_hi_fosc   param='4/(cs_hi_t1-cs_hi_t0)'
.meas tran cs_hi_tstage param='(cs_hi_t1-cs_hi_t0)/(4*2*5)'
.meas tran cs_hi_iavg avg i(vddh) from=120n to=150n
