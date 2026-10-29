# Artifact manifests

Raw sim and signoff output for new runs is stored in the fleet artifact store,
not in git. Git keeps one manifest per run here, plus the usual Markdown
summary record. Evidence bytes are private; a manifest only names objects by
size and sha256, so it is safe to commit to a public repository.

## Writing one

```bash
sim/lib/artifact-put.sh <bench> <run-id> <file>...
```

Stage the files in `sim/.artifact-stage/` (git-ignored) or anywhere else. This
runs `klt artifact put --manifest manifests/artifacts/<bench>-<run-id>.manifest.json`
and requires `$KLT_ARTIFACT_BROKER` (set for agent sessions on fleet workers).
It fails closed: broker unset (exit 3), `klt` without `artifact put` (exit 4),
or an unreachable broker (klt's status) all leave no manifest and never fall
back to committing bytes.

Check one against the store with `klt artifact verify <manifest>` (needs the
broker, so it is run by hand on a fleet worker, not in CI).

## Format (`schema_version` 1)

```json
{
  "schema_version": 1,
  "entries": [
    {
      "sha256": "<64 lowercase hex>",
      "size": 1234,
      "kind": "evidence",
      "producer": {"tool": "klt", "version": "…", "loom.repo": "owner/name", "commit": "<sha>"},
      "uri": "artifact:<key>",
      "name": "optional/path",
      "media_type": "optional"
    }
  ]
}
```

Never write a storage location (bucket, endpoint, account id, or any non-`artifact:` URI)
into this directory.

## CI

`sim/lib/check-artifact-manifests.sh` validates the schema, requires every
`uri` to start with `artifact:`, and fails if any tracked file's sha256 equals
a stored object's. Tests: `sim/tests/test_artifact_manifests.py`.

## Scope

Manifest-forward only. Evidence committed before this existed stays where it is.
