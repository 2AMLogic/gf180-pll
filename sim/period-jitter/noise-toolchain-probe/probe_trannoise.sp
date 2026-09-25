* Probe 1 of 4 -- does `.option TRANNOISE=1` inject device noise into a .tran?
*
* DR-002 Decision 5 specifies a VCO-dominated TRANSIENT-NOISE testbench as the
* method for this repository's random period-jitter number. Every
* sim/period-jitter record states that the option does nothing on this repo's
* pinned ngspice-46. This deck re-derives that from scratch rather than citing
* it, because DR-023 turns on it.
*
* The circuit is deliberately trivial and noise-dominated-by-construction: a DC
* source into a 100k/100k divider. Both resistors are large enough that their
* thermal noise, IF the build injected it, would be plainly visible in the
* transient -- 4kTR at 100k is 1.66e-15 V^2/Hz, so over the ~500 MHz bandwidth
* a 1 ns timestep implies, an injecting build would show tens of microvolts of
* wander on v(n1). A build that injects nothing holds v(n1) at exactly 0.5 V.
*
* PASS/FAIL for DR-023's purposes: `vspan` is the discriminator. Exactly zero
* means no injection. Anything non-zero would mean the option works after all
* and DR-023's Decision 2 must be revisited.

.option TRANNOISE=1

v1 vdd 0 dc 1
r1 vdd n1 100k
r2 n1 0  100k

.tran 1n 10u

.control
run
let vmin  = vecmin(v(n1))
let vmax  = vecmax(v(n1))
let vspan = vmax - vmin
echo "PROBE trannoise"
print vmin vmax vspan
.endc

.end
