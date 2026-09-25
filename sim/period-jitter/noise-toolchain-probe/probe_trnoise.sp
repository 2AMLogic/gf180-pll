* Probe 2 of 4 -- does the explicit `trnoise()` PWL source function work?
*
* This is the complement of probe 1. The automatic path (.option TRANNOISE)
* injects nothing; the question DR-023 must answer is whether an EXPLICIT
* injected-noise source exists, because that is what alternative (B) in issue
* #520 would be built on.
*
* trnoise(RMS_white, timestep, exponent, RMS_1overf): a 1 mV RMS white source
* on a 1 ns grid, with no 1/f component. The source drives a 1 Meg resistor to
* ground so v(n1) IS the source waveform.
*
* What this probe does NOT establish, and the distinction DR-023 turns on: that
* the amplitude means anything physical. `trnoise()` synthesizes a waveform
* from an amplitude the DECK supplies. It knows nothing about any device. A
* working trnoise() is a necessary ingredient of a calibrated measurement and
* not by itself any part of one.

v1 n1 0 dc 0 trnoise(1m 1n 0 0)
r1 n1 0 1meg

.tran 1n 50u

.control
run
let vmin = vecmin(v(n1))
let vmax = vecmax(v(n1))
let vrms = sqrt(mean(v(n1)*v(n1)))
echo "PROBE trnoise"
print vmin vmax vrms
.endc

.end
