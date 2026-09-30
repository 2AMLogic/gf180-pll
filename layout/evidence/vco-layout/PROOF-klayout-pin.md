# Every block-level DRC/LVS verdict, re-derived on the pinned KLayout (issue #127)

This file is not a geometry increment. No `.gds` in this repository changes
by this work, and no generator changes. It answers one question that had
never been asked of `layout/evidence/`:

> **Is every DRC-clean and LVS-match verdict this repository scores
> reproducible on the KLayout build it pins?**

The answer turned out to be *no* for one of the four blocks, and the reason
nobody knew is that nothing checked.

## Why this was asked now

Issue `#127` tracks this block's gap to T1 (sim-validated / bronze). Its
2026-09-28 part-27 pass re-derived T1 item 11's `klt erc` evidence from its
inputs rather than from its own prose, and found that all four committed ERC
reports had been produced on `klt 0.6.0+gf2d249ab23d4` — a PEP 440 *local
version*, i.e. a source build after the `v0.6.0` tag, not the released wheel
CI pins — while the checker that existed to catch exactly that asked
`stated.startswith(pinned)` and let it through. That was fixed in PR `#628`.

The debt that pass recorded for the next one was to give items **3 (DRC
clean)** and **4 (LVS clean)** the same treatment, and it named the specific
suspicion: the ERC runs were on KLayout `0.30.12` while the DRC/LVS evidence
was believed to be on the repo's `0.28.16` pin — *"an asymmetry this body
records but has never re-measured."*

Re-measuring it is what this file records.

## Finding 1 — the asymmetry was not what either document said it was

`layout/harness/env.py` has carried

```python
KNOWN_GOOD_KLAYOUT_VERSION = "KLayout 0.28.16"
```

since bring-up, and `layout/README.md` stated, flatly, that *"the committed
DRC/LVS evidence under `layout/evidence/*/` was captured against KLayout
0.28.16."* Issue `#127`'s own body said the same thing in stronger words:
*"every DRC and LVS artifact in this repo is produced on the repo's pinned
0.28.16."*

A census of every committed deck log that records its own engine — the
foundry runner prints `Your Klayout version is: KLayout X.Y.Z` on every run
— says otherwise. Of the **51** such logs on `origin/main`@`ac714b46`:

| KLayout | logs |
|---|---|
| 0.28.16 (the pin) | 35 |
| 0.30.10 | 9 |
| 0.30.9 | 7 |

**16 of 51 were off-pin**, and two of them are block-level verdicts T1 scores:

| log | KLayout | what it is |
|---|---|---|
| `vco-layout/drc-clean/drc-block.stdout.log` | 0.30.10 | **`vco_block`'s DRC-clean verdict (item 3)** |
| `vco-layout/lvs-clean/lvs.stdout.log` | 0.30.10 | **`vco_block`'s LVS-match verdict (item 4)** |
| `vco-layout/drc-clean/drc.stdout.log` | 0.30.9 | `vco_ring` sub-cell DRC |
| `vco-layout/drc-clean/drc-vtoi-core.stdout.log` | 0.30.9 | `vco_vtoi_core` sub-cell DRC |
| `vco-layout/drc-clean/drc-buffer.stdout.log` | 0.30.10 | `vco_out_buffer` sub-cell DRC |
| `vco-layout/lvs-ring/lvs.stdout.log` | 0.30.9 | `vco_ring` sub-cell LVS |
| `vco-layout/lvs-buffer/lvs.stdout.log` | 0.30.10 | `vco_out_buffer` sub-cell LVS |
| `cp-leg-proof/{drc-clean,lvs-clean}/*` (4) | 0.30.10 | leaf-cell generator proofs |
| `inv-tb-proof/{drc,lvs}-{clean,fault}/*` (4) | 0.30.9 | harness bring-up proof + its 2 fault controls |
| `lock-detector-layout/lvs-recheck-klayout-0.30.10/lvs.stdout.log` | 0.30.10 | deliberately off-pin (PR `#471`) |

The other three blocks — `pfd_cp`, `divider_chain`, `lock_detector` — were
already on the pin for both verdicts. `vco_block` was the outlier, and it was
the outlier on **both**.

**This is not a cosmetic bookkeeping point in this repository.** Issue `#360`
records a newer KLayout reporting a **false LVS mismatch** on a
`divider_chain` layout that was otherwise LVS-clean and unchanged, with DRC
on the same binary unaffected. `env.py`'s own comment says so. A repository
that knows its LVS verdict can move with the engine, and then scores an LVS
verdict taken on a different engine, is scoring something it has not
measured.

