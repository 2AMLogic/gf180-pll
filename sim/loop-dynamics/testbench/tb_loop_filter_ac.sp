* gf180-pll :: loop-dynamics :: small-signal impedance of the passive loop filter
*
* The DUT is the real `design/loop_filter.sch` export (4 x ppolyf_u in series,
* 4 x cap_nmos_03v3_b, 1 x cap_mim_2f0_m2m3_noshield) -- no ideal R/C anywhere.
* What this deck measures is Z(jw) looking into the filter's VCTRL node, at six
* control-node bias points spanning (and one point below) the DR-003 Vctrl
* window.
*
* Why an impedance sweep is the whole measurement:
*   the open-loop gain of the type-II charge-pump loop is
*       T(s) = (Icp/2pi) * Z(s) * (2pi*Kvco/s) / N = Icp*Kvco*Z(s)/(N*s)
*   so Icp, Kvco and N enter ONLY as the scalar A = Icp*Kvco/N.  For a linear
*   time-invariant filter that scalar moves the crossover along the measured
*   |Z|/w curve and changes nothing else:
*       |T(wc)| = 1        <=>  |Z(wc)|/wc = 1/A
*       PM      = 180 + arg T(wc) = 90 + arg Z(wc)
*   Measuring Z once per (passive corner, temperature, Vctrl) point therefore
*   covers the ENTIRE Kvco x N x Icp-trim x f_ref cross-product exactly, rather
*   than approximately -- see analyze.py, which does that algebra against #8's
*   and #9's measured Kvco/Icp tables, and tb_loop_ac.sp, which re-simulates
*   the whole linearized loop at selected points as an independent check.
*
* Measurement topology: six independent copies of the filter, each fed by its
* own 1 A AC current source, each DC-biased through a 1 TH inductor from its own
* DC source.  At the lowest swept frequency (100 Hz) the inductor's 6.3e14 ohm
* reactance is six orders of magnitude above |Z|, so the bias path is invisible
* to the AC result while still giving every node a DC operating point.  With
* 1 A of drive, v(vcN) IS Z(jw) in ohms.
*
* Expects from the generated header (see sim/lib/simenv.sh):
*   .lib res_<corner> .lib moscap_<corner> .lib mimcap_<corner>
*   .temp <temp_c>
* and `dut.spice` staged beside the generated deck by run.sh.

.include "dut.spice"

* Control-node bias points.  0.9-2.7 V is the usable Vctrl window DR-003
* Decision 5 measured on the ring VCO; 0.3 V is BELOW it and is included only
* to characterize the MOS cap's C-V behaviour during cold-start acquisition,
* where the loop drives Vctrl to the rail before it captures.
.param vb1=0.3
.param vb2=0.9
.param vb3=1.35
.param vb4=1.8
.param vb5=2.25
.param vb6=2.7

xf1 vc1 0 loop_filter
i1  0 vc1 dc 0 ac 1
lb1 vc1 nb1 1e12
vb1 nb1 0 dc {vb1}

xf2 vc2 0 loop_filter
i2  0 vc2 dc 0 ac 1
lb2 vc2 nb2 1e12
vb2 nb2 0 dc {vb2}

xf3 vc3 0 loop_filter
i3  0 vc3 dc 0 ac 1
lb3 vc3 nb3 1e12
vb3 nb3 0 dc {vb3}

xf4 vc4 0 loop_filter
i4  0 vc4 dc 0 ac 1
lb4 vc4 nb4 1e12
vb4 nb4 0 dc {vb4}

xf5 vc5 0 loop_filter
i5  0 vc5 dc 0 ac 1
lb5 vc5 nb5 1e12
vb5 nb5 0 dc {vb5}

xf6 vc6 0 loop_filter
i6  0 vc6 dc 0 ac 1
lb6 vc6 nb6 1e12
vb6 nb6 0 dc {vb6}

* The MOS cap model is a pure C with no DC path, so its plate is floating for
* the operating-point solve; rshunt gives the solver a 1 Tohm path to ground.
* At 1 Tohm it is 4 orders of magnitude above |Z| at the lowest swept frequency
* and does not perturb the measurement.
.option rshunt=1e12

.control
  set noaskquit
  ac dec 40 100 1e8
  let m1 = mag(v(vc1))
  let a1 = 180/pi*ph(v(vc1))
  let m2 = mag(v(vc2))
  let a2 = 180/pi*ph(v(vc2))
  let m3 = mag(v(vc3))
  let a3 = 180/pi*ph(v(vc3))
  let m4 = mag(v(vc4))
  let a4 = 180/pi*ph(v(vc4))
  let m5 = mag(v(vc5))
  let a5 = 180/pi*ph(v(vc5))
  let m6 = mag(v(vc6))
  let a6 = 180/pi*ph(v(vc6))
  set wr_singlescale
  wrdata z.dat m1 a1 m2 a2 m3 a3 m4 a4 m5 a5 m6 a6
.endc
