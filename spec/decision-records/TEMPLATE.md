# DR-000: <short title>

<!--
USAGE NOTE — read before filing a decision record.

Copy this file to spec/decision-records/DR-NNN-<slug>.md and fill it in.
DR-NNN is zero-padded to three digits (DR-001, DR-002, ... DR-010, ...).
This is the ONLY filename/numbering convention for this directory — do not
invent a variant.

A decision record is required for every spec change (CLAUDE.md: "Spec
changes go through spec/ with a decision record"). One decision per record;
keep it to one page.

Numbering / collision rule:
  - NNN is the next unused number AT MERGE TIME, not at the time you started
    writing the record. Two records racing for the same number is a real
    failure mode (it has already happened once in a sister repo), so:
  - Immediately before opening the PR, and again after any rebase onto a
    moved main, re-check spec/decision-records/ for the current highest NNN
    and renumber your record if another record claimed it first.
  - Reviewers MUST reject a PR that introduces a duplicate NNN.

Stable ID rule:
  - DR-NNN is the permanent, stable identifier for the decision. Reference
    it from issues and from sim/ evidence records exactly as "DR-NNN"
    (e.g. "see DR-003", "invalidated by DR-007") so the reference survives
    any later rewording of the record's title or slug.

Status lifecycle (the Status field below):
  - proposed            — drafted, not yet binding on design work.
  - ratified            — binding; design/sim work may rely on it.
  - superseded by DR-NNN — no longer binding; DR-NNN replaces it.

Append-only / never-rewrite rule:
  - Do NOT delete or rewrite a ratified record, even to fix it. If a
    ratified decision changes or was wrong, write a NEW record that states
    "superseded by DR-NNN" is now filled in as the pointer FROM the old
    record TO the new one, and the new record's Context should say what it
    revises. This mirrors the sim/ evidence-record convention (#5), which
    uses a `Supersedes` field with the same never-rewrite semantics — a
    decision record and the evidence record that exercises it should always
    be traceable to each other through IDs, never through an edited-in-place
    history.

Provenance:
  - Adapted from 2AMLogic/gf180-bandgap `spec/decision-records/TEMPLATE.md`
    at commit d40bd5de98e355c93137df0bfd8b46ce43766db4 (fetched directly via
    the GitHub API, byte-for-byte source confirmed reachable — not a
    from-memory reconstruction). Deviations from that source are additive
    only: this usage-note header is expanded with the explicit collision
    rule, the stable-ID rule, and the sim/ (#5) cross-reference; the field
    set and body sections (Status/Date/Decided by, Context, Decision,
    Alternatives considered, Consequences) are unchanged.
-->

- **Status**: proposed | ratified | superseded by DR-NNN
- **Date**: YYYY-MM-DD
- **Decided by**: <name / role>

## Context

What forced this decision? One short paragraph: the constraint, the
measurement, or the conflict that made the current spec inadequate. Link to
the issue, the simulation evidence in `sim/`, or the prior record it revises.

## Decision

The decision, stated as a change to the spec — the parameter and its new
value, or the approach now ratified. Be specific enough that design work can
lock to it without further interpretation.

## Alternatives considered

- **<alternative>** — why it was not chosen.
- **<alternative>** — why it was not chosen.

## Consequences

What follows from this: what becomes possible, what becomes harder, which
testbenches or corner sets change, what work is invalidated or must be
re-run. Include the bad consequences, not just the good ones.
