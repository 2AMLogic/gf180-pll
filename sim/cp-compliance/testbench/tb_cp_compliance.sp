* gf180-pll :: cp-compliance :: charge pump compliance, mismatch, trim
*
* DUT: the charge pump implemented in design/cp.sch (transcribed here at the
* transistor level in hand-written SPICE -- see design/cp.sch's own header
* note and this record's Environment provenance for why xschem could not be
* invoked to verify the schematic in this environment).
*
* Topology: wide-swing NMOS cascode sink (DN) and wide-swing PMOS cascode
* source (UP), chosen from sim/devchar-cp's six-stack characterization
* (n_ws/p_ws: markedly higher output resistance than a simple mirror at a
* headroom cost the target ~0.9-2.4 V Vctrl window can afford, unlike the
* full cascode stacks which need more headroom than that window has -- see
* this record's Methodology for the actual headroom arithmetic). Reuses
* devchar-cp's exact unit device geometry (W=5u(N)/15u(P), L=1u, cascode
* bias diode at W/4) so this record's compliance numbers are directly
* comparable to that characterization. 2-bit Icp trim: a base leg (always
* on) plus two binary-weighted legs (1x, 2x) gated by a static enable mux on
* each leg's bottom-mirror gate -- Icp = iunit*(1 + b0 + 2*b1), the only
* loop-side programmability DR-001 permits (no filter R/C trim banks).
* Current-steering UP/DN switches route each polarity's tail current to
* VOUT when active or to a dump rail (VDD for the DN leg, VSS for the UP
* leg) when idle, keeping both mirror branches always biased (no
* turn-on/turn-off transient on the mirror itself, only on the steering
* switch) -- standard current-steering CP practice.
*
* Expects from the generated header (see sim/lib/simenv.sh):
*   .lib <process corner section>   one of typical/ff/ss/fs/sf
*   .temp <temp_c>
*   .param vsup=<supply volts>

.param wn=5u
.param wp=15u
.param lm=1u
.param wbn='wn/4'
.param wbp='wp/4'
.param sab=0.44u

* -------------------------- static digital cells --------------------------
.subckt inv_u a y vdd vss
xp y a vdd vdd pfet_03v3 w=1u l=0.3u
+ as='1u*0.44u' ad='1u*0.44u' ps='2*0.44u+1u' pd='2*0.44u+1u'
xn y a vss vss nfet_03v3 w=0.5u l=0.3u
+ as='0.5u*0.44u' ad='0.5u*0.44u' ps='2*0.44u+0.5u' pd='2*0.44u+0.5u'
.ends inv_u

* ------------------------------ trimmed legs -------------------------------
* wgt = mirror weight (current multiple of the ibias reference leg).
* NOTE: parameter is named "wgt", not "m" -- ngspice reserves "m" as the
* built-in subcircuit-instance multiplier and silently overrides a
* same-named .subckt parameter (hit and fixed during this design's
* prototyping: two mismatched-Icp runs before the rename).
.subckt dn_leg_n vbn vcascn tail vdd vss b bb wgt=1
xg_en  bgate b  vbn vss nfet_03v3 w=1u l=0.3u
+ as='1u*0.44u' ad='1u*0.44u' ps='2*0.44u+1u' pd='2*0.44u+1u'
xg_dis bgate bb vss vss nfet_03v3 w=1u l=0.3u
+ as='1u*0.44u' ad='1u*0.44u' ps='2*0.44u+1u' pd='2*0.44u+1u'
xbot bot bgate vss vss nfet_03v3 w='wn*wgt' l=lm
+ as='wn*wgt*sab' ad='wn*wgt*sab' ps='2*sab+wn*wgt' pd='2*sab+wn*wgt'
xcasc tail vcascn bot vss nfet_03v3 w='wn*wgt' l=lm
+ as='wn*wgt*sab' ad='wn*wgt*sab' ps='2*sab+wn*wgt' pd='2*sab+wn*wgt'
.ends dn_leg_n

.subckt up_leg_p vbp vcascp tail vdd vss b bb wgt=1
xg_enp  bgate bb vbp vdd pfet_03v3 w=1u l=0.3u
+ as='1u*0.44u' ad='1u*0.44u' ps='2*0.44u+1u' pd='2*0.44u+1u'
xg_disp bgate b  vdd vdd pfet_03v3 w=1u l=0.3u
+ as='1u*0.44u' ad='1u*0.44u' ps='2*0.44u+1u' pd='2*0.44u+1u'
xtop top bgate vdd vdd pfet_03v3 w='wp*wgt' l=lm
+ as='wp*wgt*sab' ad='wp*wgt*sab' ps='2*sab+wp*wgt' pd='2*sab+wp*wgt'
xcasc tail vcascp top vdd pfet_03v3 w='wp*wgt' l=lm
+ as='wp*wgt*sab' ad='wp*wgt*sab' ps='2*sab+wp*wgt' pd='2*sab+wp*wgt'
.ends up_leg_p

