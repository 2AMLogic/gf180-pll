# spec/

- `pll.md` — the target specification (one row per measured parameter).
- `decision-records/` — numbered decision records (`DR-NNN`); see
  `decision-records/TEMPLATE.md` for the format and ID rules.
- `lib/`, `tests/` — spec tooling and its tests.

## What a decision record's `Status` means

A record's `Status` is that record's own ratification state. It is
independent of the state of `spec/pll.md`, with one grandfathered exception
described below.

| Status | Meaning |
|---|---|
| `proposed` | Drafted on evidence; not binding. Becomes `ratified` only by the two-key ceremony: a builder drafts the record, and the operator's approval of the PR that carries it is the ratifying act. |
| `ratified (date, ref)` | Binding; design and sim work may rely on it. |
| `superseded by DR-NNN` | No longer binding; DR-NNN replaces it. |

A record's `Status` line must say which of these it is and, if `ratified`,
the date and the issue or PR that ratified it.

### The one-time grandfathering of the first ratification (#1)

`spec/pll.md` was ratified through #1 on 2026-09-08, before the two-key
ceremony above was in force for decision records. By operator ruling on #446
(2026-10-02), that ratification also ratified every decision record listed
on `spec/pll.md`'s `**Consumes**:` line **as of 2026-09-08**, except those
that revise the two rows DR-007 Amendment A1 carved out (Lock time, row 9;
Lock detector, row 16).

Covered, and stamped `ratified (2026-09-08, #1; …)`:

| Record | Note |
|---|---|
| DR-001 | Architecture. |
| DR-002 | Scope decisions. Its Decision 5 (jitter) stays `proposed` on its own terms. |
| DR-003 | VCO band map / Kvco contract. |
| DR-005 | Dump-node buffer. |
| DR-006 | Loop filter sizing and trim rule. |
| DR-007 | The spec-review verdict (ratified directly, before this ruling). |

Not covered, and left alone:

| Records | Why |
|---|---|
| DR-010, DR-011 | Created 2026-09-15 (#387), after #1 closed. They were added to `**Consumes**:` later and revise the carved-out row 16 / Lock time section. |
| DR-013, DR-014, and other lock-detector records (DR-015, DR-022, DR-026) | Revise the carved-out row 16. |
| DR-004, DR-008, DR-009, DR-012 | Not on the `**Consumes**:` line; each follows its own ratification route and stays `proposed` until it runs. |
| DR-016 and every later record | Created after 2026-09-08. |

This is a one-time grandfathering of a spec ratification that predates the
two-key ceremony for records. Every record created or amended after
2026-09-08 — including any later amendment to a covered record — goes
through the two-key ceremony. The `**Consumes**:` line of `spec/pll.md`
being extended later does not retroactively ratify a record.
