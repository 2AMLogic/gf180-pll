* gf180-pll :: lock-window-trim :: the trimmed delaywin_3v3's code ladder (#411)
*
* ONE question, asked of the lock detector's trimmed window and nothing else:
* with design/delaywin_3v3.sch's per-stage switched MOS-cap segment array in
* place (DR-014's fixed, test-set trim code), where does the comparator window
* t_win land for each of the sixteen trim codes at every point of the full
* 13-bundle PVT grid -- and is there, per process bundle, a code whose
* within-bundle voltage/temperature envelope sits inside the [1, 2] ns band
* with the whole trimmed population's spread at or under DR-013 Decision 4's
* 1.65x target?
*
* Why this is a different question from sim/lock-window-sizing's.  That
* campaign swept a GEOMETRY axis on the untrimmed chain and answered "is there
* one sizing that holds every corner at once" -- no, because the window's
* ~1.93x PVT spread is wider than the band's own 2.0x and leaves no margin.
* This campaign sweeps a CODE axis on a cell that can be set per part, so the
* reduction is per PROCESS BUNDLE: a part is one bundle, gets one code at test,
* and then only has to survive its own voltage and temperature range.  That is
* the whole mechanism DR-014 picked, and the per-bundle table below is what
* makes it a measurement instead of an argument.
*
* Which edge IS the window (unchanged from sim/lock-window-sizing, restated so
* this deck can be read alone).  ERR rises at t0 and falls at t0 + tau (tau =
* the phase error).  ERRD rises at t0 + twin_r and falls at t0 + tau + twin_f.
* WIDE = ERR . ERRD is therefore high over [t0 + twin_r, t0 + tau] and is
* non-empty exactly when tau > twin_r.  The discrimination threshold is
* twin_r; twin_f only sets how wide the resulting WIDE pulse is once the
* threshold has already been crossed.  twin_f is measured and reported anyway
* so the asymmetry is visible rather than assumed away.
*
* TWO copies share every transient, the same control/replica pairing
* sim/lock-window-sizing used:
*
*   XCTL  the COMMITTED delaywin_3v3 subcircuit, verbatim from
*         design/netlist/lock_detector.spice.  This is the campaign's SUBJECT:
*         every number the per-bundle code table is built from comes from this
*         copy, i.e. from the cell as drawn.
*
*   XVAR  a PARAMETERISED structural replica of the same cell -- four inv_3v3
*         stages, each loaded by one always-present base MOS cap (W = kwbase)
*         plus four switched segments (W = kw0/kw1/kw2/kw3) whose back plates
*         are driven by local inv_3v3 buffers off the same trim bits.  Same leaf
*         cells, same topology, same device flavour, L = 2u as drawn; the ONLY
*         difference is that the five widths are parameters.  At the drawn
*         widths the two are the same circuit, and the derived repl_err_pct
*         column proves that point-by-point instead of assuming it.  The
*         replica exists so the segment widths can be re-explored later without
*         editing the schematic first -- the sizing question DR-014 left to
*         this issue (bit count, step size) was answered by sweeping
*         kwbase/kw0..kw3 here before the widths were committed to
*         design/delaywin_3v3.sch.  A 3-bit, 1 um-LSB first cut measured a
*         6-8 % step, i.e. a +/-3 to 4 % quantization error that leaves DR-013
*         Decision 4's 1.65x target no usable margin; the fourth bit and the
*         0.5 um LSB are that measurement's answer.
*
* The stimulus is an IDEAL step (a 100 ps-edge voltage source), not a PFD
* pulse pair, for the same reason sim/lock-window-sizing and sim/lock-detector's
* own XW probe use one: the quantity under test is a propagation delay, and
* driving it from a real XOR output would fold that gate's own corner-dependent
* edge rate into the number.  The full in-situ loop measurement -- the window
* AT THE FLAG, which is what DR-013 Decision 1 requires T1'/T2' to be judged on
* -- is sim/lock-detector's, not this deck's.
*
* The trim bits are STATIC for the whole transient, which is the point: the
* code is set once at test and held for the life of the part (DR-014
* Decision 2).  Nothing here models writing a code at run time, because
* nothing on chip can.
*
* Expects from the harness-generated header:
*   .lib <process corner section>, .temp <temp_c>
*   .param vdd_val=<supply volts>  vdd_nom=<nominal volts>
*   .param kt0..kt3=<0 or 1>       the trim code, one parameter per bit
*   .param kwbase/kw0..kw3=<replica widths>
*   .param ktstep=<max timestep>   ktstop=<stop>
*
* design/netlist/lock_detector.spice is composed ahead of this fragment by
* the harness (tb.json "dut"), which is where delaywin_3v3, inv_3v3 and the
* rest of the leaf cells come from.

.param ttr='100p'
.param ttd='2n'
.param twide='ktstop/2'

vdd vdd 0 dc 'vdd_val'

* ---- the trim code, as four static rails ----------------------------------
* kt<j> is 0 or 1; the rail is that bit times the supply, so a code point is
* the same code at every supply corner rather than a fixed absolute voltage.
vt0 t0 0 dc 'kt0*vdd_val'
vt1 t1 0 dc 'kt1*vdd_val'
vt2 t2 0 dc 'kt2*vdd_val'
vt3 t3 0 dc 'kt3*vdd_val'

* ---- the shared ideal step ------------------------------------------------
* One rising edge at ttd and one falling edge at ttd + twide, so a single
* transient yields both twin_r and twin_f.
vstep step 0 pulse(0 'vdd_val' 'ttd' 'ttr' 'ttr' 'twide' '1000*ktstop')

* ---- XCTL: the committed trimmed cell, as drawn ---------------------------
xctl step octl t0 t1 t2 t3 vdd 0 delaywin_3v3

* ---- XVAR: structural replica with parameterised segment widths -----------
* Stage k: one base cap, four switched segments, one local back-plate driver
* per segment.  nb<j>_<k> is segment j of stage k's back plate.

xv1 step v1 vdd 0 inv_3v3
xmb1 0 v1 0 0 nfet_03v3 L=2u W='kwbase' nf=1
+ ad='int((nf+1)/2) * W/nf * 0.18u' as='int((nf+2)/2) * W/nf * 0.18u'
+ pd='2*int((nf+1)/2) * (W/nf + 0.18u)'
xnb01 t0 nb0_1 vdd 0 inv_3v3
xmt01 nb0_1 v1 nb0_1 0 nfet_03v3 L=2u W='kw0' nf=1
+ ad='int((nf+1)/2) * W/nf * 0.18u' as='int((nf+2)/2) * W/nf * 0.18u'
+ pd='2*int((nf+1)/2) * (W/nf + 0.18u)'
xnb11 t1 nb1_1 vdd 0 inv_3v3
xmt11 nb1_1 v1 nb1_1 0 nfet_03v3 L=2u W='kw1' nf=1
+ ad='int((nf+1)/2) * W/nf * 0.18u' as='int((nf+2)/2) * W/nf * 0.18u'
+ pd='2*int((nf+1)/2) * (W/nf + 0.18u)'
xnb21 t2 nb2_1 vdd 0 inv_3v3
xmt21 nb2_1 v1 nb2_1 0 nfet_03v3 L=2u W='kw2' nf=1
+ ad='int((nf+1)/2) * W/nf * 0.18u' as='int((nf+2)/2) * W/nf * 0.18u'
+ pd='2*int((nf+1)/2) * (W/nf + 0.18u)'
xnb31 t3 nb3_1 vdd 0 inv_3v3
xmt31 nb3_1 v1 nb3_1 0 nfet_03v3 L=2u W='kw3' nf=1
+ ad='int((nf+1)/2) * W/nf * 0.18u' as='int((nf+2)/2) * W/nf * 0.18u'
+ pd='2*int((nf+1)/2) * (W/nf + 0.18u)'

xv2 v1 v2 vdd 0 inv_3v3
xmb2 0 v2 0 0 nfet_03v3 L=2u W='kwbase' nf=1
+ ad='int((nf+1)/2) * W/nf * 0.18u' as='int((nf+2)/2) * W/nf * 0.18u'
+ pd='2*int((nf+1)/2) * (W/nf + 0.18u)'
xnb02 t0 nb0_2 vdd 0 inv_3v3
xmt02 nb0_2 v2 nb0_2 0 nfet_03v3 L=2u W='kw0' nf=1
+ ad='int((nf+1)/2) * W/nf * 0.18u' as='int((nf+2)/2) * W/nf * 0.18u'
+ pd='2*int((nf+1)/2) * (W/nf + 0.18u)'
xnb12 t1 nb1_2 vdd 0 inv_3v3
xmt12 nb1_2 v2 nb1_2 0 nfet_03v3 L=2u W='kw1' nf=1
+ ad='int((nf+1)/2) * W/nf * 0.18u' as='int((nf+2)/2) * W/nf * 0.18u'
+ pd='2*int((nf+1)/2) * (W/nf + 0.18u)'
xnb22 t2 nb2_2 vdd 0 inv_3v3
xmt22 nb2_2 v2 nb2_2 0 nfet_03v3 L=2u W='kw2' nf=1
+ ad='int((nf+1)/2) * W/nf * 0.18u' as='int((nf+2)/2) * W/nf * 0.18u'
+ pd='2*int((nf+1)/2) * (W/nf + 0.18u)'
xnb32 t3 nb3_2 vdd 0 inv_3v3
xmt32 nb3_2 v2 nb3_2 0 nfet_03v3 L=2u W='kw3' nf=1
+ ad='int((nf+1)/2) * W/nf * 0.18u' as='int((nf+2)/2) * W/nf * 0.18u'
+ pd='2*int((nf+1)/2) * (W/nf + 0.18u)'

xv3 v2 v3 vdd 0 inv_3v3
xmb3 0 v3 0 0 nfet_03v3 L=2u W='kwbase' nf=1
+ ad='int((nf+1)/2) * W/nf * 0.18u' as='int((nf+2)/2) * W/nf * 0.18u'
+ pd='2*int((nf+1)/2) * (W/nf + 0.18u)'
xnb03 t0 nb0_3 vdd 0 inv_3v3
xmt03 nb0_3 v3 nb0_3 0 nfet_03v3 L=2u W='kw0' nf=1
+ ad='int((nf+1)/2) * W/nf * 0.18u' as='int((nf+2)/2) * W/nf * 0.18u'
+ pd='2*int((nf+1)/2) * (W/nf + 0.18u)'
xnb13 t1 nb1_3 vdd 0 inv_3v3
xmt13 nb1_3 v3 nb1_3 0 nfet_03v3 L=2u W='kw1' nf=1
+ ad='int((nf+1)/2) * W/nf * 0.18u' as='int((nf+2)/2) * W/nf * 0.18u'
+ pd='2*int((nf+1)/2) * (W/nf + 0.18u)'
xnb23 t2 nb2_3 vdd 0 inv_3v3
xmt23 nb2_3 v3 nb2_3 0 nfet_03v3 L=2u W='kw2' nf=1
+ ad='int((nf+1)/2) * W/nf * 0.18u' as='int((nf+2)/2) * W/nf * 0.18u'
+ pd='2*int((nf+1)/2) * (W/nf + 0.18u)'
xnb33 t3 nb3_3 vdd 0 inv_3v3
xmt33 nb3_3 v3 nb3_3 0 nfet_03v3 L=2u W='kw3' nf=1
+ ad='int((nf+1)/2) * W/nf * 0.18u' as='int((nf+2)/2) * W/nf * 0.18u'
+ pd='2*int((nf+1)/2) * (W/nf + 0.18u)'

xv4 v3 ovar vdd 0 inv_3v3
xmb4 0 ovar 0 0 nfet_03v3 L=2u W='kwbase' nf=1
+ ad='int((nf+1)/2) * W/nf * 0.18u' as='int((nf+2)/2) * W/nf * 0.18u'
+ pd='2*int((nf+1)/2) * (W/nf + 0.18u)'
xnb04 t0 nb0_4 vdd 0 inv_3v3
xmt04 nb0_4 ovar nb0_4 0 nfet_03v3 L=2u W='kw0' nf=1
+ ad='int((nf+1)/2) * W/nf * 0.18u' as='int((nf+2)/2) * W/nf * 0.18u'
+ pd='2*int((nf+1)/2) * (W/nf + 0.18u)'
xnb14 t1 nb1_4 vdd 0 inv_3v3
xmt14 nb1_4 ovar nb1_4 0 nfet_03v3 L=2u W='kw1' nf=1
+ ad='int((nf+1)/2) * W/nf * 0.18u' as='int((nf+2)/2) * W/nf * 0.18u'
+ pd='2*int((nf+1)/2) * (W/nf + 0.18u)'
xnb24 t2 nb2_4 vdd 0 inv_3v3
xmt24 nb2_4 ovar nb2_4 0 nfet_03v3 L=2u W='kw2' nf=1
+ ad='int((nf+1)/2) * W/nf * 0.18u' as='int((nf+2)/2) * W/nf * 0.18u'
+ pd='2*int((nf+1)/2) * (W/nf + 0.18u)'
xnb34 t3 nb3_4 vdd 0 inv_3v3
xmt34 nb3_4 ovar nb3_4 0 nfet_03v3 L=2u W='kw3' nf=1
+ ad='int((nf+1)/2) * W/nf * 0.18u' as='int((nf+2)/2) * W/nf * 0.18u'
+ pd='2*int((nf+1)/2) * (W/nf + 0.18u)'
