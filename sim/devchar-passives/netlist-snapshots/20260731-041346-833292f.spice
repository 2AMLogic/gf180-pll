* gf180-pll :: devchar-passives :: loop-filter resistor comparison
*
* Poly resistor candidates for the loop filter series resistor, each drawn at
* two lengths so that sheet resistance can be separated from the fixed head
* resistance of the contacts:
*
*   ppolyf_u      unsalicided p+ poly, the analog baseline (~350 ohm/sq)
*   ppolyf_u_1k   high-sheet p+ poly (~1 kohm/sq)
*   ppolyf_u_2k   high-sheet p+ poly (~2 kohm/sq)
*   ppolyf_u_3k   high-sheet p+ poly (~3 kohm/sq)
*   npolyf_u      unsalicided n+ poly (~310 ohm/sq), for polarity comparison
*   ppolyf_s      salicided p+ poly (~7 ohm/sq), included to show why a
*                 salicided resistor is not a loop-filter candidate
*
* Measurement topology: every device sits between a shared swept node and
* ground, with its own 0 V ammeter; the substrate terminal is grounded. A DC
* sweep of 0 -> 1.0 V gives R(V) = V/I, so the voltage coefficient is measured
* rather than assumed. Two lengths (10 um and 50 um at W = 1 um) let run.sh
* extract the effective sheet resistance from the slope
*   rsh_eff = (R(50um) - R(10um)) / ((50 - 10) squares)
* which cancels the contact head resistance, and back out that head resistance
* as the intercept. ppolyf_u is additionally drawn at W = 2 um to expose the
* effective-width narrowing that makes rsh_eff differ from the model rsh.
*
* Expects from the generated header (see sim/lib/simenv.sh):
*   .lib res_<corner>   one of res_typical / res_ff / res_ss
*   .temp <temp_c>

.param wr=1u
.param wr2=2u
.param lshort=10u
.param llong=50u

vr r 0 dc 0

*--------------------------------------------------------------- ppolyf_u, W=1u
vam_pu_s r n_pu_s 0
xpu_s n_pu_s 0 0 ppolyf_u r_width=wr r_length=lshort
vam_pu_l r n_pu_l 0
xpu_l n_pu_l 0 0 ppolyf_u r_width=wr r_length=llong

*--------------------------------------------------------------- ppolyf_u, W=2u
vam_pu2_s r n_pu2_s 0
xpu2_s n_pu2_s 0 0 ppolyf_u r_width=wr2 r_length=lshort
vam_pu2_l r n_pu2_l 0
xpu2_l n_pu2_l 0 0 ppolyf_u r_width=wr2 r_length=llong

*------------------------------------------------------------------ ppolyf_u_1k
vam_p1k_s r n_p1k_s 0
xp1k_s n_p1k_s 0 0 ppolyf_u_1k r_width=wr r_length=lshort
vam_p1k_l r n_p1k_l 0
xp1k_l n_p1k_l 0 0 ppolyf_u_1k r_width=wr r_length=llong

*------------------------------------------------------------------ ppolyf_u_2k
vam_p2k_s r n_p2k_s 0
xp2k_s n_p2k_s 0 0 ppolyf_u_2k r_width=wr r_length=lshort
vam_p2k_l r n_p2k_l 0
xp2k_l n_p2k_l 0 0 ppolyf_u_2k r_width=wr r_length=llong

*------------------------------------------------------------------ ppolyf_u_3k
vam_p3k_s r n_p3k_s 0
xp3k_s n_p3k_s 0 0 ppolyf_u_3k r_width=wr r_length=lshort
vam_p3k_l r n_p3k_l 0
xp3k_l n_p3k_l 0 0 ppolyf_u_3k r_width=wr r_length=llong

*--------------------------------------------------------------------- npolyf_u
vam_nu_s r n_nu_s 0
xnu_s n_nu_s 0 0 npolyf_u r_width=wr r_length=lshort
vam_nu_l r n_nu_l 0
xnu_l n_nu_l 0 0 npolyf_u r_width=wr r_length=llong

*--------------------------------------------------------------------- ppolyf_s
vam_ps_s r n_ps_s 0
xps_s n_ps_s 0 0 ppolyf_s r_width=wr r_length=lshort
vam_ps_l r n_ps_l 0
xps_l n_ps_l 0 0 ppolyf_s r_width=wr r_length=llong

*------------------------------------------------------------------- analysis
.option abstol=1e-15 reltol=1e-7
.control
  set noaskquit
  dc vr 0 1.0 0.025
  wrdata rdc.dat i(vam_pu_s) i(vam_pu_l) i(vam_pu2_s) i(vam_pu2_l)
+ i(vam_p1k_s) i(vam_p1k_l) i(vam_p2k_s) i(vam_p2k_l)
+ i(vam_p3k_s) i(vam_p3k_l) i(vam_nu_s) i(vam_nu_l)
+ i(vam_ps_s) i(vam_ps_l)
.endc
