* Probe 4 of 4 -- is a periodic-steady-state analysis available?
*
* This is the decisive probe for DR-023. Probe 3 shows the device noise PSDs
* exist at a DC operating point. An oscillator's phase noise needs those PSDs
* weighted over the oscillation cycle, because the devices are cyclostationary
* -- the standard tool for that is a periodic-steady-state solve followed by a
* periodic (cyclostationary) noise analysis, `pss` + `pnoise`.
*
* ngspice has carried an experimental `pss` command in some builds, so this
* must be checked on THIS build rather than assumed either way. The circuit is
* an irrelevant RC; only whether the command resolves matters.
*
* Expected on this repository's pinned ngspice-46:
*     pss: no such command available in ngspice
*
* If a future build answers differently, DR-023's Decision 2 is falsified and
* issue #520's alternative (C) is already in hand.

v1 n1 0 dc 0 sin(0 1 1meg)
r1 n1 n2 1k
c1 n2 0 1n

.control
echo "PROBE pss -- help pss:"
help pss
echo "PROBE pss -- invoking pss:"
pss 1meg 1024 n2 5 10 1e-3
echo "PROBE pss -- done"
.endc

.end