The direction of the known drift happens to be the benign one — 0.30.x was
observed producing false *mismatches*, so a `Match` from it is, if anything,
conservative. That is an argument for expecting the re-run to pass. It is not
a substitute for running it.

## Finding 2 — re-run on the pin, all four blocks reproduce

Every block's DRC and LVS was re-run **from the committed GDS and the
committed reference netlist**, on this repository's pinned KLayout and pinned
PDK. Nothing was regenerated first; the inputs are the bytes on `main`.

Environment, from `python3 layout/run_pv.py check-env`:

```
PDK        : OK   ~/.volare/gf180mcuD (variant D, open_pdks c6d73a35f524070e85faff4a6a9eef49553ebc2b)
KLayout    : OK   /usr/bin/klayout (KLayout 0.28.16)
DRC runner : <pdk>/libs.tech/klayout/drc/run_drc.py
LVS runner : <pdk>/libs.tech/klayout/lvs/run_lvs.py
```

`open_pdks c6d73a35…` is the hash `.github/workflows/ci.yml` pins via volare,
and `KLayout 0.28.16` is `KNOWN_GOOD_KLAYOUT_VERSION` exactly — so this is the
engine and deck the repository grades on, not merely a nearby one.

```bash
python3 layout/run_pv.py drc layout/evidence/vco-layout/vco_block.gds \
  --top vco_block --run-dir <rundir>
python3 layout/run_pv.py lvs layout/evidence/vco-layout/vco_block.gds \
  layout/evidence/vco-layout/lvs-clean/vco_block.spice \
  --top vco_block --lvs-sub GND_VCO --run-dir <rundir>
```

(and the analogous pair for each of the other three blocks; `pfd_cp`,
`divider_chain` and `lock_detector` take no `--lvs-sub`.)

| block | DRC on 0.28.16 | LVS on 0.28.16 | extracted devices | `.SUBCKT` ports |
|---|---|---|---|---|
| `vco_block` | `Klayout DRC run is clean. GDS has no DRC violations.` | `INFO : Congratulations! Netlists match.` | 65 (31 `pfet_03v3` + 31 `nfet_03v3` + 3 resistors) | 20 |
| `pfd_cp` | clean | match | 168 (84 + 84) | 13 |
| `divider_chain` | clean | match | 452 (226 + 226) | 71 |
| `lock_detector` | clean | match | 117 (40 `pfet_03v3` + 77 `nfet_03v3`) | 48 |

**4 of 4 DRC-clean, 4 of 4 LVS-matched, on the pin, from the committed
inputs.** Deck run times 9.1–11.3 s (DRC) and 4.0–5.4 s (LVS); `POLY_RES
Selected is 3k` on every LVS run, this repository's ratified process option
(DR-009).

### The extracted netlists agree, and where they do not is informative

The re-run's extracted `.cir` was compared against the committed one, not
merely its verdict:

| block | device lines | multiset identical (ignoring `M$NN` index) | port set | port **order** |
|---|---|---|---|---|
| `vco_block` (committed on **0.30.10**) | 65 / 65 | **yes** | identical | **differs** |
| `pfd_cp` (committed on 0.28.16) | 168 / 168 | yes | identical | identical |
| `divider_chain` (committed on 0.28.16) | 452 / 452 | yes | identical | identical |
| `lock_detector` (committed on 0.28.16) | 117 / 117 | yes | identical | identical |

The three blocks whose committed extraction was already on the pin reproduce
**exactly** — same devices, same parameters, same port order, differing only
in the extraction timestamp comment. `vco_block`, the one whose committed
extraction came off 0.30.10, reproduces device-for-device with the **same
20-port set in a different order**.

That is worth naming rather than waving past, because it is the second
independent observation of the same cross-version signature. PR `#471` ran
`lock_detector`'s LVS on 0.30.10 against a committed 0.28.16 extraction and
reported exactly this: identical sorted device lines, *"only `.SUBCKT` port
ordering differing across the 48 ports."* Here the comparison runs in the
opposite direction — a 0.28.16 re-run against a committed 0.30.10 extraction
— and produces the same signature on a different block. Two blocks, both
directions, same difference: `.SUBCKT` port ordering is engine-dependent
between these releases and the extracted device population is not.

## Finding 3 — the inputs are what they claim to be

A re-run is only evidence if it ran on the committed bytes. Verified in the
same pass:

* `python3 -m pytest layout/tests/test_gds_reproducibility.py` → **7 passed,
  29 subtests passed** — every committed block GDS rebuilds from its own
  generator, so the GDS fed to the decks above is the one the generators
  produce today.
