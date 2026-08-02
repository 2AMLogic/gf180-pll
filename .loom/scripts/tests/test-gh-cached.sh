#!/usr/bin/env bash
# test-gh-cached.sh — Tests for the gh-cached TTL cache wrapper (issue #107).
#
# The cache is file-backed under a well-known /tmp path shared by every
# checkout on the host, so its key MUST carry a repo-identifying component.
# Without one, two repositories issuing byte-identical `gh` argv — e.g. the
# Loom queue listing `gh pr list --label=loom:review-requested --state=open
# --limit 500`, which is identical in every Loom-templated repo — collide on
# the same key and one repo is served the other's response.
#
# Covers:
#   a. Baseline: a repeated read in one repo is a cache HIT (one `gh` call).
#   b. Cross-repo isolation: identical argv from two different repos never
#      share an entry, and never serve each other's response.
#   c. Same-repo/different-worktree: a linked worktree still SHARES the main
#      checkout's entries (scope is the resolved remote, not the cwd).
#   d. Scope derivation: ssh/https/bare/GH_REPO spellings of the same repo all
#      normalize to one scope; a local-path remote falls back to path scope.
#   e. Mutation invalidation stays inside the mutating repo's partition.
#   f. --clear-cache is scope-local; --clear-cache --all is host-wide.
#   g. Regression guard: the key is no longer the repo-agnostic
#      sha256(" ".join(args))[:16] that produced the observed collision.
#
# Style matches test-fleet-send.sh — plain bash, hand-rolled assertions.
# Bats is NOT used in this repository.
#
# Usage:
#   bash .loom/scripts/tests/test-gh-cached.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
GH_CACHED="$SCRIPTS_DIR/gh-cached"
PY="${LOOM_PYTHON:-python3}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

pass() {
    TESTS_RUN=$((TESTS_RUN + 1))
    TESTS_PASSED=$((TESTS_PASSED + 1))
    echo -e "  ${GREEN}PASS${NC}: $1"
}
fail() {
    TESTS_RUN=$((TESTS_RUN + 1))
    TESTS_FAILED=$((TESTS_FAILED + 1))
    echo -e "  ${RED}FAIL${NC}: $1"
    [[ -n "${2:-}" ]] && echo "    $2"
}

assert_eq() {
    if [[ "$1" == "$2" ]]; then pass "$3"; else fail "$3" "expected '$1', got '$2'"; fi
}
assert_ne() {
    if [[ "$1" != "$2" ]]; then pass "$3"; else fail "$3" "expected values to differ, both were '$1'"; fi
}
assert_contains() {
    if [[ "$2" == *"$1"* ]]; then pass "$3"; else fail "$3" "expected substring '$1' in '$2'"; fi
}
assert_not_contains() {
    if [[ "$2" != *"$1"* ]]; then pass "$3"; else fail "$3" "unexpected substring '$1' in '$2'"; fi
}

if [[ ! -f "$GH_CACHED" ]]; then
    echo -e "  ${RED}FAIL${NC}: gh-cached not found at $GH_CACHED"
    exit 1
fi
if ! command -v "$PY" >/dev/null 2>&1; then
    echo -e "  ${YELLOW}SKIP${NC}: python3 not available; gh-cached tests need it"
    exit 0
fi
if ! command -v git >/dev/null 2>&1; then
    echo -e "  ${YELLOW}SKIP${NC}: git not available; gh-cached tests need it"
    exit 0
fi

TMPDIR_TEST="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_TEST"' EXIT

CACHE_BASE="$TMPDIR_TEST/gh-cache"
STUB_DIR="$TMPDIR_TEST/bin"
CALLS="$TMPDIR_TEST/gh-calls.log"
mkdir -p "$STUB_DIR"
: >"$CALLS"

# Stub `gh`: records each real invocation and echoes a caller-supplied payload,
# so a cache HIT is observable (no new line in $CALLS) and a contaminated
# response is observable (wrong payload on stdout).
cat >"$STUB_DIR/gh" <<'STUB'
#!/usr/bin/env bash
echo "$*" >>"$GH_STUB_CALLS"
printf '%s\n' "$GH_STUB_PAYLOAD"
exit 0
STUB
chmod +x "$STUB_DIR/gh"

# The exact primary-queue listing every Loom-templated repo issues verbatim —
# this is the argv that collided in the field.
QUEUE_ARGS=(pr list --label=loom:review-requested --state=open --limit 500)

