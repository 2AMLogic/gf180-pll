# gf180-pll — agent instructions

Canary block: an integer-N ring-oscillator PLL on gf180mcu. Apache-2.0.

- **PDK**: gf180mcu (open PDK). Open-source flow: xschem + ngspice for
  design/sim, klayout-tools (`klt`) for layout work.
- **Friction protocol (the canary's job)**: every time klayout-tools is
  awkward, missing a capability, or wrong for what you need, file an issue
  at `2AMLogic/klayout-tools` describing the need generically — describe
  the tool gap, not the design. A tool issue that only makes sense to
  someone who has read this repo's spec is a bad tool issue.
- **Verification is the product**: no claim without a testbench. PVT
  corners on every recorded result. `sim/` results are append-only
  evidence.
- **Publication**: this repo is prepared to be public (#38) — the
  visibility flip itself is an operator action, not an agent one. Write
  every commit message, issue, and document here as if a stranger will
  read it, because one will. Nothing about business positioning,
  commercial terms, or the contents of other 2AM Logic repositories
  belongs in this one.
- Spec changes go through `spec/` with a decision record; agents do not
  relax the ratified spec to make results pass.
- Harness bootstrap: copy the sim-harness pattern from
  `2AMLogic/gf180-bandgap` once it lands there rather than reinventing.
- **Curator — never restate an unchanged conclusion.** Before posting a
  Dependencies re-check / "still blocked" comment, read the most recent prior
  Curator comment on that issue. If your conclusion is identical — same
  blocking issue number(s), same blocker status — post **nothing**: leave the
  issue as-is, still `loom:blocked`. Silence is the correct output of a no-op
  pass. Exception: if that unchanged prior comment is older than 24h, one
  fresh confirmation comment is allowed as a heartbeat on long-stalled work.
  Genuinely *new* information must still be commented — a dependency closed, a
  stale file reference, a scope or blocker change. This rule suppresses
  repetition, never news.
  - Skip: #13's last Curator comment says "blocked on #1
    (`loom:operator-only`), unchanged"; 40 min later #1 is still open and
    nothing else moved → no comment, no label change.
  - Post: #1 has since closed → comment that the spec ratified, drop
    `loom:blocked`, re-curate.
  (Belongs upstream in `rjwalters/loom`'s `curator.md`; it lives here because
  both local copies of that file are installer-managed and get overwritten.)

<!-- BEGIN LOOM ORCHESTRATION -->
This repository uses [Loom](https://github.com/rjwalters/loom) for AI-powered development orchestration — see the Loom repository for the full guide (roles, labels, worktrees, configuration). When installed, Loom also writes a locally-substituted copy of that guide to `.loom/CLAUDE.md`.
<!-- END LOOM ORCHESTRATION -->
<!-- BEGIN REPO-SKILLS -->
This repository has [Repo Skills](https://github.com/rjwalters/repo) v0.8.1 installed —
general repository hygiene and environment commands invoked as `/repo:<command>`. Run
`/repo:help` for the command list, or see `.claude/skills/repo/SKILL.md` for the full
guide. Hygiene commands apply safe, reversible fixes by default and report each
change; run with `--ask` to review first, and `--prune` to allow irreversible
removals. Managed by `install.sh` — edit outside the markers only.
<!-- END REPO-SKILLS -->
