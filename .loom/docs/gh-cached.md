# gh-cached — TTL cache wrapper for the GitHub CLI

`.loom/scripts/gh-cached` is a drop-in `gh` replacement that caches read-only
responses (`view` / `list` / `search` / `status`, and `gh api` GETs) to a
file-backed cache, so the many roles in a sweep don't re-issue the same
queries against the API. Mutations (`edit`, `create`, `comment`, …) bypass the
cache and invalidate related entries.

The cache is file-backed under `/tmp/gh-cache/` rather than in-process, so
separate role processes running concurrently **against the same repository**
hit the same entries.

## Repo scoping (the isolation guarantee)

Because the cache lives at a well-known `/tmp` path shared by every checkout on
the host, entries are **partitioned per target repository**:

- Entries live in `/tmp/gh-cache/<repo-slug>/`, not directly in the base dir.
- The resolved repo scope is also mixed into the cache key itself, so identical
  argv from two repositories cannot collide even if the partition directories
  are bypassed.
- Eviction (`GH_CACHE_MAX_SIZE`), mutation invalidation, hit/miss stats, and
  `--clear-cache` are consequently all per-repo as well.

This matters because the Loom queue listings are byte-identical in every
templated repo — e.g. `gh pr list --label=loom:review-requested --state=open
--limit 500`. Before scoping, two repos issuing that command within the TTL
window shared one key and one could be served the other's response (issue
#107, observed live 2026-08-02).

**Two worktrees of the same repository still share entries.** The scope is the
*resolved repository identity*, not the working directory, so a Builder in
`.loom/worktrees/issue-N` gets the same cache hits as the main checkout.

### How the scope is resolved

Resolution is subprocess-free — it reads git's own config files, costing
microseconds rather than the hundreds of milliseconds a `gh repo view` would
add to every call (which would defeat the point of a cache that exists to be
faster than invoking `gh`). It is recomputed per process from the live cwd, so
it cannot go stale across a `cd`. Precedence mirrors `gh`'s own:

1. `GH_CACHE_SCOPE` — explicit override (advanced / testing).
2. `GH_REPO` (`OWNER/REPO`, `HOST/OWNER/REPO`, or a URL), with `GH_HOST` as the
   default host.
3. The git remote of the cwd's repository, read from the *common* git dir so
   every linked worktree resolves identically. Remote preference matches `gh`:
   an explicit `gh-resolved = base` marker, then `upstream`, `github`,
   `origin`, then the first remaining remote by name.
4. The git common dir path, when the repo has no usable remote.
5. The cwd, when not inside a git repository at all.

Levels 4 and 5 are coarser but never shared: an unidentifiable checkout gets
its own partition rather than falling into a common one where it could collide
with another unidentifiable checkout. Equivalent spellings of the same repo
(`git@github.com:Owner/Repo.git`, `https://github.com/owner/repo`, with or
without `.git`) normalize to one scope; a local filesystem remote is treated as
a path scope rather than an invented `owner/repo`.

## Usage

```bash
gh-cached issue view 42 --json labels
gh-cached pr list --label "loom:review-requested" --state open
gh-cached --no-cache issue view 42 --json labels   # bypass the cache
gh-cached --cache-scope                            # print scope + partition dir
gh-cached --cache-stats                            # hit/miss stats for this repo
gh-cached --clear-cache                            # clear this repo's entries
gh-cached --clear-cache --all                      # clear every repo's entries
```

`--clear-cache --all` also sweeps any un-partitioned entries left directly in
the base dir by a pre-scoping version of this script. Those are never read any
more, so stale ones are inert, but they are exactly the cross-repo-contaminated
entries worth removing.

## Environment

| Variable | Default | Purpose |
|---|---|---|
| `GH_CACHE_DIR` | `/tmp/gh-cache` | Cache **base** dir; per-repo partitions are created underneath |
| `GH_CACHE_TTL` | `30` | Default TTL in seconds |
| `GH_CACHE_MAX_SIZE` | `256` | Max cached entries, per repo |
| `GH_CACHE_DISABLE` | unset | `1` disables caching entirely |
| `GH_CACHE_DEBUG` | unset | `1` logs scope/hit/miss/evict to stderr |
| `GH_CACHE_SCOPE` | unset | Forces the repo scope (advanced / testing) |
| `GH_REPO`, `GH_HOST` | unset | Honored when resolving the scope, as `gh` does |

## Tests

```bash
bash .loom/scripts/tests/test-gh-cached.sh
```

Covers baseline caching, cross-repo isolation, same-repo/different-worktree
sharing, scope derivation across remote spellings, per-repo invalidation,
`--clear-cache` scoping, and a regression guard that the key is no longer the
repo-agnostic `sha256(" ".join(args))[:16]`.

## Consumers

`.loom/scripts/merge-pr.sh` uses `gh-cached` for read-only queries when it is
executable, falling back to plain `gh` otherwise;
`.loom/scripts/lib/forge-helpers.sh` passes `--no-cache` through the wrapper
only (it is a wrapper flag, not a real `gh` flag) for reads that must not be
served stale.
