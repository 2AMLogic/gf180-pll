#!/usr/bin/env bash
#
# Fails if a manifest under manifests/artifacts/ is malformed, names a
# non-`artifact:` location, or lists an object whose bytes are also committed
# (issue #830). Logic lives in check_artifact_manifests.py; this is the
# family-conventional entry point.
#
# Usage: sim/lib/check-artifact-manifests.sh
# Exit codes: 0 clean, 1 violation.

set -uo pipefail
exec python3 "$(dirname "${BASH_SOURCE[0]}")/check_artifact_manifests.py" "$@"