# run_in <dir> <payload> <args...> — invoke gh-cached from <dir> with the stub.
run_in() {
    local dir="$1" payload="$2"
    shift 2
    (
        cd "$dir" || exit 1
        PATH="$STUB_DIR:$PATH" \
        GH_CACHE_DIR="$CACHE_BASE" \
        GH_STUB_CALLS="$CALLS" \
        GH_STUB_PAYLOAD="$payload" \
        "$PY" "$GH_CACHED" "$@" 2>/dev/null
    )
}

# scope_of <dir> [env assignments...] — print the resolved scope string.
scope_of() {
    local dir="$1"
    shift
    (
        cd "$dir" || exit 1
        env "$@" GH_CACHE_DIR="$CACHE_BASE" "$PY" "$GH_CACHED" --cache-scope 2>/dev/null | head -1
    )
}

call_count() { wc -l <"$CALLS" | tr -d ' '; }
entry_count() { find "$CACHE_BASE" -name '*.json' ! -name '_stats.json' 2>/dev/null | wc -l | tr -d ' '; }

# make_repo <dir> <origin-url> [--commit]
make_repo() {
    local dir="$1" url="$2"
    mkdir -p "$dir"
    git -C "$dir" init -q
    git -C "$dir" remote add origin "$url"
    if [[ "${3:-}" == "--commit" ]]; then
        echo seed >"$dir/seed.txt"
        git -C "$dir" add seed.txt
        git -C "$dir" -c user.email=t@example.com -c user.name=Test \
            commit -qm seed
    fi
}

REPO_A="$TMPDIR_TEST/repo-a"
REPO_B="$TMPDIR_TEST/repo-b"
make_repo "$REPO_A" "https://github.com/2AMLogic/repo-alpha.git" --commit
make_repo "$REPO_B" "https://github.com/2AMLogic/repo-beta.git"

echo ""
echo "=== gh-cached: repo-scoped caching ==="
echo ""

# ============================================================
# (a) Baseline — caching still works within a single repo
# ============================================================
echo "-- (a) repeated identical read in one repo is a cache hit --"
before="$(call_count)"
out_a1="$(run_in "$REPO_A" "ALPHA-PAYLOAD" "${QUEUE_ARGS[@]}")"
out_a2="$(run_in "$REPO_A" "ALPHA-PAYLOAD" "${QUEUE_ARGS[@]}")"
after="$(call_count)"
assert_eq "ALPHA-PAYLOAD" "$out_a1" "(a) first read returns the real response"
assert_eq "ALPHA-PAYLOAD" "$out_a2" "(a) second read returns the same response"
assert_eq "1" "$((after - before))" "(a) second read served from cache (one gh call)"

# ============================================================
# (b) Cross-repo isolation — THE bug in issue #107
# ============================================================
echo ""
echo "-- (b) identical argv from a different repo is never served repo A's response --"
before="$(call_count)"
# Payload differs so a contaminated read is unmistakable: if the key were
# repo-agnostic, repo B would receive ALPHA-PAYLOAD from repo A's live entry.
out_b1="$(run_in "$REPO_B" "BETA-PAYLOAD" "${QUEUE_ARGS[@]}")"
after="$(call_count)"
assert_eq "BETA-PAYLOAD" "$out_b1" "(b) repo B gets its OWN response"
assert_not_contains "ALPHA" "$out_b1" "(b) repo B is not served repo A's cached response"
assert_eq "1" "$((after - before))" "(b) repo B's read was a MISS (repo A's entry did not match)"

# Repo A's own entry must still be intact and unpolluted afterwards.
before="$(call_count)"
out_a3="$(run_in "$REPO_A" "ALPHA-PAYLOAD" "${QUEUE_ARGS[@]}")"
after="$(call_count)"
assert_eq "ALPHA-PAYLOAD" "$out_a3" "(b) repo A still gets its own cached response"
assert_eq "0" "$((after - before))" "(b) repo A's entry survived repo B's read (still a hit)"

scope_a="$(scope_of "$REPO_A")"
scope_b="$(scope_of "$REPO_B")"
assert_ne "$scope_a" "$scope_b" "(b) the two repos resolve to different scopes"
assert_eq "repo:github.com/2amlogic/repo-alpha" "$scope_a" "(b) repo A scope is its resolved owner/repo"

dirs="$(find "$CACHE_BASE" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')"
assert_eq "2" "$dirs" "(b) each repo got its own cache partition directory"

