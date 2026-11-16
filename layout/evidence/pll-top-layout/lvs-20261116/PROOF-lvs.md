# Assembled `pll_top` LVS — first top-level run (issues #237, #149)

> **Verdict in one line:** the foundry LVS deck ran end to end on the
> committed `pll_top.gds` against a new, mechanically composed flat
> reference — and mismatched, on exactly **two structural causes**, both
> already tracked: the #753 option-A C2 **does not extract as a device at
> all** under the variant-D deck, and the open_pdks **f6eeac7 re-pin
> flipped the runset's extracted-side parallel-device merge off**
> (`SIMPLIFY option: false` in this run's own log, where the
> c6d73a35-era runset the four block-level LVS-match records were
> produced on merged those devices by default). After decomposing both
> effects, **every one of the 16 device-count deltas is accounted for**
> (`signature-delta.txt`); there is **no unexplained device and no wiring
> delta**. This is not a signoff result, and it is not evidence about the
> KLayout `0.28.16` pin either — see Provenance.

## Provenance

| | |
|---|---|
| Run | 2026-11-16, `layout/run_pv.py lvs` (deep, `--lvs-sub VSS`, repo-default `poly_res 3k` shim) |
| Layout | `layout/evidence/pll-top-layout/pll_top.gds` @ `main` (sha256 `fbe40013…`, byte-identical geometry to a fresh regeneration from the current generators the same day — the committed assembly is current) |
| Reference | `pll_top.spice` in this directory — composed by `layout/pll_top/top_level/reference.py` (new in the same PR as this record) from the five blocks' own `reference_netlist()` outputs, wiring read from `design/netlist/pll_top.spice` |
| PDK | `gf180mcuD`, open_pdks `f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7` (`~/.ciel`, matches `sim/pdk.json`) |
| KLayout | `0.30.12` — **not** the `0.28.16` pin; `check-env.txt` carries the standard warning. The two findings below are decided from the deck's own extracted netlist (`pll_top.cir`), i.e. from device multisets, not from a near-miss verdict — but any *scored* clean run still needs the pin. |
| Deck verdict | `Netlists don't match` (deck log line 268); this harness's normalised exit 1 |

## The composed reference — what it is, and its three disclosed rules

`design/netlist/pll_top.spice` is hierarchical, and gf180mcu's LVS deck
(`align`) does not flatten a hierarchical schematic against a flat GDS on
its own (issue #310's finding, restated in `layout/harness/spice_flatten.py`'s
docstring). The top level therefore gets the same treatment every block got:
a flat reference composed from the five blocks' *own* `reference_netlist()`
outputs — each already the reference its block's evidence-directory LVS run
was recorded against — with port maps read from `pll_top.spice`'s instance
lines rather than restated. Three deliberate, disclosed composition rules
(all in `reference.py`'s docstring, all pinned by
`layout/tests/test_top_level_reference.py`):

1. **Substrate merge.** The deck models the p-substrate as one node named
   by `--lvs_sub`, so `pll_top`'s two separate *metal* grounds (`VSS`,
   `GND_VCO`) are mapped to one net in the reference. This run's extracted
   netlist confirms the deck does exactly that: the merged node is
   literally named **`GND_VCO|VSS`** in `pll_top.cir`. That the *routing*
   keeps the two apart remains graded by `netcheck.py` (362 labels / 39
   top-level nets / OK, re-checked this run on the regenerated GDS).
