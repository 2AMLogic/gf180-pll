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
  delay cell, `lock_detector`). Since issue #297 the **assembled `pll_top`
  GDS** is committed too: the four blocks plus the physical loop filter
  (#748), placed and wired against `design/netlist/pll_top.spice`, with the
  wiring checked from the exported file
  (`layout/evidence/pll-top-layout/PROOF.md`). It is **not signoff**: the
  foundry DRC deck reports one violation, the `MIMTM.3` the loop filter's C2
  already carried (#753); top-level LVS is still to run (#149);
  extracted-netlist re-verification is still to run (#18); and the measured
  0.4078 mm² is over the ratified 0.30 mm² area row. These counts are checked
  against the evidence tree in CI by
  `layout/lib/check-layout-status-claims.sh`, so this paragraph cannot
  silently go stale the way its predecessor did.