# ============================================================
# (c) Same repo, different worktree — must still SHARE the cache
# ============================================================
echo ""
echo "-- (c) a linked worktree of the same repo shares cache entries --"
WT_A="$TMPDIR_TEST/wt-a"
if git -C "$REPO_A" worktree add -q -b wt-branch "$WT_A" >/dev/null 2>&1; then
    scope_wt="$(scope_of "$WT_A")"
    assert_eq "$scope_a" "$scope_wt" "(c) worktree resolves to the SAME scope as its main checkout"

    before="$(call_count)"
    out_wt="$(run_in "$WT_A" "SHOULD-NOT-BE-USED" "${QUEUE_ARGS[@]}")"
    after="$(call_count)"
    assert_eq "ALPHA-PAYLOAD" "$out_wt" "(c) worktree is served the main checkout's cached response"
    assert_eq "0" "$((after - before))" "(c) worktree read was a HIT (no extra gh call)"
else
    fail "(c) could not create a linked worktree fixture"
fi

# ============================================================
# (d) Scope derivation across remote spellings
# ============================================================
echo ""
echo "-- (d) scope derivation normalizes equivalent repo identities --"
REPO_SSH="$TMPDIR_TEST/repo-ssh"
make_repo "$REPO_SSH" "git@github.com:2AMLogic/Repo-Alpha.git"
assert_eq "$scope_a" "$(scope_of "$REPO_SSH")" \
    "(d) ssh remote normalizes to the same scope as the https remote"

REPO_NOSUFFIX="$TMPDIR_TEST/repo-nosuffix"
make_repo "$REPO_NOSUFFIX" "https://github.com/2AMLogic/repo-alpha"
assert_eq "$scope_a" "$(scope_of "$REPO_NOSUFFIX")" \
    "(d) missing .git suffix normalizes to the same scope"

assert_eq "repo:github.com/2amlogic/repo-beta" \
    "$(scope_of "$REPO_A" GH_REPO=2AMLogic/repo-beta)" \
    "(d) GH_REPO overrides the git remote (matching gh's own precedence)"
assert_eq "repo:example.com/o/r" \
    "$(scope_of "$REPO_A" GH_REPO=example.com/o/r)" \
    "(d) GH_REPO accepts HOST/OWNER/REPO"
assert_eq "repo:gitea.example.com/2amlogic/repo-alpha" \
    "$(scope_of "$REPO_A" GH_HOST=gitea.example.com GH_REPO=2AMLogic/repo-alpha)" \
    "(d) GH_HOST distinguishes same-name repos on different forges"

# A local filesystem remote is not an owner/repo identity — fall back to a
# per-checkout path scope rather than inventing an owner/repo from directory
# names (which two unrelated local repos could share).
REPO_LOCAL1="$TMPDIR_TEST/local1/srv/mirrors/thing"
REPO_LOCAL2="$TMPDIR_TEST/local2/srv/mirrors/thing"
make_repo "$REPO_LOCAL1" "/srv/mirrors/thing.git"
make_repo "$REPO_LOCAL2" "/srv/mirrors/thing.git"
scope_l1="$(scope_of "$REPO_LOCAL1")"
scope_l2="$(scope_of "$REPO_LOCAL2")"
assert_contains "path:" "$scope_l1" "(d) local-path remote falls back to a path scope"
assert_ne "$scope_l1" "$scope_l2" \
    "(d) two unrelated local-path repos with identical remote strings stay isolated"

REPO_NOREMOTE="$TMPDIR_TEST/repo-noremote"
mkdir -p "$REPO_NOREMOTE"
git -C "$REPO_NOREMOTE" init -q
assert_contains "path:" "$(scope_of "$REPO_NOREMOTE")" \
    "(d) a repo with no remote falls back to a path scope"

# ============================================================
# (e) Mutation invalidation stays inside the mutating repo
# ============================================================
echo ""
echo "-- (e) a mutation in one repo does not invalidate another repo's entries --"
run_in "$REPO_A" "ALPHA-ISSUE-42" issue view 42 --json labels >/dev/null
run_in "$REPO_B" "BETA-ISSUE-42" issue view 42 --json labels >/dev/null
run_in "$REPO_A" "edited" issue edit 42 --add-label bug >/dev/null

