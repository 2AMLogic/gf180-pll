# klt sim RECORD — divider-ratio-chain, f200n33 slice (T1 item 5 pilot, #1083)

The N = 33 / 200 MHz slice of the `divider-ratio-chain` campaign, re-expressed
as a `klt sim` request (`request.json`) and run on the Spot batch fleet, to
pilot whether a migrated campaign yields a `klt sim` envelope `klt signoff`
can grade for T1 item 5. Ratified spec row 3 ([Multiplication ratio], N = 4–64
every integer, static configuration) is the row this envelope grades; this
slice covers it at the full mandated 45-point PVT matrix for one divisor
(N = 33 at 200 MHz), which is the slice the committed on-pin record carries.

[Multiplication ratio]: ../../../spec/pll.md#multiplication-ratio

## What ran

- **Request**: `request.json` — the committed DUT (`design/netlist/divider_chain.spice`)
  composed with the committed stimulus
  (`../testbench/tb_divider_chain.sp`) via the circuit body `netlist-f200n33.sp`
  (which pins the f200n33 sweep-point parameters and the campaign's four solver
  options), the 45 corners as 5 process bundles x {-40, 27, 125} °C x
  {2.97, 3.3, 3.63} V (supply swept as `corners.params` on `vdd_val`, because
  every rail source in the stimulus scales from that one parameter), and the
  campaign's eleven `.measure` cards verbatim, with the reducer's ratio limits
  (both periods within 0.05 of N) applied as `limits` on `n_fb`/`ndo`, each
  tagged `spec_row: multiplication-ratio`.
- **Envelope**: `envelope.json` — `status: pass`, 45/45 corners PASS,
  0 failed / 0 errored / 0 inconclusive; `coverage.measurements_with_limits: 2`.
- **Execution**: `--backend batch --wait-for-capacity 600`, split by
  `batch.max_units_per_job: 11` into 5 jobs (fleet whole-job ceiling 3600 s):
  `klt-sim-613ed8ccc258`, `klt-sim-2fff5603dc9e`, `klt-sim-93e699668a9d`,
  `klt-sim-4f635238cd1b`, `klt-sim-93c6a8a72220`, all spot (c7i/m7i 4–8 xlarge),
  all `state: done`, exit 0.

## Provenance (worker-observed)

- **PDK**: worker image stamp `gf180mcuD`, `open_pdks
  f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7` — identical to the client's pin and
  to the committed record's PDK; model inputs staged from the client
  (`options.stage_model_inputs: true`), runner model hashes verified,
  `pdk_stamp_comparison: match`. `options.pdk_revision` asserts the same pin.
- **Simulator**: ngspice-47 on the worker (`/usr/local/bin/ngspice`, creation
  date 2026-11-13, KLU direct solver), `engine_build_comparison: match`. That
  comparison is each worker's version banner against its own submitting
  client's banner; the envelope records no binary hash
  (`engine_build.binary_sha256` is null), so the worker build and the build
  that produced the committed record (also reported as ngspice-47) are
  **not** shown to be the same binary. What is measured is agreement at the
  record's printed precision, below.
- **Simulator init (DR-040)**: **unmet — decisions 1 and 2 both.** The
  committed `request.json` does **not** stage the repository init text
  (`options` carries only `timeout_s`, `stage_model_inputs` and
  `pdk_revision`; there is no `options.ngspice_init`), so the 45-corner grid
  ran under the fleet worker's ambient init, not the init file DR-040
  decision 1 requires both backends to stage. Separately, the envelope
  carries no init identity (`environment.ngspice_init` is
  `{source: "runner", lines: null, sha256: null}`) and the fleet runner
  (klt 0.9.0) retains no marker line, so decision 2's evidence requirement
  is also unmet and these points are `unattributed` against the
  reference-configuration baseline: the zero-delta comparison below is a
  comparison of results, not a proven same-configuration comparison. The
  grid was not re-run with the init staged: a one-point pilot rerun with
  `options.ngspice_init` set reproduced the same values and the same null
  init identity, so a full re-run would not have changed the attribution,
  and the pilot is not committed here. Decision 1 is this repository's
  shortfall; decision 2's evidence gap is a tool gap:
  2AMLogic/klayout-tools#7368.
- **Runners**: klt 0.9.0 (fleet image), client klt 0.9.3.dev2575+g6bd18bbc8637,
  `runner_compatibility: match` (required features `corners.params`,
  `options.stage_model_inputs`).
- **Deck identity**: netlist closure — DUT `sha256:bcdaece6…`, stimulus
  `sha256:c9f11fc4…` — exactly the hashes the committed record's provenance
  block pins; `netlist_identity: sha256:2a2ef310…`.