* --------------------------------- full CP ---------------------------------
* b0,b1: 2-bit trim code (static). up,dn: PFD steering control (dynamic).
* Icp = iunit * (1 + b0 + 2*b1)  (base leg always on, +1x for b0, +2x for b1)
* ibias_n/ibias_p: idealized off-block bias reference (subcircuit
* parameters, amps) -- matches devchar-cp's own convention of biasing
* mirrors from an ideal DC current source rather than modeling the
* bandgap/reference-generation block (out of this issue's scope).
.subckt cp_core vout up dn b0 b1 vdd vss params: ibias_n=1u ibias_p=1u
xb0b b0 b0b vdd vss inv_u
xb1b b1 b1b vdd vss inv_u
xupb up upb vdd vss inv_u
xdnb dn dnb vdd vss inv_u

* Bias diodes: bottom mirror + wide-swing cascode bias, each side.
* Current-source node convention (verified against
* sim/devchar-cp/testbench/tb_cp_mirror.sp): Iname n+ n- injects current
* into the circuit at n- and sinks it from n+. NMOS diodes need current
* injected into their drain/gate node (n- = bias node); PMOS diodes source
* current into their drain/gate node, which the ideal source must sink
* (n+ = bias node).
xbias_bn  vbn  vbn  vss vss nfet_03v3 w=wn l=lm
+ as='wn*sab' ad='wn*sab' ps='2*sab+wn' pd='2*sab+wn'
iibias_n vdd vbn dc 'ibias_n'
xbias_cn vcascn vcascn vss vss nfet_03v3 w=wbn l=lm
+ as='wbn*sab' ad='wbn*sab' ps='2*sab+wbn' pd='2*sab+wbn'
iibias_cn vdd vcascn dc 'ibias_n'

xbias_bp  vbp  vbp  vdd vdd pfet_03v3 w=wp l=lm
+ as='wp*sab' ad='wp*sab' ps='2*sab+wp' pd='2*sab+wp'
iibias_p vbp 0 dc 'ibias_p'
xbias_cp vcascp vcascp vdd vdd pfet_03v3 w=wbp l=lm
+ as='wbp*sab' ad='wbp*sab' ps='2*sab+wbp' pd='2*sab+wbp'
iibias_cp vcascp 0 dc 'ibias_p'

* DN (NMOS sink) legs: base always-on (wgt=1), trim0 (wgt=1, gated b0), trim1 (wgt=2, gated b1)
xdn_base vbn vcascn dn_tail vdd vss vdd vss dn_leg_n wgt=1
xdn_t0   vbn vcascn dn_tail vdd vss b0  b0b dn_leg_n wgt=1
xdn_t1   vbn vcascn dn_tail vdd vss b1  b1b dn_leg_n wgt=2

* UP (PMOS source) legs: base always-on (wgt=1), trim0 (wgt=1, gated b0), trim1 (wgt=2, gated b1)
xup_base vbp vcascp up_tail vdd vss vdd vss up_leg_p wgt=1
xup_t0   vbp vcascp up_tail vdd vss b0  b0b up_leg_p wgt=1
xup_t1   vbp vcascp up_tail vdd vss b1  b1b up_leg_p wgt=2

* Current-steering switches: DN tail -> vout when dn=1, else dumped to vdd.
* UP tail -> vout when up=1, else dumped to vss.
xsw_dn_out  vout dn  dn_tail vss nfet_03v3 w=3u l=0.3u
+ as='3u*0.44u' ad='3u*0.44u' ps='2*0.44u+3u' pd='2*0.44u+3u'
xsw_dn_dump vdd  dnb dn_tail vss nfet_03v3 w=3u l=0.3u
+ as='3u*0.44u' ad='3u*0.44u' ps='2*0.44u+3u' pd='2*0.44u+3u'
xsw_up_out  vout upb up_tail vdd pfet_03v3 w=3u l=0.3u
+ as='3u*0.44u' ad='3u*0.44u' ps='2*0.44u+3u' pd='2*0.44u+3u'
xsw_up_dump vss  up  up_tail vdd pfet_03v3 w=3u l=0.3u
+ as='3u*0.44u' ad='3u*0.44u' ps='2*0.44u+3u' pd='2*0.44u+3u'
.ends cp_core

* ------------------------------- top level ---------------------------------
* Two instances share one swept node `sw`, one hardwired UP-only and one
* hardwired DN-only, each through its OWN 0 V ammeter to `sw` (same
* technique as sim/devchar-cp/testbench/tb_cp_mirror.sp), so both
* polarities' output I-V curves are captured from a single DC sweep and are
* directly comparable point-for-point for the current-mismatch extraction
* below. Ammeter polarity follows tb_cp_mirror.sp's own convention (N-type
* sink: `sw d_n`; P-type source: `d_p sw`) so i(vam_dn)/i(vam_up) both read
* positive for the current each branch actually delivers.
*
* b0/b1 (icp_code, from the generated header) are shared between both
* instances so both polarities always run at the SAME trim code -- DR-001's
* 2-bit trim is a single shared code, not independent per-polarity trims, so
* UP/DN mismatch at a given code is a real, code-independent design number,
* not an artifact of comparing different codes.
vdd vdd 0 dc 'vsup'
vss vss 0 dc 0
vsw sw 0 dc 0
vb0 b0 0 dc '3.3*b0_code'
vb1 b1 0 dc '3.3*b1_code'
.param b0_code=0
.param b1_code=1

