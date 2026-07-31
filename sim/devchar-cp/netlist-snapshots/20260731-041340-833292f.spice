* gf180-pll :: devchar-cp :: charge-pump current-mirror stack characterization
*
* Six candidate charge-pump output stacks, all biased from the same reference
* current and all swept against the same output-node voltage, so their output
* resistance and compliance boundary are directly comparable at one corner:
*
*   n_simple   NMOS simple (2-transistor) mirror                 -- CP sink
*   n_casc     NMOS cascode mirror, self-biased (M3 diode)       -- CP sink
*   n_ws       NMOS wide-swing (low-voltage) cascode mirror      -- CP sink
*   p_simple   PMOS simple mirror                                -- CP source
*   p_casc     PMOS cascode mirror, self-biased                  -- CP source
*   p_ws       PMOS wide-swing cascode mirror                    -- CP source
*
* Measurement topology: each stack's output drain is tied through its own 0 V
* ammeter to a single swept node `sw`. A DC sweep of `sw` from 0 V to Vdd
* therefore traces the complete output I-V of every stack in one analysis,
* through the saturation knee and into triode -- not just the flat region.
* Output resistance ro = dVout/dIout and the compliance boundary are extracted
* from those curves by run.sh.
*
* Expects from the generated header (see sim/lib/simenv.sh):
*   .lib <process corner section>   one of typical/ff/ss/fs/sf
*   .temp <temp_c>
*   .param vsup=<supply volts>
*
* Mirror sizing is deliberately a long-channel analog geometry (L = 1 um), not
* the minimum-length digital geometry used in devchar-delay: charge-pump
* mirrors trade area for output resistance and matching.

* Reference current and mirror geometry. Widths are chosen so that both
* polarities sit in moderate inversion (Vdsat ~ 0.2 V) at Iref, which is the
* regime a charge pump actually uses: deep weak inversion would flatter the
* compliance numbers, deep strong inversion would waste headroom.
.param iref=20u
.param wm=5u
.param wmp=15u
.param lm=1u
* Wide-swing cascode gate bias comes from a diode at 1/4 the aspect ratio,
* which puts the cascode gate at roughly Vth + 2*Vov.
.param wb='wm/4'
.param wbp='wmp/4'
.param sab=0.44u

.csparam vsup_c={vsup}

*------------------------------------------------------------------ supplies
vdd vdd 0 dc 'vsup'
* Swept output node, shared by every stack.
vsw sw 0 dc 0

*=========================================================== NMOS simple mirror
iref_ns vdd g_ns dc 'iref'
xns_d g_ns g_ns 0 0 nfet_03v3 w=wm l=lm
+ as='wm*sab' ad='wm*sab' ps='2*sab+wm' pd='2*sab+wm'
vam_ns sw d_ns 0
xns_o d_ns g_ns 0 0 nfet_03v3 w=wm l=lm
+ as='wm*sab' ad='wm*sab' ps='2*sab+wm' pd='2*sab+wm'

*========================================================== NMOS cascode mirror
* Reference: M1 (bottom diode) + M3 (cascode diode) stacked; both gate nodes
* feed the output branch.
iref_nc vdd a_nc dc 'iref'
xnc_c1 a_nc a_nc b_nc 0 nfet_03v3 w=wm l=lm
+ as='wm*sab' ad='wm*sab' ps='2*sab+wm' pd='2*sab+wm'
xnc_b1 b_nc b_nc 0 0 nfet_03v3 w=wm l=lm
+ as='wm*sab' ad='wm*sab' ps='2*sab+wm' pd='2*sab+wm'
vam_nc sw d_nc 0
xnc_c2 d_nc a_nc c_nc 0 nfet_03v3 w=wm l=lm
+ as='wm*sab' ad='wm*sab' ps='2*sab+wm' pd='2*sab+wm'
xnc_b2 c_nc b_nc 0 0 nfet_03v3 w=wm l=lm
+ as='wm*sab' ad='wm*sab' ps='2*sab+wm' pd='2*sab+wm'

*====================================================== NMOS wide-swing cascode
* Cascode gate bias branch: 1/4-aspect diode carrying the same reference current.
ibias_nw vdd vb_nw dc 'iref'
xnw_b vb_nw vb_nw 0 0 nfet_03v3 w=wb l=lm
+ as='wb*sab' ad='wb*sab' ps='2*sab+wb' pd='2*sab+wb'
* Reference branch: cascode gate = vb_nw, bottom gate = top of the stack.
iref_nw vdd a_nw dc 'iref'
xnw_c1 a_nw vb_nw b_nw 0 nfet_03v3 w=wm l=lm
+ as='wm*sab' ad='wm*sab' ps='2*sab+wm' pd='2*sab+wm'
xnw_b1 b_nw a_nw 0 0 nfet_03v3 w=wm l=lm
+ as='wm*sab' ad='wm*sab' ps='2*sab+wm' pd='2*sab+wm'
vam_nw sw d_nw 0
xnw_c2 d_nw vb_nw c_nw 0 nfet_03v3 w=wm l=lm
+ as='wm*sab' ad='wm*sab' ps='2*sab+wm' pd='2*sab+wm'
xnw_b2 c_nw a_nw 0 0 nfet_03v3 w=wm l=lm
+ as='wm*sab' ad='wm*sab' ps='2*sab+wm' pd='2*sab+wm'