## Cost

Estimated before submission (issue comment, 2026-11-21): ~5 spot-minutes.
Actual: 5 jobs, 22–44 s job elapsed each (160 job-seconds total), 566.9 s of
ngspice runtime across the 45 corners (12.6 s average, single-threaded).

## Old record vs klt sim, per corner

Baseline: the committed f6eeac7 successor record
`../records/20261114-093804-ad9eef8.md` (overall PASS, on `main` since #827),
per-corner table filtered to `f200n33`, joined to this envelope by
(process, temperature, supply). `ratio_pass` on the klt side is the corner
verdict (both `n_fb` and `ndo` inside [32.95, 33.05] — the reducer's 0.05
tolerance on N = 33, `derive.py` semantics preserved). `max |Δ|` is the
largest absolute difference over all eleven measurements at that corner.

| corner | record n_fb | klt n_fb | record ndo | klt ndo | record ratio_pass | klt ratio_pass | record | klt | max &#124;Δ&#124; |
|---|---|---|---|---|---|---|---|---|---|
| `ff_-40c_2.97v_f200n33` | 33 | 33 | 33 | 33 | 1 | 1 | PASS | PASS | 0 |
| `ff_-40c_3.30v_f200n33` | 33 | 33 | 33 | 33 | 1 | 1 | PASS | PASS | 0 |
| `ff_-40c_3.63v_f200n33` | 33 | 33 | 33 | 33 | 1 | 1 | PASS | PASS | 0 |
| `ff_27c_2.97v_f200n33` | 33 | 33 | 33 | 33 | 1 | 1 | PASS | PASS | 0 |
| `ff_27c_3.30v_f200n33` | 33 | 33 | 33 | 33 | 1 | 1 | PASS | PASS | 0 |
| `ff_27c_3.63v_f200n33` | 33 | 33 | 33 | 33 | 1 | 1 | PASS | PASS | 0 |
| `ff_125c_2.97v_f200n33` | 33 | 33 | 33 | 33 | 1 | 1 | PASS | PASS | 0 |
| `ff_125c_3.30v_f200n33` | 33 | 33 | 33 | 33 | 1 | 1 | PASS | PASS | 0 |
| `ff_125c_3.63v_f200n33` | 33 | 33 | 33 | 33 | 1 | 1 | PASS | PASS | 0 |
| `fs_-40c_2.97v_f200n33` | 33 | 33 | 33 | 33 | 1 | 1 | PASS | PASS | 0 |
| `fs_-40c_3.30v_f200n33` | 33 | 33 | 33 | 33 | 1 | 1 | PASS | PASS | 0 |
| `fs_-40c_3.63v_f200n33` | 33 | 33 | 33 | 33 | 1 | 1 | PASS | PASS | 0 |
| `fs_27c_2.97v_f200n33` | 33 | 33 | 33 | 33 | 1 | 1 | PASS | PASS | 0 |
| `fs_27c_3.30v_f200n33` | 33 | 33 | 33 | 33 | 1 | 1 | PASS | PASS | 0 |
| `fs_27c_3.63v_f200n33` | 33 | 33 | 33 | 33 | 1 | 1 | PASS | PASS | 0 |
| `fs_125c_2.97v_f200n33` | 33 | 33 | 33 | 33 | 1 | 1 | PASS | PASS | 0 |
| `fs_125c_3.30v_f200n33` | 33 | 33 | 33 | 33 | 1 | 1 | PASS | PASS | 0 |
| `fs_125c_3.63v_f200n33` | 33 | 33 | 33 | 33 | 1 | 1 | PASS | PASS | 0 |
| `sf_-40c_2.97v_f200n33` | 33 | 33 | 33 | 33 | 1 | 1 | PASS | PASS | 0 |
| `sf_-40c_3.30v_f200n33` | 33 | 33 | 33 | 33 | 1 | 1 | PASS | PASS | 0 |
| `sf_-40c_3.63v_f200n33` | 33 | 33 | 33 | 33 | 1 | 1 | PASS | PASS | 0 |
| `sf_27c_2.97v_f200n33` | 33 | 33 | 33 | 33 | 1 | 1 | PASS | PASS | 0 |
| `sf_27c_3.30v_f200n33` | 33 | 33 | 33 | 33 | 1 | 1 | PASS | PASS | 0 |
| `sf_27c_3.63v_f200n33` | 33 | 33 | 33 | 33 | 1 | 1 | PASS | PASS | 0 |
| `sf_125c_2.97v_f200n33` | 33 | 33 | 33 | 33 | 1 | 1 | PASS | PASS | 0 |
| `sf_125c_3.30v_f200n33` | 33 | 33 | 33 | 33 | 1 | 1 | PASS | PASS | 0 |
| `sf_125c_3.63v_f200n33` | 33 | 33 | 33 | 33 | 1 | 1 | PASS | PASS | 0 |
| `ss_-40c_2.97v_f200n33` | 33 | 33 | 33 | 33 | 1 | 1 | PASS | PASS | 0 |
| `ss_-40c_3.30v_f200n33` | 33 | 33 | 33 | 33 | 1 | 1 | PASS | PASS | 0 |
| `ss_-40c_3.63v_f200n33` | 33 | 33 | 33 | 33 | 1 | 1 | PASS | PASS | 0 |
| `ss_27c_2.97v_f200n33` | 33 | 33 | 33 | 33 | 1 | 1 | PASS | PASS | 0 |
| `ss_27c_3.30v_f200n33` | 33 | 33 | 33 | 33 | 1 | 1 | PASS | PASS | 0 |
| `ss_27c_3.63v_f200n33` | 33 | 33 | 33 | 33 | 1 | 1 | PASS | PASS | 0 |
| `ss_125c_2.97v_f200n33` | 33 | 33 | 33 | 33 | 1 | 1 | PASS | PASS | 0 |
| `ss_125c_3.30v_f200n33` | 33 | 33 | 33 | 33 | 1 | 1 | PASS | PASS | 0 |
| `ss_125c_3.63v_f200n33` | 33 | 33 | 33 | 33 | 1 | 1 | PASS | PASS | 0 |
| `typical_-40c_2.97v_f200n33` | 33 | 33 | 33 | 33 | 1 | 1 | PASS | PASS | 0 |
| `typical_-40c_3.30v_f200n33` | 33 | 33 | 33 | 33 | 1 | 1 | PASS | PASS | 0 |
| `typical_-40c_3.63v_f200n33` | 33 | 33 | 33 | 33 | 1 | 1 | PASS | PASS | 0 |
| `typical_27c_2.97v_f200n33` | 33 | 33 | 33 | 33 | 1 | 1 | PASS | PASS | 0 |
| `typical_27c_3.30v_f200n33` | 33 | 33 | 33 | 33 | 1 | 1 | PASS | PASS | 0 |
| `typical_27c_3.63v_f200n33` | 33 | 33 | 33 | 33 | 1 | 1 | PASS | PASS | 0 |
| `typical_125c_2.97v_f200n33` | 33 | 33 | 33 | 33 | 1 | 1 | PASS | PASS | 0 |
| `typical_125c_3.30v_f200n33` | 33 | 33 | 33 | 33 | 1 | 1 | PASS | PASS | 0 |
| `typical_125c_3.63v_f200n33` | 33 | 33 | 33 | 33 | 1 | 1 | PASS | PASS | 0 |

**Every delta is exactly 0.** All 45 corners join 1:1 with the committed
record — one comparison for each of the 45 expected keys, no missing or extra
measurements, and identical PASS verdicts, identical `ratio_pass`, and
equal values on all eleven measurements at the printed precision (the record
prints six significant digits; the envelope agrees at every printed digit).
This is agreement of printed values, not evidence of an identical simulator
build or initialization.

## Diagnostics

8 corners carry a recovered `nonconvergence` diagnostic (severity `warning`,
the DC solve converging via stepping): `typical`/125 °C at 3.30 and 3.63 V,
`ff`/−40 °C at 3.30 V, `ff`/125 °C at 2.97 and 3.30 V, `ss`/125 °C at 3.30 V,
`fs`/−40 °C at 3.30 V, `fs`/125 °C at 3.63 V. Every one of them still produced
values identical to the baseline row, so the transient result is unaffected;
the corners grade PASS. Recorded here, not suppressed (`#6027` names the
signoff-crediting gap for failing corners; these did not fail).

## Limits of this envelope (not covered)

- Row 3 spans N = 4–64 at 200 MHz (plus the retiming-margin worst cases); this
  envelope covers N = 33 only. The remaining divisors, the N = 64 retiming
  margins (which join `sim/divider-ratio-dff`), and the 10 MHz bottom-of-band
  checks were migrated by #1090 — see `migration/RECORD.md` (190 further
  corners, same zero-delta join against the committed record).
- `klt signoff`'s row coverage is row-granular: a row with one passing tagged
  measurement reads as covered even when only a slice of its sweep ran. The
  disclosure lives here and in the PR; the granularity gap is filed upstream.
- The pilot point comparison (`typical/27 °C/3.30 V`) and the dry-run output
  are recorded on issue #1083 before the grid was submitted.
