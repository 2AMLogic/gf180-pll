#!/usr/bin/env bash
# Render this block's T1 tier verdict with `klt signoff --manifest`, and
# either write it to signoff/tier-report.json or verify the committed copy
# still matches.
#
#   bash signoff/run-signoff.sh           # regenerate signoff/tier-report.json
#   bash signoff/run-signoff.sh --check   # fail if the committed report is stale
#
# The --check mode is what CI runs. It is the whole point of committing the
# report: a manifest that cites an evidence artifact which has since changed
# (a re-run DRC, an edited netlist, a moved file) re-renders differently, and
# the diff fails the build instead of the verdict quietly rotting.
#
# Run from anywhere; paths below are resolved against the repo root, and `klt`
# is invoked *from* the repo root so that relative evidence paths inside the
# manifest mean the same thing here, in CI, and on a reviewer's machine.
#
# Exit codes:
#   0  the report was written (default mode), or matches (--check)
#   1  the committed report is stale (--check), or the manifest is bad
#   2  `klt` is not installed, or the `klt` on PATH is not the version
#      .github/workflows/ci.yml pins (see "The version pin" below)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANIFEST="signoff/block-manifest.json"
REPORT="signoff/tier-report.json"

# The single source of truth for which klt this repository's signoff report
# is rendered on. Read below, never restated here -- the same doctrine
# layout/lib/check-layout-status-claims.sh's ERC rule uses for the same pin.
CI_WORKFLOW=".github/workflows/ci.yml"

mode="write"
case "${1-}" in
  "") ;;
  --check) mode="check" ;;
  -h | --help)
    sed -n '2,22p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    exit 0
    ;;
  *)
    echo "error: unknown argument '$1' (expected --check or nothing)" >&2
    exit 1
    ;;
esac

cd "$REPO_ROOT"

# --- The version pin -------------------------------------------------------
#
# The pin CI installs, read out of the workflow rather than restated here, so
# a pin bump needs no edit in this file and cannot disagree with it.
PIN=""
if [ -f "$CI_WORKFLOW" ]; then
  PIN="$(grep -oE "klayout-tools==[0-9][^'\"[:space:]]*" "$CI_WORKFLOW" |
    head -n 1 | sed 's/^klayout-tools==//' || true)"
fi

if [ -z "$PIN" ]; then
  echo "error: $CI_WORKFLOW names no 'klayout-tools==<version>' pin, so the" >&2
  echo "       klt this report must be rendered on cannot be determined." >&2
  echo "       That pin is this repository's only source of truth for it --" >&2
  echo "       see the 'Install klt (klayout-tools)' step in that workflow." >&2
  exit 2
fi

if ! command -v klt >/dev/null 2>&1; then
  echo "error: klt not found on PATH -- install it with:" >&2
  echo "         pip install 'klayout-tools==${PIN}'" >&2
  echo "       (https://github.com/2AMLogic/klayout-tools)" >&2
  echo "       (that version is read from $CI_WORKFLOW, which is what CI" >&2
  echo "       actually pins)" >&2
  exit 2
fi

KLT_VERSION="$(klt --version 2>&1 | head -n 1 | tr -d '\r')"

# Exact equality, not a prefix match, and against the whole `klt <version>`
# line. `klt signoff` embeds its own build identity in the rendered report
# (build.version, git_commit, git_tag, is_release, grading_ruleset_id), and a
# post-tag source build differs from the released wheel in every one of those
# fields -- so rendering on one and comparing against the other made --check
# report a current report as stale, with nothing in the message to say that
# the tool, not the evidence, was what had moved (issue #630). Prefix-matching
# here would accept exactly the build that causes it: this is the same
# `0.6.0` vs `0.6.0+g<sha>` discriminator issue #127 tightened on the
# ERC-report side of the repository, where it surfaced as a false *pass*.
if [ "$KLT_VERSION" != "klt ${PIN}" ]; then
  echo "error: the klt on PATH is not the version this repository pins." >&2
  echo "         found:  ${KLT_VERSION}  ($(command -v klt))" >&2
  echo "         pinned: klt ${PIN}  (klayout-tools==${PIN}, from $CI_WORKFLOW)" >&2
  echo >&2
  echo "       \`klt signoff\` records its own build identity in the report" >&2
  echo "       it renders, so a different klt renders a different report:" >&2
  echo "       $REPORT would be re-rendered against the wrong tool, and" >&2
  echo "       --check would call a current report stale." >&2
  echo >&2
  echo "       A \`${PIN}+g<sha>\` suffix is a PEP 440 *local version*: a" >&2
  echo "       source build of the klayout-tools tree AFTER the v${PIN} tag," >&2
  echo "       not the released wheel (is_release: false, git_tag: null)." >&2
  echo "       The released wheel prints exactly \`klt ${PIN}\`, and" >&2
  echo "       \`pip show klayout-tools\` cannot tell the two apart -- a" >&2
  echo "       source build in ~/.local/bin shadows the wheel on PATH." >&2
  echo >&2
  echo "       Run against the pinned release instead:" >&2
  echo "         uvx --from 'klayout-tools==${PIN}' klt --version   # must print: klt ${PIN}" >&2
  echo "       or, since this script needs klt on PATH, a throwaway venv:" >&2
  echo "         python3 -m venv /tmp/klt-pinned" >&2
  echo "         /tmp/klt-pinned/bin/pip install 'klayout-tools==${PIN}'" >&2
  echo "         PATH=/tmp/klt-pinned/bin:\$PATH bash signoff/run-signoff.sh${1:+ $1}" >&2
  echo "       (signoff/README.md, 'Reproducing', documents both routes)" >&2
  exit 2
