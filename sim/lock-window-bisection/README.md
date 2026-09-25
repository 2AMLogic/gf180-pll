# `lock-window-bisection`

Can a **symmetric `REF` phase-step bisection read at the `LOCK` pad** select the
lock-detector window trim code (`LDT3:LDT0`) to the accuracy
[DR-022](../../spec/decision-records/DR-022-lock-detector-trim-execution-on-silicon.md)
Decision 2 demands — with **no design change and no new pad**?

That is DR-022 Decision 5 route 1, and issue #527. The trim rule
(`spec/pll.md`'s [Lock-detector window trim-code rule]) is normative and its
measurand is internal: `t_win` is the `ERR` → `ERRD` delay of `delaywin_3v3`,
and neither node is a port of `pll_top`. DR-022 measured all four quantities
`pll_top`'s pads *do* expose against the sixteen-code window map over a
117-point grid and found none that selects the code to the accuracy
`spec/pll.md`'s Lock detector row assumes, so the rule is executable only in
simulation. This campaign characterizes the first of the two routes Decision 5
names and deliberately authorizes neither.

## The procedure under test

With the loop locked at a fixed (f_ref, N, band, `CPB1:CPB0`, trim code)
operating point, step `REF`'s phase by a known signed Δ — once,
instantaneously — and watch the design's own `LOCK` output. The detector sees
the loop's settled static offset φ_ss **plus** Δ immediately, while the loop's
≤ 430 kHz bandwidth takes microseconds to absorb the step, so `LOCK` drops for
a while once the magnitude exceeds the flag window `t_flag`. Because
`ERR = XOR(UP, DN)` responds to the *magnitude* of the phase error regardless
of sign, the two directions give

```
Θ₊ = t_flag − φ_ss          Θ₋ = t_flag + φ_ss
t_flag = (Θ₊ + Θ₋)/2        φ_ss  = (Θ₋ − Θ₊)/2
```

— the static offset **cancels out of `t_flag`**, which is exactly what
disqualifies the naive in-loop selector DR-022's Alternatives section rejects.
A tester then repeats over `LDT3:LDT0` and programs the code whose
`t_flag`/1.037 is nearest 1.343 ns.

The algebra is not in question. What this campaign measures is whether the
thresholds a tester would actually read obey it.

## Layout

| Path | What it is |
|---|---|
| `testbench/tb_bisection.sp` | the closed-loop `pll_top` deck: one transient per (bundle, code, Δ). Its header states what is measured, why the phase step is two `pulse` sources and a select rather than a generated PWL, and what each of the three warm-started state nodes is for. |
| `testbench/tb.json` | the manifest: operating point, the per-bundle `op` axis (band / trim code / warm-start voltage), the `d` phase-step ladder, and the grid that pairs them. |
| `testbench/derive.py` | the reduction — `step_ladder`, `bisection_thresholds`, `tier_verdict`. The threshold, and therefore every number graded against DR-022, is a reduction over the `d` axis, never a per-point measurement. |
| `testbench/check_config.py` | diffs every configured number in `tb.json` against the thing that owns it (the encoders in `sim/lib/pll_top_dut.sh`, `sim/supply-sensitivity`'s band/warm-start derivation, the trim rule applied to the committed 16-code map, and the deck's own `|Δ| < 0.2·t_ref` select guard). Run it before any recorded run. |
| `records/` | the append-only evidence records. |

## Running it

```bash
# every configured number against its owner -- no simulation
python3 sim/lock-window-bisection/testbench/check_config.py

# the grid, off-host (a closed-loop transient ladder is not a shared-box workload):
#   1. look -- shapes every job, submits nothing, records nothing
python3 sim/run_corners.py lock-window-bisection --backend batch
#   2. leap
python3 sim/run_corners.py lock-window-bisection --backend batch --batch-apply \
    -j 12 --timeout 3600 \
    --subset-reason "<why this is not the full mandated PVT matrix>"
```

The manifest's own grid is **not** the mandated PVT matrix and never claims to
be: temperature is 27 °C and supply 3.30 V at every point, because that is the
condition at which the trim rule is *defined* and at which a tester would
execute it, and the process axis is the three bundles carrying the three
distinct codes the rule selects across the five MOS bundles. `--subset-reason`
is therefore required, and what it says lands verbatim on the record.

## Scope of the first record

Issue #527 lists six things that must be measured before any of this can be
written into `spec/`, and states up front that the full crossing is far beyond
what has ever been run here. The first record answers the four that are about
the *method's validity* — is the deassert observable at the pad; does the
threshold in Δ reproduce `t_flag`; does the ± cancellation survive the loop's
own asymmetric correction; what Δ resolution does one trim step demand — and
declares the other two out of scope: the worst-code-error grid over temperature
and supply, and the f_ref dependence below 25 MHz. Those are only worth buying
if the first four come back clean, and the record says which way they came
back.

[Lock-detector window trim-code rule]: ../../spec/pll.md#lock-detector-window-trim-code-rule