* Static digital drives for each instance's non-active steering input.
vhi ctl_hi 0 dc 'vsup'
vlo ctl_lo 0 dc 0

* UP branch: up=ctl_hi(1, active), dn=ctl_lo(0, idle, dumped to vss).
xcp_up d_up ctl_hi ctl_lo b0 b1 vdd vss cp_core ibias_n=1u ibias_p=1u
vam_up d_up sw 0

* DN branch: up=ctl_lo(0, idle, dumped to vss), dn=ctl_hi(1, active).
xcp_dn d_dn ctl_lo ctl_hi b0 b1 vdd vss cp_core ibias_n=1u ibias_p=1u
vam_dn sw d_dn 0

* ------------------------- switch-timing sub-circuit ------------------------
* A second, independent instance pair dedicated to the UP/DN switch-timing
* mismatch measurement -- kept separate from the compliance sweep pair above
* (rather than `alter`-ing ctl_hi from a DC source into a pulse mid-.control,
* which was unreliable during this design's prototyping) so the DC
* compliance sweep and the transient timing measurement cannot interact.
* Output node held at a fixed 1.65 V (mid of the ~0.9-2.4 V Vctrl window) by
* an ideal source, isolating the CP's own switch dynamics from loop-filter
* capacitor charging (a separate, unrelated effect out of this record's
* scope). ctl_pulse drives BOTH instances' ACTIVE control input from the
* SAME edge, so any measured delay difference between i(vam_up_t) and
* i(vam_dn_t) is purely the CP's own UP/DN switch asymmetry, not stimulus
* skew.
vout_t out_t 0 dc 1.65
vctl_pulse ctl_pulse 0 pulse(0 'vsup' 10n 100p 100p 20n 60n)
vctl_idle  ctl_idle  0 dc 0

xcp_up_t d_up_t ctl_pulse ctl_idle b0 b1 vdd vss cp_core ibias_n=1u ibias_p=1u
vam_up_t d_up_t out_t 0
xcp_dn_t d_dn_t ctl_idle ctl_pulse b0 b1 vdd vss cp_core ibias_n=1u ibias_p=1u
vam_dn_t out_t d_dn_t 0

.control
  * NOTE: ngspice's control-mode "dc" command does not evaluate a quoted or
  * $&-prefixed .param reference for its sweep bounds (confirmed: both
  * `dc vsw 0 'vsup' 0.010` and `dc vsw 0 $&vsup 0.010` fail with
  * "Bad syntax!" / "no such variable" during this testbench's prototyping,
  * even though the identical 'vsup' substitution works fine in a device
  * instance line or a .tran/.meas argument). Sweeping to a fixed 3.63 V
  * (the top of the repo's supply corner grid) rather than the per-corner
  * 'vsup' is therefore a workaround, not a preference: it is a strict
  * superset of every corner's own 0-vsup range, so no compliance data is
  * lost; run.sh's extraction uses each corner's actual vsup for the
  * mid-rail/headroom arithmetic and simply has a few extra, unused sweep
  * points beyond vsup at the two lower-supply corners.
  op
  dc vsw 0 3.63 0.010
  let i_up = i(vam_up)
  let i_dn = i(vam_dn)
  wrdata iv_cp.dat i_up i_dn
.endc
.end