fi

echo "klt: $(command -v klt) (${KLT_VERSION}, the pinned release)" >&2

# No --tiers-doc: the report is graded against the checklist bundled inside
# the pinned `klt` release itself (klt 0.6.0 bundles all eleven T1 items), so
# the report's `source_doc_content_hash` is that bundled checklist's hash. A
# klt pin bump that ships an amended checklist therefore changes the rendered
# report and fails --check until someone re-renders it -- which is the moment
# to re-read the checklist diff (signoff/README.md, issue #564).
#
# `klt signoff --manifest` exits 3 when the block is not yet T1 -- which is
# the expected, honest state of this block today (see signoff/README.md). Only
# 0 (T1 reached) and 3 (not yet T1) are verdicts; anything else is a tool or
# input error and must not be written out as if it were a report.
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
status=0
klt signoff \
  --manifest "$MANIFEST" \
  --format json >"$tmp" || status=$?

case "$status" in
  0 | 3) ;;
  *)
    echo "error: klt signoff exited $status -- not a tier verdict" >&2
    cat "$tmp" >&2
    exit 1
    ;;
esac

# Says whether the only thing that moved between the committed report and the
# freshly rendered one is klt's own `build` block -- its version, git commit,
# dirty flag and grading_ruleset_id. A bare "stale" says nothing about which
# half moved, and the two halves want opposite responses: a verdict that
# moved is evidence to go read, while a build block that moved on its own is
# the tool having been replaced underneath an unchanged verdict. The version
# check above catches the common cause of the second (issue #630); this note
# covers what it cannot -- two builds reporting the same version string.
# Advisory only: it never changes the exit status, and it is skipped silently
# where python3 is absent (this script otherwise needs none).
tool_only_diff_note() {
  command -v python3 >/dev/null 2>&1 || return 0
  python3 - "$REPORT" "$tmp" "$CI_WORKFLOW" <<'PY' >&2 || true
import json
import sys

committed_path, rendered_path, ci_workflow = sys.argv[1], sys.argv[2], sys.argv[3]

try:
    with open(committed_path, encoding="utf-8") as fh:
        committed = json.load(fh)
    with open(rendered_path, encoding="utf-8") as fh:
        rendered = json.load(fh)
except (OSError, ValueError):
    sys.exit(0)

if not isinstance(committed, dict) or not isinstance(rendered, dict):
    sys.exit(0)

moved = sorted(
    key
    for key in set(committed) | set(rendered)
    if committed.get(key, KeyError) != rendered.get(key, KeyError)
)
if moved != ["build"]:
    sys.exit(0)

committed_build = committed.get("build") or {}
rendered_build = rendered.get("build") or {}
fields = sorted(
    key
    for key in set(committed_build) | set(rendered_build)
    if committed_build.get(key, KeyError) != rendered_build.get(key, KeyError)
)
sys.stderr.write(
    "       Note: the only top-level key that differs is the report's own\n"
    "       `build` block (%s) -- klt's build identity,\n"
    "       not this block's evidence: no T1 verdict changed. The tool moved\n"
    "       underneath an unchanged verdict (a klt built from source, or a\n"
    "       re-released wheel, records a different build identity for the same\n"
    "       grading). Re-render only if this klt is the one %s pins.\n"
    % (", ".join(fields), ci_workflow)
)
PY
}

if [ "$mode" = "check" ]; then
  if ! diff -u "$REPORT" "$tmp"; then
    echo >&2
    echo "error: $REPORT is stale -- re-render it with:" >&2
    echo "         bash signoff/run-signoff.sh" >&2
    echo "       and read signoff/README.md before updating any claim it backs." >&2
    tool_only_diff_note
    exit 1
  fi
  echo "$REPORT is current." >&2
  exit 0
fi

cp "$tmp" "$REPORT"
echo "wrote $REPORT" >&2
