* gf180-pll :: devchar-passives :: loop-filter capacitor comparison
*
* Ten candidate loop-filter capacitor devices, all the same drawn area, all
* driven from one shared ramp node through individual 0 V ammeters:
*
*   MIM, via the mimcap_* corner sections (sm141064_mim.ngspice / cap_mim_new):
*     cap_mim_1f0_m2m3_noshield / _1f5_ / _2f0_
*   MIM, legacy names in the .LIB cap_mim section of sm141064.ngspice:
*     cap_mim_1f0fF / cap_mim_1f5fF / cap_mim_2f0fF
*     -- included to confirm the two naming families are electrically identical;
*        note that NO corner section pulls .LIB cap_mim in, so those names only
*        resolve if the deck asks for that section explicitly (this one does).
*   3.3 V MOS caps, via the moscap_* corner sections:
*     cap_nmos_03v3, cap_pmos_03v3 and the well-tied _b variants
*
* Measurement topology:
*   C-V   a linear voltage ramp 0 -> 3.63 V in 1 us. The ramp current of each
*         branch is i = dq/dt = (dq/dv)(dv/dt), so C(V) = i / (dv/dt) is the
*         true differential (small-signal) capacitance the simulator will use,
*         independent of how the model expresses its charge. Both dv/dt and i
*         are taken from the simulated waveform, so the extraction does not
*         assume the source is exactly linear.
*   leak  after the ramp the node is held at 3.63 V for a further 1 us; with
*         dv/dt = 0 the remaining branch current is pure leakage.
*
* 3.63 V is the top of the 3.3 V +/- 10 % supply range, so one sweep covers the
* control-voltage range at every supply corner. Supply is therefore not an
* independent axis for this deck -- it is the sweep range.
*
* Expects from the generated header (see sim/lib/simenv.sh):
*   .lib mimcap_<corner> .lib moscap_<corner> .lib cap_mim
*   .temp <temp_c>

.param cw=30u
.param cl=30u

*------------------------------------------------------------------ ramp source
* 0 V for 10 ns, linear to 3.63 V at 1.01 us, then held to 2 us.
vramp r 0 pwl(0 0 10n 0 1.01u 3.63 2u 3.63)

*------------------------------------------------- MIM via mimcap_* sections
vam_m10 r n_m10 0
xm10 n_m10 0 cap_mim_1f0_m2m3_noshield c_length=cl c_width=cw
vam_m15 r n_m15 0
xm15 n_m15 0 cap_mim_1f5_m2m3_noshield c_length=cl c_width=cw
vam_m20 r n_m20 0
xm20 n_m20 0 cap_mim_2f0_m2m3_noshield c_length=cl c_width=cw

*------------------------------------------- MIM legacy names (.LIB cap_mim)
vam_l10 r n_l10 0
xl10 n_l10 0 cap_mim_1f0fF c_length=cl c_width=cw
vam_l15 r n_l15 0
xl15 n_l15 0 cap_mim_1f5fF c_length=cl c_width=cw
vam_l20 r n_l20 0
xl20 n_l20 0 cap_mim_2f0fF c_length=cl c_width=cw

*----------------------------------------------------------------- MOS caps
* cap_nmos_* want a positive terminal-1-to-terminal-2 voltage to reach their
* high-capacitance state; cap_pmos_* want a negative one, so those instances
* are wired with terminal 1 grounded and terminal 2 driven.
vam_cn r n_cn 0
xcn n_cn 0 cap_nmos_03v3 c_length=cl c_width=cw
vam_cp r n_cp 0
xcp 0 n_cp cap_pmos_03v3 c_length=cl c_width=cw
vam_cnb r n_cnb 0
xcnb n_cnb 0 cap_nmos_03v3_b c_length=cl c_width=cw
vam_cpb r n_cpb 0
xcpb 0 n_cpb cap_pmos_03v3_b c_length=cl c_width=cw

*------------------------------------------------------------------- analysis
* Leakage in these models runs from femtoamps (cap_mim_2f0, the only one with a
* leakage element) down to identically zero, so the solver has to be tightened
* well past its defaults for the leakage column to mean anything.
.option abstol=1e-18 reltol=1e-7 vntol=1e-9 gmin=1e-15
.control
  set noaskquit
  tran 1n 2u
  wrdata cv.dat v(r) i(vam_m10) i(vam_m15) i(vam_m20) i(vam_l10) i(vam_l15)
+ i(vam_l20) i(vam_cn) i(vam_cp) i(vam_cnb) i(vam_cpb)
.endc
