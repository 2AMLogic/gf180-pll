#!/usr/bin/env bash
#
# Fails if a measured number quoted in the Chipalooza proposal's spec table is
# not the number the cited record's committed per-corner evidence produces
# (issue #237). Logic lives in check_quoted_value_provenance.py; this is the
# family-conventional entry point.
#
# Usage: sim/lib/check-quoted-value-provenance.sh
# Exit codes: 0 every graded value re-derives, every derived figure follows
#             from its reduction and its ratified constant, every relative
#             figure follows from two reductions that are themselves graded,
#             every section 5 row is accounted for, every disclosed
#             ungraded figure is still in its row, and every count this check
#             prints about itself is the count section 5.1 narrates;
#             1 any rule above is violated, a table is missing or empty, or the
#             section 5 table cannot be parsed (a broken parser must not look
#             like a clean tree).

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

PROPOSAL="docs/chipalooza/challenge-5-proposal.md"
SPEC="spec/pll.md"

if ! command -v python3 >/dev/null 2>&1; then
  echo "FAIL: python3 is not on PATH -- this check could not run, and a" \
    "check that did not run is not a check that passed" >&2
  exit 1
fi

PYTHONPATH="${REPO_ROOT}/lib${PYTHONPATH:+:${PYTHONPATH}}" \
  exec python3 "$(dirname "${BASH_SOURCE[0]}")/check_quoted_value_provenance.py" \
  "${REPO_ROOT}" "${PROPOSAL}" "${SPEC}"
