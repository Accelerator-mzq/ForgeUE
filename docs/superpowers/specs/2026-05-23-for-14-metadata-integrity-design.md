# FOR-14 Metadata Integrity Design

Date: 2026-05-23

Issue: Linear FOR-14 `metadata-corruption-detection`

Status: user-approved design, awaiting written-spec review

## Problem

`_artifacts.json` is the resume cache trust root for Artifact metadata.
ForgeUE already protects file/blob payload bytes during `load_run_metadata` by
checking backend existence and current payload hash. That does not protect the
metadata file itself.

The current gap is:

- Inline payloads travel inside `_artifacts.json`, so changing the inline value
  and matching hash inside the same file can still look self-consistent.
- Metadata fields such as `artifact_id`, `hash`, `payload_ref`, lineage, tags,
  and schema fields can be changed before resume.
- A schema-valid but semantically changed `_artifacts.json` may allow a wrong
  cache hit, or hide the real reason a cache hit disappeared.

FOR-14 therefore treats `_artifacts.json` integrity as a separate trust-boundary
problem from file/blob payload drift.

## Decision

Implement the companion checksum file design.

After `ArtifactRepository.dump_run_metadata()` writes `{run_dir}/_artifacts.json`,
it also writes `{run_dir}/_artifacts.integrity.json`. On resume,
`ArtifactRepository.load_run_metadata()` verifies the integrity file before
parsing Artifact records whenever the integrity file exists.

Integrity mismatch fails fast by raising a dedicated
`ArtifactMetadataIntegrityError`. It does not silently skip entries or fall back
to re-execution.

Legacy run directories that only have `_artifacts.json` and no integrity file
remain loadable. Resume reads must not backfill or mutate legacy metadata.

## File Format

`_artifacts.integrity.json` contains a small JSON object:

```json
{
  "schema_version": "1.0",
  "artifacts_file": "_artifacts.json",
  "algorithm": "sha256",
  "artifacts_sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "artifact_count": 3,
  "artifact_ids": ["a1", "a2", "a3"]
}
```

Field rules:

- `schema_version` must equal `"1.0"` for this implementation.
- `artifacts_file` must equal `"_artifacts.json"`.
- `algorithm` must equal `"sha256"`.
- `artifacts_sha256` is computed with the existing bounded-RSS `hash_path`
  helper over the final `_artifacts.json` bytes.
- `artifact_count` equals the number of dumped artifacts.
- `artifact_ids` preserves the dumped artifact order from `_artifacts.json`.

This deliberately binds the final file bytes, not a custom per-record canonical
form. It is simpler and catches any manual file edit, including whitespace,
field, order, entry, and inline payload changes.

## Runtime Flow

Dump flow:

1. `dump_run_metadata(run_id, run_dir)` gathers artifacts via
   `find_by_producer(run_id=run_id)`.
2. It writes `_artifacts.json` exactly as it does today.
3. It hashes the written `_artifacts.json` with `hash_path`.
4. It writes `_artifacts.integrity.json` with the metadata above.

Load flow:

1. If `_artifacts.json` is absent, return `0` as today.
2. If `_artifacts.integrity.json` is absent, use the existing legacy load path.
3. If `_artifacts.integrity.json` exists, verify it first.
4. If verification fails, raise `ArtifactMetadataIntegrityError`.
5. If verification passes, continue with the existing three filters:
   already-known id skip, backend `exists()` skip, file/blob payload hash drift
   skip.

`framework.run --resume` should not catch this new exception. The CLI should
fail clearly so the operator sees that resume metadata is corrupt instead of
getting a misleading cache miss.

## Scope

In scope:

- Add the integrity file writer and verifier in
  `src/framework/artifact_store/repository.py`.
- Add `ArtifactMetadataIntegrityError`.
- Preserve legacy directories with no integrity file.
- Keep existing file/blob payload drift checks unchanged.
- Add regression tests for normal load, inline metadata tamper,
  `artifact_id` tamper, corrupt integrity JSON, and legacy compatibility.
- Update artifact/runtime contracts, SRS/testing/acceptance docs, CHANGELOG, and
  backlog closeout during implementation.

Out of scope:

- HMAC signatures, hash chains, key management, or malicious-forger resistance.
- Auto-repairing corrupt metadata.
- Backfilling integrity files from resume read paths.
- Changing `PayloadRef` schema.
- Changing file/blob payload drift behavior.

## Error Handling

`ArtifactMetadataIntegrityError` should include the run directory and a concise
reason, such as:

- integrity file is invalid JSON
- unsupported integrity schema version
- unexpected integrity file target
- algorithm is not sha256
- `_artifacts.json` hash mismatch
- artifact count mismatch
- artifact id list mismatch

All of these are fail-fast resume errors because the metadata trust root is no
longer reliable.

## Tests

Primary tests should live near existing ArtifactRepository coverage:

- `test_dump_run_metadata_writes_integrity_file`
- `test_load_run_metadata_verifies_integrity_before_registering`
- `test_load_run_metadata_fails_fast_when_inline_payload_metadata_changes`
- `test_load_run_metadata_fails_fast_when_artifact_id_changes`
- `test_load_run_metadata_fails_fast_when_integrity_json_is_invalid`
- `test_load_run_metadata_legacy_without_integrity_file_still_loads`

Regression commands for implementation:

```bash
python -m pytest tests/unit/test_artifact_repository.py -q
python -m pytest tests/unit/test_codex_audit_fixes.py tests/unit/test_repo_put_streaming.py -q
```

If CLI resume behavior changes beyond exception propagation, add and run the
smallest relevant CLI or integration smoke test.

## Acceptance

The change is accepted when:

- Fresh runs write `_artifacts.integrity.json` next to `_artifacts.json`.
- Untouched metadata still resumes and can produce cache hits.
- Hand-edited `_artifacts.json` fails resume before Artifact registration.
- Old run directories without integrity files remain compatible.
- Existing file/blob payload drift tests still pass.
- Documentation and backlog closeout cite concrete evidence files.
