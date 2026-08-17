* gf180-pll :: vco-tuning-range :: single-copy Monte Carlo mismatch bench for
* the VCO band-select mirror (#146)
*
* ONE copy of the committed design/netlist/vco.spice export (not the
* seven-copy f(Vctrl)/Kvco topology tb_vco_tuning.sp/.spice use) at a FIXED
* band code and a FIXED Vctrl, with sw_stat_mismatch=1. This deck's only job
* is the frequency DISPERSION random device mismatch (Vth/beta agauss()
* draws in every nfet_03v3/pfet_03v3 instance -- see
* sim/mc-cp-mismatch/records/20260731-212614-640560e.md's confirmed
* model-capability finding, unchanged and reused here) adds on top of the
* systematic f(Vctrl)/band-plan curve testbench/tb.json's harness-driven
* sweep already measures at 45 corners x 8 bands x 7 Vctrl points x 3 supply
* (that record's sw_stat_mismatch=0 throughout, unchanged by this file).
*
* Why a raw simenv.sh deck and not a sim/harness manifest addition: see
* run_mismatch.sh's header comment for the harness-ordering finding that
* makes a tb.json `params` override of sw_stat_mismatch silently ineffective,
* and the harness's lack of a seed/Monte-Carlo sweep axis.
*
* Devices are the PDK 3.3 V thick-oxide wrappers only (nfet_03v3 / pfet_03v3,
* ppolyf_u_3k, cap_nmos_03v3), per DR-002 Decision 3 -- identical DUT to
* tb_vco_tuning.sp/.spice, just one instance instead of seven.
*
* Expects from the generated header (see sim/lib/simenv.sh):
*   .lib <mos corner> section
*   .temp <temp_c>
*   .param vsup vctrl b0v b1v b2v tsettle tstop tstep tmax
*   .option rndseed=N  (sw_stat_mismatch's per-instance draws are parsed
*     once at netlist parse time -- set via the special-cased `rndseed=` kv
*     key simenv_run_deck already treats specially; unchanged behavior)
* Set directly in THIS file (not passed as a `.param` override kv, and not
* via tb.json's `params` key -- see run_mismatch.sh's header comment for
* why): `sw_stat_mismatch=1`, `sw_stat_global=0` -- mismatch only, matching
* every other Monte Carlo campaign in this repo (sim/README.md's worked
* distribution example). This line lands AFTER simenv_run_deck's
* `.include design.ngspice` (which sets the opposite default) because
* `.include "<this file>"` is emitted after that include -- ngspice resolves
* `.param` redefinitions by LAST occurrence in the deck, confirmed by direct
* experiment during #146 (see run_mismatch.sh).
.param sw_stat_global=0
.param sw_stat_mismatch=1

.include "vco.spice"

vdd  vdd 0 dc 'vsup'
vc   vc  0 dc 'vctrl'
vb0  nb0 0 dc 'b0v'
vb1  nb1 0 dc 'b1v'
vb2  nb2 0 dc 'b2v'
vs   vdd nvs dc 0

x1 vc nb0 nb1 nb2 clk1 nvs 0 vco

* Break the ring's DC symmetry so the operating point is not the metastable
* all-nodes-at-mid solution -- same convention as tb_vco_tuning.sp/.spice.
.ic v(x1.Y1)=0 v(x1.Y2)='vsup' v(x1.Y3)=0 v(x1.Y4)='vsup' v(x1.Y5)=0

.tran 'tstep' 'tstop' 0 'tmax'

.meas tran tp1 trig v(clk1) val='vsup/2' rise=1 td='tsettle' targ v(clk1) val='vsup/2' rise=5 td='tsettle'
.meas tran f1 param='4/tp1'
.meas tran i1 avg i(vs) from='tsettle' to='tstop'