2. **Loop filter pinned to option A.** The committed assembly draws the
   DR-006 option-A filter (`assemble.BLOCKS` pins `--mim-option A`; the
   option-B re-assembly is DR-042 follow-up under #753). The reference
   requests `mim_option="A"` to match the committed geometry, so the one
   known device delta does not mask every other comparison.
3. **Path qualification.** Every instance's devices and internal nets carry
   its instance-name prefix (`XPFD_`/`XLF_`/`XVCO_`/`XDIV_`/`XLD_`), so
   blocks cannot merge by internal-name collision.

Device completeness: 809 cards (813 device instances after `M=` expansion)
= 62+3+1 (vco) + 168 (pfd_cp) + 117 (lock_detector) + 452 (divider_chain)
+ 6 (loop filter) — asserted against the block references by the test.

## Finding 1 — the #753 option-A C2 is invisible to the variant-D deck

The deck log states `MIM Option selected: B` (variant D pins
`mim_option=B`). Under that switch the extractor does not recognise the
drawn option-A MIM cap (`cap_mim_2f0_m2m3_noshield`, M2/M3 plates) as a
device at all: the extracted netlist contains **zero** MIM caps, while the
reference's one C2 card is the only reference-only device the
decomposition cannot pair (`signature-delta.txt` names it directly).

This upgrades #753's delta from a naming question to an extraction-level
fact: **on the gf180mcuD variant-D flow this repo pins, the committed
assembly cannot produce an LVS match until C2 is redrawn as the option-B
device** — which is precisely the physical work #753's authorised campaign
covers. (The block-level `lvs-variant-D` record for the loop filter
predates this: it was recorded on the c6d73a35-era deck, and its own
`lvs-variant-A-mim-connect-diagnostic` directory shows how
variant-sensitive this device's recognition already was.)

## Finding 2 — the f6eeac7 re-pin turned the runset's parallel-device merge off

The top-level extracted netlist has **816 MOSFETs where the reference
states 799**. Every one of the 16 extra devices is a *fold segment* of a
card the reference (and the schematic behind it) states as one device:

| reference card | drawn as | extracted as |
|---|---|---|
| `XMC1 … W=78.87u nf=8` (`design/netlist/vco.spice`) | 8 gate fingers | 8 × `pfet W=9.86u L=1u` |
| one `W=60u L=1u` card | 4 fingers | 4 × `W=15u` |
| one `W=26.5u L=1u` card | 2 fingers | 2 × `W=13.25u` |
| one `W=17.22u L=1u` card | 2 fingers | 2 × `W=8.61u` |
| one `nfet W=8.61u L=1u` card | 2 fingers | 2 × `W=4.305u` |
| one `nfet W=5u L=1u` card | 2 fingers | 2 × `W=2.5u` |
| 3 of 4 `W=48u L=1u` cards | 2 segments each | 6 × `W=24u` |

Mechanism, verified not inferred: this run's deck log prints **`Selected
SIMPLIFY option: false`**, while the c6d73a35-era behaviour is on the
record in `layout/evidence/loop-filter-layout/PROOF.md` ("the runset
merges parallel devices in the extracted netlist by default") — the same
merge that let the four block-level LVS-match records match references
stating one card per schematic device. The open_pdks re-pin to `f6eeac7`
(the re-qualification wave this repo ran through `sim/` in late
October/November 2026) carried a runset that no longer merges.
**Consequence: the committed block-level LVS-match evidence describes the
deck it was recorded on, not the deck this repo now pins** — a per-block
re-establishment on the f6eeac7 runset is tracked as its own issue, and
#149/#18's "LVS-clean report" gates are blocked on it plus Finding 1.

Nothing in the delta is wiring-related: after the fold decomposition and
the MIM residual, the device-multiset delta is exactly zero, and the
extracted net names (`CLK`, `P0`, `DIVOUT`, `VDD_VCO`, `VDD_DIV`,
`GND_VCO|VSS`, …) land where the composition maps them.

## What this record is not

- Not an LVS-clean claim, and not signoff: the verdict line is a mismatch.
- Not evidence about the `0.28.16` KLayout pin (see Provenance). The two
  findings are structural — device multisets read from the deck's own
  extracted netlist — not the false-mismatch class that warning names,
  but a scored run needs the pin.
- Not a change to any block's layout, the committed `pll_top.gds`, or any
  ratified spec row. The evidence tree is append-only; this directory adds
  to it.

## Reproducing

```
LAYOUT_PV_PYTHON=<venv with klayout+docopt> python3 layout/run_pv.py check-env
python3 -m pll_top.top_level.reference --outdir <dir>      # from layout/, PV python
python3 layout/run_pv.py lvs layout/evidence/pll-top-layout/pll_top.gds \
    <dir>/pll_top.spice --top pll_top --run-dir <rundir> --lvs-sub VSS
python3 make-signature-delta.py pll_top.spice pll_top.cir  # this directory
```

The PV python this run used was a throwaway venv (`klayout` 0.30.13 wheel
+ `docopt`) — `check-env.txt` records the resolution.
