* gf180-pll :: divider-ratio-chain :: klt sim circuit body, f200n33 slice
*
* The committed campaign's deck for the N = 33 / 200 MHz point, expressed as
* a klt sim circuit body (no .control, no .end): the DUT
* design/netlist/divider_chain.spice composed with the campaign's stimulus
* fragment testbench/tb_divider_chain.sp, the f200n33 sweep-point parameters
* from testbench/tb.json, and the campaign's four solver options -- the same
* composition sim/harness/runner.py compose_deck() freezes for record
* 20261114-093804-ad9eef8 (sim/divider-ratio-chain/netlist-snapshots/).
*
* vdd_val is the supply axis: every rail source in the stimulus scales from
* it, so the request sweeps it as corners.params (one value per supply rail)
* rather than corners.supply_v, which would move only the vdiv source.
* The .measure cards that consume these params live in the request, not here.
* ---- f200n33 sweep-point parameters (tb.json sweeps.point.points.f200n33)
.param kf=200e6
.param ktstep=1e-10
.param ktstop=5.95e-07
.param kn=33
.param ksel0=0
.param ksel1=0
.param ksel2=0
.param ksel3=0
.param ksel4=1
.param ksel5=0
.param kp0=1
.param kp1=0
.param kp2=0
.param kp3=0
.param kp4=0
.param kp5=0
* ---- PVT parameter (altered per corner by the request's corners.params)
.param vdd_val=3.3
* ---- solver options (tb.json options, verbatim)
.options reltol=1e-3
.options abstol=1e-10
.options vntol=1e-5
.options chgtol=1e-13
* ---- DUT (composed by netlist.sh from design/divider_chain.sch)
.include ../../../design/netlist/divider_chain.spice
* ---- testbench stimulus (sim/divider-ratio-chain/testbench)
.include ../testbench/tb_divider_chain.sp
