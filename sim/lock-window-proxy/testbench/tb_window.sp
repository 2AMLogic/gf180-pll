* gf180-pll :: lock-window-proxy :: phase 'win' -- all sixteen trim codes at once
*
* This phase measures exactly what sim/lock-window-trim measures -- t_win, the
* ERR -> ERRD propagation delay of the committed delaywin_3v3 -- but it puts
* all sixteen codes in ONE deck rather than sweeping the code as a harness
* axis.  The reason is the campaign's whole question: the proxy phase's VCO
* frequency and this phase's window have to be a PAIR taken at the same PVT
* point of the same run, or the mapping between them is an inference across
* campaigns rather than a measurement.  Sixteen copies driven from one ideal
* source is how that pairing is made without running the code axis 16x.
*
* The sixteen copies see an IDENTICAL stimulus: `vstep` is a voltage source,
* so its output impedance is zero and the sixteen input capacitances do not
* load each other.  The measured delay is therefore the same quantity
* sim/lock-window-trim's single-copy deck measures, and the two are compared
* point-for-point in the record (the 'twin_crosscheck' table) rather than
* assumed equal.
*
* Which edge IS the window: ERR rises at t0 and falls at t0 + tau, ERRD at
* t0 + twin_r and t0 + tau + twin_f, so WIDE = ERR . ERRD is non-empty exactly
* when tau > twin_r.  twin_r is the discrimination threshold and is what this
* deck measures, per code.
*
* Expects from the harness-generated header:
*   .lib <process corner section>, .temp <temp_c>
*   .param vdd_val=<supply volts>  vdd_nom=<nominal volts>
*   .param ktstepw=<max timestep>  ktstopw=<stop>
*
* design/netlist/pll_top.spice is composed ahead of this fragment by the
* harness (tb.json "dut").  The DUT is the ASSEMBLED part's own export, not a
* block export, because the question this campaign asks is a question about a
* packaged part: both the delay cell and the VCO the tester reads have to come
* from the same netlist a tester would be holding.

.param ttr='100p'
.param ttd='2n'
.param twide='ktstopw/2'

vdd vdd 0 dc 'vdd_val'
vone vone 0 dc 'vdd_val'

* ---- the ideal step -------------------------------------------------------
vstep step 0 pulse(0 'vdd_val' 'ttd' 'ttr' 'ttr' 'twide' '1000*ktstopw')

* ---- the committed trimmed cell, one copy per code ------------------------
* delaywin_3v3 pin order: A Y T0 T1 T2 T3 VDD VSS.  A deselected segment is
* clamped to VSS by its own kill device, so tying T<n> to node 0 is the same
* configuration the code sweep drives with a 0 V source.
xd0  step w0  0    0    0    0    vdd 0 delaywin_3v3
xd1  step w1  vone 0    0    0    vdd 0 delaywin_3v3
xd2  step w2  0    vone 0    0    vdd 0 delaywin_3v3
xd3  step w3  vone vone 0    0    vdd 0 delaywin_3v3
xd4  step w4  0    0    vone 0    vdd 0 delaywin_3v3
xd5  step w5  vone 0    vone 0    vdd 0 delaywin_3v3
xd6  step w6  0    vone vone 0    vdd 0 delaywin_3v3
xd7  step w7  vone vone vone 0    vdd 0 delaywin_3v3
xd8  step w8  0    0    0    vone vdd 0 delaywin_3v3
xd9  step w9  vone 0    0    vone vdd 0 delaywin_3v3
xd10 step w10 0    vone 0    vone vdd 0 delaywin_3v3
xd11 step w11 vone vone 0    vone vdd 0 delaywin_3v3
xd12 step w12 0    0    vone vone vdd 0 delaywin_3v3
xd13 step w13 vone 0    vone vone vdd 0 delaywin_3v3
xd14 step w14 0    vone vone vone vdd 0 delaywin_3v3
xd15 step w15 vone vone vone vone vdd 0 delaywin_3v3

* Sixteen copies of a four-stage chain is ~1300 devices; retaining every node
* at this deck's timestep costs hundreds of MB of output buffer for no gain,
* and ngspice sizes that buffer against the memory it believes is free when
* the transient starts (sim/lock-detector's tb.json records a run that died
* that way).  .save changes what is RETAINED, not what is solved.
.save v(step) v(w0) v(w1) v(w2) v(w3) v(w4) v(w5) v(w6) v(w7)
+ v(w8) v(w9) v(w10) v(w11) v(w12) v(w13) v(w14) v(w15)
