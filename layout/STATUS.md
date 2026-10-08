# Layout status narrative

Long-form status of the PLL-block layout work, moved here verbatim from the
`README.md` status section so the front page can stay a scannable summary. The
block counts below are graded against `layout/evidence/` in CI by
`layout/lib/check-layout-status-claims.sh`; the campaign-side narrative is in
[`sim/STATUS.md`](../sim/STATUS.md).

- **Underway, block by block** — PLL-block layout. Issue #16 landed a
  repeatable `klt`-aware DRC/LVS flow against the gf180mcu open-PDK decks,
  proven clean (and proven to catch a deliberately injected DRC violation and
  LVS mismatch) on a trivial standard-cell inverter
  (`layout/evidence/inv-tb-proof/PROOF.md`). Real transistor-level layout has
  since been drawn against that flow: **4 of the 4 PLL sub-blocks** — the VCO
  (#293), the PFD + charge pump (#294), the divider chain (#295), and the lock
  detector (#296) — now have a committed block GDS with a DRC-clean deck log
  under `layout/evidence/`, and **4 of the 4 are LVS-matched** against an
  independently derived reference netlist (`vco_block`, `divider_chain`,
  `pfd_cp` and, since issue #449 drew DR-014's 4-bit trim network into its
  delay cell, `lock_detector`). There is **no assembled `pll_top`
  GDS** — the four blocks exist side by side, not wired into a top level, so
  no top-level DRC/LVS closure and no post-layout extracted-netlist
  re-verification exists either (#17, #18, #149). These counts are checked
  against the evidence tree in CI by
  `layout/lib/check-layout-status-claims.sh`, so this paragraph cannot
  silently go stale the way its predecessor did.
