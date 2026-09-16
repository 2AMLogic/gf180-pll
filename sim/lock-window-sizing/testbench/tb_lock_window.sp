* gf180-pll :: lock-window-sizing :: delaywin_3v3 window-sizing ladder (#387)
*
* SUPERSEDED FOR NEW RUNS by sim/lock-window-trim (#411).  This campaign
* characterised the UNTRIMMED delaywin_3v3 -- a cell that no longer exists:
* #411 replaced its four fixed MOS-cap loads with a base cap plus a switched,
* binary-weighted segment array carrying a fixed test-set trim code (DR-014).
* The committed record this deck minted, records/20260915-202802-79c0cee.md, is
* append-only evidence about the pre-#411 cell and stands unchanged; the deck
* is kept runnable, and only runnable, so that record's provenance is not left
* pointing at a fragment that no longer composes.
*
* TWO CONSEQUENCES of that replacement, both visible below rather than left
* implicit:
*   - XCTL is no longer the same circuit as the XVAR replica at any sizing, so
*     the repl_err_pct identity check this campaign used to carry has been
*     withdrawn from the manifest.  It asserted that a W = 8 um single-load
*     replica reproduces the drawn cell; the drawn cell is now a trimmed array
*     and the claim is simply false, so it is removed rather than relaxed.
*   - XCTL's trim code is driven to 0 (every segment disabled), the narrowest
*     window the trimmed cell can be set to.  That is the nearest thing the new
*     cell has to "the load as drawn" and is NOT equal to the old W = 9.5 um
*     load; ctl_r from a re-run is therefore not comparable to the committed
*     record's ctl_r, and must not be quoted as if it were.
*
* ONE question, asked of the lock detector's window and nothing else: if
* design/delaywin_3v3.sch's four MOS-capacitor loads are scaled, where does
* the comparator window t_win land over the full 45-point PVT grid, and is
* there a sizing that holds t_win inside a stated two-sided band at EVERY
* corner at once?
*
* Why the window and not the integrating node.  spec/pll.md's "Lock detector"
* section names two candidate fixes for its T1/T2 gap -- "widen the delay
* window, or scale the integrating capacitor".  Only the first of those moves
* the threshold: WIDE = ERR . ERRD fires when the error pulse outlasts the
* ERR->ERRD delay, so the phase error at which the detector reacts is that
* delay and nothing else.  XMCW (the integrating cap) sets how many
* out-of-window pulses it takes to pull VWIN down and how long the weak
* pull-up needs to bring it back -- the assert/deassert TIME CONSTANTS, not
* the phase threshold.  This deck therefore characterises the delay chain
* alone; it deliberately does not instantiate lock_detector, because a
* full-detector deck would re-measure what
* sim/lock-detector/records/20260802-050119-c24ee3a.md already measured and
* would confound the sizing axis with the integrator's own dynamics.
*
* TWO copies share every transient:
*
*   XCTL  the COMMITTED delaywin_3v3 subcircuit, verbatim from
*         design/netlist/lock_detector.spice.  In the record this deck minted
*         it was the control: its delay reproduced 20260802-050119-c24ee3a's
*         own twin_r/twin_f at the matching corner, which is what tied that
*         record's baseline to the already-committed characterisation rather
*         than asserting agreement.  Since #411 the committed cell is the
*         TRIMMED one, so that tie no longer holds -- see the supersession
*         note at the top of this file.
*
*   XVAR  a PARAMETERISED structural replica of the same chain -- four
*         inv_3v3 stages, each loaded by one nfet_03v3 wired drain = source =
*         bulk = VSS with gate on the delayed node, L = 2u as drawn, and W =
*         kwc swept.  Same leaf cells, same topology, same device flavour;
*         the ONLY difference from XCTL is that W is a parameter.  At
*         kwc = 8u the two are the same circuit, and the derived
*         repl_err_pct column below proves that point-by-point instead of
*         assuming it.
*
* Which edge IS the window.  ERR rises at t0 and falls at t0 + tau (tau = the
* phase error).  ERRD rises at t0 + twin_r and falls at t0 + tau + twin_f.
* WIDE = ERR . ERRD is therefore high over [t0 + twin_r, t0 + tau] and is
* non-empty exactly when tau > twin_r.  The discrimination threshold is
* twin_r; twin_f only sets how wide the resulting WIDE pulse is once the
* threshold has already been crossed.  twin_f is measured and reported anyway
* so the asymmetry is visible rather than assumed away.
*
* The stimulus is an IDEAL step (a 100 ps-edge voltage source), not a PFD
* pulse pair, for the same reason 20260802-050119-c24ee3a's own XW copy uses
* one: the quantity under test is a propagation delay, and driving it from a
* real XOR output would fold that gate's own corner-dependent edge rate into
* the number.
*
* Expects from the harness-generated header:
*   .lib <process corner section>, .temp <temp_c>
*   .param vdd_val=<supply volts>  vdd_nom=<nominal volts>
*   .param kwc=<swept MOS-cap width>  ktstep=<max timestep>  ktstop=<stop>
*
* design/netlist/lock_detector.spice is composed ahead of this fragment by
* the harness (tb.json "dut"), which is where delaywin_3v3, inv_3v3 and the
* rest of the leaf cells come from.

.param ttr='100p'
.param ttd='2n'
.param twide='ktstop/2'

vdd vdd 0 dc 'vdd_val'

* ---- XCTL's trim code, held at 0 ------------------------------------------
* Every switched segment disabled: the narrowest window the post-#411 cell can
* be set to.  Written out rather than parameterised because this deck does not
* sweep the code axis -- sim/lock-window-trim does.
vctl0 ctlt0 0 dc 0
vctl1 ctlt1 0 dc 0
vctl2 ctlt2 0 dc 0
vctl3 ctlt3 0 dc 0

* ---- the shared ideal step ------------------------------------------------
* One rising edge at ttd and one falling edge at ttd + twide, so a single
* transient yields both twin_r and twin_f.
vstep step 0 pulse(0 'vdd_val' 'ttd' 'ttr' 'ttr' 'twide' '1000*ktstop')

* ---- XCTL: the committed cell, as drawn -----------------------------------
xctl step octl ctlt0 ctlt1 ctlt2 ctlt3 vdd 0 delaywin_3v3

* ---- XVAR: structural replica with W = kwc --------------------------------
xv1 step   v1 vdd 0 inv_3v3
xmv1 0 v1 0 0 nfet_03v3 L=2u W='kwc' nf=1
+ ad='int((nf+1)/2) * W/nf * 0.18u' as='int((nf+2)/2) * W/nf * 0.18u'
+ pd='2*int((nf+1)/2) * (W/nf + 0.18u)'

xv2 v1     v2 vdd 0 inv_3v3
xmv2 0 v2 0 0 nfet_03v3 L=2u W='kwc' nf=1
+ ad='int((nf+1)/2) * W/nf * 0.18u' as='int((nf+2)/2) * W/nf * 0.18u'
+ pd='2*int((nf+1)/2) * (W/nf + 0.18u)'

xv3 v2     v3 vdd 0 inv_3v3
xmv3 0 v3 0 0 nfet_03v3 L=2u W='kwc' nf=1
+ ad='int((nf+1)/2) * W/nf * 0.18u' as='int((nf+2)/2) * W/nf * 0.18u'
+ pd='2*int((nf+1)/2) * (W/nf + 0.18u)'

xv4 v3   ovar vdd 0 inv_3v3
xmv4 0 ovar 0 0 nfet_03v3 L=2u W='kwc' nf=1
+ ad='int((nf+1)/2) * W/nf * 0.18u' as='int((nf+2)/2) * W/nf * 0.18u'
+ pd='2*int((nf+1)/2) * (W/nf + 0.18u)'