before="$(call_count)"
out_b_after="$(run_in "$REPO_B" "BETA-ISSUE-42-REFETCHED" issue view 42 --json labels)"
after="$(call_count)"
assert_eq "BETA-ISSUE-42" "$out_b_after" "(e) repo B's entry survived repo A's mutation"
assert_eq "0" "$((after - before))" "(e) repo B still hits its cache after repo A's mutation"

before="$(call_count)"
out_a_after="$(run_in "$REPO_A" "ALPHA-ISSUE-42-REFETCHED" issue view 42 --json labels)"
after="$(call_count)"
assert_eq "ALPHA-ISSUE-42-REFETCHED" "$out_a_after" "(e) repo A's own entry WAS invalidated by its mutation"
assert_eq "1" "$((after - before))" "(e) repo A re-fetched after its own mutation"

# ============================================================
# (f) --clear-cache scoping
# ============================================================
echo ""
echo "-- (f) --clear-cache is scope-local; --clear-cache --all is host-wide --"
run_in "$REPO_A" "unused" --clear-cache >/dev/null
a_entries="$(find "$CACHE_BASE"/*repo-alpha* -name '*.json' ! -name '_stats.json' 2>/dev/null | wc -l | tr -d ' ')"
b_entries="$(find "$CACHE_BASE"/*repo-beta* -name '*.json' ! -name '_stats.json' 2>/dev/null | wc -l | tr -d ' ')"
assert_eq "0" "$a_entries" "(f) --clear-cache emptied the invoking repo's partition"
[[ "$b_entries" -gt 0 ]] && pass "(f) --clear-cache left the other repo's entries alone" \
    || fail "(f) --clear-cache left the other repo's entries alone" "repo B partition was emptied too"

# A pre-repo-scoping leftover: an un-partitioned entry sitting directly in the
# base dir. It is never read any more, but --all should still sweep it.
echo '{}' >"$CACHE_BASE/102901682669d3f8.json"
run_in "$REPO_A" "unused" --clear-cache --all >/dev/null
assert_eq "0" "$(entry_count)" "(f) --clear-cache --all emptied every partition"
[[ -f "$CACHE_BASE/102901682669d3f8.json" ]] \
    && fail "(f) --clear-cache --all sweeps legacy un-partitioned entries" "legacy entry still present" \
    || pass "(f) --clear-cache --all sweeps legacy un-partitioned entries"

# ============================================================
# (g) Regression guard — the key is no longer repo-agnostic
# ============================================================
echo ""
echo "-- (g) cache key includes the repo scope --"
# The field collision produced /tmp/gh-cache/102901682669d3f8.json, i.e.
# sha256(" ".join(args))[:16] with no repo component. Assert (1) that legacy
# derivation is not what the key function computes, and (2) that the same argv
# under two scopes yields two different keys.
legacy="$("$PY" - <<'PYEOF'
import hashlib
print(hashlib.sha256(
    "pr list --label=loom:review-requested --state=open --limit 500".encode()
).hexdigest()[:16])
PYEOF
)"
assert_eq "102901682669d3f8" "$legacy" "(g) reproduced the legacy (repo-agnostic) key from the field report"

keys="$(GH_CACHED_PATH="$GH_CACHED" "$PY" - <<'PYEOF'
import importlib.util, os, sys

args = ["pr", "list", "--label=loom:review-requested", "--state=open", "--limit", "500"]
out = []
for scope in ("github.com/owner/alpha", "github.com/owner/beta"):
    os.environ["GH_CACHE_SCOPE"] = scope
    spec = importlib.util.spec_from_loader(
        "ghcached", importlib.machinery.SourceFileLoader(
            "ghcached", os.environ["GH_CACHED_PATH"]))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    out.append(mod.cache_key(args))
print(" ".join(out))
PYEOF
)"
key1="${keys%% *}"
key2="${keys##* }"
assert_ne "$key1" "$key2" "(g) identical argv under two scopes produce different keys"
assert_ne "$legacy" "$key1" "(g) key is no longer the legacy repo-agnostic digest"

# ============================================================
# Summary
# ============================================================
echo ""
echo "========================================"
echo "Test Results:"
echo "  Total:  $TESTS_RUN"
echo -e "  ${GREEN}Passed: $TESTS_PASSED${NC}"
if [[ "$TESTS_FAILED" -gt 0 ]]; then
    echo -e "  ${RED}Failed: $TESTS_FAILED${NC}"
    exit 1
fi
echo -e "  ${GREEN}All tests passed!${NC}"
