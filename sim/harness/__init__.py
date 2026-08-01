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
- ``testbench.py`` / ``report.py`` add the optional ``topology_groups``
  manifest key: this repo's campaigns routinely put several sub-circuits in
  one deck (the delay-cell deck alone carries five), and bandgap's single
  flat result table cannot say which of two dozen measurements belongs to
  which topology. Declaring the grouping splits the record's **Result**
  field into one sub-table per topology. Purely a rendering concern --
  omitting the key reproduces bandgap's flat table exactly.
- ``testbench.py`` / ``corners.py`` / ``runner.py`` / ``report.py`` add the four
  optional keys the ``sim/lib/simenv.sh`` campaigns need and bandgap's single
  fixed ``params`` map cannot express: ``dut`` (compose a committed
  ``design/netlist/`` export into the deck and the snapshot), ``sweeps`` +
  ``grid`` (extra independent axes with per-point derived parameters, over a
  deliberately non-rectangular union of justified slices), per-measurement
  ``optional`` (an expected ``.measure`` failure is data, and never discards
  the point's successful measurements), and ``derived`` (see ``derived.py`` --
  the campaign's own reduction over the per-point table, including a
  cross-record join). Every one defaults to off; a manifest that uses none of
  them behaves exactly as it did before they existed.
- ``derived.py`` is the extension point for that last one: campaign-specific
  reduction logic lives in the campaign's own ``testbench/derive.py``, which
  is where the equivalent awk lives today.
- ``report.py`` renders this repo's ratified field set from ``sim/README.md``
  (Record ID, Claim, Netlist provenance, **Environment provenance**, Corner
  matrix run, **Methodology / criteria / limitations**, Statistical
  convention, Result, Links, Timestamp / author, Supersedes) -- the two
  bolded fields are additions this repo's schema makes ("[PLL delta]" in
  ``sim/README.md``) that bandgap's schema does not carry.
"""

HARNESS_VERSION = "0.1.0"
