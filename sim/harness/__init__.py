"""gf180-pll PVT corner-sweep harness.

Ported and adapted from the sim-harness pattern bootstrapped in
``2AMLogic/gf180-bandgap`` PR #23 (merged 2026-07-31), per CLAUDE.md's
harness-bootstrap rule: "copy the sim-harness pattern from
2AMLogic/gf180-bandgap once it lands there rather than reinventing."

Deltas from the bandgap pattern (see ``sim/README.md`` for the evidence-record
schema these implement):

- ``corners.py`` models this repo's device menu only (MOS + the three
  independent passive axes: resistor / MOS cap / MIM cap). No BJT/diode
  axes -- gf180-pll's blocks do not use those device families.
- ``testbench.py`` / ``runner.py`` add ``raw_measures`` alongside bandgap's
  ``measure`` (post-analysis ``let`` expressions): a manifest may declare
  literal ``.measure <analysis> <name> <expr>`` statements (trig/targ,
  when/rise, avg/from-to, ...), which is what most of this repo's real
  campaigns (delay, lock time, jitter) actually need and a bare ``let``
  expression cannot express.
- ``report.py`` renders this repo's ratified field set from ``sim/README.md``
  (Record ID, Claim, Netlist provenance, **Environment provenance**, Corner
  matrix run, **Methodology / criteria / limitations**, Statistical
  convention, Result, Links, Timestamp / author, Supersedes) -- the two
  bolded fields are additions this repo's schema makes ("[PLL delta]" in
  ``sim/README.md``) that bandgap's schema does not carry.
"""

HARNESS_VERSION = "0.1.0"