* All four reference netlists are byte-identical to what their generators
  produce today: `vco.block.reference_netlist()` (4,265 B),
  `divider_chain.divider_chain.reference_netlist()` (32,627 B),
  `pfd_cp.block.reference_netlist()` (48,680 B),
  `lock_detector.build.reference_netlist()` (35,144 B). The match is against
  the same schematic, not a co-moved one.

## What is committed, and what is not

Committed beside this file, following the precedent
`lock-detector-layout/lvs-recheck-klayout-0.30.10/` set:

* `drc-recheck-klayout-0.28.16/` — `drc.stdout.log`, `vco_block_main.lyrdb`
* `lvs-recheck-klayout-0.28.16/` — `lvs.stdout.log`, `vco_block.cir`,
  `vco_block.lvsdb`

These fill a real gap: before this pass there was **no** on-pin DRC or LVS
artifact for `vco_block` anywhere in the tree.

The superseded 0.30.10 runs (`drc-clean/drc-block.stdout.log`,
`lvs-clean/lvs.stdout.log`) are **kept, not replaced**, per this
repository's append-only evidence convention. Deleting an off-pin run to
satisfy a checker destroys the record of what was actually done.

The other three blocks' re-runs are **not** committed. Their committed
artifacts were already on the pin and reproduce byte-for-byte modulo the
extraction timestamp, so a second copy would add ~2 MB of `.lvsdb` and no
information. The re-run happened; its result is the table above.

## The structural half — the check that did not exist

Finding 1 is a documentation drift that survived because nothing graded it.
`env.py`'s pin produced only a run-time `WARNING`, about the binary you are
*about to* use; it said nothing about the logs already in the tree. Two
documents therefore went on asserting something demonstrably false about 16
committed files.

`layout/lib/check-layout-status-claims.sh` gains a seventh guard, the
**KLAYOUT PIN RULE**, built on the same doctrine as its ERC rule:

* every block that reads as drawn must have at least one committed deck log
  for **its own top cell**, on the pin, carrying `Klayout DRC run is clean.`;
  every block that reads as LVS-matched must likewise have one carrying
  `Congratulations! Netlists match.`;
* **at least one**, not all — so the append-only convention above stays legal;
* the pin is read out of `layout/harness/env.py`, never restated in the
  checker (`test_the_pin_is_read_from_env_py_not_restated` moves the pin and
  watches the whole verdict move with it);
* every remaining off-pin log must be named in `OFF_PIN_DISCLOSED` **with a
  reason**, so a new off-pin log fails the build and the census — *"51 deck
  logs, 35 on the pin, 16 off-pin"* — is a number the script prints rather
  than a sentence someone re-derives by hand;
* and the list cannot rot: `test_the_off_pin_disclosure_list_has_no_stale_entries`
  asserts every named file still exists, and
  `test_every_disclosed_entry_is_actually_off_pin` asserts none of them has
  quietly become on-pin and is now carrying a pointless exemption that would
  mask a future regression.

Seven new tests in `layout/tests/test_layout_status_claims.py`, including
**the exact pre-fix state of `vco_block`** — drawn and DRC-clean, but the
only deck log for that top cell is from 0.30.10 — driven to a known failure.
Mutation-checked: making the rule non-fatal fails 4 of them.

## What this does and does not establish

**Does**: all four blocks' item-3 and item-4 verdicts are reproducible on the
pinned KLayout and pinned PDK from the committed inputs, measured rather than
asserted; and a future off-pin artifact is a build failure rather than a
discovery five days later.

**Does not**: this does not move T1 item 3's or item 4's checkbox. Both
items' pass condition is **full-`pll_top`-assembly** DRC/LVS, and no
assembled `pll_top` GDS exists (`#149`, `loom:blocked`). What moved is the
warrant under the per-block coverage those items already recorded.

~~**Residual, disclosed rather than closed**: the five VCO *sub-cell* logs
(`vco_ring`, `vco_vtoi_core`, `vco_out_buffer`) are still 0.30.9/0.30.10
only. They are supporting evidence for `vco_block`, whose own block-level
verdicts are now on the pin, so the item-3/4 claim does not rest on them —
but "the VCO's evidence is on the pin" is true of the block and not yet of
its sub-cells, and the checker now says so out loud on every run instead of
leaving it to be rediscovered. Two of the five (`lvs-ring`, `lvs-buffer`)
were additionally run at `POLY_RES 1k` rather than this repo's ratified 3k,
so re-running them on the pin is a slightly larger job than re-running the
block was.~~ **— closed 2026-09-30, see Addendum 1.** Struck rather than
deleted, per this repository's append-only evidence convention: the paragraph
records what the pass that wrote it actually left behind, and the record of an
owed job is worth keeping next to the job.