*=========================================================== PMOS simple mirror
iref_ps g_ps 0 dc 'iref'
xps_d g_ps g_ps vdd vdd pfet_03v3 w=wmp l=lm
+ as='wmp*sab' ad='wmp*sab' ps='2*sab+wmp' pd='2*sab+wmp'
vam_ps d_ps sw 0
xps_o d_ps g_ps vdd vdd pfet_03v3 w=wmp l=lm
+ as='wmp*sab' ad='wmp*sab' ps='2*sab+wmp' pd='2*sab+wmp'

*========================================================== PMOS cascode mirror
iref_pc a_pc 0 dc 'iref'
xpc_c1 a_pc a_pc b_pc vdd pfet_03v3 w=wmp l=lm
+ as='wmp*sab' ad='wmp*sab' ps='2*sab+wmp' pd='2*sab+wmp'
xpc_b1 b_pc b_pc vdd vdd pfet_03v3 w=wmp l=lm
+ as='wmp*sab' ad='wmp*sab' ps='2*sab+wmp' pd='2*sab+wmp'
vam_pc d_pc sw 0
xpc_c2 d_pc a_pc c_pc vdd pfet_03v3 w=wmp l=lm
+ as='wmp*sab' ad='wmp*sab' ps='2*sab+wmp' pd='2*sab+wmp'
xpc_b2 c_pc b_pc vdd vdd pfet_03v3 w=wmp l=lm
+ as='wmp*sab' ad='wmp*sab' ps='2*sab+wmp' pd='2*sab+wmp'

*====================================================== PMOS wide-swing cascode
ibias_pw vb_pw 0 dc 'iref'
xpw_b vb_pw vb_pw vdd vdd pfet_03v3 w=wbp l=lm
+ as='wbp*sab' ad='wbp*sab' ps='2*sab+wbp' pd='2*sab+wbp'
iref_pw a_pw 0 dc 'iref'
xpw_c1 a_pw vb_pw b_pw vdd pfet_03v3 w=wmp l=lm
+ as='wmp*sab' ad='wmp*sab' ps='2*sab+wmp' pd='2*sab+wmp'
xpw_b1 b_pw a_pw vdd vdd pfet_03v3 w=wmp l=lm
+ as='wmp*sab' ad='wmp*sab' ps='2*sab+wmp' pd='2*sab+wmp'
vam_pw d_pw sw 0
xpw_c2 d_pw vb_pw c_pw vdd pfet_03v3 w=wmp l=lm
+ as='wmp*sab' ad='wmp*sab' ps='2*sab+wmp' pd='2*sab+wmp'
xpw_b2 c_pw a_pw vdd vdd pfet_03v3 w=wmp l=lm
+ as='wmp*sab' ad='wmp*sab' ps='2*sab+wmp' pd='2*sab+wmp'

*------------------------------------------------------------------- analysis
* Output resistance is extracted from current *differences* of order 10 pA over
* a 10 mV step, so the default abstol=1e-12 would dominate the result. Tighten
* the solver before trusting any ro number above ~10 MOhm.
.option abstol=1e-16 reltol=1e-7 vntol=1e-9 gmin=1e-15
.control
  set noaskquit
  * Bias-point record for the two reference devices: the compliance numbers
  * below are only interpretable next to the inversion level they were taken
  * at, so vth/vdsat/gm/gds go into the results table too.
  op
  echo "OPN vth $&@m.xns_d.m0[vth] vdsat $&@m.xns_d.m0[vdsat] gm $&@m.xns_d.m0[gm] gds $&@m.xns_d.m0[gds] vgs $&@m.xns_d.m0[vgs]"
  echo "OPP vth $&@m.xps_d.m0[vth] vdsat $&@m.xps_d.m0[vdsat] gm $&@m.xps_d.m0[gm] gds $&@m.xps_d.m0[gds] vgs $&@m.xps_d.m0[vgs]"
  * 10 mV steps: fine enough to resolve the saturation knee, which sits within
  * a couple of hundred mV of the rail for the wide-swing stacks.
  dc vsw 0 $&vsup_c 0.010
  * Each ammeter is oriented so its branch current is positive for the current
  * the stack actually delivers (N stacks sink from `sw`, P stacks source into
  * it), giving six directly comparable positive columns.
  let i_n_simple = i(vam_ns)
  let i_n_casc   = i(vam_nc)
  let i_n_ws     = i(vam_nw)
  let i_p_simple = i(vam_ps)
  let i_p_casc   = i(vam_pc)
  let i_p_ws     = i(vam_pw)
  wrdata iv.dat i_n_simple i_n_casc i_n_ws i_p_simple i_p_casc i_p_ws
.endc
