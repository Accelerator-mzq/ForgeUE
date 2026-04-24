# Delta Spec: artifact-contract (add-run-comparison-baseline-regression)

> 本文件只描述本 change 对 `openspec/specs/artifact-contract/spec.md` 的**增量**行为。完整契约以主 spec 为准,本文件**不**复制主 spec 的 Requirement / Invariant / Validation / Non-Goals。

---

## ADDED Requirements

### Requirement: Byte-hash recomputation is allowed for comparison

The system SHALL allow the `framework.comparison` module to read an Artifact's on-disk bytes and recompute its hash via `framework.artifact_store.hashing`. The recomputed hash MUST equal the value stored in `_artifacts.json` for a healthy Run; any mismatch is reported as an `ArtifactDiff.kind="content_changed"` entry with a note indicating the recompute mismatch.

#### Scenario: Healthy Run passes the recompute check

- GIVEN a Run whose `_artifacts.json` entry for `artifact_id=img_0` records `hash=H`
- WHEN comparison loader reads the payload file and recomputes the hash
- THEN the recomputed hash equals `H`, and no note is attached to the resulting `ArtifactDiff`

#### Scenario: Tampered payload is surfaced

- GIVEN a Run whose `_artifacts.json` records `hash=H` but whose on-disk file hashes to `H'` ≠ `H`
- WHEN comparison loader runs with `include_payload_hash_check=True` (default)
- THEN the diff entry for that artifact carries `kind="content_changed"` and a note explaining the recompute mismatch

### Requirement: Lineage diff surfaces selected-by-verdict chain

The system SHALL, when an Artifact's `Lineage` fields differ between baseline and candidate, output a `lineage_delta` block on the `ArtifactDiff`, covering at minimum `source_artifact_ids`, `source_step_ids`, `transformation_kind`, `selected_by_verdict_id`, and `variant_group_id` (the five Lineage fields enumerated by main-spec Requirement "Lineage is tracked end-to-end").

### Requirement: Missing payload is distinguished from missing metadata entry

The system SHALL distinguish two absence modes:

- `missing_in_baseline` / `missing_in_candidate` — the `_artifacts.json` entry itself is absent on one side
- `payload_missing_on_disk` — the metadata entry exists on both sides but the actual payload file is missing from disk on at least one side

Both modes are valid `ArtifactDiff.kind` values; callers MUST NOT collapse them into a single "missing" bucket.

### Requirement: Comparison does not revalidate through ArtifactRepository write path

The system SHALL read `_artifacts.json` and payload files as plain files; it MUST NOT call `ArtifactRepository.put()`, `load_run_metadata()`, or any other write-side routine. This guarantees comparison has zero risk of mutating either Run's state.

## ADDED Invariants

- Comparison reports include hash values (strings) but never include raw payload bytes; Report size stays O(number of artifacts × metadata fields), not O(total payload size).
- `ArtifactDiff.kind` enumeration is closed: `unchanged` / `content_changed` / `metadata_only` / `missing_in_baseline` / `missing_in_candidate` / `payload_missing_on_disk`. New kinds require a separate change (with a bump to `RunComparisonReport.schema_version`).
- `_artifacts.json` is read but never rewritten; the main-spec Requirement "Cross-process artifact metadata persistence" is a pre-condition, not a post-condition, of comparison.

## MODIFIED Requirements

None. The main `artifact-contract` spec's existing Requirements are pre-conditions that comparison consumes as-is.

## REMOVED Requirements

None.

## Non-Goals for this delta

- Does not define perceptual / semantic similarity between images, meshes, or audio Artifacts; hash + metadata only.
- Does not reconstruct missing Artifacts from lineage parents; missing bytes stay missing and are reported.
- Does not introduce a new Artifact `artifact_type`; comparison reads whatever types already exist in the two Runs.
- Does not implement the `blob` backend (still reserved per main spec's Non-Goals).

## Validation for this delta

- Implementation-phase unit tests under `tests/unit/test_run_comparison_loader.py` cover:
  - Healthy recompute match
  - Tampered payload surfaces `content_changed` with note
  - `_artifacts.json` entry missing on one side → `missing_in_baseline` / `missing_in_candidate`
  - Metadata on both sides but payload file missing → `payload_missing_on_disk`
- Integration test under `tests/integration/test_run_comparison_cli.py` exercises at least one Lineage field divergence end-to-end (e.g. different `selected_by_verdict_id`).
- Test count is NOT hardcoded; authoritative count is `python -m pytest -q` after implementation lands.
- Cross-reference to main spec: the main `artifact-contract` Requirements "Cross-process artifact metadata persistence", "Three-state PayloadRef", and "Lineage is tracked end-to-end" are the foundation this delta builds on.