---

# Addendum 1 — the sub-cell residual, closed (2026-09-30, issue #127)

The residual struck above was disclosed on 2026-09-28 and graded by nothing.
That is the distinction this addendum turns on: `OFF_PIN_DISCLOSED` named the
five files and said, correctly, that they were off-pin — but naming a gap is
not checking it. Nothing in the tree would have noticed if those five logs had
been joined by a sixth, or if a regenerated `vco_ring.gds` had left the whole
sub-cell layer of the VCO's evidence describing geometry that no longer
existed. A disclosure that cannot fail is a note, not a guard.

## What was re-run

Same doctrine as Finding 2: from the committed GDS and, for LVS, the committed
reference netlist. Nothing was regenerated first.

Environment (`python3 layout/run_pv.py check-env`), unchanged from Finding 2 —
`~/.volare/gf180mcuD` (variant D, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b`),
`KLayout 0.28.16` = `KNOWN_GOOD_KLAYOUT_VERSION` exactly.

```bash
# for each of vco_ring, vco_vtoi_core, vco_out_buffer
python3 layout/run_pv.py drc layout/evidence/vco-layout/<cell>.gds \
  --top <cell> --run-dir <rundir>
# for each of vco_ring, vco_out_buffer
python3 layout/run_pv.py lvs layout/evidence/vco-layout/<cell>.gds \
  layout/evidence/vco-layout/lvs-<tag>/<cell>.spice \
  --top <cell> --lvs-sub GND_VCO --run-dir <rundir>
```

| cell | check | committed engine | on-pin re-run | wall |
|---|---|---|---|---|
| `vco_ring` | DRC, table `main` | 0.30.9 | `Klayout DRC run is clean. GDS has no DRC violations.` | 10.3 s |
| `vco_vtoi_core` | DRC, table `main` | 0.30.9 | same verdict | 10.0 s |
| `vco_out_buffer` | DRC, table `main` | 0.30.10 | same verdict | 9.9 s |
| `vco_ring` | LVS | 0.30.9, `POLY_RES 1k` | `INFO : Congratulations! Netlists match.`, `POLY_RES Selected is 3k` | 6.7 s |
| `vco_out_buffer` | LVS | 0.30.10, `POLY_RES 1k` | same verdict, `POLY_RES Selected is 3k` | 5.6 s |

**5 of 5 reproduce**, on the pin, at the ratified process option, from the
committed inputs.

The inputs were verified rather than assumed, as Finding 3 requires:
`python3 -m pytest layout/tests/test_gds_reproducibility.py` → **7 passed, 29
subtests passed**, and both sub-cell reference netlists are byte-identical to
what their generators produce today (`vco.ring.reference_netlist()` 1,660 B,
`vco.buffer.reference_netlist()` 806 B). Each match is against the same
schematic, not a co-moved one.

## The `POLY_RES 1k` half was benign, and now that is a measurement

The struck paragraph called the `1k`-vs-ratified-`3k` discrepancy the reason
re-running these two was "a slightly larger job." It was the right worry and
it turned out to be cheap, for a reason worth recording rather than
discovering twice: the deck's `POLY_RES` switch only decides how a **marked**
poly resistor (GDS layer `(62, 0)`) extracts, and neither of these two cells
contains one.

```
>>> for c in ("vco_ring","vco_out_buffer","vco_block","vco_bias_resistors"):
...     (62, 0) in layer_indexes(c)
False   False   True   True
```

So `vco_ring` and `vco_out_buffer` extract identically at `1k` and `3k`, which
the re-run now demonstrates instead of arguing: the extracted device
population is unchanged under `3k`. The two cells that *do* carry the marker
are `vco_block` (already re-derived on the pin at `3k`, Finding 2) and
`vco_bias_resistors`, whose committed DRC log was on the pin already and which
has no LVS run of its own.

## The cross-version signature, for the third and fourth time

Each re-run's extracted `.cir` was compared against the committed one, not
merely its verdict:

| cell | device lines | multiset identical | port set | port **order** |
|---|---|---|---|---|
| `vco_ring` | 20 / 20 (10 `pfet_03v3` + 10 `nfet_03v3`) | **yes** | identical (9) | **differs** |
| `vco_out_buffer` | 6 / 6 (3 `pfet_03v3` + 3 `nfet_03v3`) | **yes** | identical (6) | **differs** |

That is the same signature Finding 2 recorded for `vco_block` and PR `#471`
recorded for `lock_detector` in the opposite direction: identical device
population, identical port *set*, engine-dependent `.SUBCKT` port *order*.
Four blocks/cells now, both directions, same difference — which is why this
addendum treats a port-order difference as expected rather than as a finding.

## The structural half — a per-file disclosure is not a per-cell check

`OFF_PIN_DISCLOSED` is keyed by **file**. That is right for what it does:
excuse one superseded run whose on-pin successor sits beside it. It cannot
express "this *cell*'s verdicts are graded on the pin," and the KLAYOUT PIN
RULE's own cell-level half only ever asked it of the four block tops
(`blocks_spec`). Every sub-cell in the tree was therefore ungraded, and
`vco_ring`/`vco_vtoi_core`/`vco_out_buffer` were the cases where that showed.

The rule is now **per top cell**: any cell for which some committed log states
`Klayout DRC run is clean.` or `Congratulations! Netlists match.` must have at
least one such log on the pin. Cells that are deliberately not graded on the
pin are named, with reasons, in a new `OFF_PIN_TOPCELL_DISCLOSED` —
deliberately a *separate* list from the per-file one, so that disclosing a log
can never silence the cell rule:

| cell | reason |
|---|---|
| `cp_leg_n`, `cp_leg_p` | leaf-cell generator proofs, not a block verdict or its warrant |
| `inv_tb` | DRC/LVS harness bring-up proof (not a PLL block), incl. its fault controls |

All three predate this rule; nothing was added to the list to make the build
pass. The census is a number the script prints, as with the log census above:
**27 graded top cells; 24 with every stated verdict reproduced on the pin, 3
deliberately exempt.** The log census moves with the new artifacts, from
"53 logs, 37 on the pin, 16 off-pin" to **58 logs, 42 on the pin, 16 off-pin**
— the off-pin count is unchanged on purpose, because append-only evidence
keeps every superseded run in the tree.

Four new tests in `layout/tests/test_layout_status_claims.py`, the
load-bearing one being
`test_disclosing_the_sub_cell_log_alone_does_not_silence_the_rule`: it writes
the off-pin sub-cell log at a path that **is** in `OFF_PIN_DISCLOSED`, and
asserts the per-file rule stays quiet while the per-cell rule still fails. If
the generalisation had read the per-file list, that test would pass and this
residual could silently reopen. Mutation-checked: making the new rule
non-fatal fails 2 of the 4.

## What is committed

* `drc-recheck-klayout-0.28.16/` gains `drc-ring.stdout.log`,
  `drc-vtoi-core.stdout.log`, `drc-buffer.stdout.log` and the three matching
  `<cell>_main.lyrdb`.
* `lvs-recheck-klayout-0.28.16/` gains `lvs-ring.stdout.log`,
  `lvs-buffer.stdout.log`, `vco_ring.{cir,lvsdb}`,
  `vco_out_buffer.{cir,lvsdb}`.

The superseded off-pin runs (`drc-clean/drc{,-vtoi-core,-buffer}.stdout.log`,
`lvs-ring/lvs.stdout.log`, `lvs-buffer/lvs.stdout.log`) are **kept**, and
their `OFF_PIN_DISCLOSED` reasons now name the specific on-pin log that
supersedes each one rather than reading "off-pin residual".

## What this addendum does and does not establish

**Does**: every top cell in `layout/evidence/` that states a DRC-clean or
LVS-match verdict now has that verdict on the engine this repository grades
on, or is exempt by name with a reason; and a future ungraded cell is a build
failure rather than a disclosure someone has to remember to revisit.

**Does not**: no checkbox moves. T1 items 3 and 4 both pass on
**full-`pll_top`-assembly** DRC/LVS, and no assembled `pll_top` GDS exists
(`#149`, `loom:blocked` transitively on `#297`). No `.gds` in this repository
changes and no generator changes; this is warrant, not geometry.

**Found and not fixed here** (out of scope, filed as `#671`): seven documents
in this directory state their DRC was run `--offgrid` — "signoff-grade, the
off-grid check class is included, not skipped" — and name, by path, a
committed log that records `Offgrid enabled:  false`. Of the six VCO DRC logs
in `drc-clean/`, exactly one (`drc-mirror.stdout.log`) is genuinely off-grid;
`drc-recheck-klayout-0.28.16/drc.stdout.log`, from Finding 2 above, is
`false` too. The re-runs in this addendum deliberately reproduce the
**committed** invocation — this addendum grades the engine, not the check
class, and changing both at once would make neither comparison clean — so
they neither confirm nor refute the offgrid claim; the new logs record
`Offgrid enabled:  false` and say so. The discrepancy is a prose-vs-artifact
defect of the same genus as the LAYER CENSUS RULE's (issue `#660`) and wants
its own pass, including the guard that would have caught it.
